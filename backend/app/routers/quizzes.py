from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.module import Module
from app.models.quiz import Quiz
from app.models.quiz_attempt import QuizAttempt
from app.models.user import User
from app.schemas.quiz import QuizAttemptCreate, QuizAttemptRead, QuizRead
from app.services.auth_service import get_current_user
from app.services.quiz_service import generate_quiz_questions, recalibrate_difficulty, score_attempt

router = APIRouter(tags=["quizzes"])


async def _get_owned_module(module_id: int, current_user: User, db: AsyncSession) -> Module:
    result = await db.execute(
        select(Module).where(Module.id == module_id).options(selectinload(Module.course))
    )
    module = result.scalar_one_or_none()
    if module is None or module.course.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return module


@router.post("/modules/{module_id}/quiz", response_model=QuizRead, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    module_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Quiz:
    module = await _get_owned_module(module_id, current_user, db)

    if module.status != "completed" or not module.content:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Module content has not been generated yet",
        )

    difficulty = module.course.current_difficulty
    questions = await generate_quiz_questions(module, difficulty)

    quiz = Quiz(module_id=module.id, questions=questions, difficulty=difficulty)
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)
    return quiz


@router.get("/modules/{module_id}/quiz", response_model=QuizRead)
async def get_quiz(
    module_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Quiz:
    await _get_owned_module(module_id, current_user, db)

    result = await db.execute(
        select(Quiz).where(Quiz.module_id == module_id).order_by(Quiz.created_at.desc()).limit(1)
    )
    quiz = result.scalar_one_or_none()
    if quiz is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No quiz generated for this module yet")
    return quiz


@router.post("/quizzes/{quiz_id}/attempt", response_model=QuizAttemptRead)
async def attempt_quiz(
    quiz_id: int,
    payload: QuizAttemptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizAttemptRead:
    result = await db.execute(
        select(Quiz)
        .where(Quiz.id == quiz_id)
        .options(selectinload(Quiz.module).selectinload(Module.course))
    )
    quiz = result.scalar_one_or_none()
    if quiz is None or quiz.module.course.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

    course = quiz.module.course
    score, results = score_attempt(quiz.questions, payload.answers)

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=current_user.id,
        answers=payload.answers,
        score=score,
        difficulty_at_attempt=course.current_difficulty,
    )
    db.add(attempt)

    new_difficulty = recalibrate_difficulty(course.current_difficulty, score)
    course.current_difficulty = new_difficulty
    db.add(course)

    await db.commit()
    await db.refresh(attempt)

    return QuizAttemptRead(
        id=attempt.id,
        quiz_id=quiz.id,
        score=score,
        difficulty_at_attempt=attempt.difficulty_at_attempt,
        new_difficulty=new_difficulty,
        results=results,
    )
