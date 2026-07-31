from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

import pygame

from .difficulty import DIFFICULTY_KEYS
from .models import Country


class WonderCategory(StrEnum):
    LANDMARK = "landmark"
    PEAK = "peak"
    FACT = "fact"


EXPECTED_COUNTS = {
    WonderCategory.LANDMARK: 75,
    WonderCategory.PEAK: 15,
    WonderCategory.FACT: 195,
}

EXPECTED_DIFFICULTY_COUNTS = {
    WonderCategory.LANDMARK: {
        "easy": 25,
        "medium": 25,
        "hard": 25,
    },
    WonderCategory.PEAK: {
        "easy": 5,
        "medium": 5,
        "hard": 5,
    },
    WonderCategory.FACT: {
        "easy": 65,
        "medium": 65,
        "hard": 65,
    },
}

CONTENT_FILES = {
    WonderCategory.FACT: "fact.json",
    WonderCategory.LANDMARK: "landmark.json",
    WonderCategory.PEAK: "peak.json",
}


@dataclass(frozen=True, slots=True)
class WonderItem:
    key: str
    category: WonderCategory
    name: str
    country_isos: tuple[str, ...]
    continents: tuple[str, ...]
    difficulty: str
    explanation: str
    image: str = ""
    prompt: str = ""
    point: tuple[float, float] | None = None
    source: str = ""
    source_url: str = ""

    @property
    def country_iso(self) -> str:
        return self.country_isos[0]


