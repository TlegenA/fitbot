from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def confirm_kb(confirm_cb: str, cancel_cb: str = "cancel") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да", callback_data=confirm_cb)
    builder.button(text="❌ Нет", callback_data=cancel_cb)
    builder.adjust(2)
    return builder.as_markup()


def back_kb(cb: str = "back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data=cb)]]
    )
