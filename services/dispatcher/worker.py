"""
Consumes order_ready_for_dispatch, runs algorithm, assigns or logs (shadow mode).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

import aio_pika
from aio_pika import ExchangeType
import httpx
import redis.asyncio as redis

from config import settings
from pkg.dispatcher_algorithm import DispatcherAlgorithm
from pkg.dispatcher_algorithm.types import OrderContext, Candidate


# Default kitchen location (Moscow center) when not in config
DEFAULT_KITCHEN_LAT = 55.7558
DEFAULT_KITCHEN_LON = 37.6173


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    if hasattr(datetime, "fromisoformat"):
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    return None


async def try_lock(order_id: str) -> bool:
    r = redis.from_url(settings.redis_url)
    key = f"dispatch_lock:{order_id}"
    ok = await r.set(key, "1", nx=True, ex=settings.order_lock_ttl)
    await r.aclose()
    return bool(ok)


async def handle_ready_for_dispatch(body: dict) -> None:
    order_id = body.get("order_id")
    kitchen_id = body.get("kitchen_id")
    logger.info("handle_ready_for_dispatch order_id=%s kitchen_id=%s", order_id, kitchen_id)
    if not order_id or not kitchen_id:
        logger.warning("skip: missing order_id or kitchen_id in event body")
        return
    if not await try_lock(order_id):
        logger.info("skip order_id=%s: dispatch lock already held (e.g. manual assign)", order_id)
        return  # Another process (e.g. manual override) holds lock
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Available couriers
        couriers_resp = await client.get(
            f"{settings.courier_service_url}/couriers/available/{kitchen_id}"
        )
        if couriers_resp.status_code != 200:
            logger.warning("skip order_id=%s: couriers service returned %s for kitchen_id=%s", order_id, couriers_resp.status_code, kitchen_id)
            return
        couriers_data = couriers_resp.json().get("items") or []
        courier_ids = [c["courier_id"] for c in couriers_data]
        logger.info("order_id=%s: %s available couriers for kitchen %s", order_id, len(couriers_data), kitchen_id)
        # 2. Geo: verified location + trust
        geo_resp = await client.post(
            f"{settings.geo_service_url}/location/batch",
            json={"courier_ids": courier_ids},
        )
        geo_map = {}
        if geo_resp.status_code == 200:
            geo_map = geo_resp.json()
        # 3. 3PL options (optional: if gateway unavailable, continue without 3PL)
        customer = body.get("customer_location") or {}
        promised = body.get("promised_delivery_time") or ""
        three_pl_options = []
        try:
            eta_resp = await client.post(
                f"{settings.gateway3pl_url}/eta",
                json={
                    "order_id": order_id,
                    "kitchen_id": kitchen_id,
                    "customer_lat": customer.get("lat", 0),
                    "customer_lon": customer.get("lon", 0),
                    "promised_delivery_time": promised,
                },
            )
            if eta_resp.status_code == 200:
                three_pl_options = eta_resp.json().get("options") or []
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning("order_id=%s: 3PL gateway unavailable (%s), continuing without 3PL options", order_id, e)
        # 4. Algorithm config
        config_resp = await client.get(
            f"{settings.config_service_url}/configs/active/{kitchen_id}"
        )
        weights = None
        staff_bonus = 0.20
        sla_threshold = 5
        version = "v1.0"
        if config_resp.status_code == 200:
            cfg = config_resp.json()
            weights = cfg.get("weights")
            staff_bonus = cfg.get("staff_priority_bonus", 0.20)
            sla_threshold = cfg.get("sla_fallback_threshold", 5)
            version = cfg.get("version", "v1.0")
        # Build candidates
        candidates = []
        for c in couriers_data:
            g = geo_map.get(c["courier_id"], {})
            loc = c.get("current_location") or (g if isinstance(g, dict) else {})
            lat = loc.get("lat") if isinstance(loc, dict) else None
            lon = loc.get("lon") if isinstance(loc, dict) else None
            if lat is None and isinstance(g, dict):
                lat = g.get("lat")
                lon = g.get("lon")
            shift_start = _parse_dt(c.get("shift_start"))
            shift_end = _parse_dt(c.get("shift_end"))
            trust = g.get("geo_trust_score", 1.0) if isinstance(g, dict) else 1.0
            candidates.append(Candidate(
                candidate_id=c["courier_id"],
                is_staff=True,
                current_lat=lat,
                current_lon=lon,
                orders_delivered_today=c.get("orders_delivered_today", 0),
                total_delivery_time_today=c.get("total_delivery_time_today", 0),
                shift_start=shift_start,
                shift_end=shift_end,
                current_orders=c.get("current_orders") or [],
                max_batch_size=c.get("max_batch_size", 3),
                geo_trust_score=trust,
                name=c.get("name", ""),
            ))
        for opt in three_pl_options:
            candidates.append(Candidate(
                candidate_id=opt["service_id"],
                is_staff=False,
                eta_minutes=opt.get("eta_minutes", 45),
                cost_per_order=float(opt.get("cost_per_order", 0)),
                current_sla_minutes=opt.get("current_sla_minutes", 60),
                name=opt.get("name", "3PL"),
            ))
        if not candidates:
            logger.warning("skip order_id=%s: no candidates (no available couriers and no 3PL options for kitchen %s)", order_id, kitchen_id)
            return
        promised_dt = _parse_dt(body.get("promised_delivery_time")) or datetime.now(timezone.utc)
        prep_ready = _parse_dt(body.get("preparation_ready_time"))
        order_ctx = OrderContext(
            order_id=UUID(order_id),
            kitchen_id=UUID(kitchen_id),
            customer_lat=float(customer.get("lat", 0)),
            customer_lon=float(customer.get("lon", 0)),
            promised_delivery_time=promised_dt,
            preparation_ready_time=prep_ready,
        )
        algo = DispatcherAlgorithm(
            weights=weights,
            staff_priority_bonus=staff_bonus,
            sla_fallback_threshold_minutes=sla_threshold,
            algorithm_version=version,
        )
        result = algo.run(
            order_ctx,
            candidates,
            DEFAULT_KITCHEN_LAT,
            DEFAULT_KITCHEN_LON,
        )
        decision_id = str(uuid4())
        decision_payload = {
            "decision_id": decision_id,
            "order_id": order_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "assigned_to": result.assigned_to,
            "carrier_type": result.carrier_type,
            "assignment_source": result.assignment_source,
            "algorithm_version": result.algorithm_version,
            "scores": result.scores,
            "winner_score": result.winner_score,
            "reason_summary": result.reason_summary,
            "factors": result.factors,
            "context_snapshot": result.context_snapshot,
            "override_info": None,
        }
        # 5. Log decision
        await client.post(
            f"{settings.log_service_url}/decisions",
            json=decision_payload,
        )
        # 6. If not shadow: assign
        if not settings.shadow_mode:
            assign_body = {
                "assigned_courier_id": result.assigned_to if result.carrier_type == "staff" else None,
                "assigned_carrier_type": result.carrier_type,
                "assignment_source": "dispatcher_auto",
            }
            assign_resp = await client.post(
                f"{settings.order_service_url}/orders/{order_id}/assign",
                json=assign_body,
            )
            if assign_resp.status_code != 200:
                logger.error("order_id=%s: assign failed, order service returned %s: %s", order_id, assign_resp.status_code, assign_resp.text)
            else:
                logger.info("order_id=%s assigned to %s (%s)", order_id, result.assigned_to, result.carrier_type)
            if result.carrier_type == "staff":
                await client.post(
                    f"{settings.courier_service_url}/couriers/{result.assigned_to}/orders",
                    json={"order_id": order_id},
                )
            else:
                await client.post(
                    f"{settings.gateway3pl_url}/orders",
                    params={"order_id": order_id, "service_id": result.assigned_to},
                )
            # 7. Notify
            await client.post(
                f"{settings.notification_service_url}/notify/assignment",
                json={
                    "order_id": order_id,
                    "assigned_to": result.assigned_to,
                    "carrier_type": result.carrier_type,
                    "reason_summary": result.reason_summary,
                },
            )
        else:
            logger.info("order_id=%s: shadow_mode=True, decision logged only (assigned_to=%s)", order_id, result.assigned_to)
        # Publish event
        conn = await aio_pika.connect_robust(settings.rabbitmq_url)
        ch = await conn.channel()
        ex = await ch.declare_exchange(settings.dispatch_exchange, ExchangeType.TOPIC, durable=True)
        await ex.publish(
            aio_pika.Message(
                body=json.dumps(decision_payload, default=str).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key="dispatch.decision_made",
        )
        await conn.close()


async def run_worker():
    logger.info("Dispatcher worker starting, connecting to RabbitMQ %s", settings.rabbitmq_url.split("@")[-1])
    conn = await aio_pika.connect_robust(settings.rabbitmq_url)
    ch = await conn.channel()
    await ch.set_qos(prefetch_count=1)
    ex = await ch.declare_exchange(settings.order_exchange, ExchangeType.TOPIC, durable=True)
    q = await ch.declare_queue("dispatcher_ready_for_dispatch", durable=True)
    await q.bind(ex, routing_key="order.ready_for_dispatch")

    async def on_message(message: aio_pika.IncomingMessage):
        async with message.process():
            body = json.loads(message.body.decode())
            await handle_ready_for_dispatch(body)

    await q.consume(on_message)
    logger.info("Dispatcher worker ready, consuming queue dispatcher_ready_for_dispatch (routing_key=order.ready_for_dispatch)")
    await asyncio.Future()  # run forever
