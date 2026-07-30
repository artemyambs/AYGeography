from __future__ import annotations

import math
import textwrap
from pathlib import Path
from typing import Any

import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UITextEntryLine

from ..config import (
    ANSWER_FEEDBACK_SECONDS,
    ASSETS_DIR,
    CONTINENT_NAMES,
    DIFFICULTY_NAMES,
    MODE_NAMES,
    QUESTION_TIME_SECONDS,
)
from ..formatting import format_population
from ..models import GameConfig, RoundResult
from ..quiz import GameSession
from .components import (
    BG,
    BORDER,
    CYAN,
    CYAN_DARK,
    FOOTER_HEIGHT,
    GREEN,
    GREEN_DARK,
    LOGICAL_SIZE,
    MUTED,
    PANEL,
    PANEL_ALT,
    RED,
    SIDEBAR,
    SIDEBAR_WIDTH,
    TEXT,
    YELLOW,
    MapCamera,
    blit_image,
    draw_button,
    draw_checkbox,
    draw_earth_hero,
    draw_footer,
    draw_logo,
    draw_question_count_icon,
    draw_multiline,
    draw_native_arc,
    draw_native_circle,
    draw_native_ellipse,
    draw_native_line,
    draw_native_polygon,
    draw_native_rect,
    draw_sidebar,
    draw_text,
    font,
    panel,
    physical_rect,
    render_scale,
)

CONTENT = pygame.Rect(SIDEBAR_WIDTH, 0, LOGICAL_SIZE[0] - SIDEBAR_WIDTH, LOGICAL_SIZE[1] - FOOTER_HEIGHT)
GAMEPLAY_AREA = pygame.Rect(
    CONTENT.left,
    70,
    CONTENT.width,
    CONTENT.height - 70,
)
PRIMARY_ACTION_SIZE = (280, 60)
PRIMARY_ACTION_FONT_SIZE = 19
QUESTION_FLAG_IMAGE_SIZE = (280, 180)
QUESTION_FLAG_PANEL_SIZE = (300, 200)
CAPITAL_LABEL_FONT_SIZE = 26


def primary_action_rect(center_x: int, top: int) -> pygame.Rect:
    rect = pygame.Rect((0, top), PRIMARY_ACTION_SIZE)
    rect.centerx = center_x
    return rect


def blit_centered(
    surface: pygame.Surface,
    image: pygame.Surface,
    center: tuple[int, int],
    size: tuple[int, int] | None = None,
) -> pygame.Rect:
    if size is None:
        scale = render_scale(surface)
        size = (
            max(1, round(image.get_width() / scale)),
            max(1, round(image.get_height() / scale)),
        )
    rect = pygame.Rect((0, 0), size)
    rect.center = center
    return blit_image(surface, image, rect)


def draw_question_flag(
    surface: pygame.Surface,
    app,
    iso3: str,
    center: tuple[int, int],
) -> pygame.Rect:
    """Draws the shared framed flag used by all flag-based questions."""
    flag_panel = pygame.Rect((0, 0), QUESTION_FLAG_PANEL_SIZE)
    flag_panel.center = center
    panel(
        surface,
        flag_panel,
        fill=PANEL,
        border=CYAN_DARK,
        radius=7,
    )
    flag_path = ASSETS_DIR / "flags_png" / f"{iso3}.png"
    flag = app.assets.image(flag_path)
    blit_centered(surface, flag, flag_panel.center, QUESTION_FLAG_IMAGE_SIZE)
    return flag_panel


class PopulationComparisonPresenter:
    """Owns the layout and rendering of two-country population questions."""

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


class BaseView:
    active = "game"

    def __init__(self, app) -> None:
        self.app = app
        self.manager = app.manager
        self._actions: dict[UIButton, object] = {}
        self._create_sidebar_actions()

    def add_action(self, rect: pygame.Rect, action, object_id: str = "#hitbox") -> UIButton:
        button = UIButton(
            relative_rect=rect,
            text="",
            manager=self.manager,
            object_id=object_id,
        )
        self._actions[button] = action
        return button

    def _create_sidebar_actions(self) -> None:
        routes = {
            "game": self.app.show_game,
            "statistics": lambda: self.app.show("statistics"),
            "achievements": lambda: self.app.show("achievements"),
            "mastery": lambda: self.app.show("mastery"),
            "profile": lambda: self.app.show("profile"),
            "settings": lambda: self.app.show("settings"),
            "exit": self.app.request_exit,
        }
        for index, key in enumerate(routes):
            self.add_action(
                pygame.Rect(12, 156 + index * 54, SIDEBAR_WIDTH - 24, 44),
                routes[key],
            )

    def handle_button(self, element) -> None:
        action = self._actions.get(element)
        if callable(action):
            action()

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, delta: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG)
        profile = self.app.repository.profile()
        avatar = self.app.assets.avatar(int(profile["avatar"]))
        draw_sidebar(surface, self.active, profile, avatar, self.app.assets.icon)
        draw_footer(surface, self.app.assets.icon)

    def draw_page_title(self, surface: pygame.Surface, title: str, subtitle: str = "") -> None:
        draw_text(surface, title, (CONTENT.centerx, 70), 27, TEXT, bold=True, anchor="midtop")
        if subtitle:
            draw_text(surface, subtitle, (CONTENT.centerx, 110), 13, MUTED, anchor="midtop")


class HomeView(BaseView):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.play_rect = primary_action_rect(460, 450)
        self.add_action(self.play_rect, lambda: app.show("modes"))

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        hero = pygame.Rect(SIDEBAR_WIDTH + 1, 0, CONTENT.width - 1, CONTENT.height)
        earth = self.app.assets.image(
            ASSETS_DIR / "home" / "earth_hero_v2.png"
        )
        draw_earth_hero(surface, hero, earth)
        draw_text(surface, "AY", (320, 270), 48, CYAN, bold=True)
        draw_text(surface, "Geography", (391, 270), 48, TEXT, bold=True)
        draw_text(surface, "Изучай мир. Прокачивай эрудицию.", (322, 340), 19, MUTED)
        draw_button(
            surface,
            self.play_rect,
            "ИГРАТЬ",
            primary=True,
            size=PRIMARY_ACTION_FONT_SIZE,
        )
        icon = self.app.assets.icon("play", (29, 29))
        blit_centered(
            surface,
            icon,
            (self.play_rect.left + 48, self.play_rect.centery),
        )


class SelectionView(BaseView):
    title = ""
    subtitle = ""

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.draw_page_title(surface, self.title, self.subtitle)


class ModeSelectionView(SelectionView):
    title = "Выберите режимы"
    subtitle = "Можно выбрать один, несколько или все режимы"
    ITEMS = [
        ("flags", "Флаги"),
        ("capitals", "Столицы"),
        ("population", "Население"),
        ("countries", "Страны"),
        ("waters", "Акватория"),
        ("wonders", "Чудеса света"),
    ]

    def __init__(self, app) -> None:
        super().__init__(app)
        self.selected = set(app.pending_modes)
        self.cards: dict[str, pygame.Rect] = {}
        card_w, gap = 235, 24
        for index, (key, _) in enumerate(self.ITEMS):
            row, column = divmod(index, 3)
            columns = min(3, len(self.ITEMS) - row * 3)
            row_width = columns * card_w + (columns - 1) * gap
            start_x = CONTENT.centerx - row_width // 2
            rect = pygame.Rect(
                start_x + column * (card_w + gap),
                170 + row * 210,
                card_w,
                175,
            )
            self.cards[key] = rect
            self.add_action(rect, lambda item=key: self._toggle(item))
        self.next_rect = primary_action_rect(CONTENT.centerx, 615)
        self.back_rect = pygame.Rect(235, 24, 46, 46)
        self.add_action(self.next_rect, self._next)
        self.add_action(self.back_rect, lambda: app.show("home"))

    def _toggle(self, key: str) -> None:
        self.selected.symmetric_difference_update({key})

    def _next(self) -> None:
        if self.selected:
            self.app.pending_modes = [
                key for key, _ in self.ITEMS if key in self.selected
            ]
            self.app.show("continents")
        else:
            self.app.toast("Выберите хотя бы один режим", RED)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        draw_button(surface, self.back_rect, "", size=28)
        icon = self.app.assets.icon("back", (27, 27))
        blit_centered(surface, icon, self.back_rect.center)
        for key, label in self.ITEMS:
            rect = self.cards[key]
            selected = key in self.selected
            panel(
                surface,
                rect,
                fill=pygame.Color("#0b2828") if selected else PANEL,
                border=GREEN if selected else BORDER,
                radius=8,
            )
            box = pygame.Rect(rect.left + 14, rect.top + 14, 20, 20)
            draw_checkbox(surface, box, selected)
            icon = self.app.assets.icon(key, (72, 72))
            blit_centered(surface, icon, (rect.centerx, rect.top + 80))
            draw_text(surface, label, (rect.centerx, rect.bottom - 34), 17, TEXT, bold=True, anchor="center")
        draw_button(
            surface,
            self.next_rect,
            "Далее",
            primary=True,
            size=PRIMARY_ACTION_FONT_SIZE,
        )
        icon = self.app.assets.icon("next", (24, 24))
        blit_centered(
            surface,
            icon,
            (self.next_rect.right - 32, self.next_rect.centery),
        )


