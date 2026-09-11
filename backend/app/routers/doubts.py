import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.doubt import Doubt
from app.models.module import Module
from app.models.user import User
from app.schemas.doubt import DoubtCreate
from app.services.auth_service import get_current_user
from app.services.doubt_service import resolve_doubt
from app.services.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/doubts", tags=["doubts"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("")
@limiter.limit("15/minute")
async def create_doubt(
    request: Request,
    payload: DoubtCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    result = await db.execute(
        select(Module).where(Module.id == payload.module_id).options(selectinload(Module.course))
    )
    module = result.scalar_one_or_none()
    if module is None or module.course.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    if module.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Module content has not been generated yet",
        )

    question = payload.question

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for event in resolve_doubt(module, question):
                if event["type"] == "chunk":
                    yield _sse("chunk", {"delta": event["delta"]})
                    continue

                doubt = Doubt(
                    module_id=module.id,
                    user_id=current_user.id,
                    question=question,
                    answer=event["answer"],
                    cache_hit=event["cache_hit"],
                    retrieved_chunk_ids=event["retrieved_chunk_ids"],
                )
                db.add(doubt)
                await db.commit()
                await db.refresh(doubt)

                yield _sse(
                    "done",
                    {
                        "doubt_id": doubt.id,
                        "cache_hit": doubt.cache_hit,
                        "retrieved_chunk_ids": doubt.retrieved_chunk_ids,
                    },
                )
        except Exception as exc:
            logger.exception("Doubt resolution failed for module %s", module.id)
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
