import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import create_worker
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.observability.logging_config import configure_logging
from app.observability.middleware import RequestIDMiddleware, TimingMiddleware
from app.routers import admin, analytics, auth, courses, doubts, modules, quizzes
from app.services.rate_limit import limiter
from app.worker import WorkerSettings

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))

    # Deploy targets without a background-worker service type (Render's free
    # tier, notably) run the ARQ worker inside this same process instead of
    # as its own container. handle_signals=False because uvicorn already
    # owns SIGINT/SIGTERM for this process — a second handler installed by
    # arq would race it.
    in_process_worker = None
    worker_task = None
    if settings.run_worker_in_process:
        in_process_worker = create_worker(WorkerSettings, handle_signals=False)
        worker_task = asyncio.create_task(in_process_worker.async_run())

    try:
        yield
    finally:
        if in_process_worker is not None:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task
            await in_process_worker.close()
        await app.state.arq_pool.close()


app = FastAPI(title="AI-Powered Adaptive Course Generation Platform", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added in this order so RequestIDMiddleware ends up outermost (Starlette
# wraps each added middleware around the previous stack) — it needs to bind
# the request ID into structlog's contextvars before TimingMiddleware's
# "request_completed" log line is emitted, so that line carries it too.
app.add_middleware(TimingMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(modules.router)
app.include_router(doubts.router)
app.include_router(quizzes.router)
app.include_router(analytics.router)
app.include_router(admin.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
