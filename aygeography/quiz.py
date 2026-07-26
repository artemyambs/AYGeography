from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from typing import Any

from .catalog import CountryCatalog
from .config import CONFIGS_DIR, MODE_NAMES, QUESTION_TIME_SECONDS
from .difficulty import DIFFICULTY_KEYS, DifficultyCatalog
from .models import AnswerRecord, Country, GameConfig, Question, RoundResult
from .scoring import DEFAULT_SCORE_RULES, ScoreRules
from .waters import WATER_REGIONS, WaterRegion


class QuestionStrategy(ABC):
    mode: str

    @abstractmethod
    def create(
        self,
        country: Country,
        pool: list[Country],
        serial: int,
        rng: random.Random,
        *,
        eligible_water_keys: frozenset[str] | None = None,
    ) -> Question:
        raise NotImplementedError

    @staticmethod
    def options(
        correct: str, candidates: list[str], rng: random.Random, count: int = 6
    ) -> list[str]:
        unique = list(dict.fromkeys(value for value in candidates if value != correct))
        selected = rng.sample(unique, min(count - 1, len(unique)))
        result = selected + [correct]
        rng.shuffle(result)
        return result

    @staticmethod
    def continent_pool(country: Country, pool: list[Country]) -> list[Country]:
        """Returns distractor candidates from the target country's continent."""
        return [item for item in pool if item.continent == country.continent]


class PopulationPairSelector:
    """Selects unique, balanced population comparisons for one round."""

    CLOSE_MIN_RATIO = 1.15
    CLOSE_MAX_RATIO = 2.0
    CONTRAST_MAX_RATIO = 10.0

    def __init__(self) -> None:
        self._used_pairs: set[tuple[str, str]] = set()
        self._appearances: dict[str, int] = defaultdict(int)

    def reset(self) -> None:
        self._used_pairs.clear()
        self._appearances.clear()

    @staticmethod
    def _pair_key(first: Country, second: Country) -> tuple[str, str]:
        return tuple(sorted((first.iso3, second.iso3)))

    @staticmethod
    def ratio(first: Country, second: Country) -> float:
        smaller = min(first.population, second.population)
        if smaller <= 0:
            raise ValueError("Население страны должно быть положительным")
        return max(first.population, second.population) / smaller

    def _available(
        self,
        primary: Country,
        pool: list[Country],
    ) -> list[Country]:
        return [
            country
            for country in pool
            if country.iso3 != primary.iso3
            and self._pair_key(primary, country) not in self._used_pairs
        ]

    def _balanced_choice(
        self,
        candidates: list[Country],
        rng: random.Random,
    ) -> Country:
        minimum = min(self._appearances[country.iso3] for country in candidates)
        balanced = [
            country
            for country in candidates
            if self._appearances[country.iso3] == minimum
        ]
        return rng.choice(balanced)

    def select(
        self,
        primary: Country,
        pool: list[Country],
        mode_serial: int,
        rng: random.Random,
    ) -> tuple[Country, str]:
        available = self._available(primary, pool)
        if not available:
            available = [
                country for country in pool if country.iso3 != primary.iso3
            ]
        if not available:
            raise ValueError(
                "Для сравнения населения нужны как минимум две страны"
            )

        prefer_close = mode_serial % 2 == 0
        if prefer_close:
            candidates = [
                country
                for country in available
                if self.CLOSE_MIN_RATIO
                <= self.ratio(primary, country)
                < self.CLOSE_MAX_RATIO
            ]
            kind = "close"
        else:
            candidates = [
                country
                for country in available
                if self.CLOSE_MAX_RATIO
                <= self.ratio(primary, country)
                <= self.CONTRAST_MAX_RATIO
            ]
            kind = "contrast"

        if not candidates:
            candidates = [
                country
                for country in available
                if self.CLOSE_MIN_RATIO
                <= self.ratio(primary, country)
                <= self.CONTRAST_MAX_RATIO
            ]
            kind = "fallback"
        if not candidates:
            closest_ratio = min(
                self.ratio(primary, country) for country in available
            )
            candidates = [
                country
                for country in available
                if self.ratio(primary, country) == closest_ratio
            ]
            kind = "fallback"

        comparison = self._balanced_choice(candidates, rng)
        self._used_pairs.add(self._pair_key(primary, comparison))
        self._appearances[primary.iso3] += 1
        self._appearances[comparison.iso3] += 1
        return comparison, kind


