from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Onboarding
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    learning_goal: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_pace: Mapped[str | None] = mapped_column(String(50), nullable=True)
    topics_of_interest: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    courses: Mapped[list["Course"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
