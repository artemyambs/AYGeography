from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pygame


@dataclass(frozen=True, slots=True)
class UITheme:
    """Validated access to the application's shared visual design tokens."""

    colours: Mapping[str, str]
    layout: Mapping[str, Any]
    typography: Mapping[str, Any]
    components: Mapping[str, Mapping[str, Any]]
    visualizations: Mapping[str, Any]

    @classmethod
    def from_settings(cls, settings: Mapping[str, Any]) -> UITheme:
        sections = {
            name: settings.get(name)
            for name in ("layout", "typography", "components", "visualizations")
        }
        invalid = [name for name, value in sections.items() if not isinstance(value, dict)]
        if invalid:
            raise ValueError(
                "Некорректные разделы UI-конфигурации: " + ", ".join(invalid)
            )
        colours = settings.get("colours")
        if not isinstance(colours, dict):
            raise ValueError("UI-конфигурация должна содержать палитру colours")
        return cls(
            colours=dict(colours),
            layout=dict(sections["layout"]),
            typography=dict(sections["typography"]),
            components={
                str(name): dict(value)
                for name, value in sections["components"].items()
                if isinstance(value, dict)
            },
            visualizations=dict(sections["visualizations"]),
        )

    def colour(self, name: str) -> pygame.Color:
        try:
            return pygame.Color(self.colours[name])
        except KeyError as error:
            raise KeyError(f"Неизвестный цвет интерфейса: {name}") from error

    def font_size(self, name: str) -> int:
        sizes = self.typography.get("sizes", {})
        try:
            return int(sizes[name])
        except (KeyError, TypeError, ValueError) as error:
            raise KeyError(f"Неизвестный размер текста: {name}") from error

    def component(self, name: str) -> Mapping[str, Any]:
        try:
            return self.components[name]
        except KeyError as error:
            raise KeyError(f"Неизвестный UI-компонент: {name}") from error

    def component_size(self, name: str) -> tuple[int, int]:
        raw = self.component(name).get("size")
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError(f"Компонент {name} должен содержать size из двух чисел")
        return int(raw[0]), int(raw[1])
