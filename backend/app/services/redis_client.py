import hashlib
import json
from typing import Any

from redis.asyncio import Redis

from app.config import settings

redis_client: Redis = Redis.from_url(settings.redis_url, decode_responses=True)


def doubt_cache_key(module_id: int, question: str) -> str:
    digest = hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()
    return f"doubt:{module_id}:{digest}"


async def get_cached_doubt(key: str) -> dict[str, Any] | None:
    raw = await redis_client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached_doubt(key: str, payload: dict[str, Any]) -> None:
    await redis_client.set(key, json.dumps(payload), ex=settings.doubt_cache_ttl_seconds)
