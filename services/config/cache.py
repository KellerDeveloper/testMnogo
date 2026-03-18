import json
from uuid import UUID

import redis.asyncio as redis

from config import settings


async def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


def _key(kitchen_id: UUID) -> str:
    return f"algorithm_config:kitchen:{kitchen_id}"


async def get_cached_config(kitchen_id: UUID) -> dict | None:
    r = await get_redis()
    data = await r.get(_key(kitchen_id))
    await r.aclose()
    if data is None:
        return None
    return json.loads(data)


async def set_cached_config(kitchen_id: UUID, config: dict) -> None:
    r = await get_redis()
    await r.setex(_key(kitchen_id), settings.config_cache_ttl, json.dumps(config, default=str))
    await r.aclose()


async def invalidate_config(kitchen_id: UUID) -> None:
    r = await get_redis()
    await r.delete(_key(kitchen_id))
    await r.aclose()