class ContinentSelectionView(SelectionView):
    title = "Выберите континенты"
    subtitle = "Можно выбрать один, несколько или все континенты"
    STYLES = {
        "Africa": "#ff9f43",
        "Asia": "#f05d8b",
        "Europe": "#9b7bff",
        "North America": "#2ec4b6",
        "South America": "#7ac943",
        "Oceania": "#36a9e1",
    }
    BOUNDS = {
        "Africa": (-20.0, 55.0, -38.0, 38.0),
        "Asia": (25.0, 180.0, -12.0, 82.0),
        "Europe": (-25.0, 45.0, 32.0, 73.0),
        "North America": (-170.0, -50.0, 5.0, 84.0),
        "South America": (-86.0, -30.0, -58.0, 15.0),
        "Oceania": (108.0, 205.0, -52.0, 12.0),
    }

    def __init__(self, app) -> None:
        super().__init__(app)
        self.selected = set(app.pending_continents)
        self.cards: dict[str, pygame.Rect] = {}
        self._preview_cache: dict[
            tuple[str, tuple[int, int]],
            pygame.Surface,
        ] = {}
        card_w, gap = 196, 20
        row_width = 4 * card_w + 3 * gap
        start_x = CONTENT.centerx - row_width // 2
        for index, key in enumerate(CONTINENT_NAMES):
            row, column = divmod(index, 4)
            rect = pygame.Rect(start_x + column * (card_w + gap), 165 + row * 202, card_w, 168)
            self.cards[key] = rect
            self.add_action(rect, lambda item=key: self._toggle(item))
        self.all_rect = pygame.Rect(start_x + 2 * (card_w + gap), 367, card_w * 2 + gap, 168)
        self.add_action(self.all_rect, self._toggle_all)
        self.next_rect = primary_action_rect(CONTENT.centerx, 612)
        self.back_rect = pygame.Rect(235, 24, 46, 46)
        self.add_action(self.next_rect, self._next)
        self.add_action(self.back_rect, lambda: app.show("modes"))

    def _toggle(self, key: str) -> None:
        self.selected.symmetric_difference_update({key})

    def _toggle_all(self) -> None:
        self.selected = set() if len(self.selected) == len(CONTINENT_NAMES) else set(CONTINENT_NAMES)

    def _next(self) -> None:
        if self.selected:
            self.app.pending_continents = [key for key in CONTINENT_NAMES if key in self.selected]
            self.app.show("question_count")
        else:
            self.app.toast("Выберите хотя бы один континент", RED)

    @staticmethod
    def _preview_background(
        surface: pygame.Surface,
        rect: pygame.Rect,
        accent: pygame.Color,
    ) -> None:
        base = pygame.Color("#06202d")
        bands = 7
        for index in range(bands):
            band = pygame.Rect(
                rect.left,
                rect.top + rect.height * index // bands,
                rect.width,
                rect.height // bands + 1,
            )
            draw_native_rect(
                surface,
                base.lerp(accent, 0.06 + index * 0.015),
                band,
            )
        for fraction in (0.25, 0.5, 0.75):
            draw_native_line(
                surface,
                pygame.Color("#164457"),
                (rect.left + rect.width * fraction, rect.top),
                (rect.left + rect.width * fraction, rect.bottom),
            )
        for fraction in (1 / 3, 2 / 3):
            draw_native_line(
                surface,
                pygame.Color("#164457"),
                (rect.left, rect.top + rect.height * fraction),
                (rect.right, rect.top + rect.height * fraction),
            )

    @classmethod
    def _project_continent_point(
        cls,
        key: str,
        point: list[float],
        rect: pygame.Rect,
    ) -> tuple[float, float]:
        longitude, latitude = point
        if key == "Oceania" and longitude < 0:
            longitude += 360
        min_lon, max_lon, min_lat, max_lat = cls.BOUNDS[key]
        return (
            rect.left + 8 + (longitude - min_lon) / (max_lon - min_lon) * (rect.width - 16),
            rect.bottom - 7 - (latitude - min_lat) / (max_lat - min_lat) * (rect.height - 14),
        )

    def _draw_continent(
        self,
        surface: pygame.Surface,
        key: str,
        rect: pygame.Rect,
    ) -> None:
        target = physical_rect(surface, rect)
        cache_key = (key, target.size)
        cached = self._preview_cache.get(cache_key)
        if cached is not None:
            surface.blit(cached, target)
            return

        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        fill = pygame.Color(self.STYLES[key])
        self._preview_background(layer, rect, fill)
        isos = set(self.app.catalog.continents[key])
        layer.set_clip(target)
        for iso3 in isos:
            for ring in self.app.map_renderer.geometry.get(iso3, []):
                polygon = [
                    self._project_continent_point(key, point, rect)
                    for point in ring
                ]
                if len(polygon) >= 3:
                    draw_native_polygon(layer, fill, polygon)
        draw_native_rect(
            layer,
            pygame.Color(self.STYLES[key]),
            rect,
            1,
            border_radius=7,
        )
        cached = layer.subsurface(target).copy()
        self._preview_cache[cache_key] = cached
        surface.blit(cached, target)

    def _draw_world_preview(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
    ) -> None:
        target = physical_rect(surface, rect)
        cache_key = ("world", target.size)
        cached = self._preview_cache.get(cache_key)
        if cached is not None:
            surface.blit(cached, target)
            return

        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        self._preview_background(layer, rect, CYAN)
        layer.set_clip(target)
        for key, isos in self.app.catalog.continents.items():
            fill = pygame.Color(self.STYLES[key])
            for iso3 in isos:
                for ring in self.app.map_renderer.geometry.get(iso3, []):
                    polygon = [
                        (
                            rect.left + (longitude + 180) / 360 * rect.width,
                            rect.top + (90 - latitude) / 180 * rect.height,
                        )
                        for longitude, latitude in ring
                    ]
                    if len(polygon) >= 3:
                        draw_native_polygon(layer, fill, polygon)
        draw_native_rect(
            layer,
            CYAN_DARK,
            rect,
            1,
            border_radius=7,
        )
        cached = layer.subsurface(target).copy()
        self._preview_cache[cache_key] = cached
        surface.blit(cached, target)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        draw_button(surface, self.back_rect, "", size=28)
        icon = self.app.assets.icon("back", (27, 27))
        blit_centered(surface, icon, self.back_rect.center)
        for key, rect in self.cards.items():
            selected = key in self.selected
            panel(surface, rect, fill=pygame.Color("#0b2828") if selected else PANEL, border=GREEN if selected else BORDER)
            self._draw_continent(surface, key, pygame.Rect(rect.left + 20, rect.top + 20, rect.width - 40, 105))
            box = pygame.Rect(rect.left + 12, rect.top + 12, 18, 18)
            draw_checkbox(surface, box, selected)
            draw_text(surface, CONTINENT_NAMES[key], (rect.centerx, rect.bottom - 27), 14, TEXT, bold=True, anchor="center")
        all_selected = len(self.selected) == len(CONTINENT_NAMES)
        panel(surface, self.all_rect, fill=pygame.Color("#0b2828") if all_selected else PANEL, border=GREEN if all_selected else CYAN_DARK)
        mini_map = pygame.Rect(self.all_rect.left + 28, self.all_rect.top + 22, self.all_rect.width - 56, 100)
        self._draw_world_preview(surface, mini_map)
        draw_text(surface, "Все континенты", (self.all_rect.centerx, self.all_rect.bottom - 24), 15, TEXT, bold=True, anchor="center")
        draw_button(
            surface,
            self.next_rect,
            "Далее",
            primary=True,
            size=PRIMARY_ACTION_FONT_SIZE,
        )
        icon = self.app.assets.icon("next", (24, 24))
        blit_centered(
            surface,
            icon,
            (self.next_rect.right - 32, self.next_rect.centery),
        )


