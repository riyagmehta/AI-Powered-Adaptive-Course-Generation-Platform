from fastapi import FastAPI

from app.routers import auth

app = FastAPI(title="AI-Powered Adaptive Course Generation Platform")

app.include_router(auth.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
