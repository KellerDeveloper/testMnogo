import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, Path, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import AsyncSessionLocal, engine
from models_db import Base, CourierModel, _generate_login
from cache import get_cached_available_couriers, set_cached_available_couriers, invalidate_available_couriers
from websocket_manager import courier_ws_manager

logger = logging.getLogger(__name__)

COURIER_LOGIN_LEN = 6
LOCATION_BATCH_MAX_POINTS = 500

# Здесь живёт “сервис курьеров” — состояние смены, текущие заказы, гео и всё,
# что нужно кухне/офису/курьерскому приложению для синхронизации.
#
# Важный UX‑флоу: подтверждение прибытия на кухню через QR.
# - Курьер в iOS нажимает “Я на кухне” (статус returning)
# - Мы генерим короткоживущий токен (15 секунд) и пушим его в курьера
# - Веб кухни получает обновление по WS и рисует QR с именем курьера
# - Курьер сканирует QR → подтверждаем токен → переводим статус в idle → QR исчезает
#
# Это не “безопасность уровня банка”, а защита от случайных кликов/фантазийных статусов.


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Лёгкая миграция без Alembic: проект учебный, поэтому добавляем колонки “на месте”.
        # Если они уже есть — Postgres спокойно промолчит благодаря IF NOT EXISTS.
        await conn.execute(
            text(
                "ALTER TABLE couriers "
                "ADD COLUMN IF NOT EXISTS arrival_qr_token VARCHAR(255), "
                "ADD COLUMN IF NOT EXISTS arrival_qr_expires_at TIMESTAMPTZ"
            )
        )
    yield
    await engine.dispose()


app = FastAPI(title="Courier Service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_valid_login(s: str) -> bool:
    return len(s) == COURIER_LOGIN_LEN and s.isdigit()


class CourierCreateBody(BaseModel):
    kitchen_id: UUID
    name: str
    max_batch_size: int = 3
    login: str | None = None  # 6-digit; if omitted, generated automatically

    @field_validator("login")
    @classmethod
    def login_format(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not _is_valid_login(v):
            raise ValueError("login must be exactly 6 digits")
        return v


class CourierUpdateStatusBody(BaseModel):
    status: str  # idle | delivering | returning | offline


class CourierUpdateLocationBody(BaseModel):
    lat: float
    lon: float


class CourierLocationBatchPoint(BaseModel):
    lat: float
    lon: float
    timestamp: datetime | None = None
    source: str = "gps"
    accuracy_m: float | None = None


class CourierLocationBatchBody(BaseModel):
    points: list[CourierLocationBatchPoint]


class CourierAddOrderBody(BaseModel):
    order_id: UUID


class CourierRemoveOrderBody(BaseModel):
    order_id: UUID


def _courier_to_dict(row: CourierModel) -> dict:
    shift_start = row.shift_start.isoformat() if row.shift_start else None
    shift_end = row.shift_end.isoformat() if row.shift_end else None
    return {
        "courier_id": row.courier_id,
        "kitchen_id": str(row.kitchen_id),
        "name": row.name,
        "status": row.status,
        "current_location": row.current_location,
        "current_orders": row.current_orders or [],
        "max_batch_size": row.max_batch_size,
        "orders_delivered_today": row.orders_delivered_today,
        "total_delivery_time_today": row.total_delivery_time_today,
        "geo_trust_score": row.geo_trust_score,
        "shift_start": shift_start,
        "shift_end": shift_end,
        "arrival_qr_token": row.arrival_qr_token,
        "arrival_qr_expires_at": row.arrival_qr_expires_at.isoformat() if row.arrival_qr_expires_at else None,
    }


class CourierArrivalConfirmBody(BaseModel):
    token: str


@app.post("/couriers", status_code=201)
async def create_courier(body: CourierCreateBody):
    async with AsyncSessionLocal() as session:
        login = body.login
        if not login:
            for _ in range(50):
                login = _generate_login()
                r = await session.execute(select(CourierModel).where(CourierModel.courier_id == login))
                if r.scalars().first() is None:
                    break
            else:
                raise HTTPException(status_code=500, detail="Could not generate unique login")
        else:
            r = await session.execute(select(CourierModel).where(CourierModel.courier_id == login))
            if r.scalars().first() is not None:
                raise HTTPException(status_code=400, detail="Login already exists")
        courier = CourierModel(
            courier_id=login,
            kitchen_id=body.kitchen_id,
            name=body.name,
            max_batch_size=body.max_batch_size,
            status="offline",
        )
        session.add(courier)
        await session.commit()
        await session.refresh(courier)
        await courier_ws_manager.broadcast_courier_changed(courier.courier_id, str(courier.kitchen_id))
        return {"courier_id": courier.courier_id, **_courier_to_dict(courier)}


@app.get("/couriers")
async def list_couriers(kitchen_id: UUID | None = Query(None)):
    """List all couriers, optionally filtered by kitchen_id. Use for office/kitchen UI to see offline couriers and start shift."""
    if not kitchen_id:
        raise HTTPException(status_code=400, detail="kitchen_id query parameter is required")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.kitchen_id == kitchen_id))
        rows = result.scalars().all()
        return {"items": [_courier_to_dict(r) for r in rows]}