class QuestionCountView(SelectionView):
    title = ""
    subtitle = ""

    def __init__(self, app) -> None:
        super().__init__(app)
        probe = GameConfig(
            app.pending_modes.copy(),
            app.pending_continents.copy(),
            app.pending_count,
            difficulty=app.pending_difficulty,
        )
        self.available_counts = {
            count
            for count in (10, 25, 50, 100)
            if app.question_factory.supports_count(
                probe,
                app.catalog,
                count,
            )
        }
        self.selected = (
            app.pending_count
            if app.pending_count in self.available_counts
            else min(self.available_counts, default=10)
        )
        self.selected_difficulty = app.pending_difficulty
        self.cards: dict[int, pygame.Rect] = {}
        card_w, gap = 205, 24
        row_width = 4 * card_w + 3 * gap
        start_x = CONTENT.centerx - row_width // 2
        for index, count in enumerate((10, 25, 50, 100)):
            rect = pygame.Rect(start_x + index * (card_w + gap), 165, card_w, 220)
            self.cards[count] = rect
            if count in self.available_counts:
                self.add_action(
                    rect,
                    lambda value=count: setattr(self, "selected", value),
                )
        self.difficulty_cards: dict[str, pygame.Rect] = {}
        difficulty_w, difficulty_gap = 220, 24
        difficulty_width = 3 * difficulty_w + 2 * difficulty_gap
        difficulty_x = CONTENT.centerx - difficulty_width // 2
        for index, key in enumerate(DIFFICULTY_NAMES):
            rect = pygame.Rect(
                difficulty_x + index * (difficulty_w + difficulty_gap),
                475,
                difficulty_w,
                76,
            )
            self.difficulty_cards[key] = rect
            self.add_action(
                rect,
                lambda value=key: setattr(self, "selected_difficulty", value),
            )
        self.next_rect = primary_action_rect(CONTENT.centerx, 610)
        self.back_rect = pygame.Rect(235, 24, 46, 46)
        self.add_action(self.next_rect, self._start)
        self.add_action(self.back_rect, lambda: app.show("continents"))

    def _start(self) -> None:
        if self.selected not in self.available_counts:
            self.app.toast("Недостаточно уникальных вопросов", RED)
            return
        self.app.pending_count = self.selected
        self.app.pending_difficulty = self.selected_difficulty
        self.app.start_game(
            GameConfig(
                self.app.pending_modes.copy(),
                self.app.pending_continents.copy(),
                self.selected,
                difficulty=self.selected_difficulty,
            )
        )

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        draw_button(surface, self.back_rect, "", size=28)
        icon = self.app.assets.icon("back", (27, 27))
        blit_centered(surface, icon, self.back_rect.center)
        draw_text(
            surface,
            "Количество вопросов",
            (CONTENT.centerx, 125),
            18,
            TEXT,
            bold=True,
            anchor="center",
        )
        for count, rect in self.cards.items():
            selected = count == self.selected
            enabled = count in self.available_counts
            panel(
                surface,
                rect,
                fill=pygame.Color("#0b2828") if selected else PANEL,
                border=GREEN if selected else BORDER,
            )
            box = pygame.Rect(rect.left + 13, rect.top + 13, 19, 19)
            draw_checkbox(surface, box, selected)
            draw_question_count_icon(
                surface,
                (rect.centerx, rect.top + 78),
                count,
                GREEN if selected else (CYAN if enabled else MUTED),
            )
            draw_text(
                surface,
                str(count),
                (rect.centerx, rect.top + 146),
                31,
                TEXT if enabled else MUTED,
                bold=True,
                anchor="center",
            )
            if not enabled:
                draw_text(
                    surface,
                    "Недоступно",
                    (rect.centerx, rect.bottom - 24),
                    12,
                    MUTED,
                    anchor="center",
                )
        draw_text(
            surface,
            "Уровень сложности",
            (CONTENT.centerx, 440),
            18,
            TEXT,
            bold=True,
            anchor="center",
        )
        for key, rect in self.difficulty_cards.items():
            selected = key == self.selected_difficulty
            panel(
                surface,
                rect,
                fill=pygame.Color("#0b2828") if selected else PANEL,
                border=GREEN if selected else BORDER,
                radius=8,
            )
            marker = pygame.Rect(rect.left + 15, rect.centery - 9, 18, 18)
            draw_checkbox(surface, marker, selected)
            draw_text(
                surface,
                DIFFICULTY_NAMES[key],
                (rect.centerx + 8, rect.centery),
                17,
                TEXT,
                bold=True,
                anchor="center",
            )
        draw_button(
            surface,
            self.next_rect,
            "Далее",
            primary=True,
            size=PRIMARY_ACTION_FONT_SIZE,
        )
        icon = self.app.assets.icon("next", (24, 24))
        blit_centered(
            surface,
            icon,
            (self.next_rect.right - 34, self.next_rect.centery),
        )


