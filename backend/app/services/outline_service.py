import json

from app.config import settings
from app.models.user import User
from app.services.ai_client import client

OUTLINE_SYSTEM_PROMPT = """You are a curriculum designer for an adaptive online learning platform.
Given a learner's profile and a topic, design a course outline.

Respond with ONLY a JSON object of this exact shape:
{
  "title": "<concise course title>",
  "description": "<1-2 sentence course description>",
  "modules": [
    {"title": "<module title>", "summary": "<2-3 sentence summary of what the module covers and its learning objectives>"}
  ]
}
The "modules" array must contain exactly the number of modules requested, ordered from foundational to advanced."""


class OutlineGenerationError(Exception):
    pass


def _build_user_prompt(user: User, topic: str | None, num_modules: int) -> str:
    lines = [
        f"Experience level: {user.experience_level or 'unspecified'}",
        f"Preferred pace: {user.preferred_pace or 'unspecified'}",
        f"Topics of interest: {', '.join(user.topics_of_interest) if user.topics_of_interest else 'unspecified'}",
        f"Learning goal: {user.learning_goal or 'unspecified'}",
        f"Requested topic for this course: {topic or user.learning_goal or 'unspecified'}",
        f"Number of modules: {num_modules}",
    ]
    return "\n".join(lines)


async def synthesize_outline(user: User, topic: str | None, num_modules: int) -> dict:
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        temperature=0.7,
        messages=[
            {"role": "system", "content": OUTLINE_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(user, topic, num_modules)},
        ],
    )

    raw = response.choices[0].message.content
    try:
        outline = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutlineGenerationError(f"Model returned invalid JSON: {raw!r}") from exc

    modules = outline.get("modules")
    if not outline.get("title") or not isinstance(modules, list) or not modules:
        raise OutlineGenerationError(f"Model returned an incomplete outline: {outline!r}")

    for module in modules:
        if not module.get("title"):
            raise OutlineGenerationError(f"Outline module missing title: {module!r}")

    outline["modules"] = modules[:num_modules]
    return outline
