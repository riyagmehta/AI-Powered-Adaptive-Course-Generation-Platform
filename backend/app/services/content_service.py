import logging
from collections.abc import AsyncGenerator

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.course import Course
from app.models.module import Module
from app.services.ai_client import client
from app.services.embedding_service import index_module_content

logger = logging.getLogger(__name__)

DIFFICULTY_INSTRUCTIONS = {
    "beginner": (
        "Write for a complete beginner. Explain concepts from first principles, avoid unexplained "
        "jargon, use simple analogies, and include plenty of small, concrete examples."
    ),
    "intermediate": (
        "Write for a learner with some working familiarity with the subject. Assume basic vocabulary "
        "is known, focus on practical application, and move at a moderate technical depth."
    ),
    "advanced": (
        "Write for an experienced learner. Be technically precise and concise, favor depth and nuance "
        "over re-explaining basics, and highlight edge cases, trade-offs, and advanced techniques."
    ),
}

DEFAULT_DIFFICULTY = "intermediate"


def build_system_prompt(course: Course) -> str:
    tone = DIFFICULTY_INSTRUCTIONS.get(course.current_difficulty, DIFFICULTY_INSTRUCTIONS[DEFAULT_DIFFICULTY])
    return (
        f"You are an expert instructor writing a lesson for the course '{course.title}'. {tone} "
        "Write the lesson content in Markdown with headings, and end with a short 'Key takeaways' list."
    )


def build_user_prompt(module: Module) -> str:
    return (
        f"Module title: {module.title}\n"
        f"Module summary / learning objectives: {module.summary or 'N/A'}\n\n"
        "Write the full lesson content for this module."
    )


async def stream_module_content(course: Course, module: Module) -> AsyncGenerator[str, None]:
    stream = await client.chat.completions.create(
        model=settings.openai_chat_model,
        stream=True,
        temperature=0.7,
        messages=[
            {"role": "system", "content": build_system_prompt(course)},
            {"role": "user", "content": build_user_prompt(module)},
        ],
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def generate_and_save_first_module(course_id: int) -> None:
    async with AsyncSessionLocal() as db:
        course = await db.get(Course, course_id)
        if course is None:
            return

        result = await db.execute(
            select(Module)
            .where(Module.course_id == course_id)
            .order_by(Module.order_index)
            .limit(1)
        )
        module = result.scalar_one_or_none()
        if module is None or module.status != "pending":
            return

        module.status = "generating"
        db.add(module)
        await db.commit()

        try:
            chunks = [chunk async for chunk in stream_module_content(course, module)]
            module.content = "".join(chunks)
            module.status = "completed"
        except Exception:
            logger.exception("Background generation failed for module %s", module.id)
            module.status = "failed"

        db.add(module)
        await db.commit()

        if module.status == "completed":
            try:
                await index_module_content(module.id, course.id, module.content)
            except Exception:
                logger.exception("Failed to index module %s content for RAG", module.id)
