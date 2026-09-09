from unittest.mock import AsyncMock

import pytest

from app.services import doubt_service
from app.services.doubt_service import resolve_doubt
from app.services.embedding_service import index_module_content
from app.services.pinecone_client import query_module_context
from app.services.redis_client import doubt_cache_key, get_cached_doubt, redis_client


@pytest.mark.asyncio(loop_scope="session")
async def test_index_module_content_upserts_and_is_retrievable_from_pinecone(fake_openai, seeded_module):
    module, course = seeded_module.module, seeded_module.course

    await index_module_content(module.id, course.id, module.content)

    assert fake_openai.embeddings.call_count == 1
    call_kwargs = fake_openai.embeddings.call_args.kwargs
    assert len(call_kwargs["input"]) == 2  # TOPIC_A and TOPIC_B paragraphs chunked separately

    query_vector = fake_openai.fake_embedding("A learner is asking about TOPIC_A again")
    matches = await query_module_context(module.id, query_vector, top_k=2)

    assert len(matches) == 2
    assert matches[0]["id"] == f"module-{module.id}-chunk-0"
    assert "decorators" in matches[0]["text"]
    assert matches[0]["score"] > matches[1]["score"]


@pytest.mark.asyncio(loop_scope="session")
async def test_resolve_doubt_cache_miss_then_hit(fake_openai, seeded_module, monkeypatch):
    module = seeded_module.module
    await index_module_content(module.id, seeded_module.course.id, module.content)

    query_spy = AsyncMock(wraps=query_module_context)
    monkeypatch.setattr(doubt_service, "query_module_context", query_spy)

    question = "Can you explain TOPIC_A decorators again?"

    first_events = [event async for event in resolve_doubt(module, question)]
    first_done = first_events[-1]
    assert first_done["type"] == "done"
    assert first_done["cache_hit"] is False
    assert first_done["retrieved_chunk_ids"][0] == f"module-{module.id}-chunk-0"
    assert "".join(e["delta"] for e in first_events[:-1]) == first_done["answer"]
    assert fake_openai.chat.call_count == 1
    assert query_spy.call_count == 1

    cache_key = doubt_cache_key(module.id, question)
    cached = await get_cached_doubt(cache_key)
    assert cached is not None
    assert cached["answer"] == first_done["answer"]

    second_events = [event async for event in resolve_doubt(module, question)]
    second_done = second_events[-1]
    assert second_done["type"] == "done"
    assert second_done["cache_hit"] is True
    assert second_done["answer"] == first_done["answer"]

    # Chat generation and Pinecone retrieval must both be skipped on a cache hit.
    assert fake_openai.chat.call_count == 1
    assert query_spy.call_count == 1
    # The question is still embedded every time (cache check happens after embedding).
    assert fake_openai.embeddings.call_count == 3  # 1 module chunk batch + 2 question embeds

    await redis_client.delete(cache_key)