class GameView(BaseView):
    STATE_VERSION = 3
    ANSWER_KEY_INDEX = {
        pygame.K_1: 0,
        pygame.K_2: 1,
        pygame.K_3: 2,
        pygame.K_4: 3,
        pygame.K_5: 4,
        pygame.K_6: 5,
        pygame.K_KP1: 0,
        pygame.K_KP2: 1,
        pygame.K_KP3: 2,
        pygame.K_KP4: 3,
        pygame.K_KP5: 4,
        pygame.K_KP6: 5,
    }

    def __init__(
        self,
        app,
        session: GameSession,
        restored_state: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(app)
        restored_state = restored_state or {}
        now = app.clock()
        self.session = session
        displayed_index = int(restored_state.get("displayed_index", session.index))
        if not 0 <= displayed_index < len(session.questions):
            raise ValueError("Некорректный номер сохранённого вопроса")
        self.active_question = session.questions[displayed_index]
        self.active_question_number = displayed_index + 1
        elapsed = max(0.0, float(restored_state.get("question_elapsed", 0.0)))
        self.question_started = now - elapsed
        self.pause_started = now
        self.paused = bool(restored_state.get("paused", False))
        self.feedback = str(restored_state.get("feedback", ""))
        self.feedback_colour = (
            RED if restored_state.get("feedback_colour") == "red" else GREEN
        )
        advance_remaining = restored_state.get("advance_remaining")
        self.advance_at: float | None = (
            now + max(0.0, float(advance_remaining))
            if advance_remaining is not None
            else None
        )
        self.answer_buttons: dict[UIButton, str] = {}
        self.pause_rect = pygame.Rect(1530, 14, 48, 48)
        self.add_action(self.pause_rect, self._toggle_pause)
        self.continue_rect = pygame.Rect(690, 395, 220, 50)
        self.end_round_rect = pygame.Rect(690, 465, 220, 50)
        self.continue_button: UIButton | None = None
        self.end_round_button: UIButton | None = None
        self.map_rect = pygame.Rect(300, 170, 1240, 525)
        self.map_camera = MapCamera()
        self.map_buttons: dict[UIButton, tuple[str, pygame.Rect]] = {}
        self._drag_button: int | None = None
        self._drag_origin = pygame.Vector2()
        self._drag_offset = pygame.Vector2()
        self._build_question_actions()
        camera_state = restored_state.get("camera")
        if isinstance(camera_state, dict):
            self.map_camera.zoom = float(camera_state.get("zoom", self.map_camera.zoom))
            offset = camera_state.get("offset", self.map_camera.offset)
            self.map_camera.offset = pygame.Vector2(offset)
        if self.paused:
            self._create_pause_actions()

    @classmethod
    def from_state(cls, app, state: dict[str, Any]) -> GameView:
        if int(state.get("version", 0)) != cls.STATE_VERSION:
            raise ValueError("Неподдерживаемая версия сохранённой игры")
        session = GameSession.from_state(state["session"])
        return cls(app, session, restored_state=state["view"])

    def to_state(self) -> dict[str, Any]:
        now = self.app.clock()
        timer_reference = self.pause_started if self.paused else now
        question_elapsed = max(0.0, timer_reference - self.question_started)
        advance_remaining = (
            max(0.0, self.advance_at - timer_reference)
            if self.advance_at is not None
            else None
        )
        return {
            "version": self.STATE_VERSION,
            "session": self.session.to_state(),
            "view": {
                "displayed_index": self.active_question_number - 1,
                "question_elapsed": question_elapsed,
                "paused": True,
                "feedback": self.feedback,
                "feedback_colour": "red" if self.feedback_colour == RED else "green",
                "advance_remaining": advance_remaining,
                "camera": {
                    "zoom": self.map_camera.zoom,
                    "offset": list(self.map_camera.offset),
                },
            },
        }

    def _build_question_actions(self) -> None:
        question = self.active_question
        if self._has_map(question):
            self._reset_map_camera()
            self._build_map_actions()
        if not question.options:
            return
        presenter = QUESTION_PRESENTERS.get(
            question.presentation
            if question.presentation != "default"
            else str(question.metadata.get("presentation", ""))
        )
        if presenter is not None:
            for value, rect in zip(question.options, presenter.answer_rects()):
                button = self.add_action(
                    rect,
                    lambda answer=value: self._answer(answer),
                )
                self.answer_buttons[button] = value
            return
        columns = 3 if len(question.options) > 4 else 2
        width = 390 if columns == 3 else 590
        gap = 18
        total_width = columns * width + (columns - 1) * gap
        start_x = SIDEBAR_WIDTH + (CONTENT.width - total_width) // 2
        start_y = 710 if self._has_map(question) else 590
        if question.metadata.get("capital_layout"):
            start_y = 530
        elif question.visual:
            start_y = 590
        for index, value in enumerate(question.options):
            rect = pygame.Rect(start_x + (index % columns) * (width + gap), start_y + (index // columns) * 62, width, 50)
            button = self.add_action(rect, lambda answer=value: self._answer(answer))
            self.answer_buttons[button] = value

    @staticmethod
    def _has_map(question) -> bool:
        return (
            bool(question.metadata.get("highlight"))
            or bool(question.metadata.get("water_highlight"))
            or bool(question.metadata.get("map_overlay"))
        )

    def _question_water_region(self, question):
        water_key = question.metadata.get("water_highlight")
        return self.app.water_catalog.get(water_key) if water_key else None

    def _zoom_target_position(self) -> tuple[float, float] | None:
        highlighted = self.active_question.metadata.get("highlight")
        if highlighted:
            center = self.app.map_renderer.centers.get(highlighted)
            if center is not None:
                return float(center[0]), float(center[1])
        water_region = self._question_water_region(self.active_question)
        if water_region is not None:
            return water_region.longitude, water_region.latitude
        overlay = self.active_question.metadata.get("map_overlay")
        if isinstance(overlay, dict):
            point = overlay.get("point")
            if point:
                return float(point[0]), float(point[1])
            points = [
                point
                for line in overlay.get("lines", ())
                for point in line
            ]
            if points:
                return (
                    (
                        min(point[0] for point in points)
                        + max(point[0] for point in points)
                    )
                    / 2,
                    (
                        min(point[1] for point in points)
                        + max(point[1] for point in points)
                    )
                    / 2,
                )
        return None

    def _zoom_map(self, factor: float) -> None:
        target = self._zoom_target_position()
        if target is None:
            self.map_camera.zoom_by(factor, self.map_rect, self.map_rect.center)
            return
        target_screen = self.app.map_renderer.project(
            target,
            self.map_rect,
            self.map_camera,
        )
        self.map_camera.zoom_by(factor, self.map_rect, target_screen)
        self.map_camera.pan(
            self.map_rect.centerx - target_screen[0],
            self.map_rect.centery - target_screen[1],
        )

    def _reset_map_camera(self) -> None:
        self.map_camera.reset()
        highlighted = self.active_question.metadata.get("highlight")
        if highlighted:
            self.app.map_renderer.focus_country(
                self.map_camera,
                highlighted,
                self.map_rect,
                zoom=9.0,
            )
            return
        water_region = self._question_water_region(self.active_question)
        if water_region is not None:
            self.app.map_renderer.focus_position(
                self.map_camera,
                (water_region.longitude, water_region.latitude),
                self.map_rect,
                zoom=3.0,
            )
            return
        overlay = self.active_question.metadata.get("map_overlay")
        target = self._zoom_target_position()
        if isinstance(overlay, dict) and target is not None:
            self.app.map_renderer.focus_position(
                self.map_camera,
                target,
                self.map_rect,
                zoom=4.5 if overlay.get("kind") == "point" else 2.2,
            )

    def _build_map_actions(self) -> None:
        left, right, bottom = self.map_rect.left, self.map_rect.right, self.map_rect.bottom
        controls = {
            "zoom_in": pygame.Rect(left + 15, bottom - 145, 42, 42),
            "zoom_out": pygame.Rect(left + 15, bottom - 98, 42, 42),
            "reset": pygame.Rect(left + 15, bottom - 51, 42, 42),
            "up": pygame.Rect(right - 100, bottom - 145, 42, 42),
            "left": pygame.Rect(right - 147, bottom - 98, 42, 42),
            "down": pygame.Rect(right - 100, bottom - 98, 42, 42),
            "right": pygame.Rect(right - 53, bottom - 98, 42, 42),
        }
        actions = {
            "zoom_in": lambda: self._zoom_map(1.2),
            "zoom_out": lambda: self._zoom_map(1 / 1.2),
            "reset": self._reset_map_camera,
            "up": lambda: self.map_camera.pan(0, 45),
            "left": lambda: self.map_camera.pan(45, 0),
            "down": lambda: self.map_camera.pan(0, -45),
            "right": lambda: self.map_camera.pan(-45, 0),
        }
        for key, rect in controls.items():
            button = self.add_action(rect, actions[key])
            self.map_buttons[button] = (key, rect)

    def _clear_answer_actions(self) -> None:
        for button in list(self.answer_buttons):
            self._actions.pop(button, None)
            button.kill()
        self.answer_buttons.clear()
        for button in list(self.map_buttons):
            self._actions.pop(button, None)
            button.kill()
        self.map_buttons.clear()

    def _answer(self, value: str) -> None:
        if self.advance_at is not None or self.paused:
            return
        elapsed = min(QUESTION_TIME_SECONDS, self.app.clock() - self.question_started)
        question = self.active_question
        record = self.session.answer(value, elapsed)
        population_values = question.metadata.get("population_values")
        if isinstance(population_values, dict):
            countries_by_name = {
                self.app.catalog.get(iso3).name: self.app.catalog.get(iso3)
                for iso3 in question.subjects
            }
            values = []
            for option in question.options:
                country = countries_by_name.get(option)
                if country is None:
                    continue
                population = int(
                    population_values.get(country.iso3, country.population)
                )
                values.append(
                    f"{country.name} — {format_population(population)}"
                )
            prefix = "Верно!" if record.is_correct else "Неверно."
            self.feedback = f"{prefix} {' • '.join(values)} человек"
            self.feedback_colour = GREEN if record.is_correct else RED
        elif record.is_correct:
            self.feedback = f"Верно!  +{record.points} очков"
            self.feedback_colour = GREEN
        else:
            self.feedback = (
                f"Неверно. Правильный ответ: {question.correct_answer}"
            )
            self.feedback_colour = RED
        feedback_kind = "correct" if record.is_correct else "incorrect"
        feedback_seconds = ANSWER_FEEDBACK_SECONDS[question.mode][
            feedback_kind
        ]
        self.advance_at = self.app.clock() + feedback_seconds

    def _next(self) -> None:
        self._clear_answer_actions()
        self.feedback = ""
        self.advance_at = None
        if self.session.finished:
            self.app.finish_game(self.session.result())
            return
        self.active_question = self.session.current
        self.active_question_number = self.session.index + 1
        self.map_camera.reset()
        self.question_started = self.app.clock()
        self._build_question_actions()

    def _toggle_pause(self) -> None:
        if self.paused:
            self._resume()
        else:
            self.pause()

    def pause(self) -> None:
        if self.paused:
            return
        self.paused = True
        self.pause_started = self.app.clock()
        self._create_pause_actions()

    def _resume(self) -> None:
        if not self.paused:
            return
        paused_seconds = self.app.clock() - self.pause_started
        self.paused = False
        self.question_started += paused_seconds
        if self.advance_at is not None:
            self.advance_at += paused_seconds
        self._remove_pause_actions()

    def _create_pause_actions(self) -> None:
        if self.continue_button is None:
            self.continue_button = self.add_action(
                self.continue_rect,
                self._toggle_pause,
            )
        if self.end_round_button is None:
            self.end_round_button = self.add_action(
                self.end_round_rect,
                self._end_round,
            )

    def _remove_pause_actions(self) -> None:
        for attribute in ("continue_button", "end_round_button"):
            button = getattr(self, attribute)
            if button is None:
                continue
            self._actions.pop(button, None)
            button.kill()
            setattr(self, attribute, None)

    def _end_round(self) -> None:
        self.app.end_round(self.session.result())

    def update(self, delta: float) -> None:
        now = self.app.clock()
        if not self.paused and self.advance_at is not None and now >= self.advance_at:
            self._next()
            return
        if not self.paused and self.advance_at is None and now - self.question_started >= QUESTION_TIME_SECONDS:
            self._answer("")

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.paused:
            return
        if self.advance_at is not None:
            if self._is_feedback_advance_event(event):
                self._next()
            return
        question = self.active_question
        if event.type == pygame.KEYDOWN:
            answer_index = self.ANSWER_KEY_INDEX.get(event.key)
            if answer_index is not None:
                if answer_index < len(question.options):
                    self._answer(question.options[answer_index])
                return
            if self._has_map(question):
                self._handle_map_key(event.key)
                return
        if event.type == pygame.MOUSEWHEEL and self._has_map(question):
            self._zoom_map(1.15 ** event.y)
            return
        if event.type == pygame.MOUSEMOTION:
            if self._drag_button is not None:
                delta = pygame.Vector2(event.pos) - self._drag_origin
                self.map_camera.offset = self._drag_offset + delta
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self._has_map(question) or not self.map_rect.collidepoint(event.pos) or self._point_on_map_control(event.pos):
                return
            self._drag_button = event.button
            self._drag_origin.update(event.pos)
            self._drag_offset = self.map_camera.offset.copy()
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == self._drag_button:
            self._drag_button = None

    def _is_feedback_advance_event(
        self,
        event: pygame.event.Event,
    ) -> bool:
        if event.type == pygame.KEYDOWN:
            return event.key in {
                pygame.K_RETURN,
                pygame.K_KP_ENTER,
                pygame.K_SPACE,
            }
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and GAMEPLAY_AREA.collidepoint(event.pos)
        )

    def _handle_map_key(self, key: int) -> None:
        if key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._zoom_map(1.2)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._zoom_map(1 / 1.2)
        elif key == pygame.K_LEFT:
            self.map_camera.pan(45, 0)
        elif key == pygame.K_RIGHT:
            self.map_camera.pan(-45, 0)
        elif key == pygame.K_UP:
            self.map_camera.pan(0, 45)
        elif key == pygame.K_DOWN:
            self.map_camera.pan(0, -45)
        elif key == pygame.K_r:
            self._reset_map_camera()

    def _point_on_map_control(self, position: tuple[int, int]) -> bool:
        return any(rect.collidepoint(position) for _, rect in self.map_buttons.values())

    def _draw_header(self, surface: pygame.Surface) -> None:
        draw_native_rect(
            surface,
            SIDEBAR,
            (SIDEBAR_WIDTH, 0, CONTENT.width, 70),
        )
        draw_native_line(
            surface,
            BORDER,
            (SIDEBAR_WIDTH, 70),
            (1600, 70),
        )
        trophy = self.app.assets.icon("trophy", (38, 38))
        blit_centered(surface, trophy, (260, 35))
        draw_text(surface, "Очки", (288, 18), 12, MUTED)
        draw_text(surface, str(self.session.score), (288, 37), 17, TEXT, bold=True)
        elapsed = self.app.clock() - self.question_started if not self.paused else self.pause_started - self.question_started
        remaining = max(0, math.ceil(QUESTION_TIME_SECONDS - elapsed))
        draw_native_circle(surface, CYAN_DARK, (462, 35), 29, 3)
        draw_text(surface, str(remaining), (462, 29), 18, TEXT, bold=True, anchor="center")
        draw_text(surface, "сек", (462, 48), 9, MUTED, anchor="center")
        segment_width = 38
        segment_gap = 8
        segment_count = 10
        strip_width = segment_count * segment_width + (segment_count - 1) * segment_gap
        progress_x = CONTENT.centerx - strip_width // 2
        draw_text(
            surface,
            f"Вопрос {self.active_question_number} / {len(self.session.questions)}",
            (CONTENT.centerx, 15),
            12,
            MUTED,
            anchor="midtop",
        )
        answer_colours = self._recent_answer_colours(segment_count)
        for index in range(segment_count):
            colour = answer_colours[index] if index < len(answer_colours) else PANEL_ALT
            draw_native_rect(
                surface,
                colour,
                (progress_x + index * (segment_width + segment_gap), 42, segment_width, 7),
                border_radius=4,
            )
        streak = self.app.assets.icon("streak", (31, 31))
        blit_centered(surface, streak, (1410, 35))
        draw_text(surface, "Серия", (1435, 18), 12, MUTED)
        draw_text(surface, str(self.session.streak), (1435, 38), 16, TEXT, bold=True)
        draw_button(surface, self.pause_rect, "", size=18)
        pause_icon = self.app.assets.icon("play" if self.paused else "pause", (24, 24))
        blit_centered(surface, pause_icon, self.pause_rect.center)

    def _recent_answer_colours(self, limit: int = 10) -> list[pygame.Color]:
        return [
            GREEN if answer.is_correct else RED
            for answer in self.session.answers[-limit:]
        ]

    def _question_text_layout(self) -> tuple[tuple[int, int], str]:
        return (CONTENT.centerx, 102), "midtop"

    def _draw_capital_question(self, surface: pygame.Surface) -> None:
        question = self.active_question
        draw_text(
            surface,
            question.prompt,
            (CONTENT.centerx, 142),
            28,
            TEXT,
            bold=True,
            anchor="midtop",
        )
        draw_question_flag(
            surface,
            self.app,
            question.visual,
            (CONTENT.centerx, 300),
        )
        draw_text(
            surface,
            "столица",
            (CONTENT.centerx, 435),
            CAPITAL_LABEL_FONT_SIZE,
            MUTED,
            anchor="center",
        )

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self._draw_header(surface)
        question = self.active_question
        capital_layout = bool(question.metadata.get("capital_layout"))
        presenter = QUESTION_PRESENTERS.get(
            question.presentation
            if question.presentation != "default"
            else str(question.metadata.get("presentation", ""))
        )
        if capital_layout:
            self._draw_capital_question(surface)
        elif presenter is None or not getattr(presenter, "owns_prompt", False):
            question_position, question_anchor = self._question_text_layout()
            draw_text(
                surface,
                question.prompt,
                question_position,
                24,
                TEXT,
                bold=True,
                anchor=question_anchor,
            )
        has_map = self._has_map(question)
        if has_map:
            self.app.map_renderer.draw(
                surface,
                self.map_rect,
                highlight_country=question.metadata.get("highlight"),
                highlight_water=question.metadata.get("water_highlight"),
                overlay=question.metadata.get("map_overlay"),
                camera=self.map_camera,
            )
            self._draw_map_controls(surface)
            draw_text(
                surface,
                "ЛКМ: перемещение  •  колесо: масштаб  •  R: сброс",
                (self.map_rect.centerx, self.map_rect.bottom - 12),
                12,
                MUTED,
                anchor="midbottom",
            )
        if presenter is not None:
            presenter.draw(surface, self.app, question)
        if (
            question.visual
            and not capital_layout
            and not question.presentation.startswith("wonder_")
        ):
            draw_question_flag(
                surface,
                self.app,
                question.visual,
                (CONTENT.centerx, 305),
            )
        if question.options:
            for button, value in self.answer_buttons.items():
                index = question.options.index(value) + 1
                draw_button(surface, button.rect, f"{index}.  {value}", selected=False, size=17)
        if self.feedback and question.explanation:
            feedback_rect = pygame.Rect(365, 738, 1100, 105)
            panel(
                surface,
                feedback_rect,
                fill=pygame.Color("#07171f"),
                border=self.feedback_colour,
            )
            draw_text(
                surface,
                self.feedback,
                (feedback_rect.left + 20, feedback_rect.top + 12),
                15,
                self.feedback_colour,
                bold=True,
            )
            wrapped = "\n".join(
                textwrap.wrap(question.explanation, width=106)
            )
            draw_multiline(
                surface,
                wrapped,
                pygame.Rect(
                    feedback_rect.left + 20,
                    feedback_rect.top + 34,
                    feedback_rect.width - 40,
                    64,
                ),
                14,
                TEXT,
                align="left",
            )
        elif self.feedback:
            draw_text(surface, self.feedback, (CONTENT.centerx, 846), 16, self.feedback_colour, bold=True, anchor="midbottom")
        if self.paused:
            overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 7, 11, 210))
            surface.blit(overlay, (0, 0))
            panel(surface, pygame.Rect(620, 285, 360, 280), fill=PANEL_ALT, border=CYAN)
            draw_text(surface, "ПАУЗА", (800, 345), 30, TEXT, bold=True, anchor="center")
            draw_button(
                surface,
                self.continue_rect,
                "Продолжить",
                primary=True,
                size=17,
            )
            panel(surface, self.end_round_rect, fill=PANEL, border=RED, radius=7)
            draw_text(
                surface,
                "Закончить раунд",
                self.end_round_rect.center,
                17,
                RED,
                bold=True,
                anchor="center",
            )

    def _draw_map_controls(self, surface: pygame.Surface) -> None:
        for _, (key, rect) in self.map_buttons.items():
            panel(surface, rect, fill=pygame.Color("#061a25"), border=CYAN_DARK, radius=6)
            icon_name = {
                "left": "arrow_left",
                "right": "arrow_right",
                "up": "arrow_up",
                "down": "arrow_down",
            }.get(key, key)
            icon = self.app.assets.icon(icon_name, (27, 27))
            blit_centered(surface, icon, rect.center)


