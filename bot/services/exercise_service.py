import json
from pathlib import Path
from typing import Optional

_EXERCISES_PATH = Path(__file__).parent.parent.parent / "data" / "exercises.json"
_exercises: dict = {}


def _load() -> dict:
    global _exercises
    if not _exercises:
        with open(_EXERCISES_PATH, encoding="utf-8") as f:
            _exercises = json.load(f)
    return _exercises


def get_exercises_for_workout(
    plan_day: str,
    location: str,
    home_equipment: list[str],
    street_equipment: list[str],
    has_bench: bool,
    user_targets: dict | None = None,
) -> list[dict]:
    """Return exercises suitable for the given plan day, location and user equipment."""
    catalog = _load()
    available_equipment = set(
        home_equipment if location == "home" else street_equipment
    )

    result = []
    for key, ex in catalog.items():
        if plan_day not in ex["plan_days"]:
            continue
        if location not in ex["locations"]:
            continue

        required = set(ex.get("required_equipment", []))

        # bench substitution: if exercise needs bench but user has no bench,
        # skip it (the floor_press variant will be included instead)
        if "bench" in required and not has_bench:
            continue

        # if exercise is a replacement for bench-press but user has bench, skip floor variant
        if ex.get("replaces_if_no_bench") and has_bench:
            continue

        # check all required equipment is available
        if not required.issubset(available_equipment | {"bench"} if has_bench else available_equipment):
            continue

        entry = {"key": key, **ex}
        # Apply personalized targets if available
        if user_targets and key in user_targets:
            t = user_targets[key]
            entry["default_sets"] = t.target_sets
            if t.target_reps is not None:
                entry["default_reps"] = t.target_reps
            if t.target_duration_sec is not None:
                entry["default_reps"] = t.target_duration_sec
        result.append(entry)

    return result


def get_exercise(key: str) -> Optional[dict]:
    catalog = _load()
    ex = catalog.get(key)
    if ex:
        return {"key": key, **ex}
    return None


def format_exercise_line(ex: dict) -> str:
    unit = ex.get("unit", "reps")
    sets = ex["default_sets"]
    if unit == "time":
        line = f"• {ex['name']} — {sets}×{ex['default_reps']} сек"
    else:
        line = f"• {ex['name']} — {sets}×{ex['default_reps']}"
    if ex.get("note"):
        line += f"\n  ℹ️ {ex['note']}"
    return line
