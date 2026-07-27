from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from .catalog import CountryCatalog
from .config import (
    CONFIGS_DIR,
    MODE_NAMES,
    QUESTION_TIME_SECONDS,
    WONDER_CATEGORY_WEIGHTS,
)
from .difficulty import DIFFICULTY_KEYS, DifficultyCatalog
from .models import AnswerRecord, Country, GameConfig, Question, RoundResult
from .scoring import DEFAULT_SCORE_RULES, ScoreRules
from .waters import WATER_REGIONS, WaterRegion
from .wonders import WonderCatalog, WonderCategory, WonderItem


@dataclass(frozen=True, slots=True)
class QuestionBuildContext:
    catalog: CountryCatalog
    candidate_pool: list[Country]
    subject_pool: list[Country]
    continents: tuple[str, ...]
    wrong_isos: frozenset[str]
    difficulty: str | None


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

    def prepare(
        self,
        context: QuestionBuildContext,
        difficulty: DifficultyCatalog,
        rng: random.Random,
    ) -> PreparedQuestionPool:
        return CountryPreparedQuestionPool(self, context, difficulty, rng)


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

    def prepare(
        self,
        context: QuestionBuildContext,
        difficulty: DifficultyCatalog,
        rng: random.Random,
    ) -> PreparedQuestionPool:
        return WaterPreparedQuestionPool(self, context, difficulty, rng)


class WonderQuestionStrategy(QuestionStrategy):
    mode = "wonders"

    def __init__(self, catalog: WonderCatalog) -> None:
        self.catalog = catalog

    def create(
        self,
        country: Country,
        pool: list[Country],
        serial: int,
        rng: random.Random,
        *,
        eligible_water_keys: frozenset[str] | None = None,
    ) -> Question:
        raise NotImplementedError("Wonder-вопрос создаётся из WonderItem")

    def prepare(
        self,
        context: QuestionBuildContext,
        difficulty: DifficultyCatalog,
        rng: random.Random,
    ) -> PreparedQuestionPool:
        return WonderPreparedQuestionPool(self, context, difficulty, rng)

    def create_item(
        self,
        item: WonderItem,
        eligible_items: list[WonderItem],
        countries: list[Country],
        rng: random.Random,
    ) -> Question:
        if item.category == WonderCategory.LANDMARK:
            return self._landmark(item, eligible_items, countries, rng)
        if item.category == WonderCategory.PEAK:
            return self._named_map_item(item, eligible_items, rng, "point")
        if item.category == WonderCategory.RIVER:
            return self._named_map_item(item, eligible_items, rng, "line")
        return self._fact(item, countries, rng)

    def _landmark(
        self,
        item: WonderItem,
        eligible_items: list[WonderItem],
        countries: list[Country],
        rng: random.Random,
    ) -> Question:
        ask_country = rng.choice((False, True))
        if ask_country:
            correct = self.catalog.country_name(item.country_iso)
            options = self._country_options(
                correct,
                item,
                countries,
                rng,
            )
            prompt = f"В какой стране находится {item.name}?"
            presentation = "wonder_landmark_country"
        else:
            correct = item.name
            options = self._item_options(item, eligible_items, rng)
            prompt = "Какая достопримечательность изображена?"
            presentation = "wonder_landmark_name"
        return Question(
            key=f"wonders:{item.key}",
            mode=self.mode,
            prompt=prompt,
            country_iso=item.country_iso,
            country_isos=item.country_isos,
            options=options,
            correct_answer=correct,
            visual=item.image,
            presentation=presentation,
            explanation=item.explanation,
        )

    def _named_map_item(
        self,
        item: WonderItem,
        eligible_items: list[WonderItem],
        rng: random.Random,
        overlay_kind: str,
    ) -> Question:
        metadata: dict[str, Any] = {
            "map_overlay": {
                "kind": overlay_kind,
                "point": list(item.point) if item.point else None,
                "lines": [
                    [list(point) for point in line] for line in item.lines
                ],
            }
        }
        prompt = (
            "Какая горная вершина отмечена на карте?"
            if item.category == WonderCategory.PEAK
            else "Какая река выделена на карте?"
        )
        return Question(
            key=f"wonders:{item.key}",
            mode=self.mode,
            prompt=prompt,
            country_iso=item.country_iso,
            country_isos=item.country_isos,
            options=self._item_options(item, eligible_items, rng),
            correct_answer=item.name,
            presentation="wonder_map",
            explanation=item.explanation,
            metadata=metadata,
        )

    def _fact(
        self,
        item: WonderItem,
        countries: list[Country],
        rng: random.Random,
    ) -> Question:
        correct = self.catalog.country_name(item.country_iso)
        return Question(
            key=f"wonders:{item.key}",
            mode=self.mode,
            prompt=item.prompt,
            country_iso=item.country_iso,
            country_isos=item.country_isos,
            options=self._country_options(correct, item, countries, rng),
            correct_answer=correct,
            presentation="wonder_fact",
            explanation=item.explanation,
        )

    @staticmethod
    def _ranked_items(
        item: WonderItem,
        items: list[WonderItem],
    ) -> list[WonderItem]:
        return sorted(
            (
                candidate
                for candidate in items
                if candidate.category == item.category
                and candidate.key != item.key
            ),
            key=lambda candidate: (
                candidate.difficulty != item.difficulty,
                not bool(set(candidate.continents) & set(item.continents)),
                candidate.key,
            ),
        )

    def _item_options(
        self,
        item: WonderItem,
        items: list[WonderItem],
        rng: random.Random,
    ) -> list[str]:
        ranked = self._ranked_items(item, items)
        grouped: dict[tuple[bool, bool], list[str]] = defaultdict(list)
        for candidate in ranked:
            rank = (
                candidate.difficulty != item.difficulty,
                not bool(set(candidate.continents) & set(item.continents)),
            )
            grouped[rank].append(candidate.name)
        candidates: list[str] = []
        for rank in sorted(grouped):
            values = list(dict.fromkeys(grouped[rank]))
            rng.shuffle(values)
            candidates.extend(values)
        return self._six_options(item.name, candidates, rng)

    def _country_options(
        self,
        correct: str,
        item: WonderItem,
        countries: list[Country],
        rng: random.Random,
    ) -> list[str]:
        ranked = sorted(
            (country for country in countries if country.name != correct),
            key=lambda country: (
                country.continent not in item.continents,
                country.iso3,
            ),
        )
        same_continent = [
            country.name
            for country in ranked
            if country.continent in item.continents
        ]
        other = [
            country.name
            for country in ranked
            if country.continent not in item.continents
        ]
        rng.shuffle(same_continent)
        rng.shuffle(other)
        return self._six_options(correct, same_continent + other, rng)

    @staticmethod
    def _six_options(
        correct: str,
        candidates: list[str],
        rng: random.Random,
    ) -> list[str]:
        unique = list(
            dict.fromkeys(
                value for value in candidates if value and value != correct
            )
        )
        if len(unique) < 5:
            raise ValueError(
                f"Недостаточно вариантов ответа для «{correct}»"
            )
        result = unique[:5] + [correct]
        rng.shuffle(result)
        return result


