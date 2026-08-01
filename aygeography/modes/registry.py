from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Iterable, Literal, Mapping, Protocol


class ModeStrategy(Protocol):
    """Minimal contract owned by the mode registry."""

    mode: str


MasteryScope = Literal["country", "none"]


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


@dataclass(frozen=True, slots=True)
class ModeDescriptor:
    """One registration unit for gameplay, UI presentation and progression."""

    definition: ModeDefinition
    strategy: ModeStrategy | None = None
    presenter_keys: tuple[str, ...] = ()
    mastery_scope: MasteryScope = "country"

    @property
    def key(self) -> str:
        return self.definition.key


class ModeRegistry:
    """Single source of truth for mode metadata and strategies."""

    def __init__(
        self,
        definitions: Iterable[ModeDefinition],
        strategies: Iterable[ModeStrategy] = (),
        feedback_variants: Mapping[str, object] | None = None,
        presenter_keys: Mapping[str, tuple[str, ...]] | None = None,
        mastery_scopes: Mapping[str, MasteryScope] | None = None,
    ) -> None:
        ordered = tuple(definitions)
        definitions_by_key = {item.key: item for item in ordered}
        if not ordered or len(definitions_by_key) != len(ordered):
            raise ValueError("Игровые режимы должны иметь уникальные ключи")
        self._ordered = ordered
        self._definitions: Mapping[str, ModeDefinition] = MappingProxyType(
            definitions_by_key
        )
        presenter_keys = presenter_keys or {}
        mastery_scopes = mastery_scopes or {}
        unknown_metadata = (
            set(presenter_keys) | set(mastery_scopes)
        ) - set(definitions_by_key)
        if unknown_metadata:
            raise ValueError(
                f"Метаданные заданы для неизвестных режимов: {sorted(unknown_metadata)}"
            )
        self._descriptors: dict[str, ModeDescriptor] = {
            item.key: ModeDescriptor(
                definition=item,
                presenter_keys=tuple(presenter_keys.get(item.key, ())),
                mastery_scope=mastery_scopes.get(item.key, "country"),
            )
            for item in ordered
        }
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
        strategies: Iterable[ModeStrategy] = (),
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

    @classmethod
    def from_mode_settings(
        cls,
        settings: Mapping[str, object],
        strategies: Iterable[ModeStrategy] = (),
        feedback_variants: Mapping[str, object] | None = None,
    ) -> ModeRegistry:
        definitions: list[ModeDefinition] = []
        presenter_keys: dict[str, tuple[str, ...]] = {}
        mastery_scopes: dict[str, MasteryScope] = {}
        for key, raw in settings.items():
            if not isinstance(raw, Mapping):
                raise ValueError(f"Некорректное описание режима: {key}")
            feedback = raw.get("feedback")
            if not isinstance(feedback, Mapping) or set(feedback) != {
                "correct",
                "incorrect",
            }:
                raise ValueError(f"Некорректная обратная связь режима: {key}")
            correct = float(feedback["correct"])
            incorrect = float(feedback["incorrect"])
            if correct <= 0 or incorrect <= 0:
                raise ValueError(f"Задержка режима должна быть положительной: {key}")
            raw_presenters = raw.get("presenters", ())
            if not isinstance(raw_presenters, list) or not all(
                isinstance(value, str) for value in raw_presenters
            ):
                raise ValueError(f"Некорректные presenters режима: {key}")
            scope = str(raw.get("mastery_scope", "country"))
            if scope not in ("country", "none"):
                raise ValueError(f"Некорректный mastery_scope режима: {key}")
            definitions.append(
                ModeDefinition(
                    key=str(key),
                    title=str(raw.get("title", key)),
                    icon=str(raw.get("icon", key)),
                    correct_feedback_seconds=correct,
                    incorrect_feedback_seconds=incorrect,
                )
            )
            presenter_keys[str(key)] = tuple(raw_presenters)
            mastery_scopes[str(key)] = scope
        return cls(
            definitions,
            strategies,
            feedback_variants,
            presenter_keys,
            mastery_scopes,
        )

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
    def descriptors(self) -> tuple[ModeDescriptor, ...]:
        return tuple(self._descriptors[item.key] for item in self._ordered)

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

    def register_strategy(self, strategy: ModeStrategy) -> None:
        key = str(strategy.mode)
        self.definition(key)
        descriptor = self._descriptors[key]
        if descriptor.strategy is not None:
            raise ValueError(f"Стратегия режима уже зарегистрирована: {key}")
        self._descriptors[key] = replace(descriptor, strategy=strategy)

    def strategy(self, key: str) -> ModeStrategy:
        self.definition(key)
        strategy = self._descriptors[key].strategy
        if strategy is None:
            raise ValueError(f"Для режима не зарегистрирована стратегия: {key}")
        return strategy

    def strategies(self) -> Mapping[str, ModeStrategy]:
        return MappingProxyType(
            {
                key: descriptor.strategy
                for key, descriptor in self._descriptors.items()
                if descriptor.strategy is not None
            }
        )

    def descriptor(self, key: str) -> ModeDescriptor:
        self.definition(key)
        return self._descriptors[key]

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
