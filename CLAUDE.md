# Project: AI-Powered Adaptive Course Generation Platform

## Stack
- Backend: FastAPI (Python 3.11), async SQLAlchemy + asyncpg, Alembic
- DB: PostgreSQL 16 (Docker), Redis 7 (Docker)
- AI: OpenAI API (GPT-4 + text-embedding-ada-002), Pinecone (dim=1536, cosine)
- Frontend: React + Vite + TypeScript + Tailwind, Zustand, React Router

## Structure
- /backend — FastAPI app (app/models, app/schemas, app/routers, app/services)
- /frontend — React app

## Commands
- Backend dev: cd backend && uvicorn app.main:app --reload
- DB up: docker compose up -d
- Migrations: cd backend && alembic revision --autogenerate -m "msg" && alembic upgrade head
- Frontend dev: cd frontend && npm run dev
- Tests: cd backend && pytest -x

## Conventions
- All routes async, all DB access via async sessions
- Pydantic schemas for every request/response
- JWT auth via python-jose, bcrypt via passlib
- SSE for all streamed LLM output
- Secrets only in .env, never committed

## Architecture notes
- Pipeline: onboarding → outline synthesis (structured JSON) → SSE content gen → quiz gen
- RAG: embed query → Redis cache check → Pinecone top-k → context-injected GPT-4 → SSE
- Difficulty recalibrates after each quiz attempt
