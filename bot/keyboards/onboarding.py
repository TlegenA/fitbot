from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constants import (
    CB_DAYS, CB_HOME_EQUIP, CB_STREET_EQUIP, CB_HAS_BENCH,
    CB_SKIP_PREF, CB_CONFIRM,
    HOME_EQUIPMENT_OPTIONS, STREET_EQUIPMENT_OPTIONS,
)


def days_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in (2, 3, 4):
        builder.button(text=f"{n} дня" if n == 3 else f"{n} дня" if n == 4 else f"{n} дня",
                       callback_data=f"{CB_DAYS}:{n}")
    builder.adjust(3)
    return builder.as_markup()


def equipment_kb(selected: list[str], prefix: str, options: list[tuple]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in options:
        mark = "✅ " if key in selected else ""
        builder.button(text=f"{mark}{label}", callback_data=f"{prefix}:{key}")
    builder.button(text="➡️ Далее", callback_data=f"{prefix}:done")
    builder.adjust(1)
    return builder.as_markup()


def home_equipment_kb(selected: list[str]) -> InlineKeyboardMarkup:
    return equipment_kb(selected, CB_HOME_EQUIP, HOME_EQUIPMENT_OPTIONS)


def street_equipment_kb(selected: list[str]) -> InlineKeyboardMarkup:
    return equipment_kb(selected, CB_STREET_EQUIP, STREET_EQUIPMENT_OPTIONS)


def has_bench_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=f"{CB_HAS_BENCH}:yes")
    builder.button(text="❌ Нет", callback_data=f"{CB_HAS_BENCH}:no")
    builder.adjust(2)
    return builder.as_markup()


def skip_pref_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Сдвинуть", callback_data=f"{CB_SKIP_PREF}:shift")
    builder.button(text="🗑 Пропустить", callback_data=f"{CB_SKIP_PREF}:skip")
    builder.button(text="❓ Спрашивать", callback_data=f"{CB_SKIP_PREF}:ask")
    builder.adjust(1)
    return builder.as_markup()


def confirm_schedule_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data=f"{CB_CONFIRM}:yes")
    builder.button(text="🔄 Изменить", callback_data=f"{CB_CONFIRM}:restart")
    builder.adjust(2)
    return builder.as_markup()
