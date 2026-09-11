from datetime import datetime, timezone

import structlog
from arq.connections import RedisSettings
from arq.worker import Retry, func
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.course import Course
from app.models.generation_job import GenerationJob
from app.models.module import Module
from app.observability.logging_config import configure_logging
from app.services.content_service import generate_module_content
from app.services.embedding_service import index_module_content

configure_logging()
logger = structlog.get_logger()

# The `arq` CLI unconditionally calls logging.config.dictConfig() with its own
# plain-text handler after importing WorkerSettings (i.e. after
# configure_logging() above already ran) — which would attach a second,
# unstructured handler straight to the "arq" logger, printing every line
# twice. Passing this to `arq --custom-log-dict app.worker.ARQ_LOG_CONFIG`
# makes that dictConfig call a no-op for handlers instead, so "arq"'s own
# logs just propagate up to the root logger's structlog JSON handler like
# everything else.
ARQ_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {"arq": {"handlers": [], "level": "INFO", "propagate": True}},
}

MAX_TRIES = 3
JOB_TIMEOUT_SECONDS = 120
BACKOFF_BASE_SECONDS = 2
DEFAULT_ENDPOINT = "worker:generate_module_content"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def generate_module_content_task(
    ctx: dict,
    job_id: int,
    module_id: int,
    request_id: str | None = None,
    endpoint: str = DEFAULT_ENDPOINT,
) -> None:
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

    `request_id` — when set, this job was enqueued directly from an HTTP
    request (as opposed to a post-crash requeue via on_startup) — binding it
    here means every log line for this job, including the LLM call it makes,
    carries the same request_id as the request that triggered it.
    """
    structlog.contextvars.bind_contextvars(request_id=request_id, job_id=job_id, module_id=module_id)
    job_try = ctx["job_try"]

    try:
        async with AsyncSessionLocal() as db:
            job = await db.get(GenerationJob, job_id)
            module = await db.get(Module, module_id)
            if job is None or module is None:
                logger.warning("generation_job_missing", job_found=job is not None, module_found=module is not None)
                return

            if module.status == "completed":
                job.status = "succeeded"
                job.attempts = job_try
                job.finished_at = job.finished_at or _now()
                await db.commit()
                logger.info("generation_job_noop_already_completed")
                return

            course = await db.get(Course, module.course_id)

            job.status = "running"
            job.attempts = job_try
            job.started_at = job.started_at or _now()
            module.status = "generating"
            await db.commit()

            try:
                content = await generate_module_content(course, module, endpoint=endpoint)
                await index_module_content(module.id, course.id, content, endpoint=endpoint)
            except Exception as exc:
                job.last_error = str(exc)

                if job_try >= MAX_TRIES:
                    job.status = "failed"
                    job.finished_at = _now()
                    module.status = "failed"
                    await db.commit()
                    logger.exception("generation_job_failed_permanently", attempts=job_try)
                    raise

                job.status = "queued"
                await db.commit()

                backoff = BACKOFF_BASE_SECONDS**job_try
                logger.warning(
                    "generation_job_retrying",
                    attempt=job_try,
                    max_tries=MAX_TRIES,
                    backoff_s=backoff,
                    error=str(exc),
                )
                raise Retry(defer=backoff) from exc

            module.content = content
            module.status = "completed"
            job.status = "succeeded"
            job.finished_at = _now()
            await db.commit()
            logger.info("generation_job_succeeded")
    finally:
        structlog.contextvars.clear_contextvars()


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
            # No request_id here — the request that originally triggered this
            # job is long gone. The default endpoint label reflects that this
            # run is a crash-recovery requeue, not a direct HTTP trigger.
            await ctx["redis"].enqueue_job("generate_module_content_task", job.id, job.module_id)

        if stuck_jobs:
            logger.warning(
                "requeued_stuck_generation_jobs",
                count=len(stuck_jobs),
                job_ids=[job.id for job in stuck_jobs],
            )
    except DBAPIError:
        # Most likely the generation_jobs table doesn't exist yet (fresh
        # environment, migrations not applied yet). The container's restart
        # policy will retry this on the next start once migrations have run.
        logger.warning("generation_jobs_startup_check_failed", hint="has `alembic upgrade head` run?")


class WorkerSettings:
    functions = [func(generate_module_content_task, timeout=JOB_TIMEOUT_SECONDS, max_tries=MAX_TRIES)]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = on_startup
    job_timeout = JOB_TIMEOUT_SECONDS
    max_tries = MAX_TRIES
