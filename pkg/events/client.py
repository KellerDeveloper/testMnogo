import json
from typing import Any, Callable, Optional

import aio_pika
from aio_pika import Message, DeliveryMode
from pydantic import BaseModel


async def get_connection(rabbitmq_url: str):
    return await aio_pika.connect_robust(rabbitmq_url)


async def publish(exchange: aio_pika.Exchange, routing_key: str, payload: BaseModel) -> None:
    body = payload.model_dump_json().encode()
    message = Message(body=body, delivery_mode=DeliveryMode.PERSISTENT)
    await exchange.publish(message, routing_key=routing_key)


async def subscribe(
    connection: aio_pika.Connection,
    exchange_name: str,
    queue_name: str,
    routing_keys: list[str],
    handler: Callable[[dict], Any],
    exchange_type: aio_pika.ExchangeType = aio_pika.ExchangeType.TOPIC,
) -> None:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=1)
    exchange = await channel.declare_exchange(exchange_name, exchange_type, durable=True)
    queue = await channel.declare_queue(queue_name, durable=True)
    for key in routing_keys:
        await queue.bind(exchange, routing_key=key)

    async def on_message(message: aio_pika.IncomingMessage):
        async with message.process():
            body = json.loads(message.body.decode())
            await handler(body)

    await queue.consume(on_message)
