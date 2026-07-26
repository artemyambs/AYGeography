from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIGS_DIR, QUESTION_TIME_SECONDS
from .difficulty import DIFFICULTY_KEYS


@dataclass(frozen=True, slots=True)
class ScoreBand:
    min_remaining: int
    max_remaining: int
    points: int

    def contains(self, remaining: int) -> bool:
        return self.min_remaining <= remaining <= self.max_remaining


class ScoreRules:
    """Validated, data-driven scoring rules for every round difficulty."""

    def __init__(
        self,
        path: Path,
        question_time_seconds: int = QUESTION_TIME_SECONDS,
    ) -> None:
        self._question_time_seconds = question_time_seconds
        self._bands = self._load(path)
        self._validate()

    @staticmethod
    def _load(path: Path) -> dict[str, tuple[ScoreBand, ...]]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Не удалось загрузить правила начисления очков: {path}"
            ) from error
        if not isinstance(data, dict):
            raise ValueError("scoring.json должен содержать JSON-объект")
        try:
            return {
                difficulty: tuple(
                    ScoreBand(
                        min_remaining=int(item["min_remaining"]),
                        max_remaining=int(item["max_remaining"]),
                        points=int(item["points"]),
                    )
                    for item in data[difficulty]
                )
                for difficulty in DIFFICULTY_KEYS
            }
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                "Некорректная структура scoring.json"
            ) from error

    def _validate(self) -> None:
        for difficulty, bands in self._bands.items():
            if not bands:
                raise ValueError(
                    f"Для сложности {difficulty} не заданы очки"
                )
            for band in bands:
                if (
                    band.min_remaining < 0
                    or band.max_remaining > self._question_time_seconds
                    or band.min_remaining > band.max_remaining
                    or band.points < 0
                ):
                    raise ValueError(
                        f"Некорректный диапазон очков для {difficulty}"
                    )
            for second in range(self._question_time_seconds + 1):
                matches = sum(band.contains(second) for band in bands)
                if matches != 1:
                    raise ValueError(
                        f"Секунда {second} для {difficulty} должна "
                        "попадать ровно в один диапазон"
                    )

    def points(self, difficulty: str, remaining_seconds: float) -> int:
        if difficulty not in self._bands:
            raise ValueError(f"Неизвестный уровень сложности: {difficulty}")
        if not math.isfinite(remaining_seconds):
            raise ValueError("Оставшееся время должно быть конечным числом")
        displayed_second = math.ceil(
            max(
                0.0,
                min(float(self._question_time_seconds), remaining_seconds),
            )
        )
        return next(
            band.points
            for band in self._bands[difficulty]
            if band.contains(displayed_second)
        )


DEFAULT_SCORE_RULES = ScoreRules(CONFIGS_DIR / "scoring.json")
