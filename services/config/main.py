from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import AsyncSessionLocal, engine
from models_db import Base, AlgorithmConfigModel, KitchenConfigAssignmentModel
from cache import get_cached_config, set_cached_config, invalidate_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Algorithm Config Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConfigCreateBody(BaseModel):
    version: str
    name: str
    description: str = ""
    weights: dict = {}
    staff_priority_bonus: float = 0.20
    sla_fallback_threshold: int = 5
    kitchen_ids: list[str] = []
    created_by: str = ""


class ConfigUpdateBody(BaseModel):
    name: str | None = None
    description: str | None = None
    weights: dict | None = None
    staff_priority_bonus: float | None = None
    sla_fallback_threshold: int | None = None
    is_active: bool | None = None
    kitchen_ids: list[str] | None = None
    approved_by: str | None = None


class AssignKitchenBody(BaseModel):
    kitchen_id: UUID
    config_id: UUID


def _config_to_dict(row: AlgorithmConfigModel) -> dict:
    return {
        "config_id": str(row.config_id),
        "version": row.version,
        "name": row.name,
        "description": row.description,
        "weights": row.weights or {},
        "staff_priority_bonus": row.staff_priority_bonus,
        "sla_fallback_threshold": row.sla_fallback_threshold,
        "is_active": row.is_active,
        "kitchen_ids": [str(k) for k in (row.kitchen_ids or [])],
        "created_by": row.created_by,
        "approved_by": row.approved_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@app.post("/configs", status_code=201)
async def create_config(body: ConfigCreateBody):
    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(AlgorithmConfigModel).where(AlgorithmConfigModel.version == body.version)
        )
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="Version already exists")
        config = AlgorithmConfigModel(
            version=body.version,
            name=body.name,
            description=body.description,
            weights=body.weights or {
                "delivery_time": 0.40,
                "fairness": 0.25,
                "distance": 0.15,
                "batch": 0.10,
                "geo_trust": 0.10,
            },
            staff_priority_bonus=body.staff_priority_bonus,
            sla_fallback_threshold=body.sla_fallback_threshold,
            kitchen_ids=[UUID(k) for k in body.kitchen_ids] if body.kitchen_ids else [],
            created_by=body.created_by,
        )
        session.add(config)
        await session.commit()
        await session.refresh(config)
        return _config_to_dict(config)


@app.get("/configs")
async def list_configs(active_only: bool = Query(False)):
    async with AsyncSessionLocal() as session:
        q = select(AlgorithmConfigModel)
        if active_only:
            q = q.where(AlgorithmConfigModel.is_active == True)
        result = await session.execute(q)
        rows = result.scalars().all()
        return {"items": [_config_to_dict(r) for r in rows]}


@app.get("/configs/{config_id}")
async def get_config(config_id: UUID):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AlgorithmConfigModel).where(AlgorithmConfigModel.config_id == config_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Config not found")
        return _config_to_dict(row)


@app.get("/configs/active/{kitchen_id}")
async def get_active_config(kitchen_id: UUID):
    cached = await get_cached_config(kitchen_id)
    if cached is not None:
        return cached
    async with AsyncSessionLocal() as session:
        # Prefer explicit assignment
        assign = await session.execute(
            select(KitchenConfigAssignmentModel).where(KitchenConfigAssignmentModel.kitchen_id == kitchen_id)
        )
        assign_row = assign.scalars().first()
        if assign_row:
            result = await session.execute(
                select(AlgorithmConfigModel).where(AlgorithmConfigModel.config_id == assign_row.config_id)
            )
            row = result.scalars().first()
            if row:
                out = _config_to_dict(row)
                await set_cached_config(kitchen_id, out)
                return out
        # Fallback: config that has this kitchen in kitchen_ids
        result = await session.execute(
            select(AlgorithmConfigModel).where(
                AlgorithmConfigModel.is_active == True,
            )
        )
        for row in result.scalars().all():
            kid_list = row.kitchen_ids or []
            if kitchen_id in kid_list or str(kitchen_id) in [str(k) for k in kid_list]:
                out = _config_to_dict(row)
                await set_cached_config(kitchen_id, out)
                return out
        raise HTTPException(status_code=404, detail="No active config for this kitchen")


@app.patch("/configs/{config_id}")
async def update_config(config_id: UUID, body: ConfigUpdateBody):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AlgorithmConfigModel).where(AlgorithmConfigModel.config_id == config_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Config not found")
        if body.name is not None:
            row.name = body.name
        if body.description is not None:
            row.description = body.description
        if body.weights is not None:
            row.weights = body.weights
        if body.staff_priority_bonus is not None:
            row.staff_priority_bonus = body.staff_priority_bonus
        if body.sla_fallback_threshold is not None:
            row.sla_fallback_threshold = body.sla_fallback_threshold
        if body.is_active is not None:
            row.is_active = body.is_active
        if body.kitchen_ids is not None:
            row.kitchen_ids = [UUID(k) for k in body.kitchen_ids]
        if body.approved_by is not None:
            row.approved_by = body.approved_by
        await session.commit()
        for kid in row.kitchen_ids or []:
            await invalidate_config(kid)
        return _config_to_dict(row)


@app.post("/configs/assign")
async def assign_kitchen(body: AssignKitchenBody):
    async with AsyncSessionLocal() as session:
        await session.merge(KitchenConfigAssignmentModel(kitchen_id=body.kitchen_id, config_id=body.config_id))
        await session.commit()
        await invalidate_config(body.kitchen_id)
        return {"kitchen_id": str(body.kitchen_id), "config_id": str(body.config_id)}


@app.get("/health")
async def health():
    return {"status": "ok"}