@app.get("/couriers/{courier_id}")
async def get_courier(courier_id: str = Path(..., pattern=r"^\d{6}$")):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        return _courier_to_dict(row)


@app.get("/couriers/available/{kitchen_id}")
async def list_available_couriers(kitchen_id: UUID):
    cached = await get_cached_available_couriers(kitchen_id)
    if cached is not None:
        return {"items": cached}
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CourierModel).where(
                CourierModel.kitchen_id == kitchen_id,
                CourierModel.status.in_(["idle", "returning", "delivering"]),
            )
        )
        rows = result.scalars().all()
        items = []
        for r in rows:
            current = len(r.current_orders or [])
            if current < r.max_batch_size:
                items.append(_courier_to_dict(r))
        await set_cached_available_couriers(kitchen_id, items)
        return {"items": items}


@app.post("/couriers/{courier_id}/shift/start")
async def start_shift(courier_id: str = Path(..., pattern=r"^\d{6}$")):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        row.status = "idle"
        row.shift_start = datetime.now(timezone.utc)
        row.orders_delivered_today = 0
        row.total_delivery_time_today = 0
        row.current_orders = []
        await session.commit()
        await invalidate_available_couriers(row.kitchen_id)
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


@app.post("/couriers/{courier_id}/shift/end")
async def end_shift(courier_id: str = Path(..., pattern=r"^\d{6}$")):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        row.status = "offline"
        row.shift_end = datetime.now(timezone.utc)
        await session.commit()
        await invalidate_available_couriers(row.kitchen_id)
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


@app.patch("/couriers/{courier_id}/status")
async def update_status(courier_id: str = Path(..., pattern=r"^\d{6}$"), body: CourierUpdateStatusBody = ...):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        row.status = body.status
        await session.commit()
        await invalidate_available_couriers(row.kitchen_id)
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


@app.patch("/couriers/{courier_id}/location")
async def update_location(courier_id: str = Path(..., pattern=r"^\d{6}$"), body: CourierUpdateLocationBody = ...):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        row.current_location = {"lat": body.lat, "lon": body.lon}
        await session.commit()
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


async def _forward_points_to_geo(courier_id: str, points: list[CourierLocationBatchPoint]) -> None:
    base = (settings.geo_service_url or "").strip().rstrip("/")
    if not base:
        return
    async with httpx.AsyncClient(timeout=30.0) as client:
        for p in points:
            payload: dict = {
                "courier_id": courier_id,
                "lat": p.lat,
                "lon": p.lon,
                "source": p.source,
            }
            if p.timestamp is not None:
                payload["timestamp"] = p.timestamp.isoformat()
            if p.accuracy_m is not None:
                payload["accuracy_m"] = p.accuracy_m
            try:
                r = await client.post(f"{base}/location", json=payload)
                r.raise_for_status()
            except Exception as e:
                logger.warning("geo /location forward failed for %s: %s", courier_id, e)


