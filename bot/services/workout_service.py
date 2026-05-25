from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants import (
    SCHEDULE_2_DAYS, SCHEDULE_3_DAYS, SCHEDULE_4_DAYS,
    SCHEDULE_2_PLAN, SCHEDULE_3_PLAN, SCHEDULE_4_PLAN,
    STATUS_PLANNED, STATUS_DONE, STATUS_SKIPPED, STATUS_SHIFTED,
    SKIP_SHIFT, SKIP_SKIP,
    DAY_NAMES_RU,
)
from bot.db import crud
from bot.db.models import Workout, UserSettings


def build_schedule(days_per_week: int) -> list[dict]:
    """Return list of {day_of_week, plan_day} entries."""
    if days_per_week == 2:
        days, plans = SCHEDULE_2_DAYS, SCHEDULE_2_PLAN
    elif days_per_week == 4:
        days, plans = SCHEDULE_4_DAYS, SCHEDULE_4_PLAN
    else:
        days, plans = SCHEDULE_3_DAYS, SCHEDULE_3_PLAN
    return [{"day_of_week": d, "plan_day": p} for d, p in zip(days, plans)]


def schedule_summary(entries: list[dict]) -> str:
    lines = []
    for e in entries:
        lines.append(f"  {DAY_NAMES_RU[e['day_of_week']]} — тренировка {e['plan_day']}")
    return "\n".join(lines)


async def get_today_plan_day(
    session: AsyncSession, user_id: int, today: date
) -> Optional[str]:
    """Return the plan_day (A/B/C) for today based on schedule, or None."""
    schedule = await crud.get_schedule(session, user_id)
    dow = today.weekday()
    for entry in schedule:
        if entry.day_of_week == dow:
            return entry.plan_day
    return None


async def ensure_planned_workout(
    session: AsyncSession, user_id: int, today: date
) -> Optional[Workout]:
    """Ensure a planned workout record exists for today; return it."""
    existing = await crud.get_today_workout(session, user_id, today)
    if existing:
        return existing
    plan_day = await get_today_plan_day(session, user_id, today)
    if not plan_day:
        return None
    return await crud.create_workout(
        session,
        user_id=user_id,
        plan_day=plan_day,
        scheduled_date=today,
        status=STATUS_PLANNED,
    )


async def handle_skip(
    session: AsyncSession,
    workout: Workout,
    behavior: str,
    today: date,
) -> str:
    """Process skip: shift or skip. Returns a status message."""
    if behavior == SKIP_SHIFT:
        await crud.update_workout_status(session, workout.id, STATUS_SKIPPED)
        next_day = await crud.find_next_free_day(session, workout.user_id, today)
        await crud.create_workout(
            session,
            user_id=workout.user_id,
            plan_day=workout.plan_day,
            scheduled_date=next_day,
            status=STATUS_SHIFTED,
        )
        return (
            f"Тренировка перенесена на {next_day.strftime('%d.%m')} "
            f"({DAY_NAMES_RU[next_day.weekday()]})."
        )
    else:  # skip
        await crud.update_workout_status(session, workout.id, STATUS_SKIPPED)
        return "Тренировка пропущена. Серия сбросилась. До следующей! 💪"


def workout_streak(workouts: list[Workout]) -> int:
    """Count consecutive done workouts going back from the most recent."""
    done = sorted(
        [w for w in workouts if w.status == STATUS_DONE],
        key=lambda w: w.actual_date or w.scheduled_date,
        reverse=True,
    )
    if not done:
        return 0
    streak = 1
    for i in range(1, len(done)):
        gap = (
            (done[i - 1].actual_date or done[i - 1].scheduled_date)
            - (done[i].actual_date or done[i].scheduled_date)
        ).days
        # Allow up to 7 days between workouts to maintain streak
        if gap <= 7:
            streak += 1
        else:
            break
    return streak