class PreparedQuestionPool(ABC):
    @property
    @abstractmethod
    def capacity(self) -> int:
        raise NotImplementedError

    def plan(self, count: int) -> None:
        if count > self.capacity:
            raise ValueError("Недостаточно уникальных вопросов")

    @abstractmethod
    def next(self, serial: int) -> Question:
        raise NotImplementedError


T = TypeVar("T")


class DifficultyQueue(Generic[T]):
    def __init__(
        self,
        queues: dict[str, list[T]],
        selected: str | None,
        difficulty: DifficultyCatalog,
        rng: random.Random,
    ) -> None:
        self.queues = queues
        self.selected = selected
        self.difficulty = difficulty
        self.rng = rng

    @property
    def capacity(self) -> int:
        return sum(len(queue) for queue in self.queues.values())

    def pop(self) -> tuple[T, str | None]:
        available = {level for level, queue in self.queues.items() if queue}
        if not available:
            raise ValueError("Закончились уникальные вопросы")
        if self.selected is None:
            level = self.rng.choice(sorted(available))
            return self.queues[level].pop(), None
        level = self.difficulty.choose_available(
            self.selected,
            available,
            self.rng,
        )
        return self.queues[level].pop(), level


class CountryPreparedQuestionPool(PreparedQuestionPool):
    def __init__(
        self,
        strategy: QuestionStrategy,
        context: QuestionBuildContext,
        difficulty: DifficultyCatalog,
        rng: random.Random,
    ) -> None:
        self.strategy = strategy
        self.context = context
        self.rng = rng
        reset = getattr(strategy, "reset", None)
        if reset is not None:
            reset()
        queues = (
            {"all": context.subject_pool.copy()}
            if context.difficulty is None
            else {
                level: difficulty.countries(level, context.subject_pool)
                for level in DIFFICULTY_KEYS
            }
        )
        for queue in queues.values():
            rng.shuffle(queue)
        self.queue = DifficultyQueue(
            queues,
            context.difficulty,
            difficulty,
            rng,
        )

    @property
    def capacity(self) -> int:
        return self.queue.capacity

    def next(self, serial: int) -> Question:
        country, level = self.queue.pop()
        question = self.strategy.create(
            country,
            self.context.candidate_pool,
            serial,
            self.rng,
        )
        if level is not None:
            question.metadata["difficulty"] = level
        return question


