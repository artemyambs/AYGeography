from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .difficulty import DIFFICULTY_KEYS
from .domain.questions import MapOverlay
from .models import Country


@dataclass(frozen=True, slots=True)
class WaterArea:
    key: str
    name: str
    kind: str
    label: str
    prompt: str
    difficulty: str
    shape: str
    longitude: float = 0.0
    latitude: float = 0.0
    radius_x: float = 0.0
    radius_y: float = 0.0
    country_isos: tuple[str, ...] = ()
    continents: tuple[str, ...] = ()
    explanation: str = ""
    lines: tuple[tuple[tuple[float, float], ...], ...] = ()

    @property
    def center(self) -> tuple[float, float]:
        if self.shape in {"ellipse", "point"}:
            return self.longitude, self.latitude
        points = [point for line in self.lines for point in line]
        return (
            (min(point[0] for point in points) + max(point[0] for point in points)) / 2,
            (min(point[1] for point in points) + max(point[1] for point in points)) / 2,
        )

    @property
    def country_iso(self) -> str | None:
        return self.country_isos[0] if self.country_isos else None

    @property
    def map_overlay(self) -> MapOverlay | None:
        if self.shape == "point":
            return MapOverlay(
                kind="point",
                point=(self.longitude, self.latitude),
            )
        if self.shape == "line":
            return MapOverlay(kind="line", lines=self.lines)
        return None


# Backward-compatible domain name for imports outside the package.
WaterRegion = WaterArea


class WaterCatalog:
    """Loads every water type from an independent configuration file."""

    def __init__(
        self,
        path: Path,
        countries: Iterable[Country] = (),
    ) -> None:
        self.path = path
        self._country_isos = {country.iso3 for country in countries}
        self._continents = {country.continent for country in countries}
        self._items = tuple(
            item
            for file_path in sorted(path.glob("*.json"))
            for item in self._load_file(file_path)
        )
        self._by_key = {item.key: item for item in self._items}
        self._validate()

    def all(self) -> list[WaterArea]:
        return list(self._items)

    def get(self, key: str) -> WaterArea | None:
        return self._by_key.get(key)

    def by_kind(self, kind: str) -> list[WaterArea]:
        return [item for item in self._items if item.kind == kind]

    def _load_file(self, file_path: Path) -> list[WaterArea]:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("items"), list):
            raise ValueError(f"{file_path.name} должен содержать объект с items")
        kind = str(raw.get("kind", "")).strip()
        label = str(raw.get("label", "")).strip()
        prompt = str(raw.get("prompt", "")).strip()
        shape = str(raw.get("shape", "")).strip()
        if not all((kind, label, prompt)) or shape not in {
            "ellipse",
            "line",
            "point",
        }:
            raise ValueError(f"Некорректное описание типа воды: {file_path.name}")
        return [
            self._parse_item(item, kind, label, prompt, shape, file_path.name)
            for item in raw["items"]
        ]

    @staticmethod
    def _parse_item(
        raw: dict[str, Any],
        kind: str,
        label: str,
        prompt: str,
        shape: str,
        file_name: str,
    ) -> WaterArea:
        if not isinstance(raw, dict):
            raise ValueError(f"Некорректная карточка воды: {file_name}")
        center = raw.get("center", (0, 0))
        radius = raw.get("radius", (0, 0))
        lines = tuple(
            tuple((float(point[0]), float(point[1])) for point in line)
            for line in raw.get("lines", ())
        )
        return WaterArea(
            key=str(raw["id"]).strip(),
            name=str(raw["name"]).strip(),
            kind=kind,
            label=label,
            prompt=prompt,
            difficulty=str(raw["difficulty"]).strip(),
            shape=shape,
            longitude=float(center[0]),
            latitude=float(center[1]),
            radius_x=float(radius[0]),
            radius_y=float(radius[1]),
            country_isos=tuple(str(value) for value in raw.get("country_isos", ())),
            continents=tuple(str(value) for value in raw.get("continents", ())),
            explanation=str(raw.get("explanation", "")).strip(),
            lines=lines,
        )

    def _validate(self) -> None:
        if not self._items:
            raise ValueError("Каталог акватории пуст")
        keys = [item.key for item in self._items]
        if len(keys) != len(set(keys)):
            raise ValueError("ID водных объектов должны быть уникальны")
        for item in self._items:
            if not item.key or not item.name:
                raise ValueError("Неполная карточка водного объекта")
            if item.difficulty not in DIFFICULTY_KEYS:
                raise ValueError(f"Некорректная сложность: {item.key}")
            if self._country_isos and not set(item.country_isos) <= self._country_isos:
                raise ValueError(f"Некорректные ISO3: {item.key}")
            if self._continents and not set(item.continents) <= self._continents:
                raise ValueError(f"Некорректные континенты: {item.key}")
            if item.shape == "ellipse":
                self._validate_ellipse(item)
            elif item.shape == "line":
                self._validate_lines(item)
            else:
                self._validate_coordinate((item.longitude, item.latitude))

    @staticmethod
    def _validate_coordinate(point: tuple[float, float]) -> None:
        longitude, latitude = point
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise ValueError(f"Некорректные координаты: {point}")

    def _validate_ellipse(self, item: WaterArea) -> None:
        self._validate_coordinate((item.longitude, item.latitude))
        if item.radius_x <= 0 or item.radius_y <= 0:
            raise ValueError(f"Некорректный радиус водного объекта: {item.key}")

    def _validate_lines(self, item: WaterArea) -> None:
        if not item.lines or any(len(line) < 2 for line in item.lines):
            raise ValueError(f"Для водного объекта нет корректной линии: {item.key}")
        for line in item.lines:
            for point in line:
                self._validate_coordinate(point)
