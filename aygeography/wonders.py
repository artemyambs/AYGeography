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
    RIVER = "river"
    FACT = "fact"


EXPECTED_COUNTS = {
    WonderCategory.LANDMARK: 45,
    WonderCategory.PEAK: 15,
    WonderCategory.RIVER: 30,
    WonderCategory.FACT: 30,
}

EXPECTED_DIFFICULTY_COUNTS = {
    WonderCategory.LANDMARK: 15,
    WonderCategory.PEAK: 5,
    WonderCategory.RIVER: 10,
    WonderCategory.FACT: 10,
}

CONTENT_FILES = {
    WonderCategory.FACT: "fact.json",
    WonderCategory.RIVER: "river.json",
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
    lines: tuple[tuple[tuple[float, float], ...], ...] = ()

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
        lines = tuple(
            tuple((float(point[0]), float(point[1])) for point in line)
            for line in raw.get("lines", ())
        )
        return WonderItem(
            key=str(raw["id"]),
            category=category,
            name=str(raw["name"]).strip(),
            country_isos=tuple(str(value) for value in raw["country_isos"]),
            continents=tuple(str(value) for value in raw["continents"]),
            difficulty=str(raw["difficulty"]),
            explanation=str(raw["explanation"]).strip(),
            image=str(raw.get("image", "")),
            prompt=str(raw.get("prompt", "")).strip(),
            point=parsed_point,
            lines=lines,
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
            if category_counts != Counter(
                {level: expected for level in DIFFICULTY_KEYS}
            ):
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
            if len(answers) < 6:
                raise ValueError(
                    f"Недостаточно уникальных ответов: {category}"
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
        elif item.category == WonderCategory.RIVER:
            self._validate_lines(item)
        elif item.category == WonderCategory.FACT and not item.prompt:
            raise ValueError(f"Для факта отсутствует текст: {item.key}")

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

    def _validate_lines(self, item: WonderItem) -> None:
        if not item.lines or any(len(line) < 2 for line in item.lines):
            raise ValueError(f"Для реки нет корректной линии: {item.key}")
        for line in item.lines:
            for point in line:
                self._validate_coordinate(point)
