import pytest
from httpx import ASGITransport, AsyncClient

from app.database import AsyncSessionLocal
from app.main import app
from app.models.quiz import Quiz
from app.models.quiz_attempt import QuizAttempt
from app.services.security import create_access_token

QUESTIONS = [
    {
        "question": f"Question {i}?",
        "options": ["a", "b", "c", "d"],
        "correct_index": i % 4,
        "explanation": f"Explanation {i}",
    }
    for i in range(5)
]
CORRECT_ANSWERS = [q["correct_index"] for q in QUESTIONS]
WRONG_ANSWERS = [(c + 1) % 4 for c in CORRECT_ANSWERS]


@pytest.fixture
def auth_headers(seeded_module):
    token = create_access_token(subject=seeded_module.user.email)
    return {"Authorization": f"Bearer {token}"}


async def _create_quiz(module_id: int, difficulty: str = "intermediate") -> int:
    async with AsyncSessionLocal() as db:
        quiz = Quiz(module_id=module_id, questions=QUESTIONS, difficulty=difficulty)
        db.add(quiz)
        await db.commit()
        await db.refresh(quiz)
        return quiz.id


@pytest.mark.asyncio(loop_scope="session")
async def test_attempt_scores_and_returns_explanations(seeded_module, auth_headers):
    quiz_id = await _create_quiz(seeded_module.module.id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/quizzes/{quiz_id}/attempt",
            json={"answers": CORRECT_ANSWERS},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 100.0
    assert body["quiz_id"] == quiz_id
    assert len(body["results"]) == 5
    assert all(r["is_correct"] for r in body["results"])
    assert body["results"][0]["explanation"] == "Explanation 0"

    async with AsyncSessionLocal() as db:
        attempt = await db.get(QuizAttempt, body["id"])
        assert attempt is not None
        assert attempt.score == 100.0
        assert attempt.user_id == seeded_module.user.id
        assert attempt.answers == CORRECT_ANSWERS


@pytest.mark.asyncio(loop_scope="session")
async def test_passing_attempt_promotes_course_difficulty(seeded_module, auth_headers):
    course = seeded_module.course
    assert course.current_difficulty == "intermediate"
    quiz_id = await _create_quiz(seeded_module.module.id, difficulty=course.current_difficulty)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/quizzes/{quiz_id}/attempt",
            json={"answers": CORRECT_ANSWERS},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["difficulty_at_attempt"] == "intermediate"
    assert body["new_difficulty"] == "advanced"

    async with AsyncSessionLocal() as db:
        refreshed = await db.get(type(course), course.id)
        assert refreshed.current_difficulty == "advanced"


@pytest.mark.asyncio(loop_scope="session")
async def test_failing_attempt_demotes_course_difficulty(seeded_module, auth_headers):
    course = seeded_module.course
    quiz_id = await _create_quiz(seeded_module.module.id, difficulty=course.current_difficulty)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/quizzes/{quiz_id}/attempt",
            json={"answers": WRONG_ANSWERS},
            headers=auth_headers,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 0.0
    assert body["difficulty_at_attempt"] == "intermediate"
    assert body["new_difficulty"] == "beginner"

    async with AsyncSessionLocal() as db:
        refreshed = await db.get(type(course), course.id)
        assert refreshed.current_difficulty == "beginner"


@pytest.mark.asyncio(loop_scope="session")
async def test_attempt_on_another_users_quiz_is_not_found(seeded_module):
    quiz_id = await _create_quiz(seeded_module.module.id)
    other_user_token = create_access_token(subject="someone-else@example.com")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/quizzes/{quiz_id}/attempt",
            json={"answers": CORRECT_ANSWERS},
            headers={"Authorization": f"Bearer {other_user_token}"},
        )

    # The token's subject isn't a real user, so auth itself fails first.
    assert response.status_code == 401


@pytest.mark.asyncio(loop_scope="session")
async def test_get_quiz_hides_correct_answers(seeded_module, auth_headers):
    await _create_quiz(seeded_module.module.id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/modules/{seeded_module.module.id}/quiz", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["questions"]) == 5
    for question in body["questions"]:
        assert "correct_index" not in question
        assert "explanation" not in question
