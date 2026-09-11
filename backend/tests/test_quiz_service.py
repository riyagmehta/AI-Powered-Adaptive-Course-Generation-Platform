import pytest

from app.services.quiz_service import (
    DEFAULT_DIFFICULTY,
    DEMOTE_THRESHOLD,
    PROMOTE_THRESHOLD,
    recalibrate_difficulty,
    score_attempt,
)

QUESTIONS = [
    {"question": f"Q{i}", "options": ["a", "b", "c", "d"], "correct_index": i % 4, "explanation": f"exp{i}"}
    for i in range(5)
]
CORRECT_ANSWERS = [q["correct_index"] for q in QUESTIONS]


class TestScoreAttempt:
    def test_all_correct_scores_100(self):
        score, results = score_attempt(QUESTIONS, CORRECT_ANSWERS)

        assert score == 100.0
        assert all(r["is_correct"] for r in results)
        assert [r["selected_index"] for r in results] == CORRECT_ANSWERS

    def test_all_wrong_scores_0(self):
        wrong_answers = [(c + 1) % 4 for c in CORRECT_ANSWERS]

        score, results = score_attempt(QUESTIONS, wrong_answers)

        assert score == 0.0
        assert not any(r["is_correct"] for r in results)

    def test_partial_credit_computes_percentage(self):
        # First 3 correct, last 2 wrong -> 60%.
        answers = CORRECT_ANSWERS[:3] + [(c + 1) % 4 for c in CORRECT_ANSWERS[3:]]

        score, results = score_attempt(QUESTIONS, answers)

        assert score == 60.0
        assert [r["is_correct"] for r in results] == [True, True, True, False, False]

    def test_missing_answers_are_treated_as_unanswered_and_incorrect(self):
        # Only answered the first 2 of 5 questions.
        answers = CORRECT_ANSWERS[:2]

        score, results = score_attempt(QUESTIONS, answers)

        assert score == 40.0
        assert results[2]["selected_index"] is None
        assert results[2]["is_correct"] is False
        assert results[3]["selected_index"] is None
        assert results[4]["selected_index"] is None

    def test_result_rows_carry_options_and_explanation_for_review(self):
        _, results = score_attempt(QUESTIONS, CORRECT_ANSWERS)

        for question, result in zip(QUESTIONS, results):
            assert result["question"] == question["question"]
            assert result["options"] == question["options"]
            assert result["correct_index"] == question["correct_index"]
            assert result["explanation"] == question["explanation"]

    def test_empty_question_set_scores_zero_without_dividing_by_zero(self):
        score, results = score_attempt([], [])

        assert score == 0.0
        assert results == []


class TestRecalibrateDifficulty:
    def test_high_score_promotes_beginner_to_intermediate(self):
        assert recalibrate_difficulty("beginner", PROMOTE_THRESHOLD) == "intermediate"

    def test_high_score_promotes_intermediate_to_advanced(self):
        assert recalibrate_difficulty("intermediate", 100.0) == "advanced"

    def test_high_score_caps_at_advanced(self):
        assert recalibrate_difficulty("advanced", 100.0) == "advanced"

    def test_low_score_demotes_advanced_to_intermediate(self):
        assert recalibrate_difficulty("advanced", DEMOTE_THRESHOLD - 0.01) == "intermediate"

    def test_low_score_demotes_intermediate_to_beginner(self):
        assert recalibrate_difficulty("intermediate", 0.0) == "beginner"

    def test_low_score_floors_at_beginner(self):
        assert recalibrate_difficulty("beginner", 0.0) == "beginner"

    @pytest.mark.parametrize("score", [50.0, 60.0, 79.99])
    def test_middle_band_leaves_difficulty_unchanged(self, score):
        assert recalibrate_difficulty("intermediate", score) == "intermediate"

    def test_promote_threshold_is_inclusive(self):
        assert recalibrate_difficulty("beginner", PROMOTE_THRESHOLD) == "intermediate"

    def test_demote_threshold_is_exclusive(self):
        # Exactly at the threshold should NOT demote.
        assert recalibrate_difficulty("intermediate", DEMOTE_THRESHOLD) == "intermediate"

    def test_unknown_current_difficulty_falls_back_to_default_before_recalibrating(self):
        # An unrecognized value shouldn't crash — it's treated as the default
        # difficulty and recalibrated from there.
        assert recalibrate_difficulty("not-a-real-level", PROMOTE_THRESHOLD) == (
            recalibrate_difficulty(DEFAULT_DIFFICULTY, PROMOTE_THRESHOLD)
        )
