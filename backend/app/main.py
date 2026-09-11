from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import analytics, auth, courses, doubts, modules, quizzes

app = FastAPI(title="AI-Powered Adaptive Course Generation Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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
