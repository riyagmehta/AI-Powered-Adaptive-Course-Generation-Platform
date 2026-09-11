from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.generation_job import GenerationJob
from app.models.module import Module
from app.models.user import User
from app.schemas.generation_job import GenerationJobRead
from app.services.auth_service import get_current_user
from app.services.job_queue import get_arq_pool
from app.services.rate_limit import limiter

router = APIRouter(prefix="/modules", tags=["modules"])

ACTIVE_JOB_STATUSES = ("queued", "running")


async def _get_owned_module(module_id: int, current_user: User, db: AsyncSession) -> Module:
    result = await db.execute(
        select(Module).where(Module.id == module_id).options(selectinload(Module.course))
    )
    module = result.scalar_one_or_none()
    if module is None or module.course.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return module


async def _latest_job(db: AsyncSession, module_id: int) -> GenerationJob | None:
    result = await db.execute(
        select(GenerationJob)
        .where(GenerationJob.module_id == module_id)
        .order_by(GenerationJob.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post(
    "/{module_id}/generate", response_model=GenerationJobRead, status_code=status.HTTP_202_ACCEPTED
)
@limiter.limit("10/minute")
async def generate_module(
    request: Request,
    module_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> GenerationJob:
    module = await _get_owned_module(module_id, current_user, db)

    # Idempotent at the API layer too: don't enqueue a second job while one is
    # already in flight, and don't re-enqueue at all once the module is done.
    existing = await _latest_job(db, module_id)
    if module.status == "completed" or (existing and existing.status in ACTIVE_JOB_STATUSES):
        if existing is not None:
            return existing
        # Completed via some other path with no job row on record (shouldn't
        # normally happen) — synthesize a terminal one for a uniform response.
        job = GenerationJob(module_id=module_id, status="succeeded", attempts=0)
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return job

    job = GenerationJob(module_id=module_id, status="queued")
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await arq_pool.enqueue_job("generate_module_content_task", job.id, module_id)

    return job


@router.get("/{module_id}/status", response_model=GenerationJobRead)
async def get_module_status(
    module_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJob:
    await _get_owned_module(module_id, current_user, db)

    job = await _latest_job(db, module_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No generation job found for this module yet"
        )
    return job
