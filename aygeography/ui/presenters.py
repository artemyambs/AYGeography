from __future__ import annotations

import textwrap

import pygame

from ..config import ASSETS_DIR
from ..domain.questions import PopulationContent
from .components import (
    CYAN_DARK,
    PANEL,
    PANEL_ALT,
    SIDEBAR_WIDTH,
    TEXT,
    blit_image,
    draw_multiline,
    draw_text,
    panel,
)
from .layout import CONTENT, blit_centered, draw_question_flag


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
                24,
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
    answer_top = 540

    @classmethod
    def draw(cls, surface: pygame.Surface, app, question) -> None:
        fact_rect = pygame.Rect(450, 180, 940, 270)
        panel(surface, fact_rect, fill=PANEL_ALT, border=CYAN_DARK)
        wrapped = "\n".join(textwrap.wrap(question.prompt, width=58))
        draw_multiline(
            surface,
            wrapped,
            fact_rect.inflate(-70, -45),
            25,
            TEXT,
            bold=True,
            line_gap=10,
        )


QUESTION_PRESENTERS = {
    PopulationComparisonPresenter.key: PopulationComparisonPresenter(),
    "wonder_landmark_name": WonderPhotoPresenter(),
    "wonder_landmark_country": WonderPhotoPresenter(),
    "wonder_map": WonderMapPresenter(),
    "wonder_fact": WonderFactPresenter(),
}
