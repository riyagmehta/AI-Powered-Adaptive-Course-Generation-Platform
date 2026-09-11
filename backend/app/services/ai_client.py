from functools import lru_cache

from openai import AsyncOpenAI

from app.config import settings


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    """Constructed lazily and cached, not at import time — consistent with
    pinecone_client's getter, so importing any service module never has a
    side effect or an implicit credential requirement."""
    return AsyncOpenAI(api_key=settings.openai_api_key)
