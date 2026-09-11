import logging
from datetime import datetime, timezone

from arq.connections import RedisSettings
from arq.worker import Retry, func
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.course import Course
from app.models.generation_job import GenerationJob
from app.models.module import Module
from app.services.content_service import generate_module_content
from app.services.embedding_service import index_module_content

logger = logging.getLogger(__name__)

MAX_TRIES = 3
JOB_TIMEOUT_SECONDS = 120
BACKOFF_BASE_SECONDS = 2


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def generate_module_content_task(ctx: dict, job_id: int, module_id: int) -> None:
    """Generate a module's lesson content and index it for RAG, as a durable,
    retryable, idempotent job.

    Idempotency: if the module is already "completed" (this run, or a
    duplicate/requeued one, finds the work already done), this is a no-op.

    No partial state: module.content/status are only written in the single
    commit at the very end, after both the OpenAI call and the Pinecone
    indexing have fully succeeded in memory. If this job is interrupted at
    any point before that, nothing about the module's persisted content or
    "completed" status has changed — a retry (or a post-crash requeue) starts
    the generation over cleanly rather than resuming half-written state.
    """
    job_try = ctx["job_try"]

    async with AsyncSessionLocal() as db:
        job = await db.get(GenerationJob, job_id)
        module = await db.get(Module, module_id)
        if job is None or module is None:
            logger.warning("generation job %s or module %s no longer exists; skipping", job_id, module_id)
            return

        if module.status == "completed":
            job.status = "succeeded"
            job.attempts = job_try
            job.finished_at = job.finished_at or _now()
            await db.commit()
            logger.info("generation job %s: module %s already completed, no-op", job_id, module_id)
            return

        course = await db.get(Course, module.course_id)

        job.status = "running"
        job.attempts = job_try
        job.started_at = job.started_at or _now()
        module.status = "generating"
        await db.commit()

        try:
            content = await generate_module_content(course, module)
            await index_module_content(module.id, course.id, content)
        except Exception as exc:
            job.last_error = str(exc)

            if job_try >= MAX_TRIES:
                job.status = "failed"
                job.finished_at = _now()
                module.status = "failed"
                await db.commit()
                logger.exception(
                    "generation job %s failed permanently after %s attempt(s)", job_id, job_try
                )
                raise

            job.status = "queued"
            await db.commit()

            backoff = BACKOFF_BASE_SECONDS**job_try
            logger.warning(
                "generation job %s failed (attempt %s/%s), retrying in %ss: %s",
                job_id,
                job_try,
                MAX_TRIES,
                backoff,
                exc,
            )
            raise Retry(defer=backoff) from exc

        module.content = content
        module.status = "completed"
        job.status = "succeeded"
        job.finished_at = _now()
        await db.commit()
        logger.info("generation job %s succeeded for module %s", job_id, module_id)


async def on_startup(ctx: dict) -> None:
    """Recover jobs that were mid-flight when a previous worker process died —
    a hard kill leaves them stuck in "running" forever otherwise, since
    nothing else would ever revisit them."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(GenerationJob).where(GenerationJob.status == "running"))
            stuck_jobs = list(result.scalars().all())

            for job in stuck_jobs:
                job.status = "queued"
            await db.commit()

        for job in stuck_jobs:
            await ctx["redis"].enqueue_job("generate_module_content_task", job.id, job.module_id)

        if stuck_jobs:
            logger.warning(
                "requeued %d generation job(s) stuck in 'running' from a previous crash: %s",
                len(stuck_jobs),
                [job.id for job in stuck_jobs],
            )
    except DBAPIError:
        # Most likely the generation_jobs table doesn't exist yet (fresh
        # environment, migrations not applied yet). The container's restart
        # policy will retry this on the next start once migrations have run.
        logger.warning("could not check for stuck generation jobs on startup — has `alembic upgrade head` run?")


class WorkerSettings:
    functions = [func(generate_module_content_task, timeout=JOB_TIMEOUT_SECONDS, max_tries=MAX_TRIES)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = on_startup
    job_timeout = JOB_TIMEOUT_SECONDS
    max_tries = MAX_TRIES
