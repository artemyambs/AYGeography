from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIGS_DIR = BASE_DIR / "configs"
ASSETS_DIR = BASE_DIR / "assets"
SAVE_DIR = BASE_DIR / "save"
DATABASE_PATH = SAVE_DIR / "aygeography.db"


def _load_app_settings() -> dict[str, Any]:
    path = CONFIGS_DIR / "app_settings.json"
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Не удалось загрузить настройки: {path}") from error
    if not isinstance(settings, dict):
        raise ValueError("app_settings.json должен содержать JSON-объект")
    return settings


APP_SETTINGS = _load_app_settings()

APP_NAME = str(APP_SETTINGS["app"]["name"])
APP_VERSION = str(APP_SETTINGS["app"]["version"])

QUESTION_TIME_SECONDS = int(
    APP_SETTINGS["gameplay"]["question_time_seconds"]
)
CORRECT_ANSWER_FEEDBACK_SECONDS = float(
    APP_SETTINGS["gameplay"]["correct_answer_feedback_seconds"]
)
INCORRECT_ANSWER_FEEDBACK_SECONDS = float(
    APP_SETTINGS["gameplay"]["incorrect_answer_feedback_seconds"]
)

COLORS = dict(APP_SETTINGS["colors"])
CONTINENT_NAMES = dict(APP_SETTINGS["labels"]["continents"])
MODE_NAMES = dict(APP_SETTINGS["labels"]["modes"])
DIFFICULTY_NAMES = dict(APP_SETTINGS["labels"]["difficulty"])
