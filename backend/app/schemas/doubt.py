from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DoubtCreate(BaseModel):
    module_id: int
    question: str = Field(min_length=1, max_length=2000)


class DoubtRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    module_id: int
    question: str
    answer: str
    cache_hit: bool
    retrieved_chunk_ids: list
    created_at: datetime
