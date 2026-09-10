from fastapi import FastAPI

from app.routers import analytics, auth, courses, doubts, modules, quizzes

app = FastAPI(title="AI-Powered Adaptive Course Generation Platform")

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(modules.router)
app.include_router(doubts.router)
app.include_router(quizzes.router)
app.include_router(analytics.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
