from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class MapOverlay:
    kind: str
    point: tuple[float, float] | None = None
    lines: tuple[tuple[tuple[float, float], ...], ...] = ()

    def to_state(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "point": list(self.point) if self.point else None,
            "lines": [
                [list(point) for point in line]
                for line in self.lines
            ],
        }

    @classmethod
    def from_state(cls, state: object) -> MapOverlay | None:
        if state is None:
            return None
        if isinstance(state, MapOverlay):
            return state
        if not isinstance(state, dict):
            raise ValueError("Некорректное описание слоя карты")
        point = state.get("point")
        parsed_point = (
            (float(point[0]), float(point[1]))
            if isinstance(point, (list, tuple)) and len(point) == 2
            else None
        )
        lines = tuple(
            tuple((float(item[0]), float(item[1])) for item in line)
            for line in state.get("lines", ())
        )
        return cls(str(state.get("kind", "")), parsed_point, lines)


class QuestionContent:
    kind: ClassVar[str]
    presenter_key: ClassVar[str] = "default"

    def to_state(self) -> dict[str, Any]:
        return {"kind": self.kind}


@dataclass(frozen=True, slots=True)
class ChoiceContent(QuestionContent):
    kind: ClassVar[str] = "choice"


@dataclass(frozen=True, slots=True)
class FlagContent(QuestionContent):
    flag_iso3: str
    capital_layout: bool = False
    kind: ClassVar[str] = "flag"

    def to_state(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "flag_iso3": self.flag_iso3,
            "capital_layout": self.capital_layout,
        }


@dataclass(frozen=True, slots=True)
class PopulationContent(QuestionContent):
    values: dict[str, int]
    pair_kind: str
    kind: ClassVar[str] = "population"
    presenter_key: ClassVar[str] = "country_comparison"

    def to_state(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "values": dict(self.values),
            "pair_kind": self.pair_kind,
        }


@dataclass(frozen=True, slots=True)
class MapContent(QuestionContent):
    highlight_country: str = ""
    water_area_key: str = ""
    water_area_kind: str = ""
    water_highlight: str = ""
    overlay: MapOverlay | None = None
    kind: ClassVar[str] = "map"

    def to_state(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "highlight_country": self.highlight_country,
            "water_area_key": self.water_area_key,
            "water_area_kind": self.water_area_kind,
            "water_highlight": self.water_highlight,
            "overlay": self.overlay.to_state() if self.overlay else None,
        }


@dataclass(frozen=True, slots=True)
class WonderContent(QuestionContent):
    category: str
    style: str
    image: str = ""
    overlay: MapOverlay | None = None
    kind: ClassVar[str] = "wonder"

    @property
    def presenter_key(self) -> str:
        return self.style

    def to_state(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "category": self.category,
            "style": self.style,
            "image": self.image,
            "overlay": self.overlay.to_state() if self.overlay else None,
        }


QuestionContentType = (
    ChoiceContent
    | FlagContent
    | PopulationContent
    | MapContent
    | WonderContent
)


def content_from_state(state: object) -> QuestionContentType:
    if not isinstance(state, dict):
        return ChoiceContent()
    kind = str(state.get("kind", "choice"))
    if kind == FlagContent.kind:
        return FlagContent(
            str(state.get("flag_iso3", "")),
            bool(state.get("capital_layout", False)),
        )
    if kind == PopulationContent.kind:
        values = state.get("values", {})
        return PopulationContent(
            {
                str(key): int(value)
                for key, value in values.items()
            }
            if isinstance(values, dict)
            else {},
            str(state.get("pair_kind", "")),
        )
    if kind == MapContent.kind:
        return MapContent(
            highlight_country=str(state.get("highlight_country", "")),
            water_area_key=str(state.get("water_area_key", "")),
            water_area_kind=str(state.get("water_area_kind", "")),
            water_highlight=str(state.get("water_highlight", "")),
            overlay=MapOverlay.from_state(state.get("overlay")),
        )
    if kind == WonderContent.kind:
        return WonderContent(
            category=str(state.get("category", "")),
            style=str(state.get("style", "default")),
            image=str(state.get("image", "")),
            overlay=MapOverlay.from_state(state.get("overlay")),
        )
    return ChoiceContent()


