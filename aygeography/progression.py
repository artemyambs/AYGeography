from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

from .catalog import CountryCatalog
from .config import MODE_NAMES
from .storage import GameRepository


@dataclass(frozen=True, slots=True)
class MasteryLevel:
    stars: int
    correct_per_mode: int


@dataclass(frozen=True, slots=True)
class AchievementDefinition:
    id: str
    category: str
    title: str
    description: str
    icon: str
    rule: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AchievementProgress:
    definition: AchievementDefinition
    current: int
    target: int
    unlocked: bool
    unlocked_at: str = ""


@dataclass(frozen=True, slots=True)
class CountryMastery:
    iso3: str
    stars: int
    correct_by_mode: dict[str, int]


class ProgressionCatalog:
    """Validated, data-driven rules for permanent player progression."""

    def __init__(self, progression_path: Path, achievements_path: Path) -> None:
        progression = json.loads(progression_path.read_text(encoding="utf-8"))
        mastery = progression["country_mastery"]
        self.mastery_modes = tuple(str(mode) for mode in mastery["modes"])
        self.mastery_levels = tuple(
            MasteryLevel(
                stars=int(item["stars"]),
                correct_per_mode=int(item["correct_per_mode"]),
            )
            for item in mastery["levels"]
        )
        self.mastery_colors = {
            int(stars): str(colour)
            for stars, colour in mastery["colors"].items()
        }
        raw_achievements = json.loads(
            achievements_path.read_text(encoding="utf-8")
        )
        self.achievements = tuple(
            AchievementDefinition(
                id=str(item["id"]),
                category=str(item["category"]),
                title=str(item["title"]),
                description=str(item["description"]),
                icon=str(item["icon"]),
                rule=dict(item["rule"]),
            )
            for item in raw_achievements
        )
        self._validate()

    def _validate(self) -> None:
        if not self.mastery_modes or len(set(self.mastery_modes)) != len(
            self.mastery_modes
        ):
            raise ValueError("Режимы мастерства должны быть уникальны")
        ordered_levels = sorted(
            self.mastery_levels,
            key=lambda level: level.correct_per_mode,
        )
        if list(self.mastery_levels) != ordered_levels:
            raise ValueError("Уровни мастерства должны идти по возрастанию")
        if any(
            level.stars <= 0 or level.correct_per_mode <= 0
            for level in self.mastery_levels
        ):
            raise ValueError("Пороги мастерства должны быть положительными")
        ids = [item.id for item in self.achievements]
        if len(ids) != len(set(ids)):
            raise ValueError("Идентификаторы достижений должны быть уникальны")


class _LifetimeSnapshot:
    def __init__(
        self,
        rounds: list[dict[str, object]],
        answers: list[dict[str, object]],
    ) -> None:
        self.rounds = rounds
        self.answers = answers
        self.answers_by_round: dict[int, list[dict[str, object]]] = defaultdict(
            list
        )
        for answer in answers:
            self.answers_by_round[int(answer["round_id"])].append(answer)

    @staticmethod
    def _accuracy(round_row: dict[str, object]) -> int:
        total = int(round_row["question_count"])
        return round(100 * int(round_row["correct_count"]) / total) if total else 0

    @staticmethod
    def _longest_streak(values: list[bool]) -> int:
        best = current = 0
        for value in values:
            current = current + 1 if value else 0
            best = max(best, current)
        return best

    def max_streak(self, max_seconds: float | None = None) -> int:
        best = 0
        for answers in self.answers_by_round.values():
            values = [
                bool(answer["is_correct"])
                and (
                    max_seconds is None
                    or float(answer["seconds"]) <= max_seconds
                )
                for answer in answers
            ]
            best = max(best, self._longest_streak(values))
        return best

    def max_daily_streak(self) -> int:
        days = sorted(
            {
                date.fromisoformat(str(row["started_at"])[:10])
                for row in self.rounds
            }
        )
        best = current = 0
        previous: date | None = None
        for day in days:
            current = current + 1 if previous and (day - previous).days == 1 else 1
            best = max(best, current)
            previous = day
        return best


