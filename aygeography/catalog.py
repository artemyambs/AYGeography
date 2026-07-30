from __future__ import annotations

import json
from pathlib import Path

from .models import Country


class CountryCatalog:
    """Единая точка доступа к неизменяемым справочным данным."""

    def __init__(self, countries_path: Path, continents_path: Path) -> None:
        raw_countries = json.loads(countries_path.read_text(encoding="utf-8"))
        invalid_population = [
            iso3
            for iso3, data in raw_countries.items()
            if not isinstance(data.get("population"), int)
            or int(data["population"]) <= 0
        ]
        if invalid_population:
            raise ValueError(
                "Некорректное население стран: "
                + ", ".join(sorted(invalid_population))
            )
        self._countries = {
            iso3: Country(
                iso3=iso3,
                name=data["name_ru"],
                name_en=data["name_en"],
                capital=data["capital"],
                continent=data["continent"],
                population=int(data["population"]),
                area=int(data["area"]),
                official_languages=tuple(
                    str(language)
                    for language in data["official_languages"]
                ),
            )
            for iso3, data in raw_countries.items()
        }
        self._continents: dict[str, list[str]] = json.loads(
            continents_path.read_text(encoding="utf-8")
        )

    def get(self, iso3: str) -> Country:
        return self._countries[iso3]

    def all(self) -> list[Country]:
        return list(self._countries.values())

    def by_continents(self, continents: list[str]) -> list[Country]:
        allowed = set(continents)
        return [
            country
            for country in self._countries.values()
            if country.continent in allowed
        ]

    @property
    def continents(self) -> dict[str, list[str]]:
        return self._continents.copy()
