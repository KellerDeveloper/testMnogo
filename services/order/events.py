import asyncio
from datetime import datetime

import aio_pika
from aio_pika import ExchangeType

from config import settings
from pkg.events.schemas import (
    OrderReadyForDispatch,
    OrderAssigned,
    OrderPickedUp,
    OrderDelivered,
    OrderCancelled,
    PointSchema,
)


_connection = None
_exchange = None


async def get_exchange():
    global _connection, _exchange
    if _exchange is not None:
        return _exchange
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await _connection.channel()
    _exchange = await channel.declare_exchange(settings.order_exchange, ExchangeType.TOPIC, durable=True)
    return _exchange


async def publish_ready_for_dispatch(
    order_id: str,
    kitchen_id: str,
    customer_location: dict,
    promised_delivery_time: datetime,
    preparation_ready_time: datetime,
):
    ex = await get_exchange()
    ev = OrderReadyForDispatch(
        order_id=order_id,
        kitchen_id=kitchen_id,
        customer_location=PointSchema(**customer_location),
        promised_delivery_time=promised_delivery_time,
        preparation_ready_time=preparation_ready_time,
    )
    await ex.publish(
        aio_pika.Message(body=ev.model_dump_json().encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key="order.ready_for_dispatch",
    )


async def publish_assigned(order_id: str, assigned_courier_id: str | None, assigned_carrier_type: str | None, assignment_source: str):
    ex = await get_exchange()
    ev = OrderAssigned(
        order_id=order_id,
        assigned_courier_id=assigned_courier_id,
        assigned_carrier_type=assigned_carrier_type,
        assignment_source=assignment_source,
    )
    await ex.publish(
        aio_pika.Message(body=ev.model_dump_json().encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key="order.assigned",
    )


async def publish_picked_up(order_id: str, courier_id: str):
    ex = await get_exchange()
    ev = OrderPickedUp(order_id=order_id, courier_id=courier_id)
    await ex.publish(
        aio_pika.Message(body=ev.model_dump_json().encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key="order.picked_up",
    )


async def publish_delivered(order_id: str, courier_id: str | None = None):
    ex = await get_exchange()
    ev = OrderDelivered(order_id=order_id, courier_id=courier_id)
    await ex.publish(
        aio_pika.Message(body=ev.model_dump_json().encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key="order.delivered",
    )


async def publish_cancelled(order_id: str, reason: str | None = None):
    ex = await get_exchange()
    ev = OrderCancelled(order_id=order_id, reason=reason)
    await ex.publish(
        aio_pika.Message(body=ev.model_dump_json().encode(), delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key="order.cancelled",
    )
