from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class ResultLevel:
    minimum: int
    maximum: int
    title: str

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
            ):
                raise ValueError("Некорректный диапазон результата")
            for value in range(level.minimum, level.maximum + 1):
                coverage[value] += 1
        invalid = [value for value, matches in coverage.items() if matches != 1]
        if invalid:
            raise ValueError(
                "Уровни результата должны без пересечений покрывать 0–100%"
            )

    def title(self, accuracy_percent: int) -> str:
        normalized = max(0, min(100, int(accuracy_percent)))
        return next(
            level.title
            for level in self._levels
            if level.contains(normalized)
        )
