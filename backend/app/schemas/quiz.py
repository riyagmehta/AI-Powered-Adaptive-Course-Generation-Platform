from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QuizQuestionPublic(BaseModel):
    question: str
    options: list[str]


class QuizRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    difficulty: str
    created_at: datetime
    questions: list[QuizQuestionPublic]


class QuizAttemptCreate(BaseModel):
    answers: list[int] = Field(min_length=1)


class QuizQuestionResult(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    explanation: str
    selected_index: int | None
    is_correct: bool


class QuizAttemptRead(BaseModel):
    id: int
    quiz_id: int
    score: float
    difficulty_at_attempt: str
    new_difficulty: str
    results: list[QuizQuestionResult]


class ModuleScoreStat(BaseModel):
    module_id: int
    module_title: str
    attempts_count: int
    average_score: float


class ScoreTrendPoint(BaseModel):
    attempt_id: int
    module_id: int
    score: float
    created_at: datetime


class AnalyticsSummary(BaseModel):
    modules_completed: int
    modules_total: int
    average_score_by_module: list[ModuleScoreStat]
    score_trend: list[ScoreTrendPoint]