class ResultView(BaseView):
    def __init__(self, app, result: RoundResult) -> None:
        super().__init__(app)
        self.result = result
        self.wrong_rect = pygame.Rect(390, 750, 300, 58)
        self.home_rect = pygame.Rect(720, 750, 300, 58)
        if any(not answer.is_correct for answer in result.answers):
            self.add_action(self.wrong_rect, self._wrong)
        self.add_action(self.home_rect, lambda: app.show("home"))

    def _wrong(self) -> None:
        wrong = self.app.repository.wrong_country_isos()
        self.app.start_game(
            GameConfig(
                list(MODE_NAMES),
                list(CONTINENT_NAMES),
                min(25, max(10, len(wrong))),
                wrong_only=True,
            )
        )

    @staticmethod
    def _max_streak(result: RoundResult) -> int:
        best = current = 0
        for answer in result.answers:
            current = current + 1 if answer.is_correct else 0
            best = max(best, current)
        return best

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        result = self.result
        trophy_center = (565, 255)
        draw_native_ellipse(surface, (79, 50, 2), (450, 365, 230, 26))
        draw_native_rect(surface, YELLOW, (535, 340, 60, 65), border_radius=8)
        draw_native_rect(surface, YELLOW, (490, 400, 150, 20), border_radius=6)
        draw_native_arc(surface, YELLOW, (450, 190, 80, 120), math.pi / 2, math.pi * 1.5, 12)
        draw_native_arc(surface, YELLOW, (600, 190, 80, 120), -math.pi / 2, math.pi / 2, 12)
        draw_native_polygon(surface, YELLOW, [(490, 175), (640, 175), (610, 340), (520, 340)])
        draw_native_circle(surface, pygame.Color("#ffda42"), trophy_center, 48)
        draw_text(surface, "★", trophy_center, 48, pygame.Color("#9a6700"), bold=True, anchor="center")
        draw_text(surface, "Отличный результат!", (565, 470), 26, TEXT, bold=True, anchor="center")
        draw_text(surface, f"{result.score} XP", (565, 520), 35, GREEN, bold=True, anchor="center")
        accuracy = round(result.accuracy * 100)
        draw_native_circle(surface, PANEL_ALT, (565, 630), 55)
        draw_native_circle(surface, GREEN, (565, 630), 55, 5)
        draw_text(surface, f"{accuracy}%", (565, 630), 22, TEXT, bold=True, anchor="center")
        draw_text(surface, f"Правильных ответов  {result.correct_count} / {len(result.answers)}", (565, 704), 16, TEXT, anchor="center")
        metrics = [
            ("timer", "Среднее время ответа", f"{result.average_seconds:05.2f}"),
            ("timer", "Всего времени", f"{int(result.duration_seconds) // 60:02d}:{int(result.duration_seconds) % 60:02d}"),
            ("streak", "Макс. серия", str(self._max_streak(result))),
            ("trophy", "Получено очков", str(result.score)),
        ]
        for index, (icon_name, title, value) in enumerate(metrics):
            rect = pygame.Rect(1050, 160 + index * 118, 390, 90)
            panel(surface, rect)
            icon = self.app.assets.icon(icon_name, (38, 38))
            blit_centered(surface, icon, (rect.left + 35, rect.centery))
            draw_text(surface, title, (rect.left + 65, rect.top + 18), 13, MUTED)
            draw_text(surface, value, (rect.left + 65, rect.top + 43), 23, TEXT, bold=True)
        if any(not answer.is_correct for answer in result.answers):
            draw_button(surface, self.wrong_rect, "Ошибочные вопросы", size=16)
        draw_button(surface, self.home_rect, "В главное меню", primary=True, size=16)


