from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.course import Course
from app.models.llm_call import LLMCall
from app.models.user import User
from app.observability.middleware import LATENCY_ROUTES_SET_KEY
from app.schemas.admin import (
    AdminMetrics,
    CostByCourse,
    CostByEndpoint,
    CostByUser,
    CostOverTimePoint,
    RouteLatency,
)
from app.services.auth_service import get_current_user
from app.services.redis_client import redis_client

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, round(pct * (len(sorted_values) - 1))))
    return sorted_values[index]


async def _route_latency_stats() -> list[RouteLatency]:
    keys = await redis_client.smembers(LATENCY_ROUTES_SET_KEY)
    stats = []
    for key in keys:
        raw_samples = await redis_client.lrange(key, 0, -1)
        if not raw_samples:
            continue
        samples = sorted(float(s) for s in raw_samples)
        # key looks like "latency:GET:/courses/{course_id}"
        route = key.split(":", 2)[2] if key.count(":") >= 2 else key
        method = key.split(":", 2)[1] if key.count(":") >= 2 else ""
        stats.append(
            RouteLatency(
                route=f"{method} {route}",
                count=len(samples),
                p50_ms=round(_percentile(samples, 0.50), 1),
                p95_ms=round(_percentile(samples, 0.95), 1),
            )
        )
    stats.sort(key=lambda s: s.p95_ms, reverse=True)
    return stats


@router.get("/metrics", response_model=AdminMetrics)
async def get_metrics(
    days: int = Query(default=30, ge=1, le=365),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminMetrics:
    since = func.now() - func.make_interval(0, 0, 0, days)

    totals_result = await db.execute(
        select(func.coalesce(func.sum(LLMCall.cost_usd), 0.0), func.count(LLMCall.id)).where(
            LLMCall.created_at >= since
        )
    )
    total_cost_usd, total_calls = totals_result.one()

    by_user_result = await db.execute(
        select(
            LLMCall.user_id,
            User.email,
            func.sum(LLMCall.cost_usd),
            func.count(LLMCall.id),
        )
        .outerjoin(User, User.id == LLMCall.user_id)
        .where(LLMCall.created_at >= since)
        .group_by(LLMCall.user_id, User.email)
        .order_by(func.sum(LLMCall.cost_usd).desc())
    )
    cost_by_user = [
        CostByUser(user_id=uid, email=email, total_cost_usd=round(cost, 6), call_count=count)
        for uid, email, cost, count in by_user_result.all()
    ]

    by_course_result = await db.execute(
        select(
            LLMCall.course_id,
            Course.title,
            func.sum(LLMCall.cost_usd),
            func.count(LLMCall.id),
        )
        .outerjoin(Course, Course.id == LLMCall.course_id)
        .where(LLMCall.created_at >= since)
        .group_by(LLMCall.course_id, Course.title)
        .order_by(func.sum(LLMCall.cost_usd).desc())
    )
    cost_by_course = [
        CostByCourse(course_id=cid, course_title=title, total_cost_usd=round(cost, 6), call_count=count)
        for cid, title, cost, count in by_course_result.all()
    ]

    by_endpoint_result = await db.execute(
        select(
            LLMCall.endpoint,
            func.sum(LLMCall.cost_usd),
            func.count(LLMCall.id),
            func.avg(LLMCall.cache_hit.cast(Integer)),
        )
        .where(LLMCall.created_at >= since)
        .group_by(LLMCall.endpoint)
        .order_by(func.sum(LLMCall.cost_usd).desc())
    )
    cost_by_endpoint = [
        CostByEndpoint(
            endpoint=endpoint,
            total_cost_usd=round(cost, 6),
            call_count=count,
            cache_hit_rate=round(cache_rate or 0.0, 3),
        )
        for endpoint, cost, count, cache_rate in by_endpoint_result.all()
    ]

    over_time_result = await db.execute(
        select(
            func.date(LLMCall.created_at),
            func.sum(LLMCall.cost_usd),
            func.count(LLMCall.id),
        )
        .where(LLMCall.created_at >= since)
        .group_by(func.date(LLMCall.created_at))
        .order_by(func.date(LLMCall.created_at))
    )
    cost_over_time = [
        CostOverTimePoint(
            date=(day.isoformat() if isinstance(day, date) else str(day)),
            total_cost_usd=round(cost, 6),
            call_count=count,
        )
        for day, cost, count in over_time_result.all()
    ]

    return AdminMetrics(
        window_days=days,
        total_cost_usd=round(total_cost_usd, 6),
        total_calls=total_calls,
        cost_by_user=cost_by_user,
        cost_by_course=cost_by_course,
        cost_by_endpoint=cost_by_endpoint,
        cost_over_time=cost_over_time,
        route_latency=await _route_latency_stats(),
    )
