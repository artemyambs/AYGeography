from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class ModeDefinition:
    """Complete declarative description of one game mode."""

    key: str
    title: str
    icon: str
    correct_feedback_seconds: float
    incorrect_feedback_seconds: float

    def feedback_seconds(self, is_correct: bool) -> float:
        return (
            self.correct_feedback_seconds
            if is_correct
            else self.incorrect_feedback_seconds
        )


class ModeRegistry:
    """Single source of truth for mode metadata and strategies."""

    def __init__(
        self,
        definitions: Iterable[ModeDefinition],
        strategies: Iterable[Any] = (),
        feedback_variants: Mapping[str, object] | None = None,
    ) -> None:
        ordered = tuple(definitions)
        definitions_by_key = {item.key: item for item in ordered}
        if not ordered or len(definitions_by_key) != len(ordered):
            raise ValueError("Игровые режимы должны иметь уникальные ключи")
        self._ordered = ordered
        self._definitions: Mapping[str, ModeDefinition] = MappingProxyType(
            definitions_by_key
        )
        self._strategies: dict[str, Any] = {}
        self._feedback_variants = self._parse_feedback_variants(
            feedback_variants or {}
        )
        for strategy in strategies:
            self.register_strategy(strategy)

    @classmethod
    def from_settings(
        cls,
        labels: Mapping[str, object],
        feedback: Mapping[str, object],
        strategies: Iterable[Any] = (),
        feedback_variants: Mapping[str, object] | None = None,
    ) -> ModeRegistry:
        if set(labels) != set(feedback):
            raise ValueError(
                "Названия и задержки должны быть заданы для одинаковых режимов"
            )
        definitions: list[ModeDefinition] = []
        for key, title in labels.items():
            values = feedback[key]
            if not isinstance(values, Mapping) or set(values) != {
                "correct",
                "incorrect",
            }:
                raise ValueError(
                    f"Некорректные задержки ответов для режима: {key}"
                )
            correct = float(values["correct"])
            incorrect = float(values["incorrect"])
            if correct <= 0 or incorrect <= 0:
                raise ValueError(
                    f"Задержка ответа должна быть положительной: {key}"
                )
            definitions.append(
                ModeDefinition(
                    key=str(key),
                    title=str(title),
                    icon=str(key),
                    correct_feedback_seconds=correct,
                    incorrect_feedback_seconds=incorrect,
                )
            )
        return cls(definitions, strategies, feedback_variants)

    @staticmethod
    def _parse_feedback_variants(
        values: Mapping[str, object],
    ) -> Mapping[str, tuple[float, float]]:
        result: dict[str, tuple[float, float]] = {}
        for key, raw in values.items():
            if not isinstance(raw, Mapping) or set(raw) != {
                "correct",
                "incorrect",
            }:
                raise ValueError(
                    f"Некорректные задержки варианта: {key}"
                )
            correct = float(raw["correct"])
            incorrect = float(raw["incorrect"])
            if correct <= 0 or incorrect <= 0:
                raise ValueError(
                    f"Задержка варианта должна быть положительной: {key}"
                )
            result[str(key)] = correct, incorrect
        return MappingProxyType(result)

    @property
    def definitions(self) -> tuple[ModeDefinition, ...]:
        return self._ordered

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self._ordered)

    @property
    def names(self) -> Mapping[str, str]:
        return MappingProxyType(
            {item.key: item.title for item in self._ordered}
        )

    def definition(self, key: str) -> ModeDefinition:
        try:
            return self._definitions[key]
        except KeyError as error:
            raise ValueError(f"Неизвестный игровой режим: {key}") from error

    def register_strategy(self, strategy: Any) -> None:
        key = str(strategy.mode)
        self.definition(key)
        if key in self._strategies:
            raise ValueError(f"Стратегия режима уже зарегистрирована: {key}")
        self._strategies[key] = strategy

    def strategy(self, key: str) -> Any:
        self.definition(key)
        try:
            return self._strategies[key]
        except KeyError as error:
            raise ValueError(f"Для режима не зарегистрирована стратегия: {key}") from error

    def strategies(self) -> Mapping[str, Any]:
        return MappingProxyType(self._strategies)

    def feedback_seconds(
        self,
        key: str,
        is_correct: bool,
        variant: str = "",
    ) -> float:
        if variant in self._feedback_variants:
            correct, incorrect = self._feedback_variants[variant]
            return correct if is_correct else incorrect
        return self.definition(key).feedback_seconds(is_correct)
