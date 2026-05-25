from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.db import crud
from bot.db.session import AsyncSessionLocal
from bot.keyboards.onboarding import (
    days_kb, home_equipment_kb, street_equipment_kb,
    has_bench_kb, skip_pref_kb,
)
from bot.services.workout_service import build_schedule
from bot.constants import (
    CB_DAYS, CB_HOME_EQUIP, CB_HAS_BENCH, CB_STREET_EQUIP, CB_SKIP_PREF,
)

router = Router()


class SettingsStates(StatesGroup):
    menu = State()
    edit_days = State()
    edit_home_equip = State()
    edit_has_bench = State()
    edit_street_equip = State()
    edit_skip_pref = State()
    edit_reminder = State()


def settings_menu_kb(reminder_enabled: bool = True) -> any:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Дней в неделю", callback_data="settings:days")
    builder.button(text="🏠 Оборудование дома", callback_data="settings:home_equip")
    builder.button(text="🌳 Оборудование на улице", callback_data="settings:street_equip")
    builder.button(text="⏭ При пропуске", callback_data="settings:skip_pref")
    reminder_icon = "🔔" if reminder_enabled else "🔕"
    builder.button(text=f"{reminder_icon} Напоминание", callback_data="settings:reminder")
    builder.button(text="❌ Закрыть", callback_data="settings:close")
    builder.adjust(1)
    return builder.as_markup()


def reminder_kb(current_hour: int, enabled: bool) -> any:
    builder = InlineKeyboardBuilder()
    toggle_text = "🔕 Выключить" if enabled else "🔔 Включить"
    builder.button(text=toggle_text, callback_data="reminder:toggle")
    if enabled:
        for h in (7, 8, 9, 10, 11, 12, 18, 19, 20):
            mark = "✅ " if h == current_hour else ""
            builder.button(text=f"{mark}{h:02d}:00", callback_data=f"reminder:hour:{h}")
        builder.adjust(1, 3, 3, 3)
    else:
        builder.adjust(1)
    return builder.as_markup()


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext) -> None:
    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, message.from_user.id)

    if not s or not s.onboarding_done:
        await message.answer("Сначала пройди настройку — /start.")
        return

    pref_text = {"shift": "Переносить", "skip": "Пропускать", "ask": "Спрашивать"}.get(s.skip_behavior, "?")
    reminder_text = f"{s.reminder_hour:02d}:00" if s.reminder_enabled else "выключено"
    text = (
        "⚙️ Настройки\n\n"
        f"📅 Тренировок в неделю: {s.days_per_week}\n"
        f"🏠 Оборудование дома: {', '.join(s.home_equipment) or 'нет'}\n"
        f"🪑 Скамья: {'есть' if s.has_bench else 'нет'}\n"
        f"🌳 Оборудование на улице: {', '.join(s.street_equipment) or 'нет'}\n"
        f"⏭ При пропуске: {pref_text}\n"
        f"🔔 Напоминание: {reminder_text}\n\n"
        "Что изменить?"
    )
    await message.answer(text, reply_markup=settings_menu_kb(s.reminder_enabled))
    await state.set_state(SettingsStates.menu)


@router.callback_query(F.data == "settings:close", SettingsStates.menu)
async def cb_settings_close(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Настройки закрыты.")
    await callback.answer()


@router.callback_query(F.data == "settings:days", SettingsStates.menu)
async def cb_edit_days(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text("Сколько дней в неделю тренироваться?", reply_markup=days_kb())
    await state.set_state(SettingsStates.edit_days)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_DAYS + ":"), SettingsStates.edit_days)
async def cb_save_days(callback: CallbackQuery, state: FSMContext) -> None:
    n = int(callback.data.split(":")[1])
    schedule = build_schedule(n)
    async with AsyncSessionLocal() as session:
        await crud.upsert_user_settings(session, callback.from_user.id, days_per_week=n)
        await crud.replace_schedule(session, callback.from_user.id, schedule)
        await session.commit()
    await callback.message.edit_text(f"Сохранено: {n} дня в неделю. Расписание обновлено.")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "settings:home_equip", SettingsStates.menu)
async def cb_edit_home_equip(callback: CallbackQuery, state: FSMContext) -> None:
    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, callback.from_user.id)
    selected = s.home_equipment or []
    await state.update_data(home_equipment=list(selected))
    await callback.message.edit_text(
        "Оборудование дома (выбери всё подходящее):",
        reply_markup=home_equipment_kb(selected),
    )
    await state.set_state(SettingsStates.edit_home_equip)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_HOME_EQUIP + ":"), SettingsStates.edit_home_equip)
