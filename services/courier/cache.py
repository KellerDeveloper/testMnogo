import json
from typing import List
from uuid import UUID

import redis.asyncio as redis

from config import settings


async def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _cache_key_available(kitchen_id: UUID) -> str:
    return f"couriers:available:{kitchen_id}"


async def get_cached_available_couriers(kitchen_id: UUID) -> List[dict] | None:
    r = await get_redis()
    key = _cache_key_available(kitchen_id)
    data = await r.get(key)
    await r.aclose()
    if data is None:
        return None
    return json.loads(data)


async def set_cached_available_couriers(kitchen_id: UUID, couriers: List[dict]) -> None:
    r = await get_redis()
    key = _cache_key_available(kitchen_id)
    await r.setex(key, settings.cache_available_couriers_ttl, json.dumps(couriers))
    await r.aclose()


async def invalidate_available_couriers(kitchen_id: UUID) -> None:
    r = await get_redis()
    await r.delete(_cache_key_available(kitchen_id))
    await r.aclose()
