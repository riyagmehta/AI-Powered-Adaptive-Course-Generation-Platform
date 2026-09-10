import json

from app.config import settings
from app.models.course import Course
from app.models.module import Module
from app.services.ai_client import client

DIFFICULTY_LEVELS = ["beginner", "intermediate", "advanced"]
DEFAULT_DIFFICULTY = "intermediate"

PROMOTE_THRESHOLD = 80.0
DEMOTE_THRESHOLD = 50.0

QUIZ_SYSTEM_PROMPT = """You are an assessment designer for an adaptive online learning platform.
Given a module's lesson content, write exactly 5 multiple-choice questions that test understanding
of that content at the requested difficulty level.

Respond with ONLY a JSON object of this exact shape:
{
  "questions": [
    {
      "question": "<question text>",
      "options": ["<option A>", "<option B>", "<option C>", "<option D>"],
      "correct_index": <0-based index of the correct option>,
      "explanation": "<1-2 sentence explanation of why the correct answer is correct>"
    }
  ]
}
The "questions" array must contain exactly 5 questions, each with exactly 4 options."""


class QuizGenerationError(Exception):
    pass


def _build_user_prompt(module: Module, difficulty: str) -> str:
    return (
        f"Module title: {module.title}\n"
        f"Difficulty level: {difficulty}\n\n"
        f"Module content:\n{module.content}\n\n"
        "Write 5 multiple-choice questions covering this content at the given difficulty level."
    )


async def generate_quiz_questions(module: Module, difficulty: str) -> list[dict]:
    response = await client.chat.completions.create(
        model=settings.openai_chat_model,
        response_format={"type": "json_object"},
        temperature=0.7,
        messages=[
            {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(module, difficulty)},
        ],
    )

    raw = response.choices[0].message.content
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise QuizGenerationError(f"Model returned invalid JSON: {raw!r}") from exc

    questions = payload.get("questions")
    if not isinstance(questions, list) or len(questions) != 5:
        raise QuizGenerationError(f"Model returned an incomplete quiz: {payload!r}")

    for q in questions:
        options = q.get("options")
        correct_index = q.get("correct_index")
        if (
            not q.get("question")
            or not isinstance(options, list)
            or len(options) != 4
            or not isinstance(correct_index, int)
            or not (0 <= correct_index < 4)
            or not q.get("explanation")
        ):
            raise QuizGenerationError(f"Quiz question malformed: {q!r}")

    return questions


def score_attempt(questions: list[dict], answers: list[int]) -> tuple[float, list[dict]]:
    results = []
    correct_count = 0
    for i, q in enumerate(questions):
        selected = answers[i] if i < len(answers) else None
        is_correct = selected == q["correct_index"]
        if is_correct:
            correct_count += 1
        results.append(
            {
                "question": q["question"],
                "options": q["options"],
                "correct_index": q["correct_index"],
                "explanation": q["explanation"],
                "selected_index": selected,
                "is_correct": is_correct,
            }
        )

    score = (correct_count / len(questions)) * 100 if questions else 0.0
    return score, results


def recalibrate_difficulty(current_difficulty: str, score: float) -> str:
    current_index = (
        DIFFICULTY_LEVELS.index(current_difficulty)
        if current_difficulty in DIFFICULTY_LEVELS
        else DIFFICULTY_LEVELS.index(DEFAULT_DIFFICULTY)
    )

    if score >= PROMOTE_THRESHOLD:
        new_index = min(current_index + 1, len(DIFFICULTY_LEVELS) - 1)
    elif score < DEMOTE_THRESHOLD:
        new_index = max(current_index - 1, 0)
    else:
        new_index = current_index

    return DIFFICULTY_LEVELS[new_index]
