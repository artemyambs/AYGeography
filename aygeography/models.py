from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Country:
    iso3: str
    name: str
    name_en: str
    capital: str
    continent: str
    population: int
    area: int


@dataclass(slots=True)
class GameConfig:
    modes: list[str]
    continents: list[str]
    question_count: int
    wrong_only: bool = False
    difficulty: str | None = None


@dataclass(slots=True)
class Question:
    key: str
    mode: str
    prompt: str
    country_iso: str
    options: list[str] = field(default_factory=list)
    correct_answer: str = ""
    visual: str = ""
    interaction: str = "choices"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnswerRecord:
    mode: str
    country_iso: str
    prompt: str
    answer: str
    correct_answer: str
    is_correct: bool
    seconds: float
    points: int


@dataclass(slots=True)
class RoundResult:
    started_at: str
    duration_seconds: float
    score: int
    answers: list[AnswerRecord]
    difficulty: str = "medium"

    @property
    def correct_count(self) -> int:
        return sum(item.is_correct for item in self.answers)

    @property
    def accuracy(self) -> float:
        return self.correct_count / len(self.answers) if self.answers else 0.0

    @property
    def average_seconds(self) -> float:
        if not self.answers:
            return 0.0
        return sum(item.seconds for item in self.answers) / len(self.answers)
