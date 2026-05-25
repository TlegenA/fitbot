from datetime import date, datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.db import crud
from bot.db.session import AsyncSessionLocal
from bot.db.models import Workout, UserSettings
from bot.keyboards.workout import (
    location_kb, skip_action_kb, finish_workout_kb, apply_adjustments_kb,
)
from bot.services import exercise_service
from bot.services.workout_service import ensure_planned_workout, handle_skip
from bot.services.analysis_service import analyze_workout_performance, format_analysis_message
from bot.constants import CB_LOCATION, CB_SKIP_ACTION, CB_DONE_CONFIRM, SKIP_ASK, STATUS_DONE

router = Router()


async def _rebuild_state(
    workout: Workout,
    s: UserSettings,
    user_targets: dict,
    state: FSMContext,
    logged_sets: list,
) -> tuple[list[dict], int, int]:
    """
    Reconstruct workout FSM state from logged sets in DB.
    Returns (exercises, ex_index, set_num_to_do_next).
    """
    exercises = exercise_service.get_exercises_for_workout(
        workout.plan_day,
        workout.location,
        s.home_equipment or [],
        s.street_equipment or [],
        s.has_bench,
        user_targets,
    )

    # Count completed sets per exercise
    sets_done: dict[str, int] = {}
    for row in logged_sets:
        sets_done[row.exercise_key] = sets_done.get(row.exercise_key, 0) + 1

    # Find first exercise with incomplete sets
    ex_index = len(exercises)  # default: all done
    set_num = 1
    for i, ex in enumerate(exercises):
        done = sets_done.get(ex["key"], 0)
        if done < ex["default_sets"]:
            ex_index = i
            set_num = done + 1
            break

    ex_key = exercises[ex_index]["key"] if ex_index < len(exercises) else None
    await state.update_data(
        workout_id=workout.id,
        plan_day=workout.plan_day,
        location=workout.location,
        exercises=[e["key"] for e in exercises],
        current_ex_index=ex_index,
        current_set=set_num,
        current_ex_key=ex_key,
    )
    return exercises, ex_index, set_num


@router.message(Command("workout"))
async def cmd_workout(message: Message, state: FSMContext) -> None:
    today = date.today()
    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, message.from_user.id)
        if not s or not s.onboarding_done:
            await message.answer("Сначала пройди настройку — отправь /start.")
            return

        workout = await ensure_planned_workout(session, message.from_user.id, today)
        user_targets = await crud.get_user_targets(session, message.from_user.id)

        logged_sets = []
        if workout:
            logged_sets = await crud.get_workout_sets(session, workout.id)

        await session.commit()

    if not workout:
        await message.answer("Сегодня нет запланированной тренировки. 😴\nПосмотри /plan.")
        return

    # Resume in-progress workout (has sets logged AND location chosen)
    if logged_sets and workout.location:
        exercises, ex_index, set_num = await _rebuild_state(
            workout, s, user_targets, state, logged_sets
        )
        if ex_index >= len(exercises):
            await message.answer(
                "Все упражнения уже выполнены! Нажми кнопку, чтобы завершить.",
                reply_markup=finish_workout_kb(workout.id),
            )
        else:
            ex = exercises[ex_index]
            await message.answer(
                f"▶️ Продолжаю тренировку {workout.plan_day} с места остановки.\n"
                f"Следующий: {ex['name']}, подход {set_num}/{ex['default_sets']}"
            )
            await _prompt_next_set(message, state, exercises, ex_index, set_num)
        return

    # Normal start: ask location
    await state.update_data(workout_id=workout.id, plan_day=workout.plan_day)
    await message.answer(
        f"Тренировка {workout.plan_day} — {today.strftime('%d.%m.%Y')} 💪\n\nГде тренируешься?",
        reply_markup=location_kb(),
    )


