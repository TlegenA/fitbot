from collections import defaultdict
from typing import Optional

from bot.services.exercise_service import _load as load_catalog


def analyze_workout_performance(
    sets_data: list,
    user_targets: dict,
) -> list[dict]:
    """
    Compare actual reps/time vs targets for each exercise.

    Returns list of adjustment dicts:
    {
        exercise_key, name, unit,
        reps_per_set: [int, ...],
        avg: float,
        target: int,
        suggested: int,
        direction: 'down' | 'up' | 'same',
    }
    """
    catalog = load_catalog()
    by_exercise: dict[str, list[int]] = defaultdict(list)

    for s in sets_data:
        value = s.reps if s.reps is not None else s.duration_sec
        if value is not None:
            by_exercise[s.exercise_key].append(value)

    results = []
    for ex_key, values in by_exercise.items():
        if not values:
            continue

        ex_data = catalog.get(ex_key, {})
        unit = ex_data.get("unit", "reps")

        # Current target: personalized or JSON default
        if ex_key in user_targets:
            t = user_targets[ex_key]
            target = (t.target_reps if unit == "reps" else t.target_duration_sec) or ex_data.get("default_reps", 10)
            current_sets = t.target_sets
        else:
            target = ex_data.get("default_reps", 10)
            current_sets = ex_data.get("default_sets", 3)

        avg = sum(values) / len(values)
        min_val = min(values)

        # Adjustment logic
        if avg < target * 0.75:
            # Significantly under — reduce to just above actual avg
            suggested = max(1, round(avg) + 1)
            direction = "down"
        elif min_val >= target and len(values) >= 2:
            # Every set hit or exceeded target — ready to progress
            suggested = target + 2
            direction = "up"
        else:
            suggested = target
            direction = "same"

        results.append({
            "exercise_key": ex_key,
            "name": ex_data.get("name", ex_key),
            "unit": unit,
            "reps_per_set": values,
            "avg": round(avg, 1),
            "target": target,
            "suggested": suggested,
            "current_sets": current_sets,
            "direction": direction,
        })

    return results


def format_analysis_message(results: list[dict]) -> str:
    lines = ["📊 Анализ тренировки:\n"]
    has_changes = False

    for r in results:
        unit_label = "сек" if r["unit"] == "time" else "повт"
        sets_str = " / ".join(str(v) for v in r["reps_per_set"])
        lines.append(f"<b>{r['name']}</b>")
        lines.append(f"  Факт: {sets_str} {unit_label}  |  Цель была: {r['target']} {unit_label}")

        if r["direction"] == "down":
            lines.append(
                f"  📉 Рекомендую снизить до <b>{r['suggested']} {unit_label}</b> "
                f"— так ты будешь работать в правильном диапазоне"
            )
            has_changes = True
        elif r["direction"] == "up":
            lines.append(
                f"  📈 Готов к прогрессу! Повышаю до <b>{r['suggested']} {unit_label}</b>"
            )
            has_changes = True
        else:
            lines.append(f"  ✅ Цель актуальна ({r['target']} {unit_label})")
        lines.append("")

    if has_changes:
        lines.append("Применить скорректированные цели?")
    else:
        lines.append("Все цели актуальны — отличная работа! 💪")

    return "\n".join(lines)
