import json
import logging
from datetime import date, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from sqlalchemy import select

from bot.db.session import AsyncSessionLocal
from bot.db.models import User, UserSettings, Workout
from bot.db import crud
from bot.services.claude_service import get_weekly_analysis
from bot.constants import (
    WEEKLY_ANALYSIS_HOUR, WEEKLY_ANALYSIS_MINUTE, WEEKLY_ANALYSIS_DAY,
    DAY_NAMES_FULL_RU,
)

logger = logging.getLogger(__name__)


async def send_workout_reminders(bot: Bot, current_hour: int, today: date) -> None:
    """Send training-day reminders to users whose reminder_hour matches current_hour."""
    dow = today.weekday()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).join(UserSettings).where(
                UserSettings.onboarding_done == True,
                UserSettings.reminder_enabled == True,
                UserSettings.reminder_hour == current_hour,
                User.is_active == True,
            )
        )
        users = list(result.scalars())

    for user in users:
        try:
            async with AsyncSessionLocal() as session:
                schedule = await crud.get_schedule(session, user.id)
                plan_day = next(
                    (e.plan_day for e in schedule if e.day_of_week == dow), None
                )
                if not plan_day:
                    continue

                # Don't remind if workout already done or skipped today
                result = await session.execute(
                    select(Workout).where(
                        Workout.user_id == user.id,
                        Workout.scheduled_date == today,
                        Workout.status.in_(("done", "skipped")),
                    )
                )
                if result.scalar_one_or_none():
                    continue

            day_name = DAY_NAMES_FULL_RU[dow]
            plan_labels = {
                "A": "A — грудь, плечи, трицепс 💪",
                "B": "B — спина, бицепс 🏋️",
                "C": "C — руки и кор 💪",
                "D": "D — реабилитация ног 🦵",
            }
            plan_text = plan_labels.get(plan_day, f"тренировка {plan_day}")

            await bot.send_message(
                user.id,
                f"⏰ Привет! Сегодня {day_name} — день тренировки.\n\n"
                f"📋 {plan_text}\n\n"
                "Отправь /workout чтобы начать. Удачи! 💪",
            )
        except Exception as e:
            logger.error(f"Reminder error for user {user.id}: {e}")


async def send_weekly_analysis(bot: Bot) -> None:
    """Send AI weekly analysis to all active users with completed workouts."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 1)  # last Monday

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).join(UserSettings).where(
                UserSettings.onboarding_done == True,
                User.is_active == True,
            )
        )
        users = list(result.scalars())

    for user in users:
        try:
            async with AsyncSessionLocal() as session:
                s = await crud.get_user_settings(session, user.id)
                workouts = await crud.get_week_workouts(session, user.id, week_start)

            if not workouts:
                continue

            done = [w for w in workouts if w.status == "done"]
            skipped = [w for w in workouts if w.status == "skipped"]

            ex_stats: dict[str, dict] = {}
            for w in done:
                for ex_set in (w.sets or []):
                    if ex_set.exercise_key not in ex_stats:
                        ex_stats[ex_set.exercise_key] = {"sets": 0, "reps": 0}
                    ex_stats[ex_set.exercise_key]["sets"] += 1
                    ex_stats[ex_set.exercise_key]["reps"] += ex_set.reps or 0

            week_data = {
                "home_equipment": s.home_equipment or [],
                "street_equipment": s.street_equipment or [],
                "planned": len(workouts),
                "done": len(done),
                "skipped": len(skipped),
                "exercises_json": json.dumps(ex_stats, ensure_ascii=False),
            }

            analysis = await get_weekly_analysis(user.id, week_data)
            await bot.send_message(
                user.id,
                f"📊 Анализ недели от AI-тренера:\n\n{analysis}",
            )
        except Exception as e:
            logger.error(f"Weekly analysis error for user {user.id}: {e}")


async def _reminder_dispatcher(bot: Bot) -> None:
    """Called every hour — passes the current Astana hour and date to the reminder sender."""
    from datetime import datetime
    import zoneinfo
    now_almaty = datetime.now(tz=zoneinfo.ZoneInfo("Asia/Almaty"))
    await send_workout_reminders(bot, now_almaty.hour, now_almaty.date())


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Almaty")

    # Weekly AI analysis — Sunday at 20:00 Moscow
    scheduler.add_job(
        send_weekly_analysis,
        trigger="cron",
        day_of_week=WEEKLY_ANALYSIS_DAY,
        hour=WEEKLY_ANALYSIS_HOUR,
        minute=WEEKLY_ANALYSIS_MINUTE,
        kwargs={"bot": bot},
    )

    # Daily workout reminders — run every hour, filter by user's reminder_hour
    scheduler.add_job(
        _reminder_dispatcher,
        trigger="cron",
        minute=0,
        kwargs={"bot": bot},
        misfire_grace_time=3600,  # fire even if bot restarted up to 1h late
    )

    return scheduler
