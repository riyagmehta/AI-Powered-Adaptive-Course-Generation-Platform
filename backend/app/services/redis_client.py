import hashlib
import json
from functools import lru_cache
from typing import Any

from redis.asyncio import Redis

from app.config import settings


@lru_cache
def get_redis_client() -> Redis:
    """Constructed lazily and cached, not at import time. `Redis.from_url`
    doesn't validate anything eagerly today, but building it lazily keeps
    this module consistent with ai_client/pinecone_client: importing a
    service module should never have a side effect or require credentials
    for a service that particular import path doesn't actually use yet."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


def doubt_cache_key(module_id: int, question: str) -> str:
    digest = hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()
    return f"doubt:{module_id}:{digest}"


async def get_cached_doubt(key: str) -> dict[str, Any] | None:
    raw = await get_redis_client().get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached_doubt(key: str, payload: dict[str, Any]) -> None:
    await get_redis_client().set(key, json.dumps(payload), ex=settings.doubt_cache_ttl_seconds)