class StatisticsView(BaseView):
    active = "statistics"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.mouse_position: tuple[int, int] | None = None
        self.activity_cells: list[
            tuple[pygame.Rect, str, float]
        ] = []

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.mouse_position = event.pos

    @staticmethod
    def _format_play_time(seconds: float) -> str:
        minutes = round(seconds / 60)
        if minutes < 1:
            return "0 минут"
        hours, remaining = divmod(minutes, 60)
        if not hours:
            return f"{remaining} мин"
        if not remaining:
            return f"{hours} ч"
        return f"{hours} ч {remaining} мин"

    @staticmethod
    def _activity_colour(seconds: float) -> pygame.Color:
        bands = (
            (15 * 60, pygame.Color("#76c52b")),
            (30 * 60, pygame.Color("#61ad28")),
            (60 * 60, pygame.Color("#4b9424")),
            (2 * 60 * 60, pygame.Color("#367b20")),
            (float("inf"), pygame.Color("#1c641b")),
        )
        return next(colour for limit, colour in bands if seconds <= limit)

    @staticmethod
    def _answer_percentage(correct: int, total: int) -> int:
        return round(100 * correct / total) if total else 0

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        stats = self.app.repository.statistics()
        total = stats["total"]
        metrics = [
            ("Раундов", str(total["rounds"])),
            ("Ответов", str(total["question_count"])),
            ("Игровых минут", str(round(total["duration"] / 60))),
            (
                "Лучший результат за последние 7 д.",
                f"{total['best_score_last_7_days_25_questions']} XP",
            ),
        ]
        for index, (title, value) in enumerate(metrics):
            rect = pygame.Rect(250 + index * 325, 42, 290, 92)
            panel(surface, rect)
            draw_text(surface, title, (rect.left + 18, rect.top + 16), 13, MUTED)
            draw_text(surface, value, (rect.left + 18, rect.top + 44), 25, TEXT, bold=True)
        left = pygame.Rect(250, 165, 620, 330)
        right = pygame.Rect(900, 165, 620, 330)
        bottom = pygame.Rect(250, 525, 1270, 285)
        panel(surface, left)
        panel(surface, right)
        panel(surface, bottom)
        draw_text(surface, "Правильные ответы по континентам", (left.left + 20, left.top + 18), 16, TEXT, bold=True)
        country_stats = {item["country_iso"]: item for item in stats["countries"]}
        for index, (continent, label) in enumerate(CONTINENT_NAMES.items()):
            rows = [country_stats.get(iso3) for iso3 in self.app.catalog.continents[continent]]
            rows = [row for row in rows if row]
            attempts = sum(row["total"] for row in rows)
            correct = sum(row["correct"] for row in rows)
            percent = self._answer_percentage(correct, attempts)
            y = left.top + 62 + index * 40
            draw_text(surface, label, (left.left + 20, y), 12, TEXT)
            draw_native_rect(surface, PANEL_ALT, (left.left + 190, y + 3, 335, 12), border_radius=6)
            draw_native_rect(surface, GREEN, (left.left + 190, y + 3, round(335 * percent / 100), 12), border_radius=6)
            draw_text(surface, f"{percent}%", (left.right - 22, y), 12, TEXT, bold=True, anchor="topright")
        draw_text(surface, "Правильные ответы по режимам", (right.left + 20, right.top + 18), 16, TEXT, bold=True)
        mode_stats = {item["mode"]: item for item in stats["modes"]}
        centre = (right.centerx, right.centery + 25)
        colours = [
            CYAN,
            pygame.Color("#6e83c9"),
            GREEN,
            pygame.Color("#f18b3a"),
            pygame.Color("#a76cd1"),
            YELLOW,
        ]
        start = -math.pi / 2
        total_attempts = max(1, sum(item["total"] for item in mode_stats.values()))
        for index, (mode, label) in enumerate(MODE_NAMES.items()):
            mode_stat = mode_stats.get(
                mode,
                {"total": 0, "correct": 0},
            )
            amount = mode_stat["total"]
            percent = self._answer_percentage(
                mode_stat["correct"],
                amount,
            )
            angle = math.tau * amount / total_attempts
            draw_native_arc(surface, colours[index], (centre[0] - 90, centre[1] - 90, 180, 180), start, start + max(.03, angle), 25)
            start += angle
            row_y = right.top + 75 + index * 37
            draw_text(
                surface,
                f"• {label}",
                (right.left + 420, row_y),
                13,
                colours[index],
            )
            draw_text(
                surface,
                f"{percent}%",
                (right.right - 24, row_y),
                13,
                TEXT,
                bold=True,
                anchor="topright",
            )
        draw_text(surface, str(total["question_count"]), centre, 25, TEXT, bold=True, anchor="center")
        draw_text(surface, "ответов", (centre[0], centre[1] + 26), 11, MUTED, anchor="center")
        draw_text(surface, "Активность за последние 30 дней", (bottom.left + 20, bottom.top + 18), 16, TEXT, bold=True)
        self.activity_cells.clear()
        for column, item in enumerate(stats["recent"]):
            rect = pygame.Rect(
                bottom.left + 22 + column * 41,
                bottom.top + 82,
                30,
                30,
            )
            duration = float(item["duration"])
            if duration > 0:
                draw_native_rect(
                    surface,
                    self._activity_colour(duration),
                    rect,
                    border_radius=5,
                )
            draw_native_rect(
                surface,
                GREEN_DARK if duration > 0 else BORDER,
                rect,
                1,
                border_radius=5,
            )
            self.activity_cells.append((rect, item["day"], duration))

        draw_text(
            surface,
            "Шкала времени в игре",
            (bottom.left + 22, bottom.top + 145),
            12,
            TEXT,
            bold=True,
        )
        legend = (
            (10 * 60, "до 15 мин"),
            (20 * 60, "15–30 мин"),
            (45 * 60, "30–60 мин"),
            (90 * 60, "1–2 часа"),
            (3 * 60 * 60, "более 2 часов"),
        )
        for index, (seconds, label) in enumerate(legend):
            x = bottom.left + 22 + index * 238
            marker = pygame.Rect(x, bottom.top + 178, 18, 18)
            draw_native_rect(
                surface,
                self._activity_colour(seconds),
                marker,
                border_radius=4,
            )
            draw_text(
                surface,
                label,
                (marker.right + 9, marker.centery),
                11,
                MUTED,
                anchor="midleft",
            )
        if self.mouse_position is not None:
            hovered = next(
                (
                    (rect, day, duration)
                    for rect, day, duration in self.activity_cells
                    if rect.collidepoint(self.mouse_position)
                ),
                None,
            )
            if hovered is not None:
                rect, day, duration = hovered
                tooltip = pygame.Rect(rect.centerx - 100, rect.top - 62, 200, 50)
                tooltip.clamp_ip(pygame.Rect(bottom.left + 8, bottom.top + 8, bottom.width - 16, bottom.height - 16))
                panel(surface, tooltip, fill=pygame.Color("#0d2b38"), border=CYAN_DARK, radius=7)
                day_label = ".".join(reversed(day.split("-")))
                draw_text(surface, day_label, (tooltip.centerx, tooltip.top + 10), 11, MUTED, anchor="midtop")
                draw_text(
                    surface,
                    self._format_play_time(duration),
                    (tooltip.centerx, tooltip.top + 27),
                    13,
                    TEXT,
                    bold=True,
                    anchor="midtop",
                )


