from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "🤖 FitBot — твой персональный тренер\n\n"
        "Команды:\n"
        "/start — начало работы / регистрация\n"
        "/workout — начать тренировку сегодня\n"
        "/skip — пропустить сегодняшнюю тренировку\n"
        "/plan — план на текущую неделю\n"
        "/stats — статистика тренировок\n"
        "/settings — изменить настройки\n"
        "/help — эта справка\n\n"
        "Тренировки:\n"
        "• A — грудь, плечи, трицепс (толкающие)\n"
        "• B — спина, бицепс (тянущие)\n"
        "• C — ноги, кор\n\n"
        "Каждое воскресенье в 20:00 ты получишь анализ недели от AI-тренера 🧠"
    )