@router.callback_query(F.data.startswith(CB_LOCATION + ":"))
async def cb_location(callback: CallbackQuery, state: FSMContext) -> None:
    location = callback.data.split(":")[1]
    data = await state.get_data()
    workout_id = data.get("workout_id")
    plan_day = data.get("plan_day")

    if not workout_id:
        await callback.answer("Сначала запусти /workout", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, callback.from_user.id)
        user_targets = await crud.get_user_targets(session, callback.from_user.id)
        await crud.update_workout_status(
            session, workout_id, "planned",
            location=location,
            started_at=datetime.now(),
        )
        await session.commit()
        home_eq = s.home_equipment or []
        street_eq = s.street_equipment or []
        has_bench = s.has_bench

    exercises = exercise_service.get_exercises_for_workout(
        plan_day, location, home_eq, street_eq, has_bench, user_targets
    )

    if not exercises:
        await callback.message.edit_text(
            "Нет подходящих упражнений для этой локации и оборудования. "
            "Проверь настройки /settings."
        )
        await callback.answer()
        return

    await state.update_data(
        location=location,
        exercises=[e["key"] for e in exercises],
        current_ex_index=0,
        current_set=1,
    )

    lines = [f"Тренировка {plan_day} — {'дома 🏠' if location == 'home' else 'на улице 🌳'}\n"]

    if plan_day == "D":
        lines.append(
            "⚕️ Реабилитационная тренировка ног\n"
            "Все упражнения подобраны с учётом хондромаляции надколенника "
            "и синовита. Останавливайся при появлении боли или отёка.\n"
        )

    for ex in exercises:
        lines.append(exercise_service.format_exercise_line(ex))
    lines.append("\nНачнём! Введи результат первого подхода.")

    await callback.message.edit_text("\n".join(lines))
    await _prompt_next_set(callback.message, state, exercises, 0, 1)
    await callback.answer()


async def _prompt_next_set(
    message: Message,
    state: FSMContext,
    exercises: list[dict] | None,
    ex_index: int,
    set_num: int,
) -> None:
    data = await state.get_data()
    if exercises is None:
        ex_keys = data["exercises"]
        exercises = [exercise_service.get_exercise(k) for k in ex_keys]

    if ex_index >= len(exercises):
        workout_id = data["workout_id"]
        await message.answer(
            "Все упражнения выполнены! Нажми кнопку ниже, чтобы завершить тренировку. 🏁",
            reply_markup=finish_workout_kb(workout_id),
        )
        return

    ex = exercises[ex_index]
    total_sets = ex["default_sets"]
    unit = ex.get("unit", "reps")

    if unit == "time":
        prompt = (
            f"⏱ {ex['name']}: подход {set_num}/{total_sets} — цель {ex['default_reps']} сек\n"
            "Введи фактическое время (сек):"
        )
    else:
        prompt = (
            f"💪 {ex['name']}: подход {set_num}/{total_sets} — цель {ex['default_reps']} повт.\n"
            "Введи количество повторений:"
        )

    await state.update_data(current_ex_index=ex_index, current_set=set_num, current_ex_key=ex["key"])
    await message.answer(prompt)


