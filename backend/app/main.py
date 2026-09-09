from fastapi import FastAPI

from app.routers import auth, courses, doubts, modules

app = FastAPI(title="AI-Powered Adaptive Course Generation Platform")

app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(modules.router)
app.include_router(doubts.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
