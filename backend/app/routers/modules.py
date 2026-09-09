import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.module import Module
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.content_service import stream_module_content
from app.services.embedding_service import index_module_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/modules", tags=["modules"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/{module_id}/stream")
async def stream_module(
    module_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    result = await db.execute(
        select(Module).where(Module.id == module_id).options(selectinload(Module.course))
    )
    module = result.scalar_one_or_none()
    if module is None or module.course.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    if module.status == "generating":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Module is already generating")

    course = module.course

    async def event_stream() -> AsyncGenerator[str, None]:
        if module.status == "completed" and module.content:
            yield _sse("chunk", {"delta": module.content})
            yield _sse("done", {"module_id": module.id, "status": module.status})
            return

        module.status = "generating"
        db.add(module)
        await db.commit()

        chunks: list[str] = []
        try:
            async for delta in stream_module_content(course, module):
                chunks.append(delta)
                yield _sse("chunk", {"delta": delta})
        except Exception as exc:
            module.status = "failed"
            db.add(module)
            await db.commit()
            yield _sse("error", {"detail": str(exc)})
            return

        module.content = "".join(chunks)
        module.status = "completed"
        db.add(module)
        await db.commit()

        try:
            await index_module_content(module.id, course.id, module.content)
        except Exception:
            logger.exception("Failed to index module %s content for RAG", module.id)

        yield _sse("done", {"module_id": module.id, "status": module.status})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
