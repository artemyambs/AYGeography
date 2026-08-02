from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ...catalog import CountryCatalog
from ...waters import WaterCatalog
from ...wonders import WonderCatalog


@dataclass(frozen=True, slots=True)
class ContentCatalogs:
    countries: CountryCatalog
    waters: WaterCatalog
    wonders: WonderCatalog


class ContentCatalogLoader:
    """Composition adapter for all validated offline learning catalogs."""

    def __init__(self, configs_dir: Path, assets_dir: Path) -> None:
        self._configs_dir = configs_dir
        self._assets_dir = assets_dir

    def load_countries(self) -> CountryCatalog:
        return CountryCatalog(
            self._configs_dir / "countries_by_iso3.json",
        )

    def load_waters(self, countries: CountryCatalog) -> WaterCatalog:
        return WaterCatalog(
            self._configs_dir / "water_area",
            countries.all(),
        )

    def load_wonders(self, countries: CountryCatalog) -> WonderCatalog:
        return WonderCatalog(
            self._configs_dir / "wonders",
            countries.all(),
            self._assets_dir,
        )

    def load(self) -> ContentCatalogs:
        countries = self.load_countries()
        return ContentCatalogs(
            countries=countries,
            waters=self.load_waters(countries),
            wonders=self.load_wonders(countries),
        )
