# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


FROM python:3.11-slim AS runtime
WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# Config is loaded from real process environment variables (see app/config.py) —
# pass them with `docker run --env-file .env` / a compose `environment:` block,
# not by baking a .env file into the image.
#
# $PORT is respected (falling back to 8000) because platforms like Railway
# assign it dynamically rather than letting you fix it. $WEB_CONCURRENCY
# controls the uvicorn worker count (default 2) — raise it if your instance
# has the CPU/RAM to spare.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"]
