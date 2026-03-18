from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import AsyncSessionLocal, engine
from models_db import Base, ThirdPartyProviderModel


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="3PL Gateway", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProviderCreateBody(BaseModel):
    name: str
    kitchen_id: UUID
    avg_pickup_time_minutes: float = 0.0
    avg_delivery_time_minutes: float = 0.0
    cost_per_order: Decimal = Decimal("0")
    current_sla_minutes: int = 60
    success_rate: float = 1.0


class OrderForEtaBody(BaseModel):
    order_id: str
    kitchen_id: str
    customer_lat: float
    customer_lon: float
    promised_delivery_time: str


def _provider_to_dict(row: ThirdPartyProviderModel) -> dict:
    return {
        "service_id": str(row.service_id),
        "name": row.name,
        "kitchen_id": str(row.kitchen_id),
        "is_available": row.is_available,
        "avg_pickup_time_minutes": row.avg_pickup_time_minutes,
        "avg_delivery_time_minutes": row.avg_delivery_time_minutes,
        "cost_per_order": str(row.cost_per_order),
        "current_sla_minutes": row.current_sla_minutes,
        "success_rate": row.success_rate,
    }


@app.post("/providers", status_code=201)
async def create_provider(body: ProviderCreateBody):
    async with AsyncSessionLocal() as session:
        p = ThirdPartyProviderModel(
            name=body.name,
            kitchen_id=body.kitchen_id,
            avg_pickup_time_minutes=body.avg_pickup_time_minutes,
            avg_delivery_time_minutes=body.avg_delivery_time_minutes,
            cost_per_order=body.cost_per_order,
            current_sla_minutes=body.current_sla_minutes,
            success_rate=body.success_rate,
        )
        session.add(p)
        await session.commit()
        await session.refresh(p)
        return _provider_to_dict(p)


@app.get("/providers/available/{kitchen_id}")
async def list_available_providers(kitchen_id: UUID):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ThirdPartyProviderModel).where(
                ThirdPartyProviderModel.kitchen_id == kitchen_id,
                ThirdPartyProviderModel.is_available == True,
            )
        )
        rows = result.scalars().all()
        return {"items": [_provider_to_dict(r) for r in rows]}


@app.post("/eta")
async def get_eta_and_cost(body: OrderForEtaBody):
    """Return list of 3PL options with ETA and cost for the order."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ThirdPartyProviderModel).where(
                ThirdPartyProviderModel.kitchen_id == UUID(body.kitchen_id),
                ThirdPartyProviderModel.is_available == True,
            )
        )
        rows = result.scalars().all()
        out = []
        for r in rows:
            eta_minutes = r.avg_pickup_time_minutes + r.avg_delivery_time_minutes
            out.append({
                "service_id": str(r.service_id),
                "name": r.name,
                "eta_minutes": eta_minutes,
                "cost_per_order": str(r.cost_per_order),
                "current_sla_minutes": r.current_sla_minutes,
                "success_rate": r.success_rate,
            })
        return {"options": out}


@app.post("/orders")
async def create_3pl_order(order_id: str, service_id: UUID):
    """Create delivery order at 3PL provider (stub - would call external API)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ThirdPartyProviderModel).where(ThirdPartyProviderModel.service_id == service_id)
        )
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Provider not found")
        if not row.is_available:
            raise HTTPException(status_code=400, detail="Provider not available")
        return {
            "order_id": order_id,
            "service_id": str(service_id),
            "external_id": f"3pl-{order_id}-{service_id}",
            "status": "created",
        }


@app.get("/health")
async def health():
    return {"status": "ok"}