async def cb_save_home_equip(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected: list = data.get("home_equipment", [])
    value = callback.data.split(":")[1]
    if value == "done":
        has_bench = "bench" in selected
        async with AsyncSessionLocal() as session:
            await crud.upsert_user_settings(
                session,
                callback.from_user.id,
                home_equipment=selected,
                has_bench=has_bench,
            )
            await session.commit()
        await callback.message.edit_text("Оборудование дома сохранено.")
        await state.clear()
    else:
        if value in selected:
            selected.remove(value)
        else:
            selected.append(value)
        await state.update_data(home_equipment=selected)
        await callback.message.edit_reply_markup(reply_markup=home_equipment_kb(selected))
    await callback.answer()


@router.callback_query(F.data == "settings:street_equip", SettingsStates.menu)
async def cb_edit_street_equip(callback: CallbackQuery, state: FSMContext) -> None:
    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, callback.from_user.id)
    selected = s.street_equipment or []
    await state.update_data(street_equipment=list(selected))
    await callback.message.edit_text(
        "Оборудование на улице:",
        reply_markup=street_equipment_kb(selected),
    )
    await state.set_state(SettingsStates.edit_street_equip)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_STREET_EQUIP + ":"), SettingsStates.edit_street_equip)
async def cb_save_street_equip(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected: list = data.get("street_equipment", [])
    value = callback.data.split(":")[1]
    if value == "done":
        async with AsyncSessionLocal() as session:
            await crud.upsert_user_settings(session, callback.from_user.id, street_equipment=selected)
            await session.commit()
        await callback.message.edit_text("Оборудование на улице сохранено.")
        await state.clear()
    else:
        if value in selected:
            selected.remove(value)
        else:
            selected.append(value)
        await state.update_data(street_equipment=selected)
        await callback.message.edit_reply_markup(reply_markup=street_equipment_kb(selected))
    await callback.answer()


@router.callback_query(F.data == "settings:skip_pref", SettingsStates.menu)
async def cb_edit_skip_pref(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_text("Что делать с пропущенными тренировками?", reply_markup=skip_pref_kb())
    await state.set_state(SettingsStates.edit_skip_pref)
    await callback.answer()


@router.callback_query(F.data.startswith(CB_SKIP_PREF + ":"), SettingsStates.edit_skip_pref)
async def cb_save_skip_pref(callback: CallbackQuery, state: FSMContext) -> None:
    pref = callback.data.split(":")[1]
    async with AsyncSessionLocal() as session:
        await crud.upsert_user_settings(session, callback.from_user.id, skip_behavior=pref)
        await session.commit()
    labels = {"shift": "Переносить", "skip": "Пропускать", "ask": "Спрашивать"}
    await callback.message.edit_text(f"Сохранено: {labels[pref]}.")
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "settings:reminder", SettingsStates.menu)
async def cb_edit_reminder(callback: CallbackQuery, state: FSMContext) -> None:
    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, callback.from_user.id)
    enabled = s.reminder_enabled
    hour = s.reminder_hour
    status = f"{hour:02d}:00" if enabled else "выключено"
    await callback.message.edit_text(
        f"🔔 Напоминание о тренировке\n\nТекущее: <b>{status}</b>\n\n"
        "Выбери время (МСК) или выключи:",
        reply_markup=reminder_kb(hour, enabled),
        parse_mode="HTML",
    )
    await state.set_state(SettingsStates.edit_reminder)
    await callback.answer()


@router.callback_query(F.data == "reminder:toggle", SettingsStates.edit_reminder)
async def cb_reminder_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    async with AsyncSessionLocal() as session:
        s = await crud.get_user_settings(session, callback.from_user.id)
        new_enabled = not s.reminder_enabled
        await crud.upsert_user_settings(session, callback.from_user.id, reminder_enabled=new_enabled)
        await session.commit()
        hour = s.reminder_hour

    status = f"{hour:02d}:00" if new_enabled else "выключено"
    await callback.message.edit_text(
        f"🔔 Напоминание о тренировке\n\nТекущее: <b>{status}</b>\n\n"
        "Выбери время (МСК) или выключи:",
        reply_markup=reminder_kb(hour, new_enabled),
        parse_mode="HTML",
    )
    await callback.answer("Включено ✅" if new_enabled else "Выключено 🔕")


@router.callback_query(F.data.startswith("reminder:hour:"), SettingsStates.edit_reminder)
async def cb_reminder_hour(callback: CallbackQuery, state: FSMContext) -> None:
    hour = int(callback.data.split(":")[2])
    async with AsyncSessionLocal() as session:
        await crud.upsert_user_settings(
            session, callback.from_user.id,
            reminder_enabled=True,
            reminder_hour=hour,
        )
        await session.commit()

    await callback.message.edit_text(
        f"✅ Напоминание сохранено: <b>{hour:02d}:00 МСК</b>\n\n"
        "В дни тренировок буду напоминать в это время.",
        parse_mode="HTML",
    )
    await state.clear()
    await callback.answer()
