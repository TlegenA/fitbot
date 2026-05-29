from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constants import CB_LOCATION, CB_SKIP_ACTION, CB_DONE_CONFIRM, CB_CONFIRM, STREET_EQUIPMENT_OPTIONS


def location_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Дома", callback_data=f"{CB_LOCATION}:home")
    builder.button(text="🌳 На улице", callback_data=f"{CB_LOCATION}:street")
    builder.adjust(2)
    return builder.as_markup()


def skip_action_kb() -> InlineKeyboardMarkup:
    """Shown when skip_behavior = 'ask'."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Перенести", callback_data=f"{CB_SKIP_ACTION}:shift")
    builder.button(text="🗑 Пропустить", callback_data=f"{CB_SKIP_ACTION}:skip")
    builder.button(text="💪 Сделать сейчас", callback_data=f"{CB_SKIP_ACTION}:now")
    builder.adjust(1)
    return builder.as_markup()


def set_logged_kb(exercise_key: str, set_num: int, total_sets: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if set_num < total_sets:
        builder.button(
            text=f"➡️ Следующий подход ({set_num + 1}/{total_sets})",
            callback_data=f"next_set:{exercise_key}:{set_num + 1}",
        )
    builder.button(text="✅ Завершить упражнение", callback_data=f"done_exercise:{exercise_key}")
    builder.adjust(1)
    return builder.as_markup()


def apply_adjustments_kb(workout_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Применить", callback_data=f"apply_targets:{workout_id}:yes")
    builder.button(text="⏭ Пропустить", callback_data=f"apply_targets:{workout_id}:no")
    builder.adjust(2)
    return builder.as_markup()


def street_equipment_today_kb(selected: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, label in STREET_EQUIPMENT_OPTIONS:
        mark = "✅ " if key in selected else "☐ "
        builder.button(text=f"{mark}{label}", callback_data=f"street_eq_today:{key}")
    builder.button(text="▶️ Начать тренировку", callback_data="street_eq_today:done")
    builder.adjust(1)
    return builder.as_markup()


def finish_early_kb(workout_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏁 Завершить как есть", callback_data=f"finish_early:{workout_id}")
    builder.adjust(1)
    return builder.as_markup()


def unfinished_workout_kb(workout_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="▶️ Продолжить", callback_data=f"unfinished:{workout_id}:resume")
    builder.button(text="✅ Засчитать выполненной", callback_data=f"unfinished:{workout_id}:done")
    builder.button(text="🗑 Пропустить", callback_data=f"unfinished:{workout_id}:skip")
    builder.adjust(1)
    return builder.as_markup()


def finish_workout_kb(workout_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏁 Завершить тренировку", callback_data=f"{CB_DONE_CONFIRM}:{workout_id}")
    builder.adjust(1)
    return builder.as_markup()
