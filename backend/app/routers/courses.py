from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.course import Course
from app.models.generation_job import GenerationJob
from app.models.module import Module
from app.models.user import User
from app.schemas.course import CourseCreate, CourseDetail, CourseRead
from app.services.auth_service import get_current_user
from app.services.job_queue import get_arq_pool
from app.services.outline_service import OutlineGenerationError, synthesize_outline
from app.services.rate_limit import limiter

router = APIRouter(prefix="/courses", tags=["courses"])

DIFFICULTY_BY_EXPERIENCE = {
    "beginner": "beginner",
    "intermediate": "intermediate",
    "advanced": "advanced",
}


@router.post("", response_model=CourseDetail, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_course(
    request: Request,
    payload: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> Course:
    if not payload.topic and not current_user.learning_goal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a topic or complete onboarding with a learning goal first.",
        )

    try:
        outline = await synthesize_outline(current_user, payload.topic, payload.num_modules)
    except OutlineGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to generate course outline: {exc}",
        ) from exc

    course = Course(
        owner_id=current_user.id,
        title=outline["title"],
        description=outline.get("description"),
        status="active",
        current_difficulty=DIFFICULTY_BY_EXPERIENCE.get(current_user.experience_level, "intermediate"),
    )
    course.modules = [
        Module(order_index=i, title=m["title"], summary=m.get("summary"))
        for i, m in enumerate(outline["modules"])
    ]

    db.add(course)
    await db.commit()

    first_module = course.modules[0] if course.modules else None
    if first_module is not None:
        job = GenerationJob(module_id=first_module.id, status="queued")
        db.add(job)
        await db.commit()
        await arq_pool.enqueue_job(
            "generate_module_content_task",
            job.id,
            first_module.id,
            request_id=getattr(request.state, "request_id", None),
            endpoint="POST /courses",
        )

    return course


@router.get("", response_model=list[CourseRead])
async def list_courses(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Course]:
    result = await db.execute(
        select(Course)
        .where(Course.owner_id == current_user.id)
        .options(selectinload(Course.modules))
        .order_by(Course.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{course_id}", response_model=CourseDetail)
async def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Course:
    result = await db.execute(
        select(Course)
        .where(Course.id == course_id, Course.owner_id == current_user.id)
        .options(selectinload(Course.modules))
    )
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course