class FlagQuestionStrategy(QuestionStrategy):
    mode = "flags"

    def create(
        self,
        country: Country,
        pool: list[Country],
        serial: int,
        rng: random.Random,
        *,
        eligible_water_keys: frozenset[str] | None = None,
    ) -> Question:
        candidates = self.continent_pool(country, pool)
        return Question(
            key=f"flags:{country.iso3}",
            mode=self.mode,
            prompt="Какая страна?",
            country_iso=country.iso3,
            options=self.options(
                country.name,
                [item.name for item in candidates],
                rng,
            ),
            correct_answer=country.name,
            visual=country.iso3,
        )


class CapitalQuestionStrategy(QuestionStrategy):
    mode = "capitals"

    def create(
        self,
        country: Country,
        pool: list[Country],
        serial: int,
        rng: random.Random,
        *,
        eligible_water_keys: frozenset[str] | None = None,
    ) -> Question:
        candidates = self.continent_pool(country, pool)
        return Question(
            key=f"capitals:{country.iso3}",
            mode=self.mode,
            prompt=country.name,
            country_iso=country.iso3,
            options=self.options(
                country.capital,
                [item.capital for item in candidates],
                rng,
            ),
            correct_answer=country.capital,
            visual=country.iso3,
            metadata={"capital_layout": True},
        )


class PopulationQuestionStrategy(QuestionStrategy):
    mode = "population"

    def __init__(
        self,
        pair_selector: PopulationPairSelector | None = None,
    ) -> None:
        self._pair_selector = pair_selector or PopulationPairSelector()

    def reset(self) -> None:
        self._pair_selector.reset()

    def create(
        self,
        country: Country,
        pool: list[Country],
        serial: int,
        rng: random.Random,
        *,
        eligible_water_keys: frozenset[str] | None = None,
    ) -> Question:
        comparison, pair_kind = self._pair_selector.select(
            country,
            pool,
            serial,
            rng,
        )
        countries = [country, comparison]
        rng.shuffle(countries)
        correct_country = max(countries, key=lambda item: item.population)
        return Question(
            key="population:compare:" + ":".join(
                sorted((country.iso3, comparison.iso3))
            ),
            mode=self.mode,
            prompt="В какой стране население больше?",
            country_iso=country.iso3,
            country_isos=(country.iso3, comparison.iso3),
            options=[item.name for item in countries],
            correct_answer=correct_country.name,
            metadata={
                "presentation": "country_comparison",
                "pair_kind": pair_kind,
                "population_values": {
                    item.iso3: item.population for item in countries
                },
            },
        )


class CountryMapQuestionStrategy(QuestionStrategy):
    mode = "countries"

    def create(
        self,
        country: Country,
        pool: list[Country],
        serial: int,
        rng: random.Random,
        *,
        eligible_water_keys: frozenset[str] | None = None,
    ) -> Question:
        candidates = self.continent_pool(country, pool)
        return Question(
            key=f"countries:choice:{country.iso3}",
            mode=self.mode,
            prompt="Какая страна выделена на карте?",
            country_iso=country.iso3,
            options=self.options(
                country.name,
                [item.name for item in candidates],
                rng,
            ),
            correct_answer=country.name,
            interaction="choices",
            metadata={"highlight": country.iso3},
        )


