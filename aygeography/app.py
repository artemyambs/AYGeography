from __future__ import annotations

import ctypes
import os
import time
from pathlib import Path
from typing import Callable

os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
os.environ.setdefault("SDL_WINDOWS_DPI_SCALING", "0")


def _enable_windows_dpi_awareness() -> None:
    """Запрещает Windows растягивать окно и размывать готовый кадр."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


_enable_windows_dpi_awareness()

import pygame
import pygame_gui

from .catalog import CountryCatalog
from .config import (
    APP_NAME,
    APP_VERSION,
    ASSETS_DIR,
    CONFIGS_DIR,
    CONTINENT_NAMES,
    DATABASE_PATH,
)
from .models import GameConfig, RoundResult
from .progression import ProgressionCatalog, ProgressionService
from .quiz import GameSession, QuestionFactory
from .storage import GameRepository
from .ui.components import (
    BG,
    GREEN,
    LOGICAL_SIZE,
    RED,
    TEXT,
    MapRenderer,
    draw_native_rect,
    draw_text,
)
from .ui.modals import ConfirmationModal
from .ui.screens import GameView, HomeView, ResultView, VIEW_TYPES
from .wonders import WonderCatalog


class AssetStore:
    def __init__(self) -> None:
        self._images: dict[Path, pygame.Surface] = {}
        self._avatars: dict[int, pygame.Surface] = {}
        self._icons: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}
        self._render_scale = 1.0

    def set_render_scale(self, scale: float) -> None:
        self._render_scale = max(0.1, scale)

    def image(self, path: Path) -> pygame.Surface:
        path = path.resolve()
        if path not in self._images:
            self._images[path] = pygame.image.load(path).convert_alpha()
        return self._images[path]

    def avatar(self, index: int) -> pygame.Surface:
        index %= 10
        if index not in self._avatars:
            self._avatars[index] = pygame.transform.smoothscale(
                self.image(
                    ASSETS_DIR / "avatars" / f"avatar_{index + 1:02d}.png"
                ),
                (160, 160),
            )
        return self._avatars[index]

    def icon(self, name: str, size: tuple[int, int] = (32, 32)) -> pygame.Surface:
        target_size = (
            max(1, round(size[0] * self._render_scale)),
            max(1, round(size[1] * self._render_scale)),
        )
        key = (name, target_size)
        if key not in self._icons:
            source = self.image(ASSETS_DIR / "icons" / f"{name}.svg")
            self._icons[key] = pygame.transform.smoothscale(
                source,
                target_size,
            )
        return self._icons[key]

    def clear_profile_cache(self) -> None:
        self._avatars.clear()


class LogicalUIManager(pygame_gui.UIManager):
    """Keeps pygame_gui hover checks in the logical render coordinate system."""

    def __init__(
        self,
        window_resolution: tuple[int, int],
        *,
        mouse_position_mapper: Callable[[tuple[int, int]], tuple[int, int]],
        **kwargs,
    ) -> None:
        self._mouse_position_mapper = mouse_position_mapper
        super().__init__(window_resolution, **kwargs)

    def _update_mouse_position(self) -> None:
        physical_position = pygame.mouse.get_pos()
        logical_position = self._mouse_position_mapper(physical_position)
        self.mouse_position = self.calculate_scaled_mouse_position(logical_position)


class AYGeographyApp:
    """Pygame CE runtime, маршрутизация экранов и композиция сервисов."""

    def __init__(
        self,
        *,
        headless: bool = False,
        repository: GameRepository | None = None,
    ) -> None:
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_caption(f"{APP_NAME} {APP_VERSION}")
        self._headless = headless
        self._fullscreen = False
        self._windowed_size = self._safe_window_size()
        self.display = pygame.display.set_mode(self._windowed_size, pygame.RESIZABLE)
        self.logical = pygame.Surface(self._render_size()).convert()
        self.clock_source = time.monotonic
        self.frame_clock = pygame.time.Clock()
        self.running = False

        self.catalog = CountryCatalog(
            CONFIGS_DIR / "countries_by_iso3.json",
            CONFIGS_DIR / "continents.json",
        )
        self.wonder_catalog = WonderCatalog(
            CONFIGS_DIR / "wonders",
            self.catalog.all(),
            ASSETS_DIR,
        )
        self.repository = repository or GameRepository(DATABASE_PATH)
        self.progression_catalog = ProgressionCatalog(
            CONFIGS_DIR / "progression.json",
            CONFIGS_DIR / "achievements.json",
        )
        self.progression = ProgressionService(
            self.repository,
            self.catalog,
            self.progression_catalog,
        )
        self.progression.sync()
        self.question_factory = QuestionFactory(
            wonder_catalog=self.wonder_catalog
        )
        self.map_renderer = MapRenderer(ASSETS_DIR / "maps/world_geometry.json")
        self.assets = AssetStore()
        self.manager = LogicalUIManager(
            LOGICAL_SIZE,
            mouse_position_mapper=self._logical_position,
            theme_path=ASSETS_DIR / "theme.json",
            enable_live_theme_updates=False,
            starting_language="ru",
        )
        self.pending_modes = ["countries", "waters"]
        self.pending_continents = list(CONTINENT_NAMES)
        self.pending_count = 25
        self.pending_difficulty = "medium"
        self.view = None
        self._active_game_state = self.repository.load_active_game()
        self._confirmation: ConfirmationModal | None = None
        self._confirmation_action: Callable[[], None] | None = None
        self._toast = ""
        self._toast_colour = GREEN
        self._toast_until = 0.0
        self.show("home")
        if self._active_game_state is not None:
            self._offer_resume_game()
        if self.repository.settings()["fullscreen"] and not headless:
            self.set_fullscreen(True)

    @staticmethod
    def _safe_window_size() -> tuple[int, int]:
        if os.environ.get("SDL_VIDEODRIVER") == "dummy":
            return LOGICAL_SIZE
        desktop_width, desktop_height = pygame.display.get_desktop_sizes()[0]
        available_width = max(960, desktop_width - 80)
        available_height = max(540, desktop_height - 120)
        scale = min(
            1.0,
            available_width / LOGICAL_SIZE[0],
            available_height / LOGICAL_SIZE[1],
        )
        return round(LOGICAL_SIZE[0] * scale), round(LOGICAL_SIZE[1] * scale)

    def clock(self) -> float:
        return self.clock_source()

    def show(self, name: str) -> None:
        if isinstance(self.view, GameView):
            self._suspend_game(self.view)
        self.manager.clear_and_reset()
        self._confirmation = None
        self._confirmation_action = None
        self.view = VIEW_TYPES[name](self)

    def show_game(self) -> None:
        if isinstance(self.view, GameView):
            return
        if self._active_game_state is None:
            self.show("home")
            return
        self.manager.clear_and_reset()
        try:
            restored_view = GameView.from_state(self, self._active_game_state)
        except (KeyError, TypeError, ValueError):
            self._clear_active_game()
            self.view = None
            self.show("home")
            self.toast("Не удалось восстановить сохранённую игру", RED)
            return
        self._confirmation = None
        self._confirmation_action = None
        self.view = restored_view

    def start_game(self, config: GameConfig) -> None:
        try:
            questions = self.question_factory.build(
                config,
                self.catalog,
                self.repository.wrong_country_isos(),
            )
        except ValueError as error:
            self.toast(str(error), RED)
            return
        self._clear_active_game()
        self.manager.clear_and_reset()
        self._confirmation = None
        self._confirmation_action = None
        self.view = GameView(
            self,
            GameSession(
                questions,
                difficulty=config.difficulty or "medium",
            ),
        )

    def finish_game(self, result: RoundResult) -> None:
        self._clear_active_game()
        self.repository.save_round(result)
        unlocked = self.progression.sync()
        self.manager.clear_and_reset()
        self.view = ResultView(self, result)
        self._notify_achievements(unlocked)

    def end_round(self, result: RoundResult) -> None:
        self._clear_active_game()
        if result.answers:
            self.repository.save_round(result)
            unlocked = self.progression.sync()
        else:
            unlocked = []
        self.view = None
        self.show("home")
        self._notify_achievements(unlocked)

    def _notify_achievements(self, unlocked) -> None:
        if len(unlocked) == 1:
            self.toast(f"Достижение: {unlocked[0].title}", GREEN)
        elif unlocked:
            self.toast(f"Открыто достижений: {len(unlocked)}", GREEN)

    def _suspend_game(self, view: GameView) -> None:
        view.pause()
        self._active_game_state = view.to_state()
        self.repository.save_active_game(self._active_game_state)

    def _clear_active_game(self) -> None:
        self._active_game_state = None
        self.repository.clear_active_game()

    def _offer_resume_game(self) -> None:
        view_state = self._active_game_state.get("view", {})
        question_number = int(view_state.get("displayed_index", 0)) + 1
        self._open_confirmation(
            title="Незаконченная игра",
            description=(
                f"Продолжить сохранённый раунд с вопроса №{question_number}?"
            ),
            action_name="Продолжить",
            action=self.show_game,
        )

    def toast(self, message: str, colour=TEXT) -> None:
        self._toast = message
        self._toast_colour = colour
        self._toast_until = self.clock() + 2.4

    def request_answer_statistics_reset(self) -> None:
        self._open_confirmation(
            title="Сброс статистики",
            description=(
                "Сбросить раунды, ответы и лучшие результаты?\n"
                "Игровое время, активность и XP сохранятся."
            ),
            action_name="Сбросить",
            action=self._reset_answer_statistics,
            danger=True,
        )

    def _reset_answer_statistics(self) -> None:
        self.repository.reset_answer_statistics()
        self.toast("Статистика ответов сброшена", GREEN)

    def request_exit(self) -> None:
        if isinstance(self.view, GameView):
            self._suspend_game(self.view)
        if not self.repository.settings()["confirm_exit"]:
            self.running = False
            return
        self._open_confirmation(
            title="Выход",
            description="Завершить игру AYGeography?",
            action_name="Выйти",
            action=self._confirm_exit,
            danger=True,
        )

    def _confirm_exit(self) -> None:
        self.running = False

    def _open_confirmation(
        self,
        *,
        title: str,
        description: str,
        action_name: str,
        action: Callable[[], None],
        danger: bool = False,
    ) -> None:
        if self._confirmation is not None:
            return
        self._confirmation_action = action
        self._confirmation = ConfirmationModal(
            title=title,
            description=description,
            action_name=action_name,
            danger=danger,
        )

    def set_fullscreen(self, enabled: bool) -> None:
        self._fullscreen = enabled
        if enabled:
            if not self._headless:
                self._windowed_size = self.display.get_size()
            self.display = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self._windowed_size = self._safe_window_size()
            self.display = pygame.display.set_mode(self._windowed_size, pygame.RESIZABLE)

    def _logical_position(self, position: tuple[int, int]) -> tuple[int, int]:
        width, height = self.display.get_size()
        scale = min(width / LOGICAL_SIZE[0], height / LOGICAL_SIZE[1])
        draw_width, draw_height = LOGICAL_SIZE[0] * scale, LOGICAL_SIZE[1] * scale
        offset_x, offset_y = (width - draw_width) / 2, (height - draw_height) / 2
        return (
            round((position[0] - offset_x) / scale),
            round((position[1] - offset_y) / scale),
        )

    def _translate_event(self, event: pygame.event.Event) -> pygame.event.Event:
        if hasattr(event, "pos"):
            values = event.dict.copy()
            values["pos"] = self._logical_position(event.pos)
            if "rel" in values:
                width, height = self.display.get_size()
                scale = min(width / LOGICAL_SIZE[0], height / LOGICAL_SIZE[1])
                values["rel"] = (round(values["rel"][0] / scale), round(values["rel"][1] / scale))
            return pygame.event.Event(event.type, values)
        return event

    def _render_size(self) -> tuple[int, int]:
        width, height = self.display.get_size()
        scale = min(width / LOGICAL_SIZE[0], height / LOGICAL_SIZE[1])
        return (
            max(1, round(LOGICAL_SIZE[0] * scale)),
            max(1, round(LOGICAL_SIZE[1] * scale)),
        )

    def _ensure_render_surface(self) -> None:
        size = self._render_size()
        if self.logical.get_size() != size:
            self.logical = pygame.Surface(size).convert()

    def process_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.request_exit()
            return
        if event.type in (pygame.VIDEORESIZE, pygame.WINDOWRESIZED):
            self.display = pygame.display.get_surface()
            if not self._fullscreen and self.display is not None:
                self._windowed_size = self.display.get_size()
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self._confirmation is not None:
                self._confirmation = None
                self._confirmation_action = None
            elif isinstance(self.view, GameView):
                self.view.pause()
            elif isinstance(self.view, HomeView):
                self.request_exit()
            else:
                self.show("home")
            return
        translated = self._translate_event(event)
        if self._confirmation is not None:
            result = self._confirmation.handle_event(translated)
            if result == "cancel":
                self._confirmation = None
                self._confirmation_action = None
            elif result == "confirm":
                action = self._confirmation_action
                self._confirmation = None
                self._confirmation_action = None
                if action is not None:
                    action()
            return
        self.manager.process_events(translated)
        if translated.type == pygame_gui.UI_BUTTON_PRESSED and self.view is not None:
            self.view.handle_button(translated.ui_element)
        if self.view is not None:
            self.view.handle_event(translated)

    def update(self, delta: float) -> None:
        if self.view is not None:
            self.view.update(delta)
        self.manager.update(delta)

    def render(self) -> pygame.Surface:
        self._ensure_render_surface()
        self.assets.set_render_scale(
            self.logical.get_width() / LOGICAL_SIZE[0]
        )
        self.logical.fill(BG)
        if self.view is not None:
            self.view.draw(self.logical)
        if self._toast and self.clock() < self._toast_until:
            rect = pygame.Rect(550, 800, 500, 46)
            draw_native_rect(
                self.logical,
                (6, 25, 34),
                rect,
                border_radius=8,
            )
            draw_native_rect(
                self.logical,
                self._toast_colour,
                rect,
                1,
                border_radius=8,
            )
            draw_text(self.logical, self._toast, rect.center, 15, self._toast_colour, bold=True, anchor="center")
        if self._confirmation is not None:
            self._confirmation.draw(self.logical)
        return self.logical

    def present(self) -> None:
        frame = self.render()
        width, height = self.display.get_size()
        self.display.fill((0, 0, 0))
        self.display.blit(
            frame,
            (
                (width - frame.get_width()) // 2,
                (height - frame.get_height()) // 2,
            ),
        )
        pygame.display.flip()

    def run(self, *, max_frames: int | None = None) -> None:
        self.running = True
        frames = 0
        while self.running:
            delta = self.frame_clock.tick(60) / 1000.0
            for event in pygame.event.get():
                self.process_event(event)
            self.update(delta)
            self.present()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        if isinstance(self.view, GameView):
            self._suspend_game(self.view)
        pygame.quit()

    def save_screenshot(self, path: Path) -> None:
        pygame.image.save(self.render(), path)


def run() -> None:
    AYGeographyApp().run()
