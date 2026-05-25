from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import crud
from bot.db.session import AsyncSessionLocal
from bot.keyboards.onboarding import (
    days_kb, home_equipment_kb, has_bench_kb,
    street_equipment_kb, skip_pref_kb, confirm_schedule_kb,
)
from bot.services.workout_service import build_schedule, schedule_summary
from bot.constants import CB_DAYS, CB_HOME_EQUIP, CB_HAS_BENCH, CB_STREET_EQUIP, CB_SKIP_PREF, CB_CONFIRM

router = Router()


class OnboardingStates(StatesGroup):
    days = State()
    home_equip = State()
    has_bench = State()
    street_equip = State()
    skip_pref = State()
    confirm = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    async with AsyncSessionLocal() as session:
        user, created = await crud.get_or_create_user(
            session,
            user_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name or "Атлет",
        )
        settings_row = await crud.get_user_settings(session, message.from_user.id)
        await session.commit()

    if settings_row and settings_row.onboarding_done:
        await message.answer(
            f"С возвращением, {user.first_name}! 💪\n"
            "Используй /workout чтобы начать тренировку или /help для списка команд."
        )
        return

    await message.answer(
        f"Привет, {user.first_name}! 👋\n\n"
        "Я FitBot — твой персональный тренер для домашних и уличных тренировок.\n\n"
        "Давай настроим твой план. Сколько дней в неделю ты готов тренироваться?"
        , reply_markup=days_kb()
    )
    await state.set_state(OnboardingStates.days)


@router.callback_query(F.data.startswith(CB_DAYS + ":"), OnboardingStates.days)
async def cb_days(callback: CallbackQuery, state: FSMContext) -> None:
    n = int(callback.data.split(":")[1])
    await state.update_data(days_per_week=n)
    await callback.message.edit_text(
        f"Отлично, {n} дня в неделю! 💪\n\n"
        "Какое оборудование есть у тебя дома? (выбери всё подходящее)",
        reply_markup=home_equipment_kb([]),
    )
    await state.set_state(OnboardingStates.home_equip)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_HOME_EQUIP + ":"), OnboardingStates.home_equip)
async def cb_home_equip(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected: list = data.get("home_equipment", [])
    value = callback.data.split(":")[1]

    if value == "done":
        await state.update_data(home_equipment=selected)
        has_bench = "bench" in selected
        if has_bench:
            # Skip the has_bench question — already answered
            await state.update_data(has_bench=True)
            await _ask_street_equip(callback, state)
        else:
            await callback.message.edit_text(
                "Есть ли у тебя скамья или лавка для жима?",
                reply_markup=has_bench_kb(),
            )
            await state.set_state(OnboardingStates.has_bench)
    else:
        if value in selected:
            selected.remove(value)
        else:
            selected.append(value)
        await state.update_data(home_equipment=selected)
        await callback.message.edit_reply_markup(reply_markup=home_equipment_kb(selected))

    await callback.answer()


@router.callback_query(F.data.startswith(CB_HAS_BENCH + ":"), OnboardingStates.has_bench)
async def cb_has_bench(callback: CallbackQuery, state: FSMContext) -> None:
    has_bench = callback.data.split(":")[1] == "yes"
    await state.update_data(has_bench=has_bench)
    await _ask_street_equip(callback, state)
    await callback.answer()


async def _ask_street_equip(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text(
        "Какое оборудование есть на твоей уличной площадке? (выбери всё подходящее)",
        reply_markup=street_equipment_kb([]),
    )
    await state.set_state(OnboardingStates.street_equip)


@router.callback_query(F.data.startswith(CB_STREET_EQUIP + ":"), OnboardingStates.street_equip)
async def cb_street_equip(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected: list = data.get("street_equipment", [])
    value = callback.data.split(":")[1]

    if value == "done":
        await state.update_data(street_equipment=selected)
        await callback.message.edit_text(
            "Как поступать с пропущенными тренировками?",
            reply_markup=skip_pref_kb(),
        )
        await state.set_state(OnboardingStates.skip_pref)
    else:
        if value in selected:
            selected.remove(value)
        else:
            selected.append(value)
        await state.update_data(street_equipment=selected)
        await callback.message.edit_reply_markup(reply_markup=street_equipment_kb(selected))

    await callback.answer()


@router.callback_query(F.data.startswith(CB_SKIP_PREF + ":"), OnboardingStates.skip_pref)
async def cb_skip_pref(callback: CallbackQuery, state: FSMContext) -> None:
    pref = callback.data.split(":")[1]
    await state.update_data(skip_behavior=pref)
    data = await state.get_data()

    schedule = build_schedule(data["days_per_week"])
    summary = schedule_summary(schedule)

    pref_text = {"shift": "Переносить на свободный день", "skip": "Пропускать", "ask": "Спрашивать"}[pref]

    await callback.message.edit_text(
        f"Почти готово! Проверь настройки:\n\n"
        f"📅 Тренировок в неделю: {data['days_per_week']}\n"
        f"🏠 Оборудование дома: {', '.join(data.get('home_equipment', [])) or 'нет'}\n"
        f"🪑 Скамья: {'есть' if data.get('has_bench') else 'нет'}\n"
        f"🌳 Оборудование на улице: {', '.join(data.get('street_equipment', [])) or 'нет'}\n"
        f"⏭ При пропуске: {pref_text}\n\n"
        f"Расписание:\n{summary}\n\n"
        "Всё верно?",
        reply_markup=confirm_schedule_kb(),
    )
    await state.set_state(OnboardingStates.confirm)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_CONFIRM + ":"), OnboardingStates.confirm)
async def cb_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":")[1]
    if action == "restart":
        await callback.message.edit_text(
            "Хорошо, начнём сначала. Сколько дней в неделю?",
            reply_markup=days_kb(),
        )
        await state.set_state(OnboardingStates.days)
        await callback.answer()
        return

    data = await state.get_data()
    schedule = build_schedule(data["days_per_week"])

    async with AsyncSessionLocal() as session:
        await crud.upsert_user_settings(
            session,
            user_id=callback.from_user.id,
            days_per_week=data["days_per_week"],
            home_equipment=data.get("home_equipment", []),
            street_equipment=data.get("street_equipment", []),
            has_bench=data.get("has_bench", False),
            skip_behavior=data["skip_behavior"],
            onboarding_done=True,
        )
        await crud.replace_schedule(session, callback.from_user.id, schedule)
        await session.commit()

    await state.clear()
    await callback.message.edit_text(
        "Отлично! Всё настроено. 🎉\n\n"
        "Используй /workout чтобы начать сегодняшнюю тренировку.\n"
        "/plan — посмотреть план на неделю.\n"
        "/help — все команды."
    )
    await callback.answer()