class WaterQuestionStrategy(QuestionStrategy):
    mode = "waters"

    @staticmethod
    def _options(
        correct_region: WaterRegion,
        rng: random.Random,
        count: int = 6,
    ) -> list[str]:
        same_kind = list(
            dict.fromkeys(
                region.name
                for region in WATER_REGIONS
                if region.kind == correct_region.kind
                and region.name != correct_region.name
            )
        )
        distractors = rng.sample(same_kind, min(count - 1, len(same_kind)))
        if len(distractors) < count - 1:
            fallback = list(
                dict.fromkeys(
                    region.name
                    for region in WATER_REGIONS
                    if region.name != correct_region.name
                    and region.name not in distractors
                )
            )
            distractors.extend(
                rng.sample(fallback, count - 1 - len(distractors))
            )
        options = distractors + [correct_region.name]
        rng.shuffle(options)
        return options

    def create(
        self,
        country: Country,
        pool: list[Country],
        serial: int,
        rng: random.Random,
        *,
        eligible_water_keys: frozenset[str] | None = None,
    ) -> Question:
        regions = [
            region
            for region in WATER_REGIONS
            if eligible_water_keys is None or region.key in eligible_water_keys
        ]
        if not regions:
            regions = WATER_REGIONS
        region = regions[serial % len(regions)]
        return Question(
            key=f"waters:choice:{region.key}",
            mode=self.mode,
            prompt=(
                "Какое море выделено?"
                if region.kind == "Море"
                else "Какой океан выделен?"
            ),
            country_iso=country.iso3,
            options=self._options(region, rng),
            correct_answer=region.name,
            interaction="choices",
            metadata={"water_highlight": region.key},
        )