class AchievementsView(BaseView):
    active = "achievements"
    ACHIEVEMENTS_PER_PAGE = 9

    def __init__(self, app) -> None:
        super().__init__(app)
        self.page = 0
        self.achievement_items = app.progression.achievements()
        self.previous_rect = pygame.Rect(810, 770, 48, 42)
        self.next_rect = pygame.Rect(947, 770, 48, 42)
        self.add_action(self.previous_rect, lambda: self._change_page(-1))
        self.add_action(self.next_rect, lambda: self._change_page(1))

    @property
    def page_count(self) -> int:
        return max(
            1,
            math.ceil(
                len(self.achievement_items) / self.ACHIEVEMENTS_PER_PAGE
            ),
        )

    def _change_page(self, offset: int) -> None:
        self.page = max(0, min(self.page_count - 1, self.page + offset))

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.draw_page_title(surface, "Достижения")
        self._draw_achievements(surface)

    def _draw_achievements(self, surface: pygame.Surface) -> None:
        start = self.page * self.ACHIEVEMENTS_PER_PAGE
        items = self.achievement_items[
            start : start + self.ACHIEVEMENTS_PER_PAGE
        ]
        for index, item in enumerate(items):
            column, row = index % 3, index // 3
            rect = pygame.Rect(245 + column * 425, 135 + row * 195, 395, 174)
            complete = item.unlocked
            panel(
                surface,
                rect,
                fill=pygame.Color("#0b2b2b") if complete else PANEL,
                border=GREEN if complete else BORDER,
            )
            icon = self.app.assets.icon(
                item.definition.icon,
                (40, 40),
            )
            blit_centered(surface, icon, (rect.left + 38, rect.top + 40))
            draw_text(
                surface,
                item.definition.category,
                (rect.left + 70, rect.top + 16),
                11,
                GREEN if complete else MUTED,
            )
            draw_text(
                surface,
                item.definition.title,
                (rect.left + 70, rect.top + 38),
                15,
                TEXT,
                bold=True,
            )
            description = "\n".join(
                textwrap.wrap(item.definition.description, width=46)
            )
            draw_multiline(
                surface,
                description,
                pygame.Rect(rect.left + 16, rect.top + 72, rect.width - 32, 42),
                11,
                MUTED,
                align="left",
                line_gap=2,
            )
            progress = min(1.0, item.current / max(1, item.target))
            bar = pygame.Rect(rect.left + 16, rect.bottom - 27, rect.width - 90, 8)
            draw_native_rect(surface, PANEL_ALT, bar, border_radius=4)
            if progress:
                draw_native_rect(
                    surface,
                    GREEN if complete else CYAN,
                    (bar.x, bar.y, round(bar.width * progress), bar.height),
                    border_radius=4,
                )
            label = "Готово" if complete else f"{item.current}/{item.target}"
            draw_text(
                surface,
                label,
                (rect.right - 16, bar.centery),
                11,
                GREEN if complete else TEXT,
                bold=True,
                anchor="midright",
            )
        draw_button(
            surface,
            self.previous_rect,
            "‹",
            disabled=self.page == 0,
            size=22,
        )
        draw_text(
            surface,
            f"{self.page + 1} / {self.page_count}",
            (CONTENT.centerx, self.previous_rect.centery),
            13,
            MUTED,
            anchor="center",
        )
        draw_button(
            surface,
            self.next_rect,
            "›",
            disabled=self.page >= self.page_count - 1,
            size=22,
        )


