from __future__ import annotations

import os
import sys
from pathlib import Path

from .infrastructure.content import ConfigProvider


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
CONFIG_PROVIDER = ConfigProvider(CONFIGS_DIR)
CONFIG_PROVIDER.validate_manifest()


def _load_app_settings() -> dict[str, object]:
    return CONFIG_PROVIDER.object("app_settings.json", schema_version=1)


APP_SETTINGS = _load_app_settings()

APP_NAME = str(APP_SETTINGS["app"]["name"])
APP_VERSION = str(APP_SETTINGS["app"]["version"])

QUESTION_TIME_SECONDS = int(
    APP_SETTINGS["gameplay"]["question_time_seconds"]
)

COLORS = dict(APP_SETTINGS["colors"])
CONTINENT_NAMES = dict(APP_SETTINGS["labels"]["continents"])
MODE_SETTINGS = dict(APP_SETTINGS["modes"])
MODE_NAMES = {
    str(key): str(value["title"])
    for key, value in MODE_SETTINGS.items()
}
DIFFICULTY_NAMES = dict(APP_SETTINGS["labels"]["difficulty"])
MODE_FEEDBACK_SETTINGS = {
    str(key): dict(value["feedback"])
    for key, value in MODE_SETTINGS.items()
}
WATER_KIND_FEEDBACK_SETTINGS = dict(
    APP_SETTINGS["gameplay"]["answer_feedback_seconds_by_water_kind"]
)


def _load_wonder_category_weights() -> dict[str, int]:
    wonders = MODE_SETTINGS.get("wonders", {})
    raw = wonders.get("category_weights") if isinstance(wonders, dict) else None
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
