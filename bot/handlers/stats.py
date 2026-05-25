from datetime import date, timedelta
from collections import Counter

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.db import crud
from bot.db.session import AsyncSessionLocal
from bot.services.workout_service import workout_streak
from bot.services import exercise_service
from bot.constants import STATUS_DONE, STATUS_SKIPPED, DAY_NAMES_RU

router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, message.from_user.id)
        if not s or not s.onboarding_done:
            await message.answer("Сначала пройди настройку — /start.")
            return

        workouts = await crud.get_all_workouts(session, message.from_user.id)

    if not workouts:
        await message.answer("Пока нет данных о тренировках. Начни первую: /workout")
        return

    done = [w for w in workouts if w.status == STATUS_DONE]
    skipped = [w for w in workouts if w.status == STATUS_SKIPPED]
    streak = workout_streak(workouts)

    # Exercise volume
    ex_counter: Counter = Counter()
    reps_counter: Counter = Counter()
    for w in done:
        for s_row in (w.sets or []):
            ex_counter[s_row.exercise_key] += 1
            if s_row.reps:
                reps_counter[s_row.exercise_key] += s_row.reps

    top_exercises = ex_counter.most_common(3)
    top_lines = []
    for key, sets_count in top_exercises:
        ex = exercise_service.get_exercise(key)
        name = ex["name"] if ex else key
        total_reps = reps_counter.get(key, 0)
        top_lines.append(f"  • {name}: {sets_count} подх., {total_reps} повт.")

    text = (
        f"📊 Статистика\n\n"
        f"✅ Выполнено тренировок: {len(done)}\n"
        f"🗓 Всего запланировано: {len(workouts)}\n"
        f"❌ Пропущено: {len(skipped)}\n"
        f"🔥 Текущая серия: {streak} тренировок\n"
    )
    if top_lines:
        text += "\n🏆 Топ упражнений:\n" + "\n".join(top_lines)

    await message.answer(text)


@router.message(Command("plan"))
async def cmd_plan(message: Message) -> None:
    today = date.today()
    # Show next 7 days
    week_start = today - timedelta(days=today.weekday())  # Monday of current week
    week_end = week_start + timedelta(days=6)

    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, message.from_user.id)
        if not s or not s.onboarding_done:
            await message.answer("Сначала пройди настройку — /start.")
            return
        schedule = await crud.get_schedule(session, message.from_user.id)
        week_workouts = await crud.get_week_workouts(session, message.from_user.id, week_start)

    scheduled_by_dow = {e.day_of_week: e.plan_day for e in schedule}
    workouts_by_date = {w.scheduled_date: w for w in week_workouts}

    lines = [f"📅 План на неделю ({week_start.strftime('%d.%m')} — {week_end.strftime('%d.%m')})\n"]
    for i in range(7):
        d = week_start + timedelta(days=i)
        dow = d.weekday()
        day_name = DAY_NAMES_RU[dow]
        marker = "👉 " if d == today else "   "

        if dow in scheduled_by_dow:
            plan_day = scheduled_by_dow[dow]
            w = workouts_by_date.get(d)
            if w:
                status_icon = {"done": "✅", "skipped": "❌", "shifted": "📅", "planned": "💪", "active": "🔄"}.get(w.status, "💪")
                lines.append(f"{marker}{day_name} {d.strftime('%d.%m')} — {status_icon} Тренировка {plan_day}")
            else:
                lines.append(f"{marker}{day_name} {d.strftime('%d.%m')} — 💪 Тренировка {plan_day}")
        else:
            lines.append(f"{marker}{day_name} {d.strftime('%d.%m')} — 😴 Отдых")

    await message.answer("\n".join(lines))