class WaterPreparedQuestionPool(PreparedQuestionPool):
    def __init__(
        self,
        strategy: WaterQuestionStrategy,
        context: QuestionBuildContext,
        difficulty: DifficultyCatalog,
        rng: random.Random,
    ) -> None:
        self.strategy = strategy
        self.context = context
        self.rng = rng
        queues = (
            {"all": list(WATER_REGIONS)}
            if context.difficulty is None
            else {
                level: [
                    region
                    for region in WATER_REGIONS
                    if region.key in difficulty.water_keys(level)
                ]
                for level in DIFFICULTY_KEYS
            }
        )
        for queue in queues.values():
            rng.shuffle(queue)
        self.queue = DifficultyQueue(
            queues,
            context.difficulty,
            difficulty,
            rng,
        )

    @property
    def capacity(self) -> int:
        return self.queue.capacity

    def next(self, serial: int) -> Question:
        region, level = self.queue.pop()
        country = self.context.candidate_pool[
            serial % len(self.context.candidate_pool)
        ]
        question = self.strategy.create(
            country,
            self.context.candidate_pool,
            serial,
            self.rng,
            eligible_water_keys=frozenset({region.key}),
        )
        if level is not None:
            question.metadata["difficulty"] = level
        return question


class WonderPreparedQuestionPool(PreparedQuestionPool):
    def __init__(
        self,
        strategy: WonderQuestionStrategy,
        context: QuestionBuildContext,
        difficulty: DifficultyCatalog,
        rng: random.Random,
    ) -> None:
        self.strategy = strategy
        self.context = context
        self.difficulty = difficulty
        self.rng = rng
        self.items = strategy.catalog.eligible(
            context.continents,
            context.wrong_isos,
        )
        self.queues: dict[
            WonderCategory,
            dict[str, list[WonderItem]],
        ] = {
            category: {
                level: [
                    item
                    for item in self.items
                    if item.category == category
                    and item.difficulty == level
                ]
                for level in DIFFICULTY_KEYS
            }
            for category in WonderCategory
        }
        for levels in self.queues.values():
            for queue in levels.values():
                rng.shuffle(queue)
        self.category_cycle = self._build_category_cycle()
        self.schedule: list[WonderCategory] = []

    @staticmethod
    def _build_category_cycle() -> tuple[WonderCategory, ...]:
        weights = {
            WonderCategory(key): value
            for key, value in WONDER_CATEGORY_WEIGHTS.items()
        }
        categories = tuple(weights)
        current = dict.fromkeys(categories, 0)
        total = sum(weights.values())
        cycle: list[WonderCategory] = []
        for _ in range(total):
            for category in categories:
                current[category] += weights[category]
            selected = max(categories, key=current.__getitem__)
            current[selected] -= total
            cycle.append(selected)
        return tuple(cycle)

    @property
    def capacity(self) -> int:
        return len(self.items)

    def plan(self, count: int) -> None:
        super().plan(count)
        remaining = {
            category: sum(len(queue) for queue in levels.values())
            for category, levels in self.queues.items()
        }
        schedule: list[WonderCategory] = []
        cycle_index = 0
        while len(schedule) < count:
            category = self.category_cycle[
                cycle_index % len(self.category_cycle)
            ]
            cycle_index += 1
            if remaining[category] <= 0:
                if cycle_index > count * len(self.category_cycle) * 2:
                    break
                continue
            schedule.append(category)
            remaining[category] -= 1
        if len(schedule) < count:
            for category in WonderCategory:
                while remaining[category] > 0 and len(schedule) < count:
                    schedule.append(category)
                    remaining[category] -= 1
        if len(schedule) != count:
            raise ValueError("Недостаточно уникальных вопросов wonders")
        self.schedule = schedule

    def next(self, serial: int) -> Question:
        if not self.schedule:
            raise ValueError("Очередь wonders не подготовлена")
        category = self.schedule.pop(0)
        levels = self.queues[category]
        available = {level for level, queue in levels.items() if queue}
        if self.context.difficulty is None:
            level = self.rng.choice(sorted(available))
            sampled_level: str | None = None
        else:
            level = self.difficulty.choose_available(
                self.context.difficulty,
                available,
                self.rng,
            )
            sampled_level = level
        item = levels[level].pop()
        question = self.strategy.create_item(
            item,
            self.items,
            self.context.candidate_pool,
            self.rng,
        )
        if sampled_level is not None:
            question.metadata["difficulty"] = sampled_level
        question.metadata["wonder_category"] = category.value
        return question