class WonderCatalog:
    """Loads and validates the complete offline content set."""

    def __init__(
        self,
        path: Path,
        countries: Iterable[Country],
        assets_dir: Path,
    ) -> None:
        self.path = path
        self.assets_dir = assets_dir
        self._countries = {country.iso3: country for country in countries}
        self._items = tuple(
            self._parse(item)
            for category, file_name in CONTENT_FILES.items()
            for item in self._load_file(category, file_name)
        )
        self._validate()

    def all(self) -> list[WonderItem]:
        return list(self._items)

    def by_category(self, category: WonderCategory) -> list[WonderItem]:
        return [item for item in self._items if item.category == category]

    def facts_by_country(self) -> dict[str, WonderItem]:
        return {
            iso3: item
            for item in self.by_category(WonderCategory.FACT)
            for iso3 in item.country_isos
        }

    def country_name(self, iso3: str) -> str:
        return self._countries[iso3].name

    def eligible(
        self,
        continents: Iterable[str],
        wrong_isos: Iterable[str] | None = None,
    ) -> list[WonderItem]:
        selected = set(continents)
        result = [
            item
            for item in self._items
            if selected.intersection(item.continents)
        ]
        wrong = set(wrong_isos or ())
        if wrong:
            mistakes = [
                item for item in result if wrong.intersection(item.country_isos)
            ]
            if mistakes:
                return mistakes
        return result

    def _load_file(
        self,
        category: WonderCategory,
        file_name: str,
    ) -> list[dict[str, Any]]:
        file_path = self.path / file_name
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{file_name} должен содержать список")
        if any(
            not isinstance(item, dict)
            or item.get("category") != category.value
            for item in raw
        ):
            raise ValueError(
                f"{file_name} должен содержать только {category.value}"
            )
        return raw

    def _parse(self, raw: dict[str, Any]) -> WonderItem:
        category = WonderCategory(str(raw["category"]))
        point = raw.get("point")
        parsed_point = (
            (float(point[0]), float(point[1])) if point is not None else None
        )
        return WonderItem(
            key=str(raw["id"]),
            category=category,
            name=str(raw["name"]).strip(),
            country_isos=tuple(str(value) for value in raw["country_isos"]),
            continents=tuple(str(value) for value in raw["continents"]),
            difficulty=str(raw["difficulty"]),
            explanation=self._with_country_context(
                str(raw["explanation"]).strip(),
                tuple(str(value) for value in raw["country_isos"]),
            ),
            image=str(raw.get("image", "")),
            prompt=str(raw.get("prompt", "")).strip(),
            point=parsed_point,
            source=str(raw.get("source", "")).strip(),
            source_url=str(raw.get("source_url", "")).strip(),
        )

    def _validate(self) -> None:
        keys = [item.key for item in self._items]
        if len(keys) != len(set(keys)):
            raise ValueError("ID объектов wonders должны быть уникальны")
        counts = Counter(item.category for item in self._items)
        if counts != Counter(EXPECTED_COUNTS):
            raise ValueError(f"Некорректное количество wonders: {dict(counts)}")
        for category, expected in EXPECTED_DIFFICULTY_COUNTS.items():
            category_counts = Counter(
                item.difficulty
                for item in self._items
                if item.category == category
            )
            if category_counts != Counter(expected):
                raise ValueError(
                    f"Некорректная сложность {category}: {dict(category_counts)}"
                )
        valid_continents = {
            country.continent for country in self._countries.values()
        }
        for item in self._items:
            self._validate_item(item, valid_continents)
        for category in WonderCategory:
            answers = {
                item.name
                for item in self._items
                if item.category == category
            }
            if (
                category != WonderCategory.FACT
                and len(answers) != counts[category]
            ):
                raise ValueError(
                    f"Названия объектов должны быть уникальны: {category}"
                )
            if len(answers) < 6:
                raise ValueError(
                    f"Недостаточно уникальных ответов: {category}"
                )
        fact_prompts = {
            item.prompt
            for item in self._items
            if item.category == WonderCategory.FACT
        }
        if len(fact_prompts) != counts[WonderCategory.FACT]:
            raise ValueError("Тексты фактов должны быть уникальны")
        covered_countries = {
            iso3
            for item in self._items
            if item.category == WonderCategory.FACT
            for iso3 in item.country_isos
        }
        missing_facts = set(self._countries) - covered_countries
        if missing_facts:
            raise ValueError(
                "Нет фактов для стран: "
                + ", ".join(sorted(missing_facts))
            )
        for continent in valid_continents:
            available = [
                item for item in self._items if continent in item.continents
            ]
            if len(available) < 10:
                raise ValueError(
                    f"Для континента {continent} доступно меньше 10 wonders"
                )
            country_answers = {
                country.name
                for country in self._countries.values()
                if country.continent == continent
            }
            if len(country_answers) < 6:
                raise ValueError(
                    f"Для континента {continent} недостаточно стран-ответов"
                )

    def _validate_item(
        self,
        item: WonderItem,
        valid_continents: set[str],
    ) -> None:
        if not item.key or not item.name or not item.explanation:
            raise ValueError(f"Неполная карточка wonders: {item.key}")
        if item.difficulty not in DIFFICULTY_KEYS:
            raise ValueError(f"Некорректная сложность: {item.key}")
        if not item.country_isos or not set(item.country_isos) <= set(
            self._countries
        ):
            raise ValueError(f"Некорректные ISO3: {item.key}")
        if not item.continents or not set(item.continents) <= valid_continents:
            raise ValueError(f"Некорректные континенты: {item.key}")
        if item.category == WonderCategory.LANDMARK:
            self._validate_image(item)
        elif item.category == WonderCategory.PEAK:
            self._validate_point(item)
        elif item.category == WonderCategory.FACT and not item.prompt:
            raise ValueError(f"Для факта отсутствует текст: {item.key}")

    def _with_country_context(
        self,
        explanation: str,
        country_isos: tuple[str, ...],
    ) -> str:
        country_names = [self.country_name(iso3) for iso3 in country_isos]
        missing = [name for name in country_names if name not in explanation]
        if not missing:
            return explanation
        label = "Страна" if len(country_names) == 1 else "Страны"
        return f"{label}: {', '.join(country_names)}. {explanation}"

    def _validate_image(self, item: WonderItem) -> None:
        path = self.assets_dir / item.image
        if not item.image or not path.is_file():
            raise ValueError(f"Не найдено изображение: {item.key}")
        try:
            pygame.image.load(path)
        except pygame.error as error:
            raise ValueError(f"Не читается изображение: {item.key}") from error

    @staticmethod
    def _validate_coordinate(point: tuple[float, float]) -> None:
        longitude, latitude = point
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError(f"Некорректные координаты: {point}")

    def _validate_point(self, item: WonderItem) -> None:
        if item.point is None:
            raise ValueError(f"Для вершины нет точки: {item.key}")
        self._validate_coordinate(item.point)
