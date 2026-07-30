from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProfileProgress:
    level: int
    xp: int
    required_xp: int
    title: str


class ProfileProgression:
    """Data-driven level thresholds and profile titles."""

    def __init__(self, config_path: Path) -> None:
        raw = json.loads(config_path.read_text(encoding="utf-8"))["profile"]
        self._thresholds = {
            int(item["level"]): int(item["xp"])
            for item in raw["levels"]
        }
        self._repeat_from_level = int(raw["repeat_from_level"])
        self._repeat_xp = int(raw["repeat_xp"])
        self._titles = tuple(raw["titles"])
        self._validate()

    def _validate(self) -> None:
        if sorted(self._thresholds) != list(
            range(2, self._repeat_from_level)
        ):
            raise ValueError("Пороги уровней должны идти без пропусков")
        if any(value <= 0 for value in self._thresholds.values()):
            raise ValueError("Пороги уровней должны быть положительными")
        if self._repeat_xp <= 0:
            raise ValueError("Повторяемый порог уровня должен быть положительным")

        expected_min = 1
        for item in self._titles:
            minimum = int(item["min_level"])
            maximum = item.get("max_level")
            if minimum != expected_min:
                raise ValueError("Диапазоны званий должны идти без пропусков")
            if maximum is None:
                expected_min = -1
                break
            maximum = int(maximum)
            if maximum < minimum:
                raise ValueError("Некорректный диапазон звания")
            expected_min = maximum + 1
        if expected_min != -1:
            raise ValueError("Последнее звание должно быть бессрочным")

    def required_xp(self, level: int) -> int:
        target_level = max(1, level) + 1
        return self._thresholds.get(target_level, self._repeat_xp)

    def title(self, level: int) -> str:
        for item in self._titles:
            maximum = item.get("max_level")
            if level >= int(item["min_level"]) and (
                maximum is None or level <= int(maximum)
            ):
                return str(item["title"])
        raise ValueError(f"Не найдено звание для уровня {level}")

    def progress(self, level: int, xp: int) -> ProfileProgress:
        safe_level = max(1, int(level))
        safe_xp = max(0, int(xp))
        return ProfileProgress(
            safe_level,
            safe_xp,
            self.required_xp(safe_level),
            self.title(safe_level),
        )

    def add_score(self, level: int, xp: int, score: int) -> ProfileProgress:
        current = self.progress(level, xp)
        accumulated = current.xp + max(0, int(score))
        if accumulated >= current.required_xp:
            return self.progress(current.level + 1, 0)
        return self.progress(current.level, accumulated)
