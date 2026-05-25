from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey,
    Integer, Numeric, String, ARRAY, Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    settings: Mapped[Optional["UserSettings"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    schedule: Mapped[List["WorkoutSchedule"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    workouts: Mapped[List["Workout"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    exercise_targets: Mapped[List["UserExerciseTarget"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    days_per_week: Mapped[int] = mapped_column(Integer, default=3)
    home_equipment: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    street_equipment: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list)
    has_bench: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_behavior: Mapped[str] = mapped_column(String(16), default="ask")
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="settings")


class WorkoutSchedule(Base):
    __tablename__ = "workout_schedule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    day_of_week: Mapped[int] = mapped_column(Integer)  # 0=Mon ... 6=Sun
    plan_day: Mapped[str] = mapped_column(String(2))   # A, B, C

    user: Mapped["User"] = relationship(back_populates="schedule")


class Workout(Base):
    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    plan_day: Mapped[str] = mapped_column(String(2))
    scheduled_date: Mapped[date] = mapped_column(Date)
    actual_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="planned")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="workouts")
    sets: Mapped[List["ExerciseSet"]] = relationship(
        back_populates="workout", cascade="all, delete-orphan"
    )


class UserExerciseTarget(Base):
    __tablename__ = "user_exercise_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE")
    )
    exercise_key: Mapped[str] = mapped_column(String(64))
    target_sets: Mapped[int] = mapped_column(Integer)
    target_reps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="exercise_targets")


class ExerciseSet(Base):
    __tablename__ = "sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workout_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workouts.id", ondelete="CASCADE")
    )
    exercise_key: Mapped[str] = mapped_column(String(64))
    set_number: Mapped[int] = mapped_column(Integer)
    reps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    logged_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    workout: Mapped["Workout"] = relationship(back_populates="sets")