class QuestionFactory:
    """Реестр стратегий: новый режим добавляется без изменения движка."""

    def __init__(
        self,
        strategies: list[QuestionStrategy] | None = None,
        difficulty_catalog: DifficultyCatalog | None = None,
    ) -> None:
        items = strategies or [
            FlagQuestionStrategy(),
            CapitalQuestionStrategy(),
            PopulationQuestionStrategy(),
            CountryMapQuestionStrategy(),
            WaterQuestionStrategy(),
        ]
        self._strategies = {item.mode: item for item in items}
        self._difficulty = difficulty_catalog or DifficultyCatalog(
            CONFIGS_DIR / "difficulty_levels.json"
        )

    def build(
        self,
        config: GameConfig,
        catalog: CountryCatalog,
        wrong_isos: list[str] | None = None,
        seed: int | None = None,
    ) -> list[Question]:
        rng = random.Random(seed)
        candidate_pool = catalog.by_continents(config.continents)
        if not config.modes:
            raise ValueError("Выберите хотя бы один режим")
        unknown_modes = set(config.modes) - set(self._strategies)
        if unknown_modes:
            raise ValueError(f"Неизвестные режимы: {sorted(unknown_modes)}")
        if not candidate_pool:
            raise ValueError("Для выбранных континентов нет стран")

        subject_pool = candidate_pool.copy()
        if config.wrong_only and wrong_isos:
            wrong_set = set(wrong_isos)
            subject_pool = [
                country for country in subject_pool if country.iso3 in wrong_set
            ] or subject_pool
        if config.difficulty is not None:
            return self._build_by_difficulty(
                config,
                catalog,
                candidate_pool,
                subject_pool,
                rng,
            )
        return self._build_without_difficulty(
            config,
            candidate_pool,
            subject_pool,
            rng,
        )

    def _reset_round_strategies(self, modes: list[str]) -> None:
        for mode in dict.fromkeys(modes):
            reset = getattr(self._strategies[mode], "reset", None)
            if reset is not None:
                reset()

    @staticmethod
    def _required_by_mode(config: GameConfig) -> dict[str, int]:
        required = dict.fromkeys(config.modes, 0)
        for serial in range(config.question_count):
            mode = config.modes[serial % len(config.modes)]
            required[mode] += 1
        return required

    @staticmethod
    def _ensure_capacity(
        required: dict[str, int],
        capacities: dict[str, int],
    ) -> None:
        for mode, count in required.items():
            available = capacities[mode]
            if count > available:
                name = MODE_NAMES.get(mode, mode)
                raise ValueError(
                    f"Для режима «{name}» доступно {available} уникальных "
                    f"вопросов, требуется {count}"
                )

    def _build_without_difficulty(
        self,
        config: GameConfig,
        candidate_pool: list[Country],
        subject_pool: list[Country],
        rng: random.Random,
    ) -> list[Question]:
        self._reset_round_strategies(config.modes)
        country_queues: dict[str, list[Country]] = {}
        for mode in dict.fromkeys(config.modes):
            if mode == WaterQuestionStrategy.mode:
                continue
            country_queues[mode] = subject_pool.copy()
            rng.shuffle(country_queues[mode])

        water_queue = [region.key for region in WATER_REGIONS]
        rng.shuffle(water_queue)
        capacities = {
            mode: (
                len(water_queue)
                if mode == WaterQuestionStrategy.mode
                else len(country_queues[mode])
            )
            for mode in dict.fromkeys(config.modes)
        }
        self._ensure_capacity(self._required_by_mode(config), capacities)

        questions: list[Question] = []
        mode_serials: dict[str, int] = defaultdict(int)
        for serial in range(config.question_count):
            mode = config.modes[serial % len(config.modes)]
            mode_serial = mode_serials[mode]
            mode_serials[mode] += 1
            if mode == WaterQuestionStrategy.mode:
                water_key = water_queue.pop()
                country = candidate_pool[serial % len(candidate_pool)]
                question = self._strategies[mode].create(
                    country,
                    candidate_pool,
                    mode_serial,
                    rng,
                    eligible_water_keys=frozenset({water_key}),
                )
            else:
                country = country_queues[mode].pop()
                question = self._strategies[mode].create(
                    country,
                    candidate_pool,
                    mode_serial,
                    rng,
                )
            questions.append(question)
        return questions

    def _build_by_difficulty(
        self,
        config: GameConfig,
        catalog: CountryCatalog,
        candidate_pool: list[Country],
        subject_pool: list[Country],
        rng: random.Random,
    ) -> list[Question]:
        self._reset_round_strategies(config.modes)
        if config.difficulty not in DIFFICULTY_KEYS:
            raise ValueError(f"Неизвестный уровень сложности: {config.difficulty}")
        if not candidate_pool:
            raise ValueError("Для выбранных континентов нет стран")
        self._difficulty.validate_countries(catalog.all())
        self._difficulty.validate_water_keys(
            {region.key for region in WATER_REGIONS}
        )

        country_queues: dict[str, dict[str, list[Country]]] = {}
        for mode in dict.fromkeys(config.modes):
            if mode == WaterQuestionStrategy.mode:
                continue
            country_queues[mode] = {}
            for level in DIFFICULTY_KEYS:
                queue = self._difficulty.countries(level, subject_pool)
                rng.shuffle(queue)
                country_queues[mode][level] = queue

        water_queues: dict[str, list[str]] = {}
        for level in DIFFICULTY_KEYS:
            allowed = self._difficulty.water_keys(level)
            queue = [
                region.key
                for region in WATER_REGIONS
                if region.key in allowed
            ]
            rng.shuffle(queue)
            water_queues[level] = queue

        capacities = {
            mode: (
                sum(len(queue) for queue in water_queues.values())
                if mode == WaterQuestionStrategy.mode
                else sum(
                    len(queue)
                    for queue in country_queues[mode].values()
                )
            )
            for mode in dict.fromkeys(config.modes)
        }
        self._ensure_capacity(self._required_by_mode(config), capacities)

        questions: list[Question] = []
        mode_serials: dict[str, int] = defaultdict(int)
        for serial in range(config.question_count):
            mode = config.modes[serial % len(config.modes)]
            mode_serial = mode_serials[mode]
            mode_serials[mode] += 1
            queues = (
                water_queues
                if mode == WaterQuestionStrategy.mode
                else country_queues[mode]
            )
            available_levels = {
                level for level, queue in queues.items() if queue
            }
            level = self._difficulty.choose_available(
                config.difficulty,
                available_levels,
                rng,
            )
            if mode == WaterQuestionStrategy.mode:
                water_key = water_queues[level].pop()
                country = candidate_pool[serial % len(candidate_pool)]
                question = self._strategies[mode].create(
                    country,
                    candidate_pool,
                    mode_serial,
                    rng,
                    eligible_water_keys=frozenset({water_key}),
                )
            else:
                country = country_queues[mode][level].pop()
                question = self._strategies[mode].create(
                    country,
                    candidate_pool,
                    mode_serial,
                    rng,
                )
            question.metadata["difficulty"] = level
            questions.append(question)
        return questions