@app.post("/couriers/{courier_id}/location/batch")
async def update_location_batch(
    courier_id: str = Path(..., pattern=r"^\d{6}$"), body: CourierLocationBatchBody = ...
):
    """
    Очередь офлайн-точек с телефона: принимаем пачку, сортируем по времени,
    прокидываем в geo по порядку (если настроен GEO_SERVICE_URL), в БД курьера — последняя точка.
    """
    if len(body.points) > LOCATION_BATCH_MAX_POINTS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many points (max {LOCATION_BATCH_MAX_POINTS})",
        )
    if not body.points:
        raise HTTPException(status_code=400, detail="points must not be empty")

    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    ordered = sorted(
        body.points,
        key=lambda p: p.timestamp if p.timestamp is not None else epoch,
    )

    await _forward_points_to_geo(courier_id, ordered)

    last = ordered[-1]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        row.current_location = {"lat": last.lat, "lon": last.lon}
        await session.commit()
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


@app.patch("/couriers/{courier_id}/geo_trust_score")
async def update_geo_trust_score(courier_id: str = Path(..., pattern=r"^\d{6}$"), score: float = Query(ge=0, le=1)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        row.geo_trust_score = score
        await session.commit()
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


@app.post("/couriers/{courier_id}/arrival_qr")
async def create_arrival_qr(courier_id: str = Path(..., pattern=r"^\d{6}$")):
    """Сгенерировать QR-токен для подтверждения прибытия курьера на кухню (валиден 15 секунд)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        now = datetime.now(timezone.utc)
        import secrets

        row.arrival_qr_token = secrets.token_urlsafe(16)
        row.arrival_qr_expires_at = now + timedelta(seconds=15)
        await session.commit()
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return {
            "token": row.arrival_qr_token,
            "expires_at": row.arrival_qr_expires_at.isoformat() if row.arrival_qr_expires_at else None,
        }


@app.post("/couriers/{courier_id}/arrival_confirm")
async def confirm_arrival(courier_id: str = Path(..., pattern=r"^\d{6}$"), body: CourierArrivalConfirmBody = ...):
    """Подтвердить прибытие курьера: проверка QR-токена и перевод в статус idle."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        now = datetime.now(timezone.utc)
        if (
            not row.arrival_qr_token
            or row.arrival_qr_token != body.token
            or not row.arrival_qr_expires_at
            or row.arrival_qr_expires_at < now
        ):
            raise HTTPException(status_code=400, detail="QR invalid or expired")
        row.arrival_qr_token = None
        row.arrival_qr_expires_at = None
        row.status = "idle"
        await session.commit()
        await invalidate_available_couriers(row.kitchen_id)
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


@app.post("/couriers/{courier_id}/orders")
async def add_order_to_courier(courier_id: str = Path(..., pattern=r"^\d{6}$"), body: CourierAddOrderBody = ...):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        orders = list(row.current_orders or [])
        if len(orders) >= row.max_batch_size:
            raise HTTPException(status_code=400, detail="Max batch size reached")
        orders.append(str(body.order_id))
        row.current_orders = orders
        row.status = "delivering"
        await session.commit()
        await invalidate_available_couriers(row.kitchen_id)
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


@app.delete("/couriers/{courier_id}/orders/{order_id}")
async def remove_order_from_courier(courier_id: str = Path(..., pattern=r"^\d{6}$"), order_id: UUID = ...):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        orders = list(row.current_orders or [])
        if str(order_id) in orders:
            orders.remove(str(order_id))
        row.current_orders = orders
        if not orders:
            row.status = "returning"
        await session.commit()
        await invalidate_available_couriers(row.kitchen_id)
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


@app.post("/couriers/{courier_id}/delivered")
async def record_delivery(courier_id: str = Path(..., pattern=r"^\d{6}$"), order_id: UUID = ..., delivery_time_minutes: int = Query(ge=0)):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        row.orders_delivered_today = (row.orders_delivered_today or 0) + 1
        row.total_delivery_time_today = (row.total_delivery_time_today or 0) + delivery_time_minutes
        orders = list(row.current_orders or [])
        if str(order_id) in orders:
            orders.remove(str(order_id))
        row.current_orders = orders
        if not orders:
            row.status = "returning"
        await session.commit()
        await invalidate_available_couriers(row.kitchen_id)
        await courier_ws_manager.broadcast_courier_changed(row.courier_id, str(row.kitchen_id))
        return _courier_to_dict(row)


@app.get("/couriers/{courier_id}/stats_summary")
async def courier_stats_summary(courier_id: str = Path(..., pattern=r"^\d{6}$")):
    """Для справедливости: заказов за смену, среднее по кухне, позиция по загрузке."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
        # Среднее по кухне за текущую смену (все с shift_start сегодня)
        from datetime import date
        today = date.today()
        all_result = await session.execute(
            select(CourierModel).where(
                CourierModel.kitchen_id == row.kitchen_id,
                CourierModel.orders_delivered_today > 0,
            )
        )
        all_rows = all_result.scalars().all()
        if not all_rows:
            avg_orders = 0
            rank = 1
        else:
            orders_list = sorted([r.orders_delivered_today for r in all_rows], reverse=True)
            avg_orders = sum(orders_list) / len(orders_list)
            rank = next((i + 1 for i, o in enumerate(orders_list) if o == row.orders_delivered_today), len(orders_list))
        return {
            "courier_id": row.courier_id,
            "name": row.name,
            "orders_delivered_today": row.orders_delivered_today,
            "total_delivery_time_today_minutes": row.total_delivery_time_today,
            "kitchen_avg_orders_today": round(avg_orders, 1),
            "rank_by_orders": rank,
            "total_couriers_on_kitchen": len(all_rows),
        }


class CourierFeedbackBody(BaseModel):
    reason: str  # e.g. "unfair", "other"
    comment: str | None = None


@app.post("/couriers/{courier_id}/feedback")
async def courier_feedback(courier_id: str = Path(..., pattern=r"^\d{6}$"), body: CourierFeedbackBody = ...):
    """Канал обратной связи: курьер отмечает несправедливость или другое."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CourierModel).where(CourierModel.courier_id == courier_id))
        row = result.scalars().first()
        if not row:
            raise HTTPException(status_code=404, detail="Courier not found")
    # In production: persist to Decision Log or analytics (override-like record)
    return {"received": True, "courier_id": courier_id, "reason": body.reason}


@app.websocket("/ws")
async def websocket_courier(websocket: WebSocket):
    await websocket.accept()
    sub_courier: str | None = None
    sub_kitchen: str | None = None
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") != "subscribe":
                    continue
                if msg.get("courier_id") and _is_valid_login(str(msg["courier_id"])):
                    if sub_courier:
                        courier_ws_manager.unsubscribe_courier(websocket, sub_courier)
                    if sub_kitchen:
                        courier_ws_manager.unsubscribe_kitchen(websocket, sub_kitchen)
                        sub_kitchen = None
                    sub_courier = str(msg["courier_id"])
                    await courier_ws_manager.subscribe_courier(websocket, sub_courier)
                    await websocket.send_text(json.dumps({"type": "subscribed", "courier_id": sub_courier}))
                elif msg.get("kitchen_id"):
                    if sub_courier:
                        courier_ws_manager.unsubscribe_courier(websocket, sub_courier)
                        sub_courier = None
                    if sub_kitchen:
                        courier_ws_manager.unsubscribe_kitchen(websocket, sub_kitchen)
                    sub_kitchen = str(msg["kitchen_id"])
                    await courier_ws_manager.subscribe_kitchen(websocket, sub_kitchen)
                    await websocket.send_text(json.dumps({"type": "subscribed", "kitchen_id": sub_kitchen}))
            except (json.JSONDecodeError, TypeError):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        if sub_courier:
            courier_ws_manager.unsubscribe_courier(websocket, sub_courier)
        if sub_kitchen:
            courier_ws_manager.unsubscribe_kitchen(websocket, sub_kitchen)


@app.get("/health")
async def health():
    return {"status": "ok"}