class MasteryView(BaseView):
    active = "mastery"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.mouse_position: tuple[int, int] | None = None
        self.map_rect = pygame.Rect(275, 155, 1210, 535)
        self.mastery = app.progression.country_mastery()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.mouse_position = event.pos

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.draw_page_title(surface, "Прогресс изучения")
        self._draw_mastery(surface)

    def _draw_mastery(self, surface: pygame.Surface) -> None:
        levels = {iso3: item.stars for iso3, item in self.mastery.items()}
        mastered = sum(level > 0 for level in levels.values())
        draw_text(
            surface,
            f"Изучено стран: {mastered} / {len(levels)}",
            (275, 137),
            14,
            TEXT,
            bold=True,
            anchor="bottomleft",
        )
        self.app.map_renderer.draw_mastery_map(
            surface,
            self.map_rect,
            levels,
            self.app.progression_catalog.mastery_colors,
        )
        legend_y = 726
        legend_center = self.map_rect.centerx
        labels = ("Не изучена", "1 звезда", "2 звезды", "3 звезды")
        for stars in range(4):
            item_center = legend_center + round((stars - 1.5) * 235)
            x = item_center - 62
            colour = pygame.Color(
                self.app.progression_catalog.mastery_colors[stars]
            )
            draw_native_rect(
                surface,
                colour,
                (x, legend_y, 24, 16),
                border_radius=4,
            )
            draw_text(
                surface,
                labels[stars],
                (x + 34, legend_y + 8),
                12,
                TEXT,
                anchor="midleft",
            )
        if self.mouse_position is None:
            return
        iso3 = self.app.map_renderer.country_at(
            self.mouse_position,
            self.map_rect,
        )
        if iso3 is None or iso3 not in self.mastery:
            return
        item = self.mastery[iso3]
        country = self.app.catalog.get(iso3)
        tooltip = pygame.Rect(
            self.mouse_position[0] + 14,
            self.mouse_position[1] + 14,
            270,
            46 + 22 * len(item.correct_by_mode),
        )
        tooltip.clamp_ip(pygame.Rect(220, 165, 1360, 650))
        panel(
            surface,
            tooltip,
            fill=pygame.Color("#0d2b38"),
            border=CYAN_DARK,
        )
        draw_text(
            surface,
            country.name,
            (tooltip.left + 14, tooltip.top + 10),
            14,
            TEXT,
            bold=True,
        )
        draw_text(
            surface,
            f"{item.stars} из 3",
            (tooltip.right - 14, tooltip.top + 10),
            14,
            GREEN,
            bold=True,
            anchor="topright",
        )
        maximum = self.app.progression_catalog.mastery_levels[-1].correct_per_mode
        for index, (mode, correct) in enumerate(item.correct_by_mode.items()):
            draw_text(
                surface,
                MODE_NAMES.get(mode, mode),
                (tooltip.left + 14, tooltip.top + 38 + index * 22),
                11,
                MUTED,
            )
            draw_text(
                surface,
                f"{min(correct, maximum)} / {maximum}",
                (tooltip.right - 14, tooltip.top + 38 + index * 22),
                11,
                TEXT,
                anchor="topright",
            )


class ProfileView(BaseView):
    active = "profile"

    def __init__(self, app) -> None:
        super().__init__(app)
        profile = app.repository.profile()
        self.selected = int(profile["avatar"])
        self.avatar_rects: list[pygame.Rect] = []
        for index in range(10):
            rect = pygame.Rect(695 + (index % 5) * 120, 500 + (index // 5) * 120, 92, 92)
            self.avatar_rects.append(rect)
            self.add_action(rect, lambda value=index: setattr(self, "selected", value))
        self.entry_rect = pygame.Rect(645, 220, 360, 50)
        self.entry = UITextEntryLine(
            self.entry_rect,
            manager=self.manager,
            object_id="#profile_entry",
        )
        self.entry.set_text(str(profile["nickname"]))
        self.save_rect = primary_action_rect(825, 755)
        self.add_action(self.save_rect, self._save)

    def _save(self) -> None:
        self.app.repository.update_profile(self.entry.get_text(), self.selected)
        self.app.assets.clear_profile_cache()
        self.app.toast("Профиль сохранён", GREEN)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        profile = self.app.repository.profile()
        avatar = self.app.assets.avatar(self.selected)
        blit_centered(surface, avatar, (520, 235), (170, 170))
        draw_text(surface, "Профиль игрока", (825, 150), 27, TEXT, bold=True, anchor="center")
        panel(surface, self.entry_rect, fill=PANEL_ALT, border=CYAN_DARK)
        draw_text(
            surface,
            self.entry.get_text() or "Введите имя",
            (self.entry_rect.left + 15, self.entry_rect.centery),
            17,
            TEXT if self.entry.get_text() else MUTED,
            anchor="midleft",
        )
        xp = int(profile["xp"])
        level = xp // 500 + 1
        draw_text(surface, f"Уровень {level}", (825, 300), 17, TEXT, bold=True, anchor="center")
        draw_native_rect(surface, PANEL_ALT, (645, 335, 360, 12), border_radius=6)
        draw_native_rect(surface, GREEN, (645, 335, round(360 * ((xp % 500) / 500)), 12), border_radius=6)
        draw_text(surface, f"{xp:,} / {level * 500:,} XP".replace(",", " "), (825, 370), 14, TEXT, anchor="center")
        draw_text(surface, "Выберите аватар", (825, 445), 19, TEXT, bold=True, anchor="center")
        for index, rect in enumerate(self.avatar_rects):
            selected = index == self.selected
            blit_centered(
                surface,
                self.app.assets.avatar(index),
                rect.center,
                (88, 88) if selected else (78, 78),
            )
        draw_button(
            surface,
            self.save_rect,
            "Сохранить изменения",
            primary=True,
            size=PRIMARY_ACTION_FONT_SIZE,
        )


class SettingsView(BaseView):
    active = "settings"
    ITEMS = [
        ("fullscreen", "Полноэкранный режим", "Запускать игру в полноэкранном режиме"),
        ("confirm_exit", "Подтверждение выхода", "Показывать диалог подтверждения при выходе"),
        ("show_correct", "Показывать правильный ответ", "Показывать ответ после ошибки"),
        ("animations", "Анимации интерфейса", "Включить плавные анимации элементов интерфейса"),
    ]

    def __init__(self, app) -> None:
        super().__init__(app)
        self.values = app.repository.settings()
        self.rows: dict[str, pygame.Rect] = {}
        for index, (key, _, _) in enumerate(self.ITEMS):
            rect = pygame.Rect(330, 150 + index * 145, 1145, 110)
            self.rows[key] = rect
            self.add_action(
                pygame.Rect(rect.right - 100, rect.centery - 25, 70, 50),
                lambda item=key: self._toggle(item),
            )
        self.reset_answers_rect = pygame.Rect(330, 730, 1145, 110)
        self.reset_answers_button = self.add_action(
            self.reset_answers_rect,
            app.request_answer_statistics_reset,
        )

    def _toggle(self, key: str) -> None:
        self.values[key] = not bool(self.values[key])
        self.app.repository.set_setting(key, self.values[key])
        if key == "fullscreen":
            self.app.set_fullscreen(self.values[key])

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        draw_text(surface, "Настройки", (CONTENT.centerx, 72), 28, TEXT, bold=True, anchor="center")
        icons = ("fullscreen", "confirm", "correct", "animations")
        for index, (key, title, subtitle) in enumerate(self.ITEMS):
            rect = self.rows[key]
            panel(surface, rect)
            icon = self.app.assets.icon(icons[index], (42, 42))
            blit_centered(surface, icon, (rect.left + 42, rect.centery))
            draw_text(surface, title, (rect.left + 80, rect.top + 27), 17, TEXT, bold=True)
            draw_text(surface, subtitle, (rect.left + 80, rect.top + 59), 13, MUTED)
            toggle = pygame.Rect(rect.right - 100, rect.centery - 20, 70, 40)
            draw_native_rect(surface, GREEN_DARK if self.values[key] else PANEL_ALT, toggle, border_radius=20)
            draw_native_rect(surface, GREEN if self.values[key] else BORDER, toggle, 1, border_radius=20)
            knob_x = toggle.right - 20 if self.values[key] else toggle.left + 20
            draw_native_circle(surface, TEXT, (knob_x, toggle.centery), 15)
        panel(
            surface,
            self.reset_answers_rect,
            radius=8,
        )
        icon = self.app.assets.icon("reset", (42, 42))
        blit_centered(
            surface,
            icon,
            (
                self.reset_answers_rect.left + 42,
                self.reset_answers_rect.centery,
            ),
        )
        draw_text(
            surface,
            "Сбросить статистику ответов",
            (self.reset_answers_rect.left + 80, self.reset_answers_rect.top + 27),
            17,
            TEXT,
            bold=True,
        )
        draw_text(
            surface,
            "Игровое время, активность и XP сохранятся",
            (self.reset_answers_rect.left + 80, self.reset_answers_rect.top + 59),
            13,
            MUTED,
        )
        draw_text(
            surface,
            "Сбросить",
            (
                self.reset_answers_rect.right - 30,
                self.reset_answers_rect.centery,
            ),
            15,
            RED,
            bold=True,
            anchor="midright",
        )


VIEW_TYPES = {
    "home": HomeView,
    "modes": ModeSelectionView,
    "continents": ContinentSelectionView,
    "question_count": QuestionCountView,
    "statistics": StatisticsView,
    "achievements": AchievementsView,
    "mastery": MasteryView,
    "profile": ProfileView,
    "settings": SettingsView,
}
