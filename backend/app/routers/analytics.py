from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.course import Course
from app.models.module import Module
from app.models.quiz import Quiz
from app.models.quiz_attempt import QuizAttempt
from app.models.user import User
from app.schemas.quiz import AnalyticsSummary, ModuleScoreStat, ScoreTrendPoint
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/me", response_model=AnalyticsSummary)
async def get_my_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummary:
    module_stats_result = await db.execute(
        select(
            Module.id,
            Module.title,
            func.count(QuizAttempt.id),
            func.avg(QuizAttempt.score),
        )
        .join(Quiz, Quiz.module_id == Module.id)
        .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
        .where(QuizAttempt.user_id == current_user.id)
        .group_by(Module.id, Module.title)
        .order_by(Module.id)
    )
    average_score_by_module = [
        ModuleScoreStat(module_id=module_id, module_title=title, attempts_count=count, average_score=float(avg))
        for module_id, title, count, avg in module_stats_result.all()
    ]

    trend_result = await db.execute(
        select(QuizAttempt.id, Quiz.module_id, QuizAttempt.score, QuizAttempt.created_at)
        .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(QuizAttempt.user_id == current_user.id)
        .order_by(QuizAttempt.created_at)
    )
    score_trend = [
        ScoreTrendPoint(attempt_id=attempt_id, module_id=module_id, score=score, created_at=created_at)
        for attempt_id, module_id, score, created_at in trend_result.all()
    ]

    modules_count_result = await db.execute(
        select(
            func.count(Module.id),
            func.count(Module.id).filter(Module.status == "completed"),
        )
        .join(Course, Course.id == Module.course_id)
        .where(Course.owner_id == current_user.id)
    )
    modules_total, modules_completed = modules_count_result.one()

    return AnalyticsSummary(
        modules_completed=modules_completed or 0,
        modules_total=modules_total or 0,
        average_score_by_module=average_score_by_module,
        score_trend=score_trend,
    )
