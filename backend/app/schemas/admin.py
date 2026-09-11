from pydantic import BaseModel


class CostByUser(BaseModel):
    user_id: int | None
    email: str | None
    total_cost_usd: float
    call_count: int


class CostByCourse(BaseModel):
    course_id: int | None
    course_title: str | None
    total_cost_usd: float
    call_count: int


class CostByEndpoint(BaseModel):
    endpoint: str
    total_cost_usd: float
    call_count: int
    cache_hit_rate: float


class CostOverTimePoint(BaseModel):
    date: str
    total_cost_usd: float
    call_count: int


class RouteLatency(BaseModel):
    route: str
    count: int
    p50_ms: float
    p95_ms: float


class AdminMetrics(BaseModel):
    window_days: int
    total_cost_usd: float
    total_calls: int
    cost_by_user: list[CostByUser]
    cost_by_course: list[CostByCourse]
    cost_by_endpoint: list[CostByEndpoint]
    cost_over_time: list[CostOverTimePoint]
    route_latency: list[RouteLatency]
