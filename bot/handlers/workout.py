from datetime import date, datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.db import crud
from bot.db.session import AsyncSessionLocal
from bot.keyboards.workout import location_kb, skip_action_kb, finish_workout_kb
from bot.services import exercise_service
from bot.services.workout_service import ensure_planned_workout, handle_skip
from bot.constants import CB_LOCATION, CB_SKIP_ACTION, CB_DONE_CONFIRM, SKIP_ASK, STATUS_DONE

router = Router()


@router.message(Command("workout"))
async def cmd_workout(message: Message, state: FSMContext) -> None:
    today = date.today()
    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, message.from_user.id)
        if not s or not s.onboarding_done:
            await message.answer("Сначала пройди настройку — отправь /start.")
            return

        workout = await ensure_planned_workout(session, message.from_user.id, today)
        await session.commit()

    if not workout:
        await message.answer("Сегодня нет запланированной тренировки. 😴\nПосмотри /plan.")
        return

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
        await crud.update_workout_status(
            session, workout_id, "active",
            location=location,
            started_at=datetime.now(),
        )
        await session.commit()
        home_eq = s.home_equipment or []
        street_eq = s.street_equipment or []
        has_bench = s.has_bench

    exercises = exercise_service.get_exercises_for_workout(
        plan_day, location, home_eq, street_eq, has_bench
    )

    if not exercises:
        await callback.message.edit_text(
            "Нет подходящих упражнений для этой локации и оборудования. "
            "Проверь настройки /settings."
        )
        return

    await state.update_data(
        location=location,
        exercises=[e["key"] for e in exercises],
        current_ex_index=0,
        current_set=1,
    )

    lines = [f"Тренировка {plan_day} — {'дома 🏠' if location == 'home' else 'на улице 🌳'}\n"]
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
    from bot.keyboards.workout import set_logged_kb

    data = await state.get_data()
    if exercises is None:
        # reload from state
        ex_keys = data["exercises"]
        exercises = [exercise_service.get_exercise(k) for k in ex_keys]

    if ex_index >= len(exercises):
        # All exercises done
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
        prompt = f"⏱ {ex['name']}: подход {set_num}/{total_sets} — {ex['default_reps']} сек\nВведи фактическое время (сек):"
    else:
        prompt = f"💪 {ex['name']}: подход {set_num}/{total_sets} — цель {ex['default_reps']} повт.\nВведи количество повторений:"

    await state.update_data(current_ex_index=ex_index, current_set=set_num, current_ex_key=ex["key"])
    await message.answer(prompt)


@router.message(F.text.regexp(r"^\d+$"))
async def handle_set_result(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    if "workout_id" not in data or "current_ex_key" not in data:
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
        await message.answer(f"✅ Записано! Следующий подход...")
        await _prompt_next_set(message, state, exercises, ex_index, set_num + 1)
    else:
        next_index = ex_index + 1
        await message.answer(f"✅ {ex['name']} — завершено!")
        await _prompt_next_set(message, state, exercises, next_index, 1)


@router.callback_query(F.data.startswith(CB_DONE_CONFIRM + ":"))
async def cb_done_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    workout_id = int(callback.data.split(":")[1])

    async with AsyncSessionLocal() as session:
        await crud.update_workout_status(
            session,
            workout_id,
            STATUS_DONE,
            actual_date=date.today(),
            finished_at=datetime.now(),
        )
        await session.commit()

    await state.clear()
    await callback.message.edit_text(
        "Тренировка завершена! Отличная работа 💪\n\n"
        "Посмотри свою статистику: /stats"
    )
    await callback.answer()


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
        await callback.message.edit_text("Отлично! Давай тренироваться. Где тренируешься?",
                                         reply_markup=location_kb())
        await state.update_data(workout_id=workout_id)
        # need plan_day
        async with AsyncSessionLocal() as session:
            w = await crud.get_workout_by_id(session, workout_id)
        if w:
            await state.update_data(plan_day=w.plan_day, workout_id=w.id)
        await callback.answer()
        return

    async with AsyncSessionLocal() as session:
        w = await crud.get_workout_by_id(session, workout_id)
        result = await handle_skip(session, w, action, date.today())
        await session.commit()

    await state.clear()
    await callback.message.edit_text(result)
    await callback.answer()
