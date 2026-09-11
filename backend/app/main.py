from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.routers import analytics, auth, courses, doubts, modules, quizzes
from app.services.rate_limit import limiter

app = FastAPI(title="AI-Powered Adaptive Course Generation Platform")

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

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(modules.router)
app.include_router(doubts.router)
app.include_router(quizzes.router)
app.include_router(analytics.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
