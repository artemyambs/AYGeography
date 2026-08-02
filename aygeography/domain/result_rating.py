from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class ResultLevel:
    minimum: int
    maximum: int
    title: str
    trophy_key: str
    title_color: str
    trophy_effect: str

    def contains(self, accuracy_percent: int) -> bool:
        return self.minimum <= accuracy_percent <= self.maximum


class ResultRatingPolicy:
    """Validated mapping from integer accuracy to a result title."""

    def __init__(self, levels: Iterable[ResultLevel]) -> None:
        self._levels = tuple(levels)
        self._validate()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> ResultRatingPolicy:
        raw_levels = config.get("levels")
        if not isinstance(raw_levels, list):
            raise ValueError("result_levels.json: поле levels должно быть списком")
        try:
            levels = (
                ResultLevel(
                    minimum=int(item["min_accuracy"]),
                    maximum=int(item["max_accuracy"]),
                    title=str(item["title"]),
                    trophy_key=str(item["trophy_key"]),
                    title_color=str(item["title_color"]),
                    trophy_effect=str(item["trophy_effect"]),
                )
                for item in raw_levels
            )
            return cls(levels)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Некорректная структура result_levels.json") from error

    def _validate(self) -> None:
        if not self._levels:
            raise ValueError("Должен быть задан хотя бы один уровень результата")
        coverage: dict[int, int] = {value: 0 for value in range(101)}
        for level in self._levels:
            if (
                level.minimum < 0
                or level.maximum > 100
                or level.minimum > level.maximum
                or not level.title.strip()
                or re.fullmatch(r"[a-z0-9_]+", level.trophy_key) is None
                or re.fullmatch(r"#[0-9a-fA-F]{6}", level.title_color) is None
                or re.fullmatch(r"[a-z0-9_]+", level.trophy_effect) is None
            ):
                raise ValueError("Некорректный диапазон результата")
            for value in range(level.minimum, level.maximum + 1):
                coverage[value] += 1
        invalid = [value for value, matches in coverage.items() if matches != 1]
        if invalid:
            raise ValueError(
                "Уровни результата должны без пересечений покрывать 0–100%"
            )

    def level(self, accuracy_percent: int) -> ResultLevel:
        normalized = max(0, min(100, int(accuracy_percent)))
        return next(
            level
            for level in self._levels
            if level.contains(normalized)
        )

    def title(self, accuracy_percent: int) -> str:
        return self.level(accuracy_percent).title

    @property
    def trophy_keys(self) -> frozenset[str]:
        return frozenset(level.trophy_key for level in self._levels)

    @property
    def trophy_effects(self) -> frozenset[str]:
        return frozenset(level.trophy_effect for level in self._levels)