class ProgressionService:
    """Calculates lifetime achievements and country mastery from raw history."""

    def __init__(
        self,
        repository: GameRepository,
        countries: CountryCatalog,
        catalog: ProgressionCatalog,
    ) -> None:
        self.repository = repository
        self.countries = countries
        self.catalog = catalog
        self._evaluators: dict[
            str,
            Callable[[dict[str, Any], _LifetimeSnapshot, dict[str, CountryMastery]], tuple[int, int]],
        ] = {
            "round_count": self._round_count,
            "correct_count": self._correct_count,
            "all_modes_played": self._all_modes_played,
            "round_size": self._round_size,
            "round_accuracy": self._round_accuracy,
            "perfect_round": self._perfect_round,
            "max_streak": self._max_streak,
            "fast_correct_count": self._fast_correct_count,
            "fast_streak": self._fast_streak,
            "fast_round": self._fast_round,
            "difficulty_round_count": self._difficulty_round_count,
            "difficulty_accuracy": self._difficulty_accuracy,
            "difficulty_perfect": self._difficulty_perfect,
            "mode_correct_count": self._mode_correct_count,
            "continent_mastery": self._continent_mastery,
            "world_mastery": self._world_mastery,
            "daily_streak": self._daily_streak,
            "active_days": self._active_days,
        }

    def country_mastery(self) -> dict[str, CountryMastery]:
        counts: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        counted_population: set[tuple[int, str]] = set()
        for answer in self.repository.lifetime_answer_countries():
            if bool(answer["is_correct"]):
                country_iso = str(answer["country_iso"])
                mode = str(answer["mode"])
                if mode == "population":
                    key = int(answer["round_id"]), country_iso
                    if key in counted_population:
                        continue
                    counted_population.add(key)
                counts[country_iso][mode] += 1
        result: dict[str, CountryMastery] = {}
        for country in self.countries.all():
            by_mode = {
                mode: counts[country.iso3][mode]
                for mode in self.catalog.mastery_modes
            }
            stars = 0
            for level in self.catalog.mastery_levels:
                if all(
                    by_mode[mode] >= level.correct_per_mode
                    for mode in self.catalog.mastery_modes
                ):
                    stars = level.stars
            result[country.iso3] = CountryMastery(
                country.iso3,
                stars,
                by_mode,
            )
        return result

    def achievements(self) -> list[AchievementProgress]:
        snapshot = _LifetimeSnapshot(
            self.repository.lifetime_rounds(),
            self.repository.lifetime_answers(),
        )
        mastery = self.country_mastery()
        unlocked = self.repository.unlocked_achievements()
        result = []
        for definition in self.catalog.achievements:
            evaluator = self._evaluators.get(str(definition.rule.get("type")))
            if evaluator is None:
                raise ValueError(
                    f"Неизвестный тип достижения: {definition.rule.get('type')}"
                )
            current, target = evaluator(definition.rule, snapshot, mastery)
            is_unlocked = definition.id in unlocked or current >= target
            result.append(
                AchievementProgress(
                    definition,
                    current,
                    target,
                    is_unlocked,
                    unlocked.get(definition.id, ""),
                )
            )
        return result

    def sync(self) -> list[AchievementDefinition]:
        completed = [
            item.definition.id
            for item in self.achievements()
            if item.unlocked
        ]
        created = set(self.repository.unlock_achievements(completed))
        return [
            definition
            for definition in self.catalog.achievements
            if definition.id in created
        ]

    @staticmethod
    def _target(rule: dict[str, Any]) -> int:
        return int(rule.get("target", 1))

    def _round_count(self, rule, snapshot, mastery):
        return len(snapshot.rounds), self._target(rule)

    def _correct_count(self, rule, snapshot, mastery):
        return sum(bool(row["is_correct"]) for row in snapshot.answers), self._target(rule)

    def _all_modes_played(self, rule, snapshot, mastery):
        played = {str(row["mode"]) for row in snapshot.answers}
        return len(played & set(MODE_NAMES)), len(MODE_NAMES)

    def _round_size(self, rule, snapshot, mastery):
        target = self._target(rule)
        current = max(
            (int(row["question_count"]) for row in snapshot.rounds),
            default=0,
        )
        return current, target

    def _round_accuracy(self, rule, snapshot, mastery):
        minimum = int(rule.get("min_questions", 1))
        current = max(
            (
                snapshot._accuracy(row)
                for row in snapshot.rounds
                if int(row["question_count"]) >= minimum
            ),
            default=0,
        )
        return current, self._target(rule)

    def _perfect_round(self, rule, snapshot, mastery):
        target = self._target(rule)
        current = max(
            (
                int(row["question_count"])
                for row in snapshot.rounds
                if int(row["question_count"]) == int(row["correct_count"])
            ),
            default=0,
        )
        return current, target

    def _max_streak(self, rule, snapshot, mastery):
        return snapshot.max_streak(), self._target(rule)

    def _fast_correct_count(self, rule, snapshot, mastery):
        limit = float(rule["max_seconds"])
        current = sum(
            bool(row["is_correct"]) and float(row["seconds"]) <= limit
            for row in snapshot.answers
        )
        return current, self._target(rule)

    def _fast_streak(self, rule, snapshot, mastery):
        return snapshot.max_streak(float(rule["max_seconds"])), self._target(rule)

    def _fast_round(self, rule, snapshot, mastery):
        minimum = int(rule["min_questions"])
        limit = float(rule["max_seconds"])
        completed = any(
            len(answers) >= minimum
            and sum(float(item["seconds"]) for item in answers) / len(answers)
            <= limit
            for answers in snapshot.answers_by_round.values()
        )
        return int(completed), self._target(rule)

    def _difficulty_round_count(self, rule, snapshot, mastery):
        current = sum(
            str(row["difficulty"]) == str(rule["difficulty"])
            for row in snapshot.rounds
        )
        return current, self._target(rule)

    def _difficulty_accuracy(self, rule, snapshot, mastery):
        minimum = int(rule.get("min_questions", 1))
        current = max(
            (
                snapshot._accuracy(row)
                for row in snapshot.rounds
                if str(row["difficulty"]) == str(rule["difficulty"])
                and int(row["question_count"]) >= minimum
            ),
            default=0,
        )
        return current, self._target(rule)

    def _difficulty_perfect(self, rule, snapshot, mastery):
        target = self._target(rule)
        current = max(
            (
                int(row["question_count"])
                for row in snapshot.rounds
                if str(row["difficulty"]) == str(rule["difficulty"])
                and int(row["question_count"]) == int(row["correct_count"])
            ),
            default=0,
        )
        return current, target

    def _mode_correct_count(self, rule, snapshot, mastery):
        current = sum(
            bool(row["is_correct"]) and str(row["mode"]) == str(rule["mode"])
            for row in snapshot.answers
        )
        return current, self._target(rule)

    def _continent_mastery(self, rule, snapshot, mastery):
        country_ids = self.countries.continents[str(rule["continent"])]
        stars = int(rule["stars"])
        current = sum(mastery[iso3].stars >= stars for iso3 in country_ids)
        return current, len(country_ids)

    def _world_mastery(self, rule, snapshot, mastery):
        stars = int(rule["stars"])
        return sum(item.stars >= stars for item in mastery.values()), len(mastery)

    def _daily_streak(self, rule, snapshot, mastery):
        return snapshot.max_daily_streak(), self._target(rule)

    def _active_days(self, rule, snapshot, mastery):
        current = len({str(row["started_at"])[:10] for row in snapshot.rounds})
        return current, self._target(rule)
