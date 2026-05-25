import anthropic
from bot.config import settings

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def get_weekly_analysis(user_id: int, week_data: dict) -> str:
    prompt = f"""Ты персональный тренер. Проанализируй тренировочную неделю пользователя.

Профиль: мужчина 42 года, тренируется дома и на уличных снарядах.
Оборудование дома: {week_data['home_equipment']}
Оборудование на улице: {week_data['street_equipment']}

Итоги за неделю:
- Запланировано тренировок: {week_data['planned']}
- Выполнено: {week_data['done']}
- Пропущено: {week_data['skipped']}

Статистика по упражнениям:
{week_data['exercises_json']}

Дай короткие рекомендации:
1. Какое упражнение стоит усложнить (увеличить повторения / вес)
2. Что добавить — не более 1 нового
3. Если нужно — упражнение на следующую неделю

Ответ должен быть коротким (3-5 предложений), дружеским, мотивирующим."""

    client = get_client()
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=settings.claude_max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


async def get_program_tip(
    plan_day: str,
    exercises: list[dict],
    home_equipment: list[str],
    street_equipment: list[str],
) -> str:
    ex_names = ", ".join(e["name"] for e in exercises)
    prompt = f"""Ты персональный тренер. Пользователь сейчас делает тренировку {plan_day}.
Упражнения: {ex_names}.
Оборудование дома: {home_equipment or 'без оборудования'}.
Оборудование на улице: {street_equipment or 'без оборудования'}.

Дай 1-2 коротких совета по технике или мотивации для этой тренировки (1-2 предложения)."""

    client = get_client()
    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
