from __future__ import annotations

import textwrap
from types import MappingProxyType
from typing import Iterable, Mapping, Protocol

import pygame

from ..config import ASSETS_DIR
from ..domain.questions import PopulationContent
from .components import (
    CYAN_DARK,
    FONT_SIZES,
    PANEL,
    PANEL_ALT,
    SIDEBAR_WIDTH,
    TEXT,
    blit_image,
    draw_multiline,
    draw_text,
    panel,
)
from .layout import (
    CONTENT,
    COUNTRY_FLAG_CENTER_Y,
    COUNTRY_FLAG_NAME_FONT_SIZE,
    COUNTRY_FLAG_NAME_TOP,
    QUESTION_FLAG_PANEL_SIZE,
    blit_centered,
    draw_question_flag,
)


class QuestionPresenter(Protocol):
    def answer_rects(self) -> list[pygame.Rect]: ...

    def draw(self, surface: pygame.Surface, app, question) -> None: ...


class PopulationComparisonPresenter:
    key = "country_comparison"
    CARD_TOP = 175
    CARD_WIDTH = 430
    CARD_HEIGHT = 320
    CARD_GAP = 40
    ANSWER_TOP = 520

    @classmethod
    def answer_rects(cls) -> list[pygame.Rect]:
        total_width = cls.CARD_WIDTH * 2 + cls.CARD_GAP
        start_x = CONTENT.centerx - total_width // 2
        return [
            pygame.Rect(
                start_x + index * (cls.CARD_WIDTH + cls.CARD_GAP),
                cls.ANSWER_TOP,
                cls.CARD_WIDTH,
                58,
            )
            for index in range(2)
        ]

    @classmethod
    def draw(cls, surface: pygame.Surface, app, question) -> None:
        if not isinstance(question.content, PopulationContent):
            return
        countries_by_name = {
            app.catalog.get(iso3).name: app.catalog.get(iso3)
            for iso3 in question.subjects
        }
        for option, answer_rect in zip(question.options, cls.answer_rects()):
            country = countries_by_name.get(option)
            if country is None:
                continue
            card = pygame.Rect(
                answer_rect.left,
                cls.CARD_TOP,
                cls.CARD_WIDTH,
                cls.CARD_HEIGHT,
            )
            draw_text(
                surface,
                country.name,
                (card.centerx, card.top + 35),
                FONT_SIZES["country_card_title"],
                TEXT,
                bold=True,
                anchor="center",
            )
            draw_question_flag(
                surface,
                app,
                country.iso3,
                (card.centerx, card.top + 178),
            )


