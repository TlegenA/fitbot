from datetime import date, datetime, timedelta
from typing import Optional, List

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db.models import User, UserSettings, WorkoutSchedule, Workout, ExerciseSet, UserExerciseTarget


# ---------- Users ----------

async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: Optional[str],
    first_name: str,
) -> tuple[User, bool]:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        return user, False
    user = User(id=user_id, username=username, first_name=first_name)
    session.add(user)
    await session.flush()
    return user, True


async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(
        select(User)
        .options(selectinload(User.settings), selectinload(User.schedule))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


# ---------- Settings ----------

async def get_user_settings(session: AsyncSession, user_id: int) -> Optional[UserSettings]:
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_user_settings(
    session: AsyncSession, user_id: int, **kwargs
) -> UserSettings:
    s = await get_user_settings(session, user_id)
    if s is None:
        s = UserSettings(user_id=user_id, **kwargs)
        session.add(s)
    else:
        for k, v in kwargs.items():
            setattr(s, k, v)
    await session.flush()
    return s


# ---------- Schedule ----------

async def replace_schedule(
    session: AsyncSession, user_id: int, entries: list[dict]
) -> None:
    existing = await session.execute(
        select(WorkoutSchedule).where(WorkoutSchedule.user_id == user_id)
    )
    for row in existing.scalars():
        await session.delete(row)
    await session.flush()
    for e in entries:
        session.add(WorkoutSchedule(user_id=user_id, **e))
    await session.flush()


async def get_schedule(
    session: AsyncSession, user_id: int
) -> List[WorkoutSchedule]:
    result = await session.execute(
        select(WorkoutSchedule)
        .where(WorkoutSchedule.user_id == user_id)
        .order_by(WorkoutSchedule.day_of_week)
    )
    return list(result.scalars())


# ---------- Workouts ----------

async def create_workout(session: AsyncSession, **kwargs) -> Workout:
    w = Workout(**kwargs)
    session.add(w)
    await session.flush()
    return w


async def get_today_workout(
    session: AsyncSession, user_id: int, today: date
) -> Optional[Workout]:
    result = await session.execute(
        select(Workout).where(
            and_(
                Workout.user_id == user_id,
                Workout.scheduled_date == today,
                Workout.status.in_(["planned", "shifted"]),
            )
        ).order_by(Workout.id)
    )
    return result.scalars().first()


async def get_workout_by_id(
    session: AsyncSession, workout_id: int
) -> Optional[Workout]:
    result = await session.execute(
        select(Workout)
        .options(selectinload(Workout.sets))
        .where(Workout.id == workout_id)
    )
    return result.scalar_one_or_none()


async def update_workout_status(
    session: AsyncSession,
    workout_id: int,
    status: str,
    actual_date: Optional[date] = None,
    location: Optional[str] = None,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
) -> None:
    values: dict = {"status": status}
    if actual_date is not None:
        values["actual_date"] = actual_date
    if location is not None:
        values["location"] = location
    if started_at is not None:
        values["started_at"] = started_at
    if finished_at is not None:
        values["finished_at"] = finished_at
    await session.execute(
        update(Workout).where(Workout.id == workout_id).values(**values)
    )


async def find_next_free_day(
    session: AsyncSession, user_id: int, after: date
) -> date:
    """Return the first date after `after` that has no planned/shifted workout."""
    # Get schedule days of week
    schedule = await get_schedule(session, user_id)
    scheduled_dow = {s.day_of_week for s in schedule}

    candidate = after + timedelta(days=1)
    for _ in range(60):
        # Not a scheduled training day
        if candidate.weekday() not in scheduled_dow:
            # No existing workout on that date
            existing = await session.execute(
                select(Workout).where(
                    and_(
                        Workout.user_id == user_id,
                        Workout.scheduled_date == candidate,
                        Workout.status.in_(["planned", "shifted"]),
                    )
                )
            )
            if not existing.scalar_one_or_none():
                return candidate
        candidate += timedelta(days=1)
    return candidate


async def get_week_workouts(
    session: AsyncSession, user_id: int, week_start: date
) -> List[Workout]:
    week_end = week_start + timedelta(days=6)
    result = await session.execute(
        select(Workout)
        .options(selectinload(Workout.sets))
        .where(
            and_(
                Workout.user_id == user_id,
                Workout.scheduled_date >= week_start,
                Workout.scheduled_date <= week_end,
            )
        )
        .order_by(Workout.scheduled_date)
    )
    return list(result.scalars())


async def get_all_workouts(
    session: AsyncSession, user_id: int
) -> List[Workout]:
    result = await session.execute(
        select(Workout)
        .options(selectinload(Workout.sets))
        .where(Workout.user_id == user_id)
        .order_by(Workout.scheduled_date)
    )
    return list(result.scalars())


# ---------- Sets ----------

# ---------- Exercise Targets ----------

async def get_user_targets(
    session: AsyncSession, user_id: int
) -> dict[str, "UserExerciseTarget"]:
    result = await session.execute(
        select(UserExerciseTarget).where(UserExerciseTarget.user_id == user_id)
    )
    return {row.exercise_key: row for row in result.scalars()}


async def upsert_exercise_target(
    session: AsyncSession,
    user_id: int,
    exercise_key: str,
    target_sets: int,
    target_reps: int | None = None,
    target_duration_sec: int | None = None,
) -> UserExerciseTarget:
    result = await session.execute(
        select(UserExerciseTarget).where(
            UserExerciseTarget.user_id == user_id,
            UserExerciseTarget.exercise_key == exercise_key,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = UserExerciseTarget(
            user_id=user_id,
            exercise_key=exercise_key,
            target_sets=target_sets,
            target_reps=target_reps,
            target_duration_sec=target_duration_sec,
        )
        session.add(row)
    else:
        row.target_sets = target_sets
        row.target_reps = target_reps
        row.target_duration_sec = target_duration_sec
    await session.flush()
    return row


# ---------- Sets ----------

async def log_set(session: AsyncSession, **kwargs) -> ExerciseSet:
    s = ExerciseSet(**kwargs)
    session.add(s)
    await session.flush()
    return s


async def get_workout_sets(
    session: AsyncSession, workout_id: int
) -> List[ExerciseSet]:
    result = await session.execute(
        select(ExerciseSet)
        .where(ExerciseSet.workout_id == workout_id)
        .order_by(ExerciseSet.exercise_key, ExerciseSet.set_number)
    )
    return list(result.scalars())
