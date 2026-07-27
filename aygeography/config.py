from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


BASE_DIR = Path(
    getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
)
CONFIGS_DIR = BASE_DIR / "configs"
ASSETS_DIR = BASE_DIR / "assets"
SAVE_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AYGeography" / "save"
    if getattr(sys, "frozen", False)
    else BASE_DIR / "save"
)
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

COLORS = dict(APP_SETTINGS["colors"])
CONTINENT_NAMES = dict(APP_SETTINGS["labels"]["continents"])
MODE_NAMES = dict(APP_SETTINGS["labels"]["modes"])
DIFFICULTY_NAMES = dict(APP_SETTINGS["labels"]["difficulty"])


def _load_feedback_seconds() -> dict[str, dict[str, float]]:
    raw = APP_SETTINGS["gameplay"]["answer_feedback_seconds_by_mode"]
    if not isinstance(raw, dict) or set(raw) != set(MODE_NAMES):
        raise ValueError(
            "Задержки ответов должны быть заданы для каждого режима"
        )
    result: dict[str, dict[str, float]] = {}
    for mode, values in raw.items():
        if not isinstance(values, dict) or set(values) != {
            "correct",
            "incorrect",
        }:
            raise ValueError(
                f"Некорректные задержки ответов для режима: {mode}"
            )
        parsed = {
            answer: float(seconds)
            for answer, seconds in values.items()
        }
        if any(seconds <= 0 for seconds in parsed.values()):
            raise ValueError(
                f"Задержка ответа должна быть положительной: {mode}"
            )
        result[mode] = parsed
    return result


ANSWER_FEEDBACK_SECONDS = _load_feedback_seconds()


def _load_wonder_category_weights() -> dict[str, int]:
    path = CONFIGS_DIR / "wonders_settings.json"
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Не удалось загрузить настройки: {path}"
        ) from error
    raw = settings.get("category_weights")
    expected = {"landmark", "peak", "fact"}
    if not isinstance(raw, dict) or set(raw) != expected:
        raise ValueError(
            "Веса wonders должны быть заданы для каждой категории"
        )
    weights = {str(key): int(value) for key, value in raw.items()}
    if any(value <= 0 for value in weights.values()):
        raise ValueError("Веса категорий wonders должны быть положительными")
    return weights


WONDER_CATEGORY_WEIGHTS = _load_wonder_category_weights()
