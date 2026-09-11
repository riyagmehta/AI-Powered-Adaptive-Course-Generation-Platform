import random
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import AsyncSessionLocal
from app.main import app
from app.models.user import User
from app.services import embedding_service
from app.services.embedding_service import index_module_content
from app.services.security import create_access_token, hash_password


@pytest.mark.asyncio(loop_scope="session")
async def test_non_admin_gets_403(seeded_module):
    token = create_access_token(subject=seeded_module.user.email)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/metrics", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


@pytest.mark.asyncio(loop_scope="session")
async def test_admin_sees_metrics_including_a_real_llm_call(fake_openai, seeded_module, monkeypatch):
    async with AsyncSessionLocal() as db:
        admin = User(
            email=f"admin-test-{random.randint(1, 10**9)}@example.com",
            hashed_password=hash_password("Test1234!"),
            full_name="Admin Test User",
            is_admin=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)

    module, course = seeded_module.module, seeded_module.course
    # This test is about the /admin/metrics aggregation, not RAG — stub out
    # the actual Pinecone write so it doesn't need a live index, while still
    # exercising the real (fake_openai-mocked) embedding call that should
    # show up as an llm_calls row and be reflected in the aggregation below.
    monkeypatch.setattr(embedding_service, "replace_module_vectors", AsyncMock())
    await index_module_content(module.id, course.id, module.content, endpoint="POST /courses")

    token = create_access_token(subject=admin.email)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/metrics", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()

    assert body["window_days"] == 30
    assert body["total_calls"] >= 1
    assert any(row["endpoint"] == "POST /courses" for row in body["cost_by_endpoint"])
    assert any(row["course_id"] == course.id for row in body["cost_by_course"])
    assert isinstance(body["route_latency"], list)
    assert isinstance(body["cost_over_time"], list)

    async with AsyncSessionLocal() as db:
        await db.delete(await db.get(User, admin.id))
        await db.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_metrics_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/metrics")

    assert response.status_code == 401
