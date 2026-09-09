from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    topic: str | None = None
    num_modules: int = Field(default=5, ge=3, le=8)


class ModuleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_index: int
    title: str
    summary: str | None
    status: str


class ModuleDetail(ModuleSummary):
    content: str | None


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    status: str
    current_difficulty: str
    created_at: datetime
    modules: list[ModuleSummary]


class CourseDetail(CourseRead):
    modules: list[ModuleDetail]