class GameSession:
    def __init__(
        self,
        questions: list[Question],
        difficulty: str = "medium",
        score_rules: ScoreRules = DEFAULT_SCORE_RULES,
    ) -> None:
        if difficulty not in DIFFICULTY_KEYS:
            raise ValueError(f"Неизвестный уровень сложности: {difficulty}")
        self.questions = questions
        self.difficulty = difficulty
        self._score_rules = score_rules
        self.index = 0
        self.score = 0
        self.streak = 0
        self.answers: list[AnswerRecord] = []
        self.started_at = datetime.now()

    @property
    def current(self) -> Question:
        return self.questions[self.index]

    @property
    def finished(self) -> bool:
        return self.index >= len(self.questions)

    def answer(self, value: str, elapsed_seconds: float) -> AnswerRecord:
        question = self.current
        correct = value == question.correct_answer
        remaining = max(0, QUESTION_TIME_SECONDS - elapsed_seconds)
        points = (
            self._score_rules.points(self.difficulty, remaining)
            if correct
            else 0
        )
        self.score += points
        self.streak = self.streak + 1 if correct else 0
        record = AnswerRecord(
            mode=question.mode,
            country_iso=question.country_iso,
            prompt=question.prompt,
            answer=value,
            correct_answer=question.correct_answer,
            is_correct=correct,
            seconds=elapsed_seconds,
            points=points,
            country_isos=question.subjects,
        )
        self.answers.append(record)
        self.index += 1
        return record

    def result(self) -> RoundResult:
        duration = sum(answer.seconds for answer in self.answers)
        return RoundResult(
            started_at=self.started_at.isoformat(timespec="seconds"),
            duration_seconds=duration,
            score=self.score,
            answers=self.answers.copy(),
            difficulty=self.difficulty,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "questions": [asdict(question) for question in self.questions],
            "difficulty": self.difficulty,
            "index": self.index,
            "score": self.score,
            "streak": self.streak,
            "answers": [asdict(answer) for answer in self.answers],
            "started_at": self.started_at.isoformat(),
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> GameSession:
        questions = []
        for raw_question in state["questions"]:
            item = dict(raw_question)
            item["country_isos"] = tuple(item.get("country_isos", ()))
            questions.append(Question(**item))
        session = cls(
            questions,
            difficulty=str(state.get("difficulty", "medium")),
        )
        session.index = int(state["index"])
        if not 0 <= session.index <= len(questions):
            raise ValueError("Некорректный индекс сохранённого вопроса")
        session.score = int(state["score"])
        session.streak = int(state["streak"])
        session.answers = []
        for raw_answer in state["answers"]:
            item = dict(raw_answer)
            item["country_isos"] = tuple(item.get("country_isos", ()))
            session.answers.append(AnswerRecord(**item))
        session.started_at = datetime.fromisoformat(state["started_at"])
        return session