@router.message(F.text.regexp(r"^\d+$"))
async def handle_set_result(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if "workout_id" not in data or "current_ex_key" not in data:
        await message.answer(
            "Сессия прервалась (перезапуск бота). Отправь /workout — "
            "продолжу с того места, где остановился. 🔄"
        )
        return

    value = int(message.text)
    ex_index = data["current_ex_index"]
    set_num = data["current_set"]
    workout_id = data["workout_id"]
    ex_key = data["current_ex_key"]

    ex_keys = data["exercises"]
    exercises = [exercise_service.get_exercise(k) for k in ex_keys]
    ex = exercises[ex_index]
    unit = ex.get("unit", "reps")

    async with AsyncSessionLocal() as session:
        await crud.log_set(
            session,
            workout_id=workout_id,
            exercise_key=ex_key,
            set_number=set_num,
            reps=value if unit == "reps" else None,
            duration_sec=value if unit == "time" else None,
        )
        await session.commit()

    total_sets = ex["default_sets"]
    if set_num < total_sets:
        await message.answer("✅ Записано! Следующий подход...")
        await _prompt_next_set(message, state, exercises, ex_index, set_num + 1)
    else:
        await message.answer(f"✅ {ex['name']} — завершено!")
        await _prompt_next_set(message, state, exercises, ex_index + 1, 1)


@router.callback_query(F.data.startswith(CB_DONE_CONFIRM + ":"))
async def cb_done_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    workout_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        await crud.update_workout_status(
            session, workout_id, STATUS_DONE,
            actual_date=date.today(),
            finished_at=datetime.now(),
        )
        sets = await crud.get_workout_sets(session, workout_id)
        user_targets = await crud.get_user_targets(session, callback.from_user.id)
        await session.commit()

    await state.clear()
    await callback.message.edit_text("Тренировка завершена! Отличная работа 💪")
    await callback.answer()

    if not sets:
        return

    results = analyze_workout_performance(sets, user_targets)
    has_changes = any(r["direction"] != "same" for r in results)
    analysis_text = format_analysis_message(results)

    if has_changes:
        await callback.message.answer(
            analysis_text,
            reply_markup=apply_adjustments_kb(workout_id),
            parse_mode="HTML",
        )
    else:
        await callback.message.answer(analysis_text, parse_mode="HTML")


@router.callback_query(F.data.startswith("apply_targets:"))
async def cb_apply_targets(callback: CallbackQuery) -> None:
    # Dismiss spinner immediately — do this first so user always gets feedback
    await callback.answer()

    parts = callback.data.split(":")
    workout_id = int(parts[1])
    apply = parts[2] == "yes"

    # Remove keyboard from analysis message regardless of choice
    await callback.message.edit_reply_markup(reply_markup=None)

    if not apply:
        await callback.message.answer(
            "Понял, цели оставлены без изменений.\n"
            "До следующей тренировки! 👋"
        )
        return

    async with AsyncSessionLocal() as session:
        sets = await crud.get_workout_sets(session, workout_id)
        user_targets = await crud.get_user_targets(session, callback.from_user.id)
        results = analyze_workout_performance(sets, user_targets)

        saved = 0
        changes: list[str] = []
        for r in results:
            if r["direction"] == "same":
                continue
            unit_label = "сек" if r["unit"] == "time" else "повт"
            arrow = "📉" if r["direction"] == "down" else "📈"
            changes.append(
                f"{arrow} {r['name']}: {r['target']} → <b>{r['suggested']} {unit_label}</b>"
            )
            if r["unit"] == "time":
                await crud.upsert_exercise_target(
                    session, callback.from_user.id, r["exercise_key"],
                    target_sets=r["current_sets"],
                    target_duration_sec=r["suggested"],
                )
            else:
                await crud.upsert_exercise_target(
                    session, callback.from_user.id, r["exercise_key"],
                    target_sets=r["current_sets"],
                    target_reps=r["suggested"],
                )
            saved += 1

        # Find next workout date
        next_workout = await _get_next_workout_info(session, callback.from_user.id)
        await session.commit()

    changes_text = "\n".join(changes) if changes else "—"
    next_text = f"\n\n📅 Следующая тренировка: {next_workout}" if next_workout else ""

    await callback.message.answer(
        f"✅ <b>Цели обновлены!</b> Сохранено изменений: {saved}\n\n"
        f"{changes_text}"
        f"{next_text}\n\n"
        "Продолжай в том же духе! 💪",
        parse_mode="HTML",
    )


async def _get_next_workout_info(session, user_id: int) -> str | None:
    """Return human-readable next workout date and plan_day, or None."""
    from datetime import timedelta
    from bot.constants import DAY_NAMES_FULL_RU

    today = date.today()
    schedule = await crud.get_schedule(session, user_id)
    if not schedule:
        return None

    scheduled_dow = {e.day_of_week: e.plan_day for e in schedule}
    for i in range(1, 8):
        d = today + timedelta(days=i)
        if d.weekday() in scheduled_dow:
            plan = scheduled_dow[d.weekday()]
            day_name = DAY_NAMES_FULL_RU[d.weekday()]
            return f"{day_name}, {d.strftime('%d.%m')} — тренировка {plan}"
    return None


@router.message(Command("skip"))
async def cmd_skip(message: Message, state: FSMContext) -> None:
    today = date.today()
    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, message.from_user.id)
        if not s or not s.onboarding_done:
            await message.answer("Сначала пройди настройку — /start.")
            return

        workout = await crud.get_today_workout(session, message.from_user.id, today)
        if not workout:
            await message.answer("Сегодня нет запланированной тренировки.")
            return

        if s.skip_behavior == SKIP_ASK:
            await state.update_data(workout_id=workout.id)
            await message.answer(
                "Как поступить с сегодняшней тренировкой?",
                reply_markup=skip_action_kb(),
            )
            return

        result = await handle_skip(session, workout, s.skip_behavior, today)
        await session.commit()

    await message.answer(result)


@router.callback_query(F.data.startswith(CB_SKIP_ACTION + ":"))
async def cb_skip_action(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":")[1]
    data = await state.get_data()
    workout_id = data.get("workout_id")

    if action == "now":
        await state.clear()
        async with AsyncSessionLocal() as session:
            w = await crud.get_workout_by_id(session, workout_id)
        if w:
            await state.update_data(plan_day=w.plan_day, workout_id=w.id)
        await callback.message.edit_text(
            "Отлично! Давай тренироваться. Где тренируешься?",
            reply_markup=location_kb(),
        )
        await callback.answer()
        return

    async with AsyncSessionLocal() as session:
        w = await crud.get_workout_by_id(session, workout_id)
        result = await handle_skip(session, w, action, date.today())
        await session.commit()

    await state.clear()
    await callback.message.edit_text(result)
    await callback.answer()
