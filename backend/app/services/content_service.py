from app.config import settings
from app.models.course import Course
from app.models.module import Module
from app.services.ai_client import client

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


async def generate_module_content(course: Course, module: Module) -> str:
    """Single non-streaming completion — this runs inside a durable ARQ job, not
    a live HTTP request, so there's no client connection to stream tokens to."""
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        temperature=0.7,
        messages=[
            {"role": "system", "content": build_system_prompt(course)},
            {"role": "user", "content": build_user_prompt(module)},
        ],
    )
    return response.choices[0].message.content
