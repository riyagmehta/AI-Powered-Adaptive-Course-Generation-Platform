"""Structured (JSON) logging setup, shared by the FastAPI process and the ARQ
worker process — each calls configure_logging() once at startup.

Uses structlog's recommended stdlib integration: stdlib `logging` still owns
the actual handlers/output, but every record is rendered by structlog's
JSON renderer, and request-scoped fields (request_id, etc.) bound via
structlog.contextvars automatically merge into every log line emitted while
they're bound — including from `logging.getLogger(...)` calls in third-party
code (uvicorn, sqlalchemy, ...), not just structlog loggers.
"""

import logging
import sys

import structlog

from app.config import settings

_SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def configure_logging() -> None:
    structlog.configure(
        processors=_SHARED_PROCESSORS + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    renderer = structlog.processors.JSONRenderer() if settings.json_logs else structlog.dev.ConsoleRenderer()
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        foreign_pre_chain=_SHARED_PROCESSORS,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level)

    # Route uvicorn's own loggers (access log, error log) through the same
    # handler instead of uvicorn's default text formatter, so they come out
    # as the same structured JSON as everything else.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True
