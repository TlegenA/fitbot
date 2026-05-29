from typing import Final

# Plan days
PLAN_DAY_A: Final = "A"
PLAN_DAY_B: Final = "B"
PLAN_DAY_C: Final = "C"

# Locations
LOCATION_HOME: Final = "home"
LOCATION_STREET: Final = "street"

# Workout statuses
STATUS_PLANNED: Final = "planned"
STATUS_DONE: Final = "done"
STATUS_SKIPPED: Final = "skipped"
STATUS_SHIFTED: Final = "shifted"

# Skip behaviors
SKIP_SHIFT: Final = "shift"
SKIP_SKIP: Final = "skip"
SKIP_ASK: Final = "ask"

# Training days per week → schedule patterns
SCHEDULE_2_DAYS = [0, 3]           # Mon, Thu
SCHEDULE_3_DAYS = [0, 2, 4]        # Mon, Wed, Fri
SCHEDULE_4_DAYS = [0, 1, 3, 4]     # Mon, Tue, Thu, Fri

# Plan day rotation for each schedule
SCHEDULE_2_PLAN = ["A", "B"]
SCHEDULE_3_PLAN = ["A", "B", "C"]
SCHEDULE_4_PLAN = ["A", "B", "C", "D"]

# Home equipment options
HOME_EQUIPMENT_OPTIONS = [
    ("dumbbells", "Гантели"),
    ("kettlebell", "Гиря"),
    ("resistance_bands", "Резиновые ленты"),
    ("pull_up_bar", "Турник (дома)"),
    ("bench", "Скамья/лавка"),
]

# Street equipment options
STREET_EQUIPMENT_OPTIONS = [
    ("pull_up_bar", "Турник"),
    ("parallel_bars", "Брусья"),
    ("rings", "Кольца"),
    ("outdoor_chest_press", "Жим от груди (тренажёр)"),
    ("outdoor_lat_pulldown", "Тяга сверху (тренажёр)"),
]

# Day names in Russian
DAY_NAMES_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DAY_NAMES_FULL_RU = [
    "Понедельник", "Вторник", "Среда",
    "Четверг", "Пятница", "Суббота", "Воскресенье",
]

# Scheduler
WEEKLY_ANALYSIS_HOUR = 20
WEEKLY_ANALYSIS_MINUTE = 0
WEEKLY_ANALYSIS_DAY = "sun"

# Callback data prefixes
CB_DAYS = "days"
CB_HOME_EQUIP = "home_equip"
CB_STREET_EQUIP = "street_equip"
CB_HAS_BENCH = "has_bench"
CB_SKIP_PREF = "skip_pref"
CB_LOCATION = "location"
CB_SKIP_ACTION = "skip_action"
CB_CONFIRM = "confirm"
CB_DONE_CONFIRM = "done_confirm"
