from __future__ import annotations

from types import MappingProxyType
from typing import Callable, Mapping, Protocol


class Screen(Protocol):
    def __init__(self, app) -> None: ...


ScreenFactory = Callable[[object], Screen]


class ScreenRegistry:
    """Typed navigation registry independent from the application runtime."""

    def __init__(self, factories: Mapping[str, ScreenFactory]) -> None:
        if not factories:
            raise ValueError("Должен быть зарегистрирован хотя бы один экран")
        self._factories = dict(factories)

    def create(self, key: str, app: object) -> Screen:
        try:
            factory = self._factories[key]
        except KeyError as error:
            raise ValueError(f"Неизвестный экран: {key}") from error
        return factory(app)

    def register(self, key: str, factory: ScreenFactory) -> None:
        if key in self._factories:
            raise ValueError(f"Экран уже зарегистрирован: {key}")
        self._factories[key] = factory

    @property
    def factories(self) -> Mapping[str, ScreenFactory]:
        return MappingProxyType(self._factories)
