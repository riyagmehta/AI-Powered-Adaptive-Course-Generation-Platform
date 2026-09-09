import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import AsyncSessionLocal
from app.main import app
from app.models.doubt import Doubt
from app.services.embedding_service import index_module_content
from app.services.redis_client import doubt_cache_key, redis_client
from app.services.security import create_access_token


def _parse_sse(raw_body: str) -> list[dict]:
    events = []
    for block in raw_body.strip().split("\n\n"):
        if not block.strip():
            continue
        lines = block.splitlines()
        event = next(l.removeprefix("event: ") for l in lines if l.startswith("event: "))
        data = next(l.removeprefix("data: ") for l in lines if l.startswith("data: "))
        events.append({"event": event, "data": json.loads(data)})
    return events


@pytest.mark.asyncio(loop_scope="session")
async def test_post_doubts_streams_sse_and_persists_to_db(fake_openai, seeded_module):
    module, user = seeded_module.module, seeded_module.user
    await index_module_content(module.id, seeded_module.course.id, module.content)

    token = create_access_token(subject=user.email)
    question = "What does TOPIC_B mean here?"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream(
            "POST",
            "/doubts",
            json={"module_id": module.id, "question": question},
            headers={"Authorization": f"Bearer {token}"},
        ) as response:
            assert response.status_code == 200
            body = ""
            async for chunk in response.aiter_text():
                body += chunk

    events = _parse_sse(body)
    assert events[-1]["event"] == "done"
    done_data = events[-1]["data"]
    assert done_data["cache_hit"] is False
    assert done_data["retrieved_chunk_ids"][0] == f"module-{module.id}-chunk-1"

    chunk_events = [e for e in events if e["event"] == "chunk"]
    assert len(chunk_events) > 0

    async with AsyncSessionLocal() as db:
        doubt = await db.get(Doubt, done_data["doubt_id"])
        assert doubt is not None
        assert doubt.module_id == module.id
        assert doubt.user_id == user.id
        assert doubt.question == question
        assert doubt.cache_hit is False
        assert doubt.answer == "".join(e["data"]["delta"] for e in chunk_events)

    await redis_client.delete(doubt_cache_key(module.id, question))
