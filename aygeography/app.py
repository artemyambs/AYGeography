from __future__ import annotations

import ctypes
import json
import os
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
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

from .application import AnswerQuestion, FinishRound, StartReviewRound, StartRound
from .application.ports import Clock, RandomFactory
from .config import (
    ASSETS_DIR,
    CONFIG_PROVIDER,
    CONTINENT_NAMES,
    SAVE_DIR,
)
from .models import GameConfig, RoundResult
from .scoring import ScoreRules
from .domain.result_rating import ResultRatingPolicy
from .infrastructure.content import ConfigProvider, ContentCatalogLoader
from .infrastructure.runtime import PythonRandomFactory, SystemClock
from .profile_progress import ProfileProgression
from .profiles import ProfileManager
from .progression import ProgressionCatalog, ProgressionService
from .quiz import GameSession, QuestionFactory
from .infrastructure.sqlite import GameRepository
from .ui.components import (
    BG,
    CYAN,
    GREEN,
    LOGICAL_SIZE,
    PANEL_ALT,
    RED,
    TEXT,
    MapRenderer,
    draw_logo,
    draw_native_rect,
    draw_text,
)
from .ui.modals import ConfirmationModal
from .ui.notifications import AchievementNotificationCenter
from .ui.presenters import QuestionPresenterRegistry
from .ui.screen_registry import ScreenRegistry
from .ui.file_dialogs import WindowsProfileFileDialog
from .ui.screens import (
    GameView,
    HomeView,
    ProfileSelectionView,
    ResultView,
    VIEW_TYPES,
)


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
        clock_source: Clock | None = None,
        random_factory: RandomFactory | None = None,
        config_provider: ConfigProvider | None = None,
        content_loader: ContentCatalogLoader | None = None,
    ) -> None:
        self.config_provider = config_provider or CONFIG_PROVIDER
        self.config_provider.validate_manifest()
        runtime_settings = self.config_provider.object(
            "app_settings.json",
            schema_version=1,
        )
        self.runtime_settings = runtime_settings
        self.app_name = str(runtime_settings["app"]["name"])
        self.app_version = str(runtime_settings["app"]["version"])
        self.question_time_seconds = int(
            runtime_settings["gameplay"]["question_time_seconds"]
        )
        self.score_rules = ScoreRules(
            self.config_provider.directory / "scoring.json",
            self.question_time_seconds,
        )
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.display.set_icon(
            pygame.image.load(ASSETS_DIR / "app_icon.png")
        )
        pygame.display.set_caption(f"{self.app_name} {self.app_version}")
        self._headless = headless
        self._fullscreen = False
        self._windowed_size = self._safe_window_size()
        self.display = pygame.display.set_mode(self._windowed_size, pygame.RESIZABLE)
        self.logical = pygame.Surface(self._render_size()).convert()
        self.clock_source = clock_source or SystemClock()
        self.random_factory = random_factory or PythonRandomFactory()
        self.frame_clock = pygame.time.Clock()
        self.running = False
        self._present_loading(10, "Подготовка окна")

        content_loader = content_loader or ContentCatalogLoader(
            self.config_provider.directory,
            ASSETS_DIR,
        )
        self.catalog = content_loader.load_countries()
        self._present_loading(25, "Загрузка карты мира")
        self.wonder_catalog = content_loader.load_wonders(self.catalog)
        self.water_catalog = content_loader.load_waters(self.catalog)
        self._present_loading(42, "Загрузка игровых данных")
        self.profile_progression = ProfileProgression(
            self.config_provider.directory / "progression.json"
        )
        self.profile_manager = (
            None
            if repository is not None
            else ProfileManager(SAVE_DIR, self.profile_progression)
        )
        self._profile_selected = self.profile_manager is None
        self._bootstrap_directory: TemporaryDirectory[str] | None = None
        if self.profile_manager is not None:
            profiles = self.profile_manager.profiles()
            if profiles:
                repository = self.profile_manager.repository(profiles[0].id)
            else:
                self._bootstrap_directory = TemporaryDirectory()
                repository = GameRepository(
                    Path(self._bootstrap_directory.name) / "bootstrap.db",
                    self.profile_progression,
                )
        assert repository is not None
        self.repository = repository
        self._present_loading(60, "Загрузка профиля")
        self.progression_catalog = ProgressionCatalog(
            self.config_provider.directory / "progression.json",
            self.config_provider.directory / "achievements.json",
        )
        self.question_factory = QuestionFactory(
            water_catalog=self.water_catalog,
            wonder_catalog=self.wonder_catalog,
            mode_settings=dict(self.runtime_settings["modes"]),
        )
        self.mode_registry = self.question_factory.registry
        self.presenter_registry = QuestionPresenterRegistry.default()
        self.presenter_registry.validate(self.mode_registry.descriptors)
        self.screen_registry = ScreenRegistry(VIEW_TYPES)
        self.progression = self._create_progression_service()
        self.result_ratings = ResultRatingPolicy.from_config(
            self.config_provider.object("result_levels.json", schema_version=1)
        )
        self._create_use_cases()
        self._present_loading(75, "Подготовка режимов")
        self.map_renderer = MapRenderer(
            ASSETS_DIR / "maps/world_geometry.json",
            self.water_catalog,
        )
        self._present_loading(88, "Подготовка интерфейса")
        self.assets = AssetStore()
        self.manager = LogicalUIManager(
            LOGICAL_SIZE,
            mouse_position_mapper=self._logical_position,
            theme_path=ASSETS_DIR / "theme.json",
            enable_live_theme_updates=False,
            starting_language="ru",
        )
        self._achievement_notifications = AchievementNotificationCenter(
            self.clock,
            self.assets.icon,
        )
        self._present_loading(96, "Завершение загрузки")
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
        self._transition_surface: pygame.Surface | None = None
        self._transition_started = 0.0
        self._transition_duration = 0.24
        self._cursor_is_hand = False
        self._present_loading(100, "Готово")
        self.show("profile_select" if self.profile_manager is not None else "home")
        if self.profile_manager is None and self._active_game_state is not None:
            self._offer_resume_game()
        if (
            self.profile_manager is None
            and self.repository.settings()["fullscreen"]
            and not headless
        ):
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

    def _present_loading(self, progress: int, label: str) -> None:
        """Present real bootstrap milestones before the regular loop starts."""
        self.logical.fill(BG)
        draw_logo(self.logical, (800, 315), 88)
        draw_text(
            self.logical,
            self.app_name,
            (800, 430),
            32,
            TEXT,
            bold=True,
            anchor="center",
        )
        bar = pygame.Rect(500, 500, 600, 18)
        draw_native_rect(self.logical, PANEL_ALT, bar, border_radius=9)
        draw_native_rect(
            self.logical,
            CYAN,
            (bar.left, bar.top, round(bar.width * progress / 100), bar.height),
            border_radius=9,
        )
        draw_text(
            self.logical,
            f"{progress}% · {label}",
            (800, 550),
            15,
            TEXT,
            bold=True,
            anchor="center",
        )
        if self._headless:
            return
        width, height = self.display.get_size()
        self.display.fill((0, 0, 0))
        self.display.blit(
            self.logical,
            (
                (width - self.logical.get_width()) // 2,
                (height - self.logical.get_height()) // 2,
            ),
        )
        pygame.display.flip()

    def clock(self) -> float:
        return self.clock_source()

    def _create_progression_service(self) -> ProgressionService:
        service = ProgressionService(
            self.repository,
            self.catalog,
            self.progression_catalog,
            self.mode_registry,
        )
        service.sync()
        return service

    def _create_use_cases(self) -> None:
        self._start_round = StartRound(
            self.question_factory,
            self.catalog,
            self.repository,
            self.score_rules,
            self.question_time_seconds,
        )
        self._start_review_round = StartReviewRound(
            self.repository,
            self.random_factory,
            self.score_rules,
            self.question_time_seconds,
        )
        self._answer_question = AnswerQuestion()
        self._finish_round = FinishRound(
            self.repository,
            self.progression,
        )

    def select_profile(self, profile_id: str) -> None:
        if self.profile_manager is None:
            return
        self.profile_manager.set_active_profile(profile_id)
        self._profile_selected = True
        self.repository = self.profile_manager.repository(profile_id)
        self.progression = self._create_progression_service()
        self._create_use_cases()
        self._active_game_state = self.repository.load_active_game()
        if not self._headless:
            fullscreen = bool(self.repository.settings()["fullscreen"])
            if fullscreen != self._fullscreen:
                self.set_fullscreen(fullscreen)
        self.show("home")
        if self._active_game_state is not None:
            self._offer_resume_game()

    def create_profile(self, nickname: str, avatar: int) -> None:
        if self.profile_manager is None:
            return
        profile = self.profile_manager.create(nickname, avatar)
        self.select_profile(profile.id)
        self.toast("Профиль создан", GREEN)

    def request_profile_deletion(self, profile_id: str) -> None:
        if self.profile_manager is None:
            return
        profiles = {item.id: item for item in self.profile_manager.profiles()}
        profile = profiles.get(profile_id)
        if profile is None:
            return
        self._open_confirmation(
            title="Удаление профиля",
            description=f"Удалить профиль «{profile.nickname}»?",
            action_name="Продолжить",
            action=lambda: self._confirm_profile_deletion(profile_id),
            danger=True,
        )

    def _confirm_profile_deletion(self, profile_id: str) -> None:
        assert self.profile_manager is not None
        profiles = {item.id: item for item in self.profile_manager.profiles()}
        profile = profiles.get(profile_id)
        if profile is None:
            return
        self._open_confirmation(
            title="Подтвердите удаление",
            description=(
                f"Все данные профиля «{profile.nickname}» будут удалены безвозвратно."
            ),
            action_name="Удалить",
            action=lambda: self._delete_profile(profile_id),
            danger=True,
        )

    def _delete_profile(self, profile_id: str) -> None:
        assert self.profile_manager is not None
        self.profile_manager.delete(profile_id)
        active_id = self.profile_manager.active_profile_id()
        if active_id:
            self.repository = self.profile_manager.repository(active_id)
            self.progression = self._create_progression_service()
            self._create_use_cases()
            self.show("profile")
        else:
            self._profile_selected = False
            if self._bootstrap_directory is None:
                self._bootstrap_directory = TemporaryDirectory()
            self.repository = GameRepository(
                Path(self._bootstrap_directory.name) / "bootstrap.db",
                self.profile_progression,
            )
            self.progression = self._create_progression_service()
            self._create_use_cases()
            self.show("profile_select")
        self.toast("Профиль удалён", GREEN)

    def export_current_profile(self, destination: Path | None = None) -> None:
        if self.profile_manager is None:
            self.toast("Экспорт недоступен для временного профиля", RED)
            return
        profile_id = self.profile_manager.active_profile_id()
        if profile_id is None:
            self.toast("Сначала выберите профиль", RED)
            return
        if destination is None:
            try:
                destination = self._save_profile_dialog()
            except OSError as error:
                self.toast(f"Ошибка системного диалога: {error}", RED)
                return
        if destination is None:
            return
        try:
            path = self.profile_manager.export_profile(
                profile_id,
                destination,
            )
        except (OSError, ValueError) as error:
            self.toast(f"Ошибка экспорта: {error}", RED)
            return
        self.toast(f"Профиль сохранён: {path.name}", GREEN)

    def import_profile(self, source: Path | None = None) -> None:
        if self.profile_manager is None:
            self.toast("Импорт недоступен для временного профиля", RED)
            return
        if source is None:
            try:
                source = self._open_profile_dialog()
            except OSError as error:
                self.toast(f"Ошибка системного диалога: {error}", RED)
                return
        if source is None:
            return
        try:
            profile = self.profile_manager.import_profile(source)
        except (OSError, ValueError, zipfile.BadZipFile, json.JSONDecodeError) as error:
            self.toast(f"Ошибка импорта: {error}", RED)
            return
        self.select_profile(profile.id)
        self.toast("Профиль импортирован", GREEN)

    @staticmethod
    def _window_handle() -> int | None:
        value = pygame.display.get_wm_info().get("window")
        return int(value) if value else None

    def _save_profile_dialog(self) -> Path | None:
        return WindowsProfileFileDialog.save(self._window_handle())

    def _open_profile_dialog(self) -> Path | None:
        return WindowsProfileFileDialog.open(self._window_handle())

    def show(self, name: str) -> None:
        if (
            self.profile_manager is not None
            and not self._profile_selected
            and name not in {"profile_select", "profile_create"}
        ):
            name = "profile_select"
        previous_frame = self._capture_transition_frame()
        if isinstance(self.view, GameView):
            self._suspend_game(self.view)
        self.manager.clear_and_reset()
        self._confirmation = None
        self._confirmation_action = None
        self.view = self.screen_registry.create(name, self)
        self._transition_surface = previous_frame
        self._transition_started = self.clock()

    def animate_view_update(self, update: Callable[[], None]) -> None:
        """Apply an in-place view change using the standard screen transition."""
        previous_frame = self._capture_transition_frame()
        update()
        self._transition_surface = previous_frame
        self._transition_started = self.clock()

    def _capture_transition_frame(self) -> pygame.Surface | None:
        return self.render().copy() if self.view is not None else None

    def show_game(self) -> None:
        if isinstance(self.view, GameView):
            return
        if self._active_game_state is None:
            self.show("home")
            return
        previous_frame = self._capture_transition_frame()
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
        self._transition_surface = previous_frame
        self._transition_started = self.clock()

    def start_game(self, config: GameConfig) -> None:
        try:
            session = self._start_round.execute(config)
        except ValueError as error:
            self.toast(str(error), RED)
            return
        previous_frame = self._capture_transition_frame()
        self._clear_active_game()
        self.manager.clear_and_reset()
        self._confirmation = None
        self._confirmation_action = None
        self.view = GameView(
            self,
            session,
        )
        self._transition_surface = previous_frame
        self._transition_started = self.clock()

    def start_review_game(self) -> None:
        try:
            session = self._start_review_round.execute()
        except ValueError as error:
            self.toast(str(error), RED)
            return
        previous_frame = self._capture_transition_frame()
        self._clear_active_game()
        self.manager.clear_and_reset()
        self._confirmation = None
        self._confirmation_action = None
        self.view = GameView(self, session)
        self._transition_surface = previous_frame
        self._transition_started = self.clock()

    def pending_review_count(self) -> int:
        return self._start_review_round.pending_count()

    def answer_question(
        self,
        session: GameSession,
        value: str,
        elapsed_seconds: float,
    ):
        return self._answer_question.execute(session, value, elapsed_seconds)

    def finish_game(self, result: RoundResult) -> None:
        previous_frame = self._capture_transition_frame()
        self._clear_active_game()
        unlocked = self._finish_round.execute(result)
        self.manager.clear_and_reset()
        self.view = ResultView(self, result)
        self._transition_surface = previous_frame
        self._transition_started = self.clock()
        self._notify_achievements(unlocked)

    def end_round(self, result: RoundResult) -> None:
        previous_frame = self._capture_transition_frame()
        self._clear_active_game()
        if result.answers:
            unlocked = self._finish_round.execute(result)
        else:
            unlocked = []
        self.view = None
        self.show("home")
        self._transition_surface = previous_frame
        self._transition_started = self.clock()
        self._notify_achievements(unlocked)

    def _notify_achievements(self, unlocked) -> None:
        self._achievement_notifications.add(unlocked)

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
            description=f"Завершить игру {self.app_name}?",
            action_name="Выйти [Enter]",
            cancel_name="Отмена [Esc]",
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
        cancel_name: str = "Отмена",
        danger: bool = False,
    ) -> None:
        if self._confirmation is not None:
            return
        self._confirmation_action = action
        self._confirmation = ConfirmationModal(
            title=title,
            description=description,
            action_name=action_name,
            cancel_name=cancel_name,
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
                if self.view.paused:
                    self.view.resume()
                else:
                    self.view.pause()
            elif isinstance(self.view, (HomeView, ProfileSelectionView)):
                self.request_exit()
            elif self.profile_manager is not None and not self._profile_selected:
                self.show("profile_select")
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
        if (
            translated.type == pygame.MOUSEBUTTONUP
            and translated.button == 1
            and self._achievement_notifications.close_at(translated.pos)
        ):
            return
        self.manager.process_events(translated)
        if self.view is not None:
            self.view.record_pointer_event(translated)
        if translated.type == pygame_gui.UI_BUTTON_PRESSED and self.view is not None:
            self.view.handle_button(translated.ui_element)
        if self.view is not None:
            self.view.handle_event(translated)

    def update(self, delta: float) -> None:
        if self.view is not None:
            self.view.update(delta)
        self.manager.update(delta)
        self._update_cursor()

    def _update_cursor(self) -> None:
        if self._headless:
            return
        position = self._logical_position(pygame.mouse.get_pos())
        if self._confirmation is not None:
            hand = (
                self._confirmation.cancel_rect.collidepoint(position)
                or self._confirmation.confirm_rect.collidepoint(position)
            )
        else:
            hand = bool(
                self._achievement_notifications.interactive_at(position)
                or (
                    self.view is not None
                    and self.view.interactive_at(position)
                )
            )
        if self.view is not None:
            self.view.set_pointer_position(position)
        if hand == self._cursor_is_hand:
            return
        try:
            pygame.mouse.set_cursor(
                pygame.SYSTEM_CURSOR_HAND
                if hand
                else pygame.SYSTEM_CURSOR_ARROW
            )
        except pygame.error:
            return
        self._cursor_is_hand = hand

    def render(self) -> pygame.Surface:
        self._ensure_render_surface()
        self.assets.set_render_scale(
            self.logical.get_width() / LOGICAL_SIZE[0]
        )
        self.logical.fill(BG)
        if self.view is not None:
            self.view.draw(self.logical)
        self.manager.draw_ui(self.logical)
        if self.view is not None:
            self.view.draw_interaction_effects(self.logical)
        self._draw_transition()
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
        self._draw_achievement_cards()
        if self._confirmation is not None:
            self._confirmation.draw(
                self.logical,
                self._logical_position(pygame.mouse.get_pos()),
            )
        return self.logical

    def _draw_transition(self) -> None:
        if self._transition_surface is None:
            return
        progress = (
            self.clock() - self._transition_started
        ) / self._transition_duration
        if progress >= 1:
            self._transition_surface = None
            return
        frame = self._transition_surface
        if frame.get_size() != self.logical.get_size():
            frame = pygame.transform.smoothscale(
                frame,
                self.logical.get_size(),
            )
        frame.set_alpha(round(255 * (1 - progress)))
        self.logical.blit(
            frame,
            (-round(22 * progress), 0),
        )

    def _draw_achievement_cards(self) -> None:
        self._achievement_notifications.draw(self.logical)

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
