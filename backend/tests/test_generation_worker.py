import random
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from arq.worker import Retry
from sqlalchemy import select

from app import worker as worker_module
from app.database import AsyncSessionLocal
from app.models.course import Course
from app.models.generation_job import GenerationJob
from app.models.module import Module
from app.models.user import User
from app.services.security import hash_password
from app.worker import MAX_TRIES, generate_module_content_task, on_startup


@pytest_asyncio.fixture
async def fresh_module():
    """A brand-new module with no content yet — distinct from the shared
    `seeded_module` fixture, which starts pre-completed for RAG/doubt tests."""
    async with AsyncSessionLocal() as db:
        user = User(
            email=f"job-test-{random.randint(1, 10**9)}@example.com",
            hashed_password=hash_password("Test1234!"),
            full_name="Job Test User",
        )
        db.add(user)
        await db.flush()

        course = Course(
            owner_id=user.id, title="Job Test Course", status="active", current_difficulty="intermediate"
        )
        db.add(course)
        await db.flush()

        module = Module(course_id=course.id, order_index=0, title="Job Test Module", status="pending")
        db.add(module)
        await db.commit()
        await db.refresh(user)
        await db.refresh(course)
        await db.refresh(module)

        yield SimpleNamespace(user=user, course=course, module=module)

        await db.delete(user)
        await db.commit()


async def _create_job(module_id: int) -> int:
    async with AsyncSessionLocal() as db:
        job = GenerationJob(module_id=module_id, status="queued")
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job.id


async def _get_job(job_id: int) -> GenerationJob:
    async with AsyncSessionLocal() as db:
        return await db.get(GenerationJob, job_id)


async def _get_module(module_id: int) -> Module:
    async with AsyncSessionLocal() as db:
        return await db.get(Module, module_id)


@pytest.mark.asyncio(loop_scope="session")
async def test_job_survives_worker_restart_mid_generation(fresh_module, monkeypatch):
    """Simulates a worker that died mid-job: the row is left stuck in
    "running" with no further progress. on_startup must find it, requeue it,
    and a subsequent run of the task must then actually finish the work."""
    module_id = fresh_module.module.id
    job_id = await _create_job(module_id)

    # Simulate the crash: a previous worker had claimed this job and started
    # the module, then died before finishing — nothing ever set it to
    # "succeeded" or "failed".
    async with AsyncSessionLocal() as db:
        job = await db.get(GenerationJob, job_id)
        job.status = "running"
        job.attempts = 1
        module = await db.get(Module, module_id)
        module.status = "generating"
        await db.commit()

    fake_redis = SimpleNamespace(enqueue_job=AsyncMock())
    await on_startup({"redis": fake_redis})

    # The stuck job was reset to "queued" and handed back to arq to run again.
    requeued_job = await _get_job(job_id)
    assert requeued_job.status == "queued"
    fake_redis.enqueue_job.assert_awaited_once_with("generate_module_content_task", job_id, module_id)

    # Now actually run it, as arq would after picking the requeued job back up.
    monkeypatch.setattr(
        worker_module, "generate_module_content", AsyncMock(return_value="# Recovered lesson content")
    )
    monkeypatch.setattr(worker_module, "index_module_content", AsyncMock())

    await generate_module_content_task({"job_try": 1}, job_id, module_id)

    finished_job = await _get_job(job_id)
    finished_module = await _get_module(module_id)
    assert finished_job.status == "succeeded"
    assert finished_job.finished_at is not None
    assert finished_module.status == "completed"
    assert finished_module.content == "# Recovered lesson content"


@pytest.mark.asyncio(loop_scope="session")
async def test_job_retries_with_backoff_then_lands_in_failed(fresh_module, monkeypatch):
    module_id = fresh_module.module.id
    job_id = await _create_job(module_id)

    failing_generate = AsyncMock(side_effect=RuntimeError("openai is down"))
    monkeypatch.setattr(worker_module, "generate_module_content", failing_generate)
    monkeypatch.setattr(worker_module, "index_module_content", AsyncMock())

    # Attempts 1 and 2 (of MAX_TRIES=3) should retry with increasing backoff.
    for job_try in range(1, MAX_TRIES):
        with pytest.raises(Retry) as exc_info:
            await generate_module_content_task({"job_try": job_try}, job_id, module_id)
        assert exc_info.value.defer_score == worker_module.BACKOFF_BASE_SECONDS**job_try * 1000

        job = await _get_job(job_id)
        assert job.status == "queued"
        assert job.attempts == job_try
        assert "openai is down" in job.last_error

        module = await _get_module(module_id)
        assert module.status == "generating"  # still in flight, not failed yet

    # The final attempt (job_try == MAX_TRIES) must NOT retry again — it
    # exhausts the budget and lands in "failed" with the real error recorded.
    with pytest.raises(RuntimeError, match="openai is down"):
        await generate_module_content_task({"job_try": MAX_TRIES}, job_id, module_id)

    final_job = await _get_job(job_id)
    final_module = await _get_module(module_id)
    assert final_job.status == "failed"
    assert final_job.attempts == MAX_TRIES
    assert "openai is down" in final_job.last_error
    assert final_job.finished_at is not None
    assert final_module.status == "failed"

    assert failing_generate.await_count == MAX_TRIES


@pytest.mark.asyncio(loop_scope="session")
async def test_completed_module_is_a_no_op_on_rerun(fresh_module, monkeypatch):
    """Idempotency: running the exact same job twice (e.g. a duplicate arq
    delivery, or a post-crash requeue racing a job that actually did finish)
    must not regenerate content or call OpenAI/Pinecone a second time."""
    module_id = fresh_module.module.id
    job_id = await _create_job(module_id)

    fake_generate = AsyncMock(return_value="# Generated once")
    fake_index = AsyncMock()
    monkeypatch.setattr(worker_module, "generate_module_content", fake_generate)
    monkeypatch.setattr(worker_module, "index_module_content", fake_index)

    await generate_module_content_task({"job_try": 1}, job_id, module_id)

    module_after_first_run = await _get_module(module_id)
    assert module_after_first_run.status == "completed"
    assert module_after_first_run.content == "# Generated once"
    assert fake_generate.await_count == 1
    assert fake_index.await_count == 1

    # Run the identical job again.
    await generate_module_content_task({"job_try": 1}, job_id, module_id)

    module_after_second_run = await _get_module(module_id)
    job_after_second_run = await _get_job(job_id)
    assert module_after_second_run.content == "# Generated once"  # unchanged
    assert job_after_second_run.status == "succeeded"
    # The whole point: no second call to OpenAI or Pinecone.
    assert fake_generate.await_count == 1
    assert fake_index.await_count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_on_startup_is_a_no_op_when_nothing_is_stuck(fresh_module):
    fake_redis = SimpleNamespace(enqueue_job=AsyncMock())
    await on_startup({"redis": fake_redis})
    fake_redis.enqueue_job.assert_not_awaited()


@pytest.mark.asyncio(loop_scope="session")
async def test_missing_job_or_module_is_skipped_gracefully(fresh_module):
    # Job row was deleted/never existed, but the task still gets delivered.
    await generate_module_content_task({"job_try": 1}, 999_999_999, fresh_module.module.id)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(GenerationJob).where(GenerationJob.module_id == fresh_module.module.id))
        assert result.scalar_one_or_none() is None