class QuestionFactory:
    """Реестр стратегий: новый режим добавляется без изменения движка."""

    def __init__(
        self,
        strategies: list[QuestionStrategy] | None = None,
        difficulty_catalog: DifficultyCatalog | None = None,
        wonder_catalog: WonderCatalog | None = None,
    ) -> None:
        self._difficulty = difficulty_catalog or DifficultyCatalog(
            CONFIGS_DIR / "difficulty_levels.json"
        )
        if strategies is None:
            strategies = [
                FlagQuestionStrategy(),
                CapitalQuestionStrategy(),
                PopulationQuestionStrategy(),
                CountryMapQuestionStrategy(),
                WaterQuestionStrategy(),
            ]
            if wonder_catalog is not None:
                strategies.append(WonderQuestionStrategy(wonder_catalog))
        self._strategies = {item.mode: item for item in strategies}

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
        if config.difficulty is not None and config.difficulty not in DIFFICULTY_KEYS:
            raise ValueError(f"Неизвестный уровень сложности: {config.difficulty}")
        self._difficulty.validate_countries(catalog.all())
        self._difficulty.validate_water_keys(
            {region.key for region in WATER_REGIONS}
        )
        context = QuestionBuildContext(
            catalog=catalog,
            candidate_pool=candidate_pool,
            subject_pool=subject_pool,
            continents=tuple(config.continents),
            wrong_isos=frozenset(wrong_isos or ()) if config.wrong_only else frozenset(),
            difficulty=config.difficulty,
        )
        prepared = {
            mode: self._strategies[mode].prepare(
                context,
                self._difficulty,
                rng,
            )
            for mode in dict.fromkeys(config.modes)
        }
        required = self._required_by_mode(config)
        self._ensure_capacity(
            required,
            {mode: pool.capacity for mode, pool in prepared.items()},
        )
        for mode, count in required.items():
            prepared[mode].plan(count)

        questions: list[Question] = []
        mode_serials: dict[str, int] = defaultdict(int)
        for serial in range(config.question_count):
            mode = config.modes[serial % len(config.modes)]
            mode_serial = mode_serials[mode]
            mode_serials[mode] += 1
            questions.append(prepared[mode].next(mode_serial))
        return questions

    def capacities(
        self,
        config: GameConfig,
        catalog: CountryCatalog,
        wrong_isos: list[str] | None = None,
    ) -> dict[str, int]:
        candidate_pool = catalog.by_continents(config.continents)
        subject_pool = candidate_pool.copy()
        if config.wrong_only and wrong_isos:
            wrong_set = set(wrong_isos)
            subject_pool = [
                country for country in subject_pool if country.iso3 in wrong_set
            ] or subject_pool
        context = QuestionBuildContext(
            catalog=catalog,
            candidate_pool=candidate_pool,
            subject_pool=subject_pool,
            continents=tuple(config.continents),
            wrong_isos=frozenset(wrong_isos or ()) if config.wrong_only else frozenset(),
            difficulty=config.difficulty,
        )
        return {
            mode: self._strategies[mode]
            .prepare(context, self._difficulty, random.Random(0))
            .capacity
            for mode in dict.fromkeys(config.modes)
        }

    def supports_count(
        self,
        config: GameConfig,
        catalog: CountryCatalog,
        question_count: int,
        wrong_isos: list[str] | None = None,
    ) -> bool:
        probe = GameConfig(
            config.modes,
            config.continents,
            question_count,
            wrong_only=config.wrong_only,
            difficulty=config.difficulty,
        )
        required = self._required_by_mode(probe)
        capacities = self.capacities(probe, catalog, wrong_isos)
        return all(
            required[mode] <= capacities.get(mode, 0)
            for mode in required
        )

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