def legacy_content(state: dict[str, Any]) -> QuestionContentType:
    metadata = state.get("metadata")
    values = metadata if isinstance(metadata, dict) else {}
    presentation = str(
        state.get("presentation", values.get("presentation", "default"))
    )
    visual = str(state.get("visual", ""))
    if "population_values" in values:
        populations = values.get("population_values", {})
        return PopulationContent(
            {
                str(key): int(value)
                for key, value in populations.items()
            }
            if isinstance(populations, dict)
            else {},
            str(values.get("pair_kind", "")),
        )
    overlay = MapOverlay.from_state(values.get("map_overlay"))
    if presentation.startswith("wonder_"):
        return WonderContent(
            category=str(values.get("wonder_category", "")),
            style=presentation,
            image=visual,
            overlay=overlay,
        )
    if any(
        key in values
        for key in (
            "highlight",
            "water_area",
            "water_area_kind",
            "water_highlight",
            "map_overlay",
        )
    ):
        return MapContent(
            highlight_country=str(values.get("highlight", "")),
            water_area_key=str(values.get("water_area", "")),
            water_area_kind=str(values.get("water_area_kind", "")),
            water_highlight=str(values.get("water_highlight", "")),
            overlay=overlay,
        )
    if visual or values.get("capital_layout"):
        return FlagContent(visual, bool(values.get("capital_layout", False)))
    return ChoiceContent()


@dataclass(slots=True)
class Question:
    key: str
    mode: str
    prompt: str
    country_iso: str
    options: list[str] = field(default_factory=list)
    correct_answer: str = ""
    explanation: str = ""
    interaction: str = "choices"
    content: QuestionContentType = field(default_factory=ChoiceContent)
    country_isos: tuple[str, ...] = field(default_factory=tuple)
    sampled_difficulty: str | None = None
    scoring_difficulty: str | None = None

    @property
    def subjects(self) -> tuple[str, ...]:
        return self.country_isos or (self.country_iso,)

    @property
    def presenter_key(self) -> str:
        return self.content.presenter_key

    @property
    def visual(self) -> str:
        if isinstance(self.content, FlagContent):
            return self.content.flag_iso3
        if isinstance(self.content, WonderContent):
            return self.content.image
        return ""

    @property
    def map_overlay(self) -> MapOverlay | None:
        if isinstance(self.content, (MapContent, WonderContent)):
            return self.content.overlay
        return None

    def to_state(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "mode": self.mode,
            "prompt": self.prompt,
            "country_iso": self.country_iso,
            "options": list(self.options),
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "interaction": self.interaction,
            "content": self.content.to_state(),
            "country_isos": list(self.country_isos),
            "sampled_difficulty": self.sampled_difficulty,
            "scoring_difficulty": self.scoring_difficulty,
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> Question:
        content = (
            content_from_state(state.get("content"))
            if "content" in state
            else legacy_content(state)
        )
        metadata = state.get("metadata")
        legacy_difficulty = (
            metadata.get("difficulty")
            if isinstance(metadata, dict)
            else None
        )
        return cls(
            key=str(state["key"]),
            mode=str(state["mode"]),
            prompt=str(state["prompt"]),
            country_iso=str(state["country_iso"]),
            options=[str(value) for value in state.get("options", ())],
            correct_answer=str(state.get("correct_answer", "")),
            explanation=str(state.get("explanation", "")),
            interaction=str(state.get("interaction", "choices")),
            content=content,
            country_isos=tuple(
                str(value) for value in state.get("country_isos", ())
            ),
            sampled_difficulty=state.get(
                "sampled_difficulty",
                legacy_difficulty,
            ),
            scoring_difficulty=state.get("scoring_difficulty"),
        )
