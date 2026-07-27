from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

from .models import Country


DIFFICULTY_KEYS = ("easy", "medium", "hard")


@dataclass(frozen=True, slots=True)
class DifficultyLevel:
    key: str
    chance: float
    countries: frozenset[str]


class DifficultyCatalog:
    """Loads difficulty data and owns weighted level selection."""

    def __init__(self, path: Path) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if set(raw) != set(DIFFICULTY_KEYS):
            raise ValueError("difficulty_levels.json должен содержать easy, medium и hard")
        self._levels = {
            key: DifficultyLevel(
                key=key,
                chance=self._parse_chance(raw[key]["chance_falling_out"]),
                countries=frozenset(raw[key]["countries"]),
            )
            for key in DIFFICULTY_KEYS
        }
        self._validate_unique("countries")

    @staticmethod
    def _parse_chance(value: str) -> float:
        if not isinstance(value, str) or not value.endswith("%"):
            raise ValueError("chance_falling_out должен быть строкой с процентом")
        chance = float(value[:-1]) / 100
        if not 0 <= chance <= 1:
            raise ValueError("chance_falling_out должен быть от 0% до 100%")
        return chance

    def _validate_unique(self, field: str) -> None:
        values = [
            item
            for level in self._levels.values()
            for item in getattr(level, field)
        ]
        if len(values) != len(set(values)):
            raise ValueError(f"Объекты в difficulty_levels.json повторяются: {field}")

    def validate_countries(self, countries: list[Country]) -> None:
        expected = {country.iso3 for country in countries}
        actual = set().union(*(level.countries for level in self._levels.values()))
        if actual != expected:
            missing = sorted(expected - actual)
            unknown = sorted(actual - expected)
            raise ValueError(
                f"Некорректное распределение стран: missing={missing}, unknown={unknown}"
            )

    def choose(self, selected: str, rng: random.Random) -> str:
        if selected not in self._levels:
            raise ValueError(f"Неизвестный уровень сложности: {selected}")
        if rng.random() < self._levels[selected].chance:
            return selected
        alternatives = [key for key in DIFFICULTY_KEYS if key != selected]
        return rng.choice(alternatives)

    def choose_available(
        self,
        selected: str,
        available: set[str],
        rng: random.Random,
    ) -> str:
        chosen = self.choose(selected, rng)
        if chosen in available:
            return chosen
        alternatives = [key for key in DIFFICULTY_KEYS if key in available]
        if not alternatives:
            raise ValueError("Закончились уникальные вопросы")
        return rng.choice(alternatives)

    def countries(self, level: str, pool: list[Country]) -> list[Country]:
        allowed = self._levels[level].countries
        return [country for country in pool if country.iso3 in allowed]

    def chance(self, level: str) -> float:
        return self._levels[level].chance