class WonderPresenter:
    owns_prompt = False
    ANSWER_WIDTH = 390
    ANSWER_GAP = 18

    @classmethod
    def answer_rects(cls) -> list[pygame.Rect]:
        columns = 3
        total_width = columns * cls.ANSWER_WIDTH + (columns - 1) * cls.ANSWER_GAP
        start_x = SIDEBAR_WIDTH + (CONTENT.width - total_width) // 2
        return [
            pygame.Rect(
                start_x + (index % columns) * (cls.ANSWER_WIDTH + cls.ANSWER_GAP),
                cls.answer_top + (index // columns) * 62,
                cls.ANSWER_WIDTH,
                50,
            )
            for index in range(6)
        ]


class WonderPhotoPresenter(WonderPresenter):
    answer_top = 610

    @classmethod
    def draw(cls, surface: pygame.Surface, app, question) -> None:
        target = pygame.Rect(535, 150, 730, 420)
        panel(surface, target, fill=PANEL, border=CYAN_DARK)
        image = app.assets.image(ASSETS_DIR / question.visual)
        scale = min(
            (target.width - 18) / image.get_width(),
            (target.height - 18) / image.get_height(),
        )
        size = (
            max(1, round(image.get_width() * scale)),
            max(1, round(image.get_height() * scale)),
        )
        rect = pygame.Rect((0, 0), size)
        rect.center = target.center
        blit_image(surface, image, rect)


class WonderMapPresenter(WonderPresenter):
    answer_top = 710

    @classmethod
    def draw(cls, surface: pygame.Surface, app, question) -> None:
        return


class WonderFactPresenter(WonderPresenter):
    owns_prompt = True
    ANSWER_COUNT = 2
    ANSWER_GAP = 24
    ANSWER_HEIGHT = 52
    FLAG_FACT_GAP = 20
    FACT_ANSWER_GAP = 30
    FACT_HEIGHT = 160
    TEXT_WRAP_WIDTH = 60

    @classmethod
    def answer_row_width(cls) -> int:
        return (
            cls.ANSWER_COUNT * cls.ANSWER_WIDTH
            + (cls.ANSWER_COUNT - 1) * cls.ANSWER_GAP
        )

    @classmethod
    def answer_start_x(cls) -> int:
        return CONTENT.centerx - cls.answer_row_width() // 2

    @classmethod
    def fact_rect(cls) -> pygame.Rect:
        flag_bottom = (
            COUNTRY_FLAG_CENTER_Y + QUESTION_FLAG_PANEL_SIZE[1] // 2
        )
        return pygame.Rect(
            cls.answer_start_x(),
            flag_bottom + cls.FLAG_FACT_GAP,
            cls.answer_row_width(),
            cls.FACT_HEIGHT,
        )

    @classmethod
    def answer_rects(cls) -> list[pygame.Rect]:
        answer_top = cls.fact_rect().bottom + cls.FACT_ANSWER_GAP
        return [
            pygame.Rect(
                cls.answer_start_x()
                + index * (cls.ANSWER_WIDTH + cls.ANSWER_GAP),
                answer_top,
                cls.ANSWER_WIDTH,
                cls.ANSWER_HEIGHT,
            )
            for index in range(cls.ANSWER_COUNT)
        ]

    @classmethod
    def draw(cls, surface: pygame.Surface, app, question) -> None:
        country = app.catalog.get(question.country_iso)
        draw_text(
            surface,
            country.name,
            (CONTENT.centerx, COUNTRY_FLAG_NAME_TOP),
            COUNTRY_FLAG_NAME_FONT_SIZE,
            TEXT,
            bold=True,
            anchor="midtop",
        )
        draw_question_flag(
            surface,
            app,
            question.country_iso,
            (CONTENT.centerx, COUNTRY_FLAG_CENTER_Y),
        )
        fact_rect = cls.fact_rect()
        panel(surface, fact_rect, fill=PANEL_ALT, border=CYAN_DARK)
        wrapped = "\n".join(
            textwrap.wrap(question.prompt, width=cls.TEXT_WRAP_WIDTH)
        )
        draw_multiline(
            surface,
            wrapped,
            fact_rect.inflate(-60, -32),
            FONT_SIZES["result_percent"],
            TEXT,
            bold=True,
            line_gap=7,
        )


class QuestionPresenterRegistry:
    """UI-side registry validated against declarative mode descriptors."""

    def __init__(
        self,
        presenters: Mapping[str, QuestionPresenter],
    ) -> None:
        self._presenters = dict(presenters)

    @classmethod
    def default(cls) -> QuestionPresenterRegistry:
        return cls(
            {
                PopulationComparisonPresenter.key: PopulationComparisonPresenter(),
                "wonder_landmark_name": WonderPhotoPresenter(),
                "wonder_landmark_country": WonderPhotoPresenter(),
                "wonder_map": WonderMapPresenter(),
                "wonder_fact": WonderFactPresenter(),
            }
        )

    def get(self, key: str) -> QuestionPresenter | None:
        return self._presenters.get(key)

    def validate(self, descriptors: Iterable[object]) -> None:
        declared = {
            key
            for descriptor in descriptors
            for key in getattr(descriptor, "presenter_keys", ())
        }
        missing = declared - set(self._presenters)
        undeclared = set(self._presenters) - declared
        if missing or undeclared:
            raise ValueError(
                "Некорректная регистрация presenters: "
                f"missing={sorted(missing)}, undeclared={sorted(undeclared)}"
            )

    @property
    def presenters(self) -> Mapping[str, QuestionPresenter]:
        return MappingProxyType(self._presenters)
