import json
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import AsyncSessionLocal, engine
from models_db import Base, OrderModel
from events import (
    publish_ready_for_dispatch,
    publish_assigned,
    publish_picked_up,
    publish_delivered,
    publish_cancelled,
)
from websocket_manager import order_ws_manager
import redis.asyncio as redis
import httpx


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="Order Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response DTOs ---


class OrderCreateBody(BaseModel):
    kitchen_id: UUID
    customer_location: dict  # {"lat": float, "lon": float}
    promised_delivery_time: str  # ISO datetime
    preparation_time_estimate_minutes: int | None = None


def _courier_login_6(s: str) -> str:
    if len(s) != 6 or not s.isdigit():
        raise ValueError("courier_id must be 6 digits")
    return s


class OrderAssignBody(BaseModel):
    assigned_courier_id: str | None = None
    assigned_carrier_type: str  # staff | 3pl
    assignment_source: str  # dispatcher_auto | manual_override

    @field_validator("assigned_courier_id")
    @classmethod
    def courier_login_6(cls, v: str | None) -> str | None:
        if v is not None:
            _courier_login_6(v)
        return v


class OrderStatusUpdateBody(BaseModel):
    status: str  # picked_up | delivered | cancelled
    courier_id: str | None = None
    reason: str | None = None

    @field_validator("courier_id")
    @classmethod
    def courier_login_6(cls, v: str | None) -> str | None:
        if v is not None:
            _courier_login_6(v)
        return v


class ManualAssignBody(BaseModel):
    operator_id: str
    courier_id: str  # 6-digit courier login

    @field_validator("courier_id")
    @classmethod
    def courier_login_6(cls, v: str) -> str:
        _courier_login_6(v)
        return v


def _order_to_dict(row: OrderModel) -> dict:
    return {
        "order_id": str(row.order_id),
        "kitchen_id": str(row.kitchen_id),
        "customer_location": row.customer_location,
        "promised_delivery_time": row.promised_delivery_time.isoformat() if row.promised_delivery_time else None,
        "preparation_ready_time": row.preparation_ready_time.isoformat() if row.preparation_ready_time else None,
        "status": row.status,
        "assigned_courier_id": row.assigned_courier_id,
        "assigned_carrier_type": row.assigned_carrier_type,
        "assignment_source": row.assignment_source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@app.post("/orders", status_code=201)
async def create_order(body: OrderCreateBody):
    from datetime import datetime
    from datetime import timedelta

    prep_ready = None
    if body.preparation_time_estimate_minutes is not None:
        from datetime import timezone
        prep_ready = datetime.now(timezone.utc) + timedelta(minutes=body.preparation_time_estimate_minutes)
    promised = datetime.fromisoformat(body.promised_delivery_time.replace("Z", "+00:00"))

    async with AsyncSessionLocal() as session:
        order = OrderModel(
            kitchen_id=body.kitchen_id,
            customer_location=body.customer_location,
            promised_delivery_time=promised,
            preparation_ready_time=prep_ready,
            status="new",
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)
        await order_ws_manager.broadcast_orders_changed(order.kitchen_id)
        return {"order_id": str(order.order_id), **_order_to_dict(order)}


@app.get("/orders/{order_id}")
async def get_order(order_id: UUID):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OrderModel).where(OrderModel.order_id == order_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        return _order_to_dict(row)


@app.get("/orders")
async def list_orders(
    kitchen_id: UUID | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    async with AsyncSessionLocal() as session:
        q = select(OrderModel)
        if kitchen_id is not None:
            q = q.where(OrderModel.kitchen_id == kitchen_id)
        if status is not None:
            q = q.where(OrderModel.status == status)
        q = q.order_by(OrderModel.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(q)
        rows = result.scalars().all()
        return {"items": [_order_to_dict(r) for r in rows], "total": len(rows)}


@app.post("/orders/{order_id}/ready_for_dispatch")
async def mark_ready_for_dispatch(order_id: UUID):
    from datetime import timezone
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OrderModel).where(OrderModel.order_id == order_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        if row.status not in ("new", "pending"):
            raise HTTPException(status_code=400, detail=f"Order status is {row.status}, cannot mark ready for dispatch")
        from datetime import datetime
        now = datetime.now(timezone.utc)
        row.status = "pending"
        row.preparation_ready_time = row.preparation_ready_time or now
        await session.commit()
        await session.refresh(row)
        await order_ws_manager.broadcast_orders_changed(row.kitchen_id)
        await publish_ready_for_dispatch(
            order_id=str(row.order_id),
            kitchen_id=str(row.kitchen_id),
            customer_location=row.customer_location,
            promised_delivery_time=row.promised_delivery_time,
            preparation_ready_time=row.preparation_ready_time,
        )
        return _order_to_dict(row)


@app.post("/orders/{order_id}/manual_assign")
async def manual_assign_order(order_id: UUID, body: ManualAssignBody):
    """Set lock, assign to courier, log override. Prevents dispatcher from assigning for 30s."""
    r = redis.from_url(settings.redis_url)
    lock_key = f"dispatch_lock:{order_id}"
    await r.set(lock_key, "1", ex=settings.order_lock_ttl)
    await r.aclose()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OrderModel).where(OrderModel.order_id == order_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        previous = {"assigned_courier_id": str(row.assigned_courier_id) if row.assigned_courier_id else None}
        row.status = "assigned"
        row.assigned_courier_id = body.courier_id
        row.assigned_carrier_type = "staff"
        row.assignment_source = "manual_override"
        await session.commit()
        await session.refresh(row)
        await order_ws_manager.broadcast_orders_changed(row.kitchen_id)
    await publish_assigned(
        order_id=str(order_id),
        assigned_courier_id=str(body.courier_id),
        assigned_carrier_type="staff",
        assignment_source="manual_override",
    )
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.courier_service_url}/couriers/{body.courier_id}/orders",
            json={"order_id": str(order_id)},
        )
        await client.post(
            f"{settings.log_service_url}/decisions",
            json={
                "decision_id": str(__import__("uuid").uuid4()),
                "order_id": str(order_id),
                "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                "assigned_to": str(body.courier_id),
                "carrier_type": "staff",
                "assignment_source": "manual_override",
                "algorithm_version": "",
                "scores": {},
                "winner_score": 0,
                "reason_summary": body.override_reason or "Ручное назначение",
                "factors": [],
                "context_snapshot": {},
                "override_info": {
                    "operator_id": body.operator_id,
                    "override_reason": body.override_reason,
                    "previous_assignment": previous,
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                    "kitchen_context": None,
                },
            },
        )
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OrderModel).where(OrderModel.order_id == order_id))
        row = result.scalars().first()
        return _order_to_dict(row) if row else {}


