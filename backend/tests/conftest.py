import hashlib
import math
import random
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from app.database import AsyncSessionLocal
from app.models.course import Course
from app.models.module import Module
from app.models.user import User
from app.services import ai_client
from app.services.pinecone_client import replace_module_vectors
from app.services.security import hash_password

_TOPIC_BASE_VECTORS: dict[str, list[float]] = {}
EMBEDDING_DIM = 1536


def _unit_vector(seed_text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def fake_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Deterministic fake embedding. Texts sharing a 'TOPIC_*' marker cluster
    tightly together (cosine similarity ~0.998+); everything else is ~orthogonal
    (cosine ~0). This lets tests assert real nearest-neighbor behavior against
    live Pinecone. Jitter is a small unit vector scaled by `eps` and added to the
    topic's unit base vector, so its magnitude doesn't grow with `dim`."""
    topic = next((t for t in ("TOPIC_A", "TOPIC_B", "TOPIC_C") if t in text), text)
    if topic not in _TOPIC_BASE_VECTORS:
        _TOPIC_BASE_VECTORS[topic] = _unit_vector(topic, dim)
    base = _TOPIC_BASE_VECTORS[topic]

    raw_jitter = _unit_vector(f"jitter:{text}", dim)
    eps = 0.05
    combined = [b + eps * j for b, j in zip(base, raw_jitter)]
    norm = math.sqrt(sum(v * v for v in combined)) or 1.0
    return [v / norm for v in combined]


async def _fake_embeddings_create(*, model, input, dimensions=None, **kwargs):
    texts = input if isinstance(input, list) else [input]
    data = [SimpleNamespace(embedding=fake_embedding(t, dimensions or EMBEDDING_DIM)) for t in texts]
    return SimpleNamespace(data=data)


class _FakeChatStream:
    def __init__(self, deltas: list[str]):
        self._deltas = deltas

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for delta in self._deltas:
            yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=delta))])


async def _fake_chat_completions_create(*, model, messages, stream=False, temperature=None, **kwargs):
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    deltas = [f"[fake answer to: {user_content[:60]!r}] ", "This is a deterministic test response."]
    return _FakeChatStream(deltas)


@pytest.fixture
def fake_openai(monkeypatch):
    embeddings_mock = AsyncMock(side_effect=_fake_embeddings_create)
    chat_mock = AsyncMock(side_effect=_fake_chat_completions_create)
    monkeypatch.setattr(ai_client.get_openai_client().embeddings, "create", embeddings_mock)
    monkeypatch.setattr(ai_client.get_openai_client().chat.completions, "create", chat_mock)
    return SimpleNamespace(embeddings=embeddings_mock, chat=chat_mock, fake_embedding=fake_embedding)


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_module():
    async with AsyncSessionLocal() as db:
        user = User(
            email=f"doubt-test-{random.randint(1, 10**9)}@example.com",
            hashed_password=hash_password("Test1234!"),
            full_name="Doubt Test User",
        )
        db.add(user)
        await db.flush()

        course = Course(owner_id=user.id, title="RAG Test Course", status="active")
        db.add(course)
        await db.flush()

        module = Module(
            course_id=course.id,
            order_index=0,
            title="RAG Test Module",
            status="completed",
            content=(
                "TOPIC_A: Python decorators wrap a function to extend its behavior "
                "without modifying its source code directly. " + ("Decorators are applied with the "
                "'@' syntax above a function definition, and under the hood they simply take the "
                "decorated function as an argument and return a new callable. " * 6) + "\n\n"
                "TOPIC_B: A database index is a data structure that improves the "
                "speed of data retrieval operations on a table. " + ("Indexes trade additional write "
                "and storage overhead for much faster reads on the indexed columns, and are commonly "
                "implemented as B-trees or hash maps. " * 6)
            ),
        )
        db.add(module)
        await db.commit()
        await db.refresh(user)
        await db.refresh(course)
        await db.refresh(module)

        yield SimpleNamespace(user=user, course=course, module=module, db=db)

        # Not every test using this fixture actually indexes anything into
        # Pinecone (e.g. tests/test_quiz_attempt_endpoint.py never touches
        # RAG at all) — so this cleanup is best-effort, not required. In
        # particular it must not raise when Pinecone isn't configured at all
        # (no credentials in CI), which would otherwise fail teardown for
        # tests that never dirtied Pinecone in the first place.
        try:
            await replace_module_vectors(module.id, course.id, [], [])
        except Exception:
            pass
        await db.delete(user)
        await db.commit()
