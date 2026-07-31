from __future__ import annotations

import math
import textwrap
from pathlib import Path
from typing import Any

import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UITextEntryLine

from ..config import (
    ASSETS_DIR,
    CONTINENT_NAMES,
    DIFFICULTY_NAMES,
    QUESTION_TIME_SECONDS,
)
from ..domain.questions import (
    FlagContent,
    MapContent,
    PopulationContent,
    WonderContent,
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
from .layout import (
    CAPITAL_LABEL_FONT_SIZE,
    CONTENT,
    GAMEPLAY_AREA,
    PRIMARY_ACTION_FONT_SIZE,
    PRIMARY_ACTION_SIZE,
    QUESTION_FLAG_IMAGE_SIZE,
    QUESTION_FLAG_PANEL_SIZE,
    blit_centered,
    draw_question_flag,
    primary_action_rect,
)
from .presenters import QUESTION_PRESENTERS


class BaseView:
    active = "game"

    def __init__(self, app) -> None:
        self.app = app
        self.manager = app.manager
        self._actions: dict[UIButton, object] = {}
        self._pointer_position: tuple[int, int] | None = None
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
        if (
            self.app.profile_manager is not None
            and not self.app._profile_selected
        ):
            return
        routes = {
            "game": self.app.show_game,
            "atlas": lambda: self.app.show("atlas"),
            "statistics": lambda: self.app.show("statistics"),
            "achievements": lambda: self.app.show("achievements"),
            "mastery": lambda: self.app.show("mastery"),
            "profile": lambda: self.app.show("profile"),
            "settings": lambda: self.app.show("settings"),
            "exit": self.app.request_exit,
        }
        for index, key in enumerate(routes):
            if key == self.active:
                continue
            self.add_action(
                pygame.Rect(12, 156 + index * 54, SIDEBAR_WIDTH - 24, 44),
                routes[key],
            )
        if self.active != "profile":
            self.add_action(
                pygame.Rect(12, 746, SIDEBAR_WIDTH - 24, 96),
                lambda: self.app.show("profile"),
            )

    def handle_button(self, element) -> None:
        action = self._actions.get(element)
        if callable(action):
            action()

    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def record_pointer_event(self, event: pygame.event.Event) -> None:
        if event.type in {
            pygame.MOUSEMOTION,
            pygame.MOUSEBUTTONDOWN,
            pygame.MOUSEBUTTONUP,
        }:
            self._pointer_position = event.pos

    def interactive_at(self, position: tuple[int, int]) -> bool:
        return any(
            button.relative_rect.collidepoint(position)
            for button in self._actions
        )

    def set_pointer_position(self, position: tuple[int, int]) -> None:
        self._pointer_position = position

    def draw_interaction_effects(self, surface: pygame.Surface) -> None:
        hovered_rect = next(
            (
                button.relative_rect
                for button in self._actions
                if self._pointer_position is not None
                and button.relative_rect.collidepoint(
                    self._pointer_position
                )
            ),
            None,
        )
        if hovered_rect is not None:
            hover_layer = pygame.Surface(
                surface.get_size(),
                pygame.SRCALPHA,
            )
            hover_layer.fill((0, 0, 0, 0))
            draw_native_rect(
                hover_layer,
                (57, 215, 238, 26),
                hovered_rect,
                border_radius=8,
            )
            draw_native_rect(
                hover_layer,
                (57, 215, 238, 130),
                hovered_rect,
                1,
                border_radius=8,
            )
            surface.blit(hover_layer, (0, 0))

    def update(self, delta: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG)
        profile = self.app.repository.profile()
        progress = self.app.profile_progression.progress(
            int(profile["level"]),
            int(profile["xp"]),
        )
        profile.update(
            required_xp=progress.required_xp,
            title=progress.title,
        )
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

    def __init__(self, app) -> None:
        super().__init__(app)
        self.items = [
            (item.key, item.title)
            for item in app.mode_registry.definitions
        ]
        self.selected = set(app.pending_modes)
        self.cards: dict[str, pygame.Rect] = {}
        card_w, gap = 235, 24
        for index, (key, _) in enumerate(self.items):
            row, column = divmod(index, 3)
            columns = min(3, len(self.items) - row * 3)
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
                key for key, _ in self.items if key in self.selected
            ]
            self.app.show("continents")
        else:
            self.app.toast("Выберите хотя бы один режим", RED)

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        draw_button(surface, self.back_rect, "", size=28)
        icon = self.app.assets.icon("back", (27, 27))
        blit_centered(surface, icon, self.back_rect.center)
        for key, label in self.items:
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
    STATE_VERSION = 4
    LEGACY_STATE_VERSIONS = frozenset({3})
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
        version = int(state.get("version", 0))
        if version != cls.STATE_VERSION and version not in cls.LEGACY_STATE_VERSIONS:
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
        presenter = QUESTION_PRESENTERS.get(question.presenter_key)
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
        if (
            isinstance(question.content, FlagContent)
            and question.content.capital_layout
        ):
            start_y = 530
        elif question.visual:
            start_y = 590
        for index, value in enumerate(question.options):
            rect = pygame.Rect(start_x + (index % columns) * (width + gap), start_y + (index // columns) * 62, width, 50)
            button = self.add_action(rect, lambda answer=value: self._answer(answer))
            self.answer_buttons[button] = value

    @staticmethod
    def _has_map(question) -> bool:
        if isinstance(question.content, MapContent):
            return bool(
                question.content.highlight_country
                or question.content.water_highlight
                or question.content.overlay
            )
        return (
            isinstance(question.content, WonderContent)
            and question.content.overlay is not None
        )

    def _question_water_region(self, question):
        water_key = (
            question.content.water_highlight
            if isinstance(question.content, MapContent)
            else ""
        )
        return self.app.water_catalog.get(water_key) if water_key else None

    def _zoom_target_position(self) -> tuple[float, float] | None:
        content = self.active_question.content
        highlighted = (
            content.highlight_country
            if isinstance(content, MapContent)
            else ""
        )
        if highlighted:
            center = self.app.map_renderer.centers.get(highlighted)
            if center is not None:
                return float(center[0]), float(center[1])
        water_region = self._question_water_region(self.active_question)
        if water_region is not None:
            return water_region.longitude, water_region.latitude
        overlay = self.active_question.map_overlay
        if overlay is not None:
            point = overlay.point
            if point:
                return float(point[0]), float(point[1])
            points = [
                point
                for line in overlay.lines
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
        content = self.active_question.content
        highlighted = (
            content.highlight_country
            if isinstance(content, MapContent)
            else ""
        )
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
        overlay = self.active_question.map_overlay
        target = self._zoom_target_position()
        if overlay is not None and target is not None:
            self.app.map_renderer.focus_position(
                self.map_camera,
                target,
                self.map_rect,
                zoom=4.5 if overlay.kind == "point" else 2.2,
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
        population_values = (
            question.content.values
            if isinstance(question.content, PopulationContent)
            else None
        )
        if population_values is not None:
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
        feedback_seconds = self.app.mode_registry.feedback_seconds(
            question.mode,
            record.is_correct,
            (
                question.content.water_area_kind
                if isinstance(question.content, MapContent)
                else ""
            ),
        )
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
        capital_layout = (
            isinstance(question.content, FlagContent)
            and question.content.capital_layout
        )
        presenter = QUESTION_PRESENTERS.get(question.presenter_key)
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
                highlight_country=(
                    question.content.highlight_country
                    if isinstance(question.content, MapContent)
                    else None
                ),
                highlight_water=(
                    question.content.water_highlight
                    if isinstance(question.content, MapContent)
                    else None
                ),
                overlay=question.map_overlay,
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
            and not isinstance(question.content, WonderContent)
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
                list(self.app.mode_registry.keys),
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
    PERIODS = (
        ("today", "Сегодня"),
        ("yesterday", "Вчера"),
        ("3_days", "Последние 3 дня"),
        ("week", "Неделя"),
        ("month", "Месяц"),
        ("all", "Всё время"),
    )

    def __init__(self, app) -> None:
        super().__init__(app)
        self.mouse_position: tuple[int, int] | None = None
        self.activity_cells: list[
            tuple[pygame.Rect, str, float]
        ] = []
        self.period = "all"
        self.period_rects: dict[str, pygame.Rect] = {}
        widths = (112, 105, 165, 105, 105, 120)
        x = 772
        for (key, _), width in zip(self.PERIODS, widths):
            rect = pygame.Rect(x, 18, width, 36)
            self.period_rects[key] = rect
            self.add_action(
                rect,
                lambda value=key: setattr(self, "period", value),
            )
            x += width + 8

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
        stats = self.app.repository.statistics(self.period)
        total = stats["total"]
        draw_text(
            surface,
            "Статистика",
            (250, 27),
            15,
            TEXT,
            bold=True,
        )
        for key, label in self.PERIODS:
            draw_button(
                surface,
                self.period_rects[key],
                label,
                selected=key == self.period,
                size=12,
            )
        metrics = [
            ("Раундов", str(total["rounds"])),
            ("Ответов", str(total["question_count"])),
            ("Игровых минут", str(round(total["duration"] / 60))),
            (
                "Лучший результат (25 вопросов)",
                f"{total['best_score_25_questions']} XP",
            ),
        ]
        for index, (title, value) in enumerate(metrics):
            rect = pygame.Rect(250 + index * 325, 68, 290, 72)
            panel(surface, rect)
            draw_text(surface, title, (rect.left + 18, rect.top + 11), 12, MUTED)
            draw_text(surface, value, (rect.left + 18, rect.top + 34), 23, TEXT, bold=True)
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
        for index, definition in enumerate(
            self.app.mode_registry.definitions
        ):
            mode, label = definition.key, definition.title
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


class InteractiveMapView(BaseView):
    """Reusable pan/zoom controls for non-game world maps."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.mouse_position: tuple[int, int] | None = None
        self.map_rect = self._map_area()
        self.map_camera = MapCamera()
        self.map_buttons: dict[UIButton, tuple[str, pygame.Rect]] = {}
        self._dragging = False
        self._drag_origin = pygame.Vector2()
        self._drag_offset = pygame.Vector2()
        self._click_origin = pygame.Vector2()
        self._build_map_actions()

    def _map_area(self) -> pygame.Rect:
        return pygame.Rect(275, 155, 1210, 535)

    def _on_map_click(self, position: tuple[int, int]) -> None:
        pass

    def _build_map_actions(self) -> None:
        left, right, bottom = (
            self.map_rect.left,
            self.map_rect.right,
            self.map_rect.bottom,
        )
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
            "zoom_in": lambda: self._zoom(1.2),
            "zoom_out": lambda: self._zoom(1 / 1.2),
            "reset": self.map_camera.reset,
            "up": lambda: self.map_camera.pan(0, 45),
            "left": lambda: self.map_camera.pan(45, 0),
            "down": lambda: self.map_camera.pan(0, -45),
            "right": lambda: self.map_camera.pan(-45, 0),
        }
        for key, rect in controls.items():
            button = self.add_action(rect, actions[key])
            self.map_buttons[button] = key, rect

    def _zoom(self, factor: float) -> None:
        focus = (
            self.mouse_position
            if self.mouse_position
            and self.map_rect.collidepoint(self.mouse_position)
            else self.map_rect.center
        )
        self.map_camera.zoom_by(factor, self.map_rect, focus)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEMOTION:
            self.mouse_position = event.pos
            if self._dragging:
                delta = pygame.Vector2(event.pos) - self._drag_origin
                self.map_camera.offset = self._drag_offset + delta
            return
        if event.type == pygame.MOUSEWHEEL:
            self._zoom(1.15 ** event.y)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            on_control = any(
                rect.collidepoint(event.pos)
                for _, rect in self.map_buttons.values()
            )
            if self.map_rect.collidepoint(event.pos) and not on_control:
                self._dragging = True
                self._drag_origin.update(event.pos)
                self._drag_offset = self.map_camera.offset.copy()
                self._click_origin.update(event.pos)
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_click = (
                self._dragging
                and pygame.Vector2(event.pos).distance_to(
                    self._click_origin
                )
                < 6
            )
            self._dragging = False
            if was_click:
                self._on_map_click(event.pos)
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._zoom(1.2)
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._zoom(1 / 1.2)
        elif event.key == pygame.K_LEFT:
            self.map_camera.pan(45, 0)
        elif event.key == pygame.K_RIGHT:
            self.map_camera.pan(-45, 0)
        elif event.key == pygame.K_UP:
            self.map_camera.pan(0, 45)
        elif event.key == pygame.K_DOWN:
            self.map_camera.pan(0, -45)
        elif event.key == pygame.K_r:
            self.map_camera.reset()

    def _draw_map_controls(self, surface: pygame.Surface) -> None:
        for _, (key, rect) in self.map_buttons.items():
            panel(
                surface,
                rect,
                fill=pygame.Color("#061a25"),
                border=CYAN_DARK,
                radius=6,
            )
            icon_name = {
                "left": "arrow_left",
                "right": "arrow_right",
                "up": "arrow_up",
                "down": "arrow_down",
            }.get(key, key)
            icon = self.app.assets.icon(icon_name, (27, 27))
            blit_centered(surface, icon, rect.center)
        draw_text(
            surface,
            "ЛКМ: перемещение  •  колесо: масштаб  •  R: сброс",
            (self.map_rect.centerx, self.map_rect.bottom - 12),
            12,
            MUTED,
            anchor="midbottom",
        )


class AtlasView(InteractiveMapView):
    active = "atlas"

    def __init__(self, app) -> None:
        super().__init__(app)
        self._continents = {
            country.iso3: country.continent
            for country in app.catalog.all()
        }
        self.selected_country: str | None = None
        self._facts = app.wonder_catalog.facts_by_country()
        self._area_ranks = self._rank_countries("area")
        self._population_ranks = self._rank_countries("population")

    def _map_area(self) -> pygame.Rect:
        return pygame.Rect(275, 138, 1210, 462)

    def _rank_countries(self, field: str) -> dict[str, int]:
        ordered = sorted(
            self.app.catalog.all(),
            key=lambda country: getattr(country, field),
            reverse=True,
        )
        return {
            country.iso3: index
            for index, country in enumerate(ordered, start=1)
        }

    def _on_map_click(self, position: tuple[int, int]) -> None:
        selected = self.app.map_renderer.country_at(
            position,
            self.map_rect,
            self.map_camera,
        )
        if selected in self._continents:
            self.selected_country = selected

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.draw_page_title(
            surface,
            "Атлас мира",
            "Наведите курсор на страну, чтобы увидеть подробности",
        )
        hovered = (
            self.app.map_renderer.country_at(
                self.mouse_position,
                self.map_rect,
                self.map_camera,
            )
            if self.mouse_position is not None
            else None
        )
        self.app.map_renderer.draw_atlas_map(
            surface,
            self.map_rect,
            self._continents,
            self.map_camera,
            None if self._dragging else hovered or self.selected_country,
        )
        self._draw_map_controls(surface)
        if hovered and hovered in self._continents:
            self._draw_country_card(surface, hovered)
        self._draw_country_facts(surface)

    def _draw_country_facts(self, surface: pygame.Surface) -> None:
        rect = pygame.Rect(275, 620, 1210, 190)
        panel(surface, rect, fill=PANEL, border=BORDER, radius=9)
        if self.selected_country is None:
            icon = self.app.assets.icon("atlas", (46, 46))
            blit_centered(surface, icon, (rect.centerx, rect.top + 57))
            draw_text(
                surface,
                "Нажмите на страну, чтобы открыть три факта",
                (rect.centerx, rect.top + 112),
                16,
                MUTED,
                anchor="center",
            )
            return
        country = self.app.catalog.get(self.selected_country)
        fact = self._facts[self.selected_country]
        facts = (
            fact.explanation,
            (
                f"{self._area_ranks[country.iso3]}-е место в мире "
                f"по площади: {country.area:,} км²."
            ).replace(",", " "),
            (
                f"{self._population_ranks[country.iso3]}-е место в мире "
                f"по населению: {format_population(country.population)} человек."
            ),
        )
        draw_text(
            surface,
            f"Три факта: {country.name}",
            (rect.left + 18, rect.top + 14),
            16,
            TEXT,
            bold=True,
        )
        for index, fact_text in enumerate(facts):
            item = pygame.Rect(
                rect.left + 18 + index * 395,
                rect.top + 48,
                376,
                124,
            )
            panel(
                surface,
                item,
                fill=PANEL_ALT,
                border=CYAN_DARK,
                radius=7,
            )
            draw_native_circle(
                surface,
                GREEN_DARK,
                (item.left + 24, item.top + 24),
                15,
            )
            draw_text(
                surface,
                str(index + 1),
                (item.left + 24, item.top + 24),
                12,
                TEXT,
                bold=True,
                anchor="center",
            )
            wrapped = "\n".join(textwrap.wrap(fact_text, width=43))
            draw_multiline(
                surface,
                wrapped,
                pygame.Rect(
                    item.left + 50,
                    item.top + 12,
                    item.width - 62,
                    item.height - 24,
                ),
                11,
                TEXT,
                align="left",
                line_gap=3,
            )

    def _draw_country_card(
        self,
        surface: pygame.Surface,
        iso3: str,
    ) -> None:
        assert self.mouse_position is not None
        country = self.app.catalog.get(iso3)
        language_lines = textwrap.wrap(
            ", ".join(country.official_languages),
            width=38,
        ) or ["—"]
        card = pygame.Rect(
            self.mouse_position[0] + 18,
            self.mouse_position[1] + 18,
            390,
            170 + max(0, len(language_lines) - 1) * 18,
        )
        card.clamp_ip(self.map_rect.inflate(-12, -12))
        panel(
            surface,
            card,
            fill=PANEL,
            border=CYAN_DARK,
            radius=10,
        )
        flag = self.app.assets.image(
            ASSETS_DIR / "flags_png" / f"{iso3}.png"
        )
        blit_centered(
            surface,
            flag,
            (card.left + 57, card.top + 48),
            (82, 52),
        )
        dark = TEXT
        secondary = MUTED
        draw_text(
            surface,
            country.name,
            (card.left + 112, card.top + 22),
            18,
            dark,
            bold=True,
        )
        rows = (
            ("Столица", country.capital),
            ("Население", f"{format_population(country.population)} чел."),
            ("Площадь", f"{country.area:,} км²".replace(",", " ")),
        )
        for index, (label, value) in enumerate(rows):
            y = card.top + 72 + index * 25
            draw_text(
                surface,
                label,
                (card.left + 18, y),
                11,
                secondary,
                bold=True,
            )
            draw_text(
                surface,
                value,
                (card.left + 112, y),
                11,
                dark,
            )
        y = card.top + 147
        draw_text(
            surface,
            "Оф. язык",
            (card.left + 18, y),
            11,
            secondary,
            bold=True,
        )
        for index, line in enumerate(language_lines):
            draw_text(
                surface,
                line,
                (card.left + 112, y + index * 18),
                11,
                dark,
            )


class MasteryView(InteractiveMapView):
    active = "mastery"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.mastery = app.progression.country_mastery()

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
            self.map_camera,
        )
        self._draw_map_controls(surface)
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
            self.map_camera,
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
                self.app.mode_registry.names.get(mode, mode),
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
            rect = pygame.Rect(
                624 + (index % 5) * 116,
                435 + (index // 5) * 108,
                92,
                92,
            )
            self.avatar_rects.append(rect)
            self.add_action(rect, lambda value=index: setattr(self, "selected", value))
        self.entry_rect = pygame.Rect(645, 220, 360, 50)
        self.entry = UITextEntryLine(
            self.entry_rect,
            manager=self.manager,
            object_id="#profile_entry",
        )
        self.entry.set_text(str(profile["nickname"]))
        self.save_rect = primary_action_rect(825, 650)
        self.add_action(self.save_rect, self._save)
        self.create_rect = pygame.Rect(300, 735, 270, 52)
        self.delete_rect = pygame.Rect(590, 735, 270, 52)
        self.export_rect = pygame.Rect(880, 735, 270, 52)
        self.import_rect = pygame.Rect(1170, 735, 270, 52)
        if app.profile_manager is not None:
            self.add_action(
                self.create_rect,
                lambda: app.show("profile_create"),
            )
            self.add_action(
                self.delete_rect,
                lambda: app.show("profile_delete"),
            )
            self.add_action(self.export_rect, app.export_current_profile)
            self.add_action(self.import_rect, app.import_profile)

    def _save(self) -> None:
        self.app.repository.update_profile(self.entry.get_text(), self.selected)
        self.app.assets.clear_profile_cache()
        self.app.toast("Профиль сохранён", GREEN)

    @staticmethod
    def _draw_entry(
        surface: pygame.Surface,
        entry: UITextEntryLine,
        rect: pygame.Rect,
    ) -> None:
        value = entry.get_text()
        panel(surface, rect, fill=PANEL_ALT, border=CYAN_DARK)
        draw_text(
            surface,
            value or "Введите имя",
            (rect.left + 15, rect.centery),
            17,
            TEXT if value else MUTED,
            anchor="midleft",
        )
        if entry.is_focused and entry.cursor_on:
            edit_position = max(0, min(len(value), entry.edit_position))
            prefix_width = font(17).size(value[:edit_position])[0]
            cursor_x = min(rect.right - 10, rect.left + 15 + prefix_width)
            draw_native_rect(
                surface,
                TEXT,
                (cursor_x, rect.centery - 12, 1, 24),
            )

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        profile = self.app.repository.profile()
        avatar = self.app.assets.avatar(self.selected)
        blit_centered(surface, avatar, (520, 235), (170, 170))
        draw_text(surface, "Профиль игрока", (825, 150), 27, TEXT, bold=True, anchor="center")
        self._draw_entry(surface, self.entry, self.entry_rect)
        xp = int(profile["xp"])
        progress = self.app.profile_progression.progress(
            int(profile["level"]),
            xp,
        )
        draw_text(
            surface,
            progress.title,
            (825, 292),
            16,
            GREEN,
            bold=True,
            anchor="center",
        )
        draw_text(
            surface,
            f"Уровень {progress.level}",
            (825, 318),
            17,
            TEXT,
            bold=True,
            anchor="center",
        )
        draw_native_rect(surface, PANEL_ALT, (645, 335, 360, 12), border_radius=6)
        draw_native_rect(
            surface,
            GREEN,
            (
                645,
                335,
                round(360 * min(1.0, xp / progress.required_xp)),
                12,
            ),
            border_radius=6,
        )
        draw_text(
            surface,
            f"{xp:,} / {progress.required_xp:,} XP".replace(",", " "),
            (825, 365),
            14,
            TEXT,
            anchor="center",
        )
        draw_text(surface, "Выберите аватар", (825, 405), 19, TEXT, bold=True, anchor="center")
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
        if self.app.profile_manager is not None:
            draw_button(surface, self.create_rect, "Создать профиль", size=15)
            draw_button(
                surface,
                self.delete_rect,
                "Удалить профиль",
                size=15,
            )
            draw_button(surface, self.export_rect, "Экспорт", size=15)
            draw_button(surface, self.import_rect, "Импорт", size=15)


class ProfileCreateView(BaseView):
    active = "profile"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.selected = 0
        self.entry_rect = pygame.Rect(620, 180, 410, 52)
        self.entry = UITextEntryLine(
            self.entry_rect,
            manager=self.manager,
            object_id="#profile_entry",
        )
        self.entry.set_text("Новый игрок")
        self.avatar_rects = []
        for index in range(10):
            rect = pygame.Rect(
                624 + (index % 5) * 116,
                335 + (index // 5) * 108,
                92,
                92,
            )
            self.avatar_rects.append(rect)
            self.add_action(
                rect,
                lambda value=index: setattr(self, "selected", value),
            )
        self.create_rect = primary_action_rect(825, 615)
        self.cancel_rect = pygame.Rect(690, 690, 270, 50)
        self.add_action(
            self.create_rect,
            lambda: app.create_profile(
                self.entry.get_text(),
                self.selected,
            ),
        )
        self.add_action(
            self.cancel_rect,
            lambda: app.show(
                "profile_select"
                if app.profile_manager is not None
                and not app._profile_selected
                else "profile"
            ),
        )

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.draw_page_title(surface, "Новый профиль")
        ProfileView._draw_entry(surface, self.entry, self.entry_rect)
        draw_text(
            surface,
            "Выберите аватар",
            (825, 292),
            19,
            TEXT,
            bold=True,
            anchor="center",
        )
        for index, rect in enumerate(self.avatar_rects):
            blit_centered(
                surface,
                self.app.assets.avatar(index),
                rect.center,
                (88, 88) if index == self.selected else (78, 78),
            )
        draw_button(
            surface,
            self.create_rect,
            "Создать профиль",
            primary=True,
            size=PRIMARY_ACTION_FONT_SIZE,
        )
        draw_button(surface, self.cancel_rect, "Отмена", size=16)


class ProfileDeleteView(BaseView):
    active = "profile"
    PAGE_SIZE = 8

    def __init__(self, app) -> None:
        super().__init__(app)
        self.page = 0
        self.profile_buttons: list[
            tuple[UIButton, pygame.Rect, object]
        ] = []
        self.previous_rect = pygame.Rect(600, 740, 70, 46)
        self.next_rect = pygame.Rect(980, 740, 70, 46)
        self.add_action(self.previous_rect, lambda: self._change_page(-1))
        self.add_action(self.next_rect, lambda: self._change_page(1))
        self._build_profile_actions()

    @property
    def profiles(self):
        assert self.app.profile_manager is not None
        return self.app.profile_manager.profiles()

    @property
    def page_count(self) -> int:
        return max(1, math.ceil(len(self.profiles) / self.PAGE_SIZE))

    def _change_page(self, delta: int) -> None:
        self.page = max(0, min(self.page_count - 1, self.page + delta))
        self._build_profile_actions()

    def _build_profile_actions(self) -> None:
        for button, _, _ in self.profile_buttons:
            self._actions.pop(button, None)
            button.kill()
        self.profile_buttons.clear()
        start = self.page * self.PAGE_SIZE
        for index, profile in enumerate(
            self.profiles[start : start + self.PAGE_SIZE]
        ):
            column, row = index % 2, index // 2
            rect = pygame.Rect(
                300 + column * 620,
                155 + row * 130,
                580,
                105,
            )
            button = self.add_action(
                rect,
                lambda value=profile.id: self.app.request_profile_deletion(
                    value
                ),
            )
            self.profile_buttons.append((button, rect, profile))

    def draw(self, surface: pygame.Surface) -> None:
        super().draw(surface)
        self.draw_page_title(
            surface,
            "Удаление профиля",
            "Удаление потребует двух подтверждений",
        )
        for _, rect, profile in self.profile_buttons:
            panel(surface, rect)
            blit_centered(
                surface,
                self.app.assets.avatar(profile.avatar),
                (rect.left + 55, rect.centery),
                (76, 76),
            )
            draw_text(
                surface,
                profile.nickname,
                (rect.left + 105, rect.top + 24),
                17,
                TEXT,
                bold=True,
            )
            draw_text(
                surface,
                f"Уровень {profile.level}",
                (rect.left + 105, rect.top + 56),
                13,
                MUTED,
            )
            draw_text(
                surface,
                "Удалить",
                (rect.right - 28, rect.centery),
                14,
                RED,
                bold=True,
                anchor="midright",
            )
        if self.page_count > 1:
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
                (825, self.previous_rect.centery),
                14,
                TEXT,
                anchor="center",
            )
            draw_button(
                surface,
                self.next_rect,
                "›",
                disabled=self.page >= self.page_count - 1,
                size=22,
            )


class ProfileSelectionView(BaseView):
    PAGE_SIZE = 2

    def _create_sidebar_actions(self) -> None:
        pass

    def __init__(self, app) -> None:
        super().__init__(app)
        self.page = 0
        self.profile_buttons: list[
            tuple[UIButton, pygame.Rect, object]
        ] = []
        self.action_buttons: list[
            tuple[UIButton, pygame.Rect, str]
        ] = []
        self.previous_rect = pygame.Rect(260, 720, 70, 46)
        self.next_rect = pygame.Rect(1270, 720, 70, 46)
        self.add_action(self.previous_rect, lambda: self._change_page(-1))
        self.add_action(self.next_rect, lambda: self._change_page(1))
        self._build_profile_actions()

    @property
    def profiles(self):
        return self.app.profile_manager.profiles()

    @property
    def page_count(self) -> int:
        return max(1, math.ceil(len(self.profiles) / self.PAGE_SIZE))

    def _change_page(self, delta: int) -> None:
        self.page = max(0, min(self.page_count - 1, self.page + delta))
        self._build_profile_actions()

    def _build_profile_actions(self) -> None:
        for button, _, _ in self.profile_buttons:
            self._actions.pop(button, None)
            button.kill()
        self.profile_buttons.clear()
        for button, _, _ in self.action_buttons:
            self._actions.pop(button, None)
            button.kill()
        self.action_buttons.clear()
        start = self.page * self.PAGE_SIZE
        for index, profile in enumerate(
            self.profiles[start : start + self.PAGE_SIZE]
        ):
            column = index % 2
            rect = pygame.Rect(
                405 + column * 390,
                240,
                350,
                190,
            )
            button = self.add_action(
                rect,
                lambda value=profile.id: self.app.select_profile(value),
            )
            self.profile_buttons.append((button, rect, profile))
        action_y = 475 if self.profile_buttons else 285
        actions = (
            ("create", lambda: self.app.show("profile_create")),
            ("import", self.app.import_profile),
        )
        for index, (kind, action) in enumerate(actions):
            rect = pygame.Rect(405 + index * 390, action_y, 350, 190)
            button = self.add_action(rect, action)
            self.action_buttons.append((button, rect, kind))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BG)
        draw_logo(surface, (LOGICAL_SIZE[0] // 2, 92), 52)
        draw_text(
            surface,
            "Выберите профиль",
            (LOGICAL_SIZE[0] // 2, 158),
            30,
            TEXT,
            bold=True,
            anchor="center",
        )
        for _, rect, profile in self.profile_buttons:
            panel(surface, rect)
            blit_centered(
                surface,
                self.app.assets.avatar(profile.avatar),
                (rect.centerx, rect.top + 67),
                (100, 100),
            )
            draw_text(
                surface,
                profile.nickname,
                (rect.centerx, rect.top + 128),
                18,
                TEXT,
                bold=True,
                anchor="center",
            )
            title = self.app.profile_progression.title(profile.level)
            draw_text(
                surface,
                f"{title} • уровень {profile.level}",
                (rect.centerx, rect.top + 158),
                12,
                GREEN,
                anchor="center",
            )
        action_content = {
            "create": (
                "profile_add",
                "Создать новый профиль",
                "Новый локальный игрок",
            ),
            "import": (
                "profile_import",
                "Импортировать профиль",
                "Восстановить файл .ayprofile",
            ),
        }
        for _, rect, kind in self.action_buttons:
            panel(surface, rect)
            icon_name, title, subtitle = action_content[kind]
            icon = self.app.assets.icon(icon_name, (64, 64))
            blit_centered(
                surface,
                icon,
                (rect.centerx, rect.top + 62),
            )
            draw_text(
                surface,
                title,
                (rect.centerx, rect.top + 125),
                17,
                TEXT,
                bold=True,
                anchor="center",
            )
            draw_text(
                surface,
                subtitle,
                (rect.centerx, rect.top + 157),
                12,
                MUTED,
                anchor="center",
            )
        if self.page_count > 1:
            draw_button(surface, self.previous_rect, "‹", size=22)
            draw_button(surface, self.next_rect, "›", size=22)
        draw_footer(surface, self.app.assets.icon)


class SettingsView(BaseView):
    active = "settings"
    ITEMS = [
        ("fullscreen", "Полноэкранный режим", "Запускать игру в полноэкранном режиме"),
        ("confirm_exit", "Подтверждение выхода", "Показывать диалог подтверждения при выходе"),
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
        self.reset_answers_rect = pygame.Rect(330, 470, 1145, 110)
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
        icons = ("fullscreen", "confirm")
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
    "atlas": AtlasView,
    "statistics": StatisticsView,
    "achievements": AchievementsView,
    "mastery": MasteryView,
    "profile": ProfileView,
    "profile_create": ProfileCreateView,
    "profile_delete": ProfileDeleteView,
    "profile_select": ProfileSelectionView,
    "settings": SettingsView,
}