@app.post("/orders/{order_id}/assign")
async def assign_order(order_id: UUID, body: OrderAssignBody):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OrderModel).where(OrderModel.order_id == order_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        row.status = "assigned"
        row.assigned_courier_id = body.assigned_courier_id
        row.assigned_carrier_type = body.assigned_carrier_type
        row.assignment_source = body.assignment_source
        await session.commit()
        await session.refresh(row)
        await order_ws_manager.broadcast_orders_changed(row.kitchen_id)
        await publish_assigned(
            order_id=str(row.order_id),
            assigned_courier_id=str(body.assigned_courier_id) if body.assigned_courier_id else None,
            assigned_carrier_type=body.assigned_carrier_type,
            assignment_source=body.assignment_source,
        )
        return _order_to_dict(row)


@app.post("/orders/{order_id}/status")
async def update_order_status(order_id: UUID, body: OrderStatusUpdateBody):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OrderModel).where(OrderModel.order_id == order_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        if body.status == "picked_up":
            if not body.courier_id:
                raise HTTPException(status_code=400, detail="courier_id required for picked_up")
            row.status = "picked_up"
            await session.commit()
            await session.refresh(row)
            await order_ws_manager.broadcast_orders_changed(row.kitchen_id)
            await publish_picked_up(order_id=str(row.order_id), courier_id=str(body.courier_id))
        elif body.status == "delivered":
            row.status = "delivered"
            await session.commit()
            await session.refresh(row)
            await order_ws_manager.broadcast_orders_changed(row.kitchen_id)
            await publish_delivered(order_id=str(row.order_id), courier_id=str(body.courier_id) if body.courier_id else None)
        elif body.status == "cancelled":
            row.status = "cancelled"
            await session.commit()
            await session.refresh(row)
            await order_ws_manager.broadcast_orders_changed(row.kitchen_id)
            await publish_cancelled(order_id=str(row.order_id), reason=body.reason)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown status {body.status}")
        return _order_to_dict(row)


@app.websocket("/ws")
async def websocket_orders(websocket: WebSocket):
    await websocket.accept()
    kitchen_id: str | None = None
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "subscribe" and msg.get("kitchen_id"):
                    if kitchen_id:
                        order_ws_manager.unsubscribe(websocket, kitchen_id)
                    kitchen_id = str(msg["kitchen_id"])
                    await order_ws_manager.subscribe(websocket, kitchen_id)
                    await websocket.send_text(json.dumps({"type": "subscribed", "kitchen_id": kitchen_id}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        if kitchen_id:
            order_ws_manager.unsubscribe(websocket, kitchen_id)


@app.get("/health")
async def health():
    return {"status": "ok"}
