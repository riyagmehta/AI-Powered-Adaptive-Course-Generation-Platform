from pydantic import BaseModel, ConfigDict, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    onboarding_completed: bool
    learning_goal: str | None
    experience_level: str | None
    preferred_pace: str | None
    topics_of_interest: list[str] | None


class OnboardingUpdate(BaseModel):
    learning_goal: str | None = None
    experience_level: str | None = None
    preferred_pace: str | None = None
    topics_of_interest: list[str] | None = None
    onboarding_completed: bool | None = None
