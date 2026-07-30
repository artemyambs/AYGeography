import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from aygeography.app import AYGeographyApp
from aygeography.config import ANSWER_FEEDBACK_SECONDS, ASSETS_DIR
from aygeography.domain.questions import (
    FlagContent,
    MapContent,
    MapOverlay,
    PopulationContent,
    WonderContent,
)
from aygeography.models import GameConfig
from aygeography.formatting import format_population
from aygeography.quiz import GameSession, WaterQuestionStrategy
from aygeography.storage import GameRepository
from aygeography.ui.components import (
    GREEN,
    LOGICAL_SIZE,
    MAP_SELECTION_BORDER,
    MAP_SELECTION_FILL,
    RED,
    RIVER_BORDER_WIDTH,
    RIVER_FILL_WIDTH,
    RIVER_RENDER_SCALE,
    MapCamera,
    MapRenderer,
)
from aygeography.ui.screens import (
    CAPITAL_LABEL_FONT_SIZE,
    CONTENT,
    GAMEPLAY_AREA,
    PRIMARY_ACTION_SIZE,
    QUESTION_FLAG_IMAGE_SIZE,
    QUESTION_FLAG_PANEL_SIZE,
    GameView,
    StatisticsView,
    draw_question_flag,
)


class PygameAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory()
        repository = GameRepository(
            Path(cls.temp_directory.name) / "pygame_app.db"
        )
        cls.app = AYGeographyApp(headless=True, repository=repository)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()
        cls.temp_directory.cleanup()

    def _show_water_question(self, kind: str) -> GameView:
        area = self.app.water_catalog.by_kind(kind)[0]
        country = self.app.catalog.all()[0]
        question = WaterQuestionStrategy(self.app.water_catalog).create(
            country,
            self.app.catalog.all(),
            0,
            random.Random(1),
            eligible_water_keys=frozenset({area.key}),
        )
        self.app.manager.clear_and_reset()
        self.app.view = GameView(self.app, GameSession([question]))
        return self.app.view

    def test_all_static_views_render_at_design_resolution(self):
        for name in (
            "home",
            "modes",
            "continents",
            "question_count",
            "statistics",
            "achievements",
            "mastery",
            "profile",
            "settings",
        ):
            self.app.show(name)
            self.app.update(0.016)
            self.assertEqual(LOGICAL_SIZE, self.app.render().get_size(), name)

    def test_all_static_views_render_natively_at_full_hd(self):
        previous_display = self.app.display
        self.app.display = pygame.Surface((1920, 1080))
        try:
            for name in (
                "home",
                "modes",
                "continents",
                "question_count",
                "statistics",
                "achievements",
                "mastery",
                "profile",
                "settings",
            ):
                self.app.show(name)
                self.assertEqual((1920, 1080), self.app.render().get_size(), name)
        finally:
            self.app.display = previous_display
            self.app.show("home")
            self.app.render()

    def test_selection_rows_are_centered_in_content_area(self):
        self.app.show("modes")
        mode_view = self.app.view
        first_row = [mode_view.cards[key] for key, _ in mode_view.items[:3]]
        second_row = [mode_view.cards[key] for key, _ in mode_view.items[3:]]
        self.assertEqual(CONTENT.centerx, first_row[0].unionall(first_row).centerx)
        self.assertEqual(CONTENT.centerx, second_row[0].unionall(second_row).centerx)

        self.app.show("continents")
        continent_view = self.app.view
        cards = list(continent_view.cards.values())
        first_row = cards[:4]
        second_row = cards[4:] + [continent_view.all_rect]
        self.assertEqual(CONTENT.centerx, first_row[0].unionall(first_row).centerx)
        self.assertEqual(CONTENT.centerx, second_row[0].unionall(second_row).centerx)

    def test_primary_action_buttons_have_one_size(self):
        buttons = []
        for view_name, rect_name in (
            ("home", "play_rect"),
            ("modes", "next_rect"),
            ("continents", "next_rect"),
            ("question_count", "next_rect"),
            ("profile", "save_rect"),
        ):
            self.app.show(view_name)
            buttons.append(getattr(self.app.view, rect_name).size)

        self.assertEqual([PRIMARY_ACTION_SIZE] * len(buttons), buttons)

    def test_home_uses_a_high_resolution_earth_asset(self):
        earth = self.app.assets.image(
            ASSETS_DIR / "home" / "earth_hero_v2.png"
        )

        self.assertGreaterEqual(earth.get_width(), 1600)
        self.assertGreaterEqual(earth.get_height(), 900)

    def test_continent_previews_are_reused_after_selection_change(self):
        self.app.show("continents")
        view = self.app.view
        self.app.render()
        cached_previews = {
            key: id(preview)
            for key, preview in view._preview_cache.items()
        }

        view._toggle("Europe")
        self.app.render()

        self.assertEqual(7, len(view._preview_cache))
        self.assertEqual(
            cached_previews,
            {
                key: id(preview)
                for key, preview in view._preview_cache.items()
            },
        )

    def test_question_count_defaults_to_medium_difficulty(self):
        self.app.pending_difficulty = "medium"
        self.app.show("question_count")
        view = self.app.view
        self.assertEqual("medium", view.selected_difficulty)
        self.assertEqual({"easy", "medium", "hard"}, set(view.difficulty_cards))

    def test_mode_selection_defaults_to_countries_and_waters(self):
        self.assertEqual(["countries", "waters"], self.app.pending_modes)
        self.app.show("modes")
        self.assertEqual({"countries", "waters"}, self.app.view.selected)

    def test_activity_calendar_has_30_hoverable_cells(self):
        self.app.show("statistics")
        view = self.app.view
        self.app.render()
        self.assertEqual(30, len(view.activity_cells))
        view.handle_event(
            pygame.event.Event(
                pygame.MOUSEMOTION,
                {"pos": view.activity_cells[-1][0].center},
            )
        )
        self.assertEqual("1 ч 1 мин", StatisticsView._format_play_time(3660))
        self.assertLess(
            sum(StatisticsView._activity_colour(7200)),
            sum(StatisticsView._activity_colour(60)),
        )
        self.assertEqual(LOGICAL_SIZE, self.app.render().get_size())

    def test_statistics_answer_percentage_handles_empty_data(self):
        self.assertEqual(75, StatisticsView._answer_percentage(3, 4))
        self.assertEqual(0, StatisticsView._answer_percentage(0, 0))

    def test_all_avatars_load(self):
        for index in range(10):
            avatar = self.app.assets.avatar(index)
            self.assertEqual((160, 160), avatar.get_size())
            self.assertEqual(0, avatar.get_at((0, 0)).a)

    def test_svg_icon_set_loads(self):
        icon_names = (
            "game",
            "statistics",
            "achievements",
            "mastery",
            "profile",
            "settings",
            "exit",
            "flags",
            "capitals",
            "population",
            "countries",
            "waters",
            "wonders",
            "fullscreen",
            "confirm",
            "trophy",
            "timer",
            "streak",
            "pause",
            "zoom_in",
            "zoom_out",
        )
        for name in icon_names:
            self.assertEqual((32, 32), self.app.assets.icon(name).get_size(), name)
        achievement_icons = {
            item.icon for item in self.app.progression_catalog.achievements
        }
        self.assertEqual(
            len(self.app.progression_catalog.achievements),
            len(achievement_icons),
        )
        for name in achievement_icons:
            self.assertEqual(
                (40, 40),
                self.app.assets.icon(name, (40, 40)).get_size(),
                name,
            )

    def test_achievement_and_mastery_views_render(self):
        self.app.show("achievements")
        self.assertGreater(len(self.app.view.achievement_items), 0)
        self.assertEqual(LOGICAL_SIZE, self.app.render().get_size())

        self.app.show("mastery")
        view = self.app.view
        self.assertEqual(195, len(view.mastery))
        self.assertEqual(LOGICAL_SIZE, self.app.render().get_size())
        cache = self.app.map_renderer._mastery_cache
        self.app.render()
        self.assertIs(cache, self.app.map_renderer._mastery_cache)

    def test_every_game_mode_renders(self):
        for mode in (
            "flags",
            "capitals",
            "population",
            "countries",
            "waters",
            "wonders",
        ):
            self.app.start_game(GameConfig([mode], ["Europe", "Asia"], 10))
            self.app.update(0.016)
            self.assertEqual(LOGICAL_SIZE, self.app.render().get_size(), mode)

    def test_every_wonder_presentation_renders(self):
        questions = self.app.question_factory.build(
            GameConfig(
                ["wonders"],
                list(self.app.catalog.continents),
                120,
                difficulty="medium",
            ),
            self.app.catalog,
            seed=55,
        )
        for category in ("landmark", "peak", "fact"):
            question = next(
                item
                for item in questions
                if isinstance(item.content, WonderContent)
                and item.content.category == category
            )
            self.app.manager.clear_and_reset()
            self.app.view = GameView(
                self.app,
                GameSession([question]),
            )
            self.assertEqual(
                LOGICAL_SIZE,
                self.app.render().get_size(),
                category,
            )

    def test_wonder_feedback_text_has_one_left_edge(self):
        self.app.start_game(
            GameConfig(
                ["wonders"],
                list(self.app.catalog.continents),
                10,
            )
        )
        view = self.app.view
        view._answer(view.active_question.correct_answer)

        with (
            patch("aygeography.ui.screens.draw_text") as draw_text_mock,
            patch(
                "aygeography.ui.screens.draw_multiline"
            ) as draw_multiline_mock,
        ):
            view.draw(pygame.Surface(LOGICAL_SIZE))

        feedback_call = next(
            call
            for call in draw_text_mock.call_args_list
            if call.args[1] == view.feedback
        )
        explanation_call = next(
            call
            for call in draw_multiline_mock.call_args_list
            if view.active_question.explanation in call.args[1]
        )
        self.assertEqual(
            feedback_call.args[2][0],
            explanation_call.args[2].left,
        )

    def test_wonder_feedback_has_no_next_button(self):
        for is_correct in (True, False):
            self.app.start_game(
                GameConfig(
                    ["wonders"],
                    list(self.app.catalog.continents),
                    10,
                )
            )
            view = self.app.view
            answer = view.active_question.correct_answer
            if not is_correct:
                answer = next(
                    option
                    for option in view.active_question.options
                    if option != answer
                )
            view._answer(answer)

            with patch(
                "aygeography.ui.screens.draw_button"
            ) as draw_button_mock:
                view.draw(pygame.Surface(LOGICAL_SIZE))

            self.assertNotIn(
                "Далее",
                [
                    call.args[2]
                    for call in draw_button_mock.call_args_list
                ],
            )

    def test_feedback_keyboard_advance_in_every_mode(self):
        previous_clock = self.app.clock_source
        now = [100.0]
        self.app.clock_source = lambda: now[0]
        try:
            for mode in (
                "flags",
                "capitals",
                "population",
                "countries",
                "waters",
                "wonders",
            ):
                for key in (
                    pygame.K_RETURN,
                    pygame.K_KP_ENTER,
                    pygame.K_SPACE,
                ):
                    with self.subTest(mode=mode, key=key):
                        self.app.start_game(
                            GameConfig(
                                [mode],
                                list(self.app.catalog.continents),
                                10,
                            )
                        )
                        view = self.app.view
                        view._answer(view.active_question.correct_answer)
                        self.assertEqual(
                            100.0
                            + ANSWER_FEEDBACK_SECONDS[mode]["correct"],
                            view.advance_at,
                        )
                        view.handle_event(
                            pygame.event.Event(
                                pygame.KEYDOWN,
                                {"key": key},
                            )
                        )
                        self.assertEqual(2, view.active_question_number)
        finally:
            self.app.clock_source = previous_clock

    def test_feedback_click_advances_only_inside_gameplay_area(self):
        self.app.start_game(
            GameConfig(
                ["wonders"],
                list(self.app.catalog.continents),
                10,
            )
        )
        view = self.app.view
        incorrect = next(
            option
            for option in view.active_question.options
            if option != view.active_question.correct_answer
        )
        view._answer(incorrect)

        ignored_clicks = (
            (10, GAMEPLAY_AREA.centery),
            (GAMEPLAY_AREA.centerx, 35),
            (GAMEPLAY_AREA.centerx, LOGICAL_SIZE[1] - 10),
        )
        for position in ignored_clicks:
            view.handle_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    {"pos": position, "button": 1},
                )
            )
        view.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": GAMEPLAY_AREA.center, "button": 3},
            )
        )
        self.assertEqual(1, view.active_question_number)

        view.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": GAMEPLAY_AREA.center, "button": 1},
            )
        )
        self.assertEqual(2, view.active_question_number)

    def test_question_count_disables_unsupported_wonder_rounds(self):
        self.app.pending_modes = ["wonders"]
        self.app.pending_continents = ["Europe"]
        self.app.pending_count = 100
        self.app.show("question_count")
        view = self.app.view
        self.assertIn(10, view.available_counts)
        self.assertNotIn(100, view.available_counts)

    def test_number_keys_choose_matching_answer(self):
        number_keys = (
            pygame.K_1,
            pygame.K_2,
            pygame.K_3,
            pygame.K_4,
            pygame.K_5,
            pygame.K_6,
        )
        self.app.start_game(GameConfig(["flags"], ["Europe", "Asia"], 10))
        view = self.app.view
        answer_index = view.active_question.options.index(
            view.active_question.correct_answer
        )

        view.handle_event(
            pygame.event.Event(
                pygame.KEYDOWN,
                {"key": number_keys[answer_index]},
            )
        )
        view.handle_event(
            pygame.event.Event(
                pygame.KEYDOWN,
                {"key": number_keys[answer_index]},
            )
        )

        self.assertEqual(1, len(view.session.answers))
        self.assertTrue(view.session.answers[0].is_correct)

    def test_water_choice_draws_only_the_question_region(self):
        view = self._show_water_question("sea")
        self.assertEqual("choices", view.active_question.interaction)
        self.assertEqual(6, len(view.active_question.options))
        self.assertEqual(6, len(view.answer_buttons))
        self.assertIsInstance(view.active_question.content, MapContent)
        self.assertTrue(view.active_question.content.water_highlight)
        self.app.map_renderer._view_cache_key = None
        with patch.object(
            self.app.map_renderer,
            "_water_polygon",
            wraps=self.app.map_renderer._water_polygon,
        ) as water_polygon:
            self.app.render()
        self.assertEqual(1, water_polygon.call_count)

    def test_river_answers_are_placed_below_the_map(self):
        view = self._show_water_question("river")

        self.assertIsInstance(view.active_question.content, MapContent)
        self.assertIsNotNone(view.active_question.content.overlay)
        self.assertEqual(
            710,
            min(button.rect.top for button in view.answer_buttons),
        )
        self.assertTrue(
            all(
                not view.map_rect.colliderect(button.rect)
                for button in view.answer_buttons
            )
        )

    def test_country_and_water_use_the_shared_region_selection(self):
        for mode in ("countries", "waters"):
            if mode == "waters":
                self._show_water_question("sea")
            else:
                self.app.start_game(GameConfig([mode], ["Europe", "Asia"], 10))
            self.app.map_renderer._view_cache_key = None
            with patch.object(
                self.app.map_renderer,
                "_draw_region_selection",
                wraps=self.app.map_renderer._draw_region_selection,
            ) as draw_selection:
                self.app.render()
            self.assertEqual(1, draw_selection.call_count, mode)

    def test_region_selection_has_no_external_glow(self):
        surface = pygame.Surface((50, 50))
        background = pygame.Color("#010203")
        surface.fill(background)

        MapRenderer._draw_region_selection(
            surface,
            [[(15, 15), (35, 15), (35, 35), (15, 35)]],
        )

        self.assertEqual(background, surface.get_at((10, 25)))
        self.assertNotEqual(background, surface.get_at((25, 25)))

    def test_wonder_overlays_use_region_selection_palette(self):
        surface = pygame.Surface((200, 100))
        rect = surface.get_rect()

        with patch("pygame.draw.circle", wraps=pygame.draw.circle) as circle:
            self.app.map_renderer._draw_overlay(
                surface,
                rect,
                MapCamera(),
                MapOverlay(kind="point", point=(0, 0)),
            )
        point_colours = {call.args[1] for call in circle.call_args_list}
        self.assertIn(MAP_SELECTION_FILL, point_colours)
        self.assertIn(MAP_SELECTION_BORDER, point_colours)

        with patch("pygame.draw.lines", wraps=pygame.draw.lines) as lines:
            self.app.map_renderer._draw_overlay(
                surface,
                rect,
                MapCamera(),
                MapOverlay(
                    kind="line",
                    lines=(((-10, 0), (0, 5), (10, 0)),),
                ),
            )
        line_colours = {call.args[1] for call in lines.call_args_list}
        line_widths = {call.args[4] for call in lines.call_args_list}
        self.assertEqual(
            {MAP_SELECTION_FILL, MAP_SELECTION_BORDER},
            line_colours,
        )
        self.assertEqual(
            {
                RIVER_FILL_WIDTH * RIVER_RENDER_SCALE,
                RIVER_BORDER_WIDTH * RIVER_RENDER_SCALE,
            },
            line_widths,
        )

    def test_river_overlay_interpolates_angular_control_points(self):
        points = [(0, 0), (50, 50), (100, 0)]

        smoothed = MapRenderer._smooth_polyline(points)

        self.assertEqual((0.0, 0.0), smoothed[0])
        self.assertEqual((100.0, 0.0), smoothed[-1])
        self.assertGreater(len(smoothed), len(points))
        corner_index = smoothed.index((50.0, 50.0))
        corner = pygame.Vector2(smoothed[corner_index])
        incoming = corner - pygame.Vector2(smoothed[corner_index - 1])
        outgoing = pygame.Vector2(smoothed[corner_index + 1]) - corner
        self.assertGreater(incoming.normalize().dot(outgoing.normalize()), 0.8)

    def test_capital_question_uses_compact_flag_layout(self):
        self.app.start_game(GameConfig(["capitals"], ["Europe"], 10))
        view = self.app.view
        answers_top = min(button.rect.top for button in view.answer_buttons)
        self.assertIsInstance(view.active_question.content, FlagContent)
        self.assertTrue(view.active_question.content.capital_layout)
        self.assertEqual(view.active_question.country_iso, view.active_question.visual)
        self.assertEqual(530, answers_top)

    def test_capital_country_name_keeps_catalogue_casing(self):
        self.app.start_game(GameConfig(["capitals"], ["Europe"], 10))
        view = self.app.view
        with patch("aygeography.ui.screens.draw_text") as draw:
            view._draw_capital_question(pygame.Surface(LOGICAL_SIZE))

        self.assertEqual(view.active_question.prompt, draw.call_args_list[0].args[1])
        self.assertNotEqual(
            view.active_question.prompt.upper(),
            draw.call_args_list[0].args[1],
        )

    def test_flag_question_modes_use_one_framed_flag_size(self):
        self.assertEqual((280, 180), QUESTION_FLAG_IMAGE_SIZE)
        self.assertEqual((300, 200), QUESTION_FLAG_PANEL_SIZE)
        self.assertEqual(26, CAPITAL_LABEL_FONT_SIZE)
        for mode, expected_flags in (
            ("flags", 1),
            ("capitals", 1),
            ("population", 2),
        ):
            self.app.start_game(GameConfig([mode], ["Europe"], 10))
            with patch(
                "aygeography.ui.screens.draw_question_flag",
                wraps=draw_question_flag,
            ) as screen_flag, patch(
                "aygeography.ui.presenters.draw_question_flag",
                wraps=draw_question_flag,
            ) as presenter_flag:
                self.app.render()
            self.assertEqual(
                expected_flags,
                screen_flag.call_count + presenter_flag.call_count,
                mode,
            )

    def test_answer_feedback_does_not_mix_two_questions(self):
        for mode in ("flags", "capitals", "population", "countries", "waters"):
            self.app.start_game(GameConfig([mode], ["Europe", "Asia"], 10))
            view = self.app.view
            answer = view.active_question.correct_answer
            view._answer(answer)
            self.assertEqual(LOGICAL_SIZE, self.app.render().get_size(), mode)
            view.advance_at = 0
            view.update(1.0)
            self.assertEqual(LOGICAL_SIZE, self.app.render().get_size(), mode)

    def test_population_comparison_renders_two_answers(self):
        self.app.start_game(GameConfig(["population"], ["Europe"], 10))
        view = self.app.view
        self.assertEqual(
            "country_comparison",
            view.active_question.presenter_key,
        )
        self.assertEqual(2, len(view.active_question.country_isos))
        self.assertEqual(2, len(view.answer_buttons))
        self.assertEqual(LOGICAL_SIZE, self.app.render().get_size())

    def test_population_feedback_shows_both_exact_values(self):
        self.app.start_game(GameConfig(["population"], ["Europe"], 10))
        view = self.app.view
        question = view.active_question
        countries_by_name = {
            self.app.catalog.get(iso3).name: self.app.catalog.get(iso3)
            for iso3 in question.country_isos
        }
        details = " • ".join(
            f"{name} — {format_population(countries_by_name[name].population)}"
            for name in question.options
        )
        view._answer(view.active_question.correct_answer)
        self.assertEqual(
            f"Верно! {details} человек",
            view.feedback,
        )

        self.app.start_game(GameConfig(["population"], ["Europe"], 10))
        view = self.app.view
        question = view.active_question
        countries_by_name = {
            self.app.catalog.get(iso3).name: self.app.catalog.get(iso3)
            for iso3 in question.country_isos
        }
        details = " • ".join(
            f"{name} — {format_population(countries_by_name[name].population)}"
            for name in question.options
        )
        wrong_answer = next(
            option
            for option in view.active_question.options
            if option != view.active_question.correct_answer
        )
        view._answer(wrong_answer)
        self.assertEqual(
            f"Неверно. {details} человек",
            view.feedback,
        )

    def test_population_uses_its_own_feedback_delays(self):
        previous_clock = self.app.clock_source
        now = [100.0]
        self.app.clock_source = lambda: now[0]
        try:
            self.app.start_game(GameConfig(["population"], ["Europe"], 10))
            view = self.app.view
            view._answer(view.active_question.correct_answer)
            self.assertEqual(
                100.0 + ANSWER_FEEDBACK_SECONDS["population"]["correct"],
                view.advance_at,
            )

            self.app.start_game(GameConfig(["population"], ["Europe"], 10))
            view = self.app.view
            wrong_answer = next(
                option
                for option in view.active_question.options
                if option != view.active_question.correct_answer
            )
            view._answer(wrong_answer)
            self.assertEqual(
                100.0 + ANSWER_FEEDBACK_SECONDS["population"]["incorrect"],
                view.advance_at,
            )
        finally:
            self.app.clock_source = previous_clock

    def test_correct_answer_feedback_is_visible_for_one_second(self):
        previous_clock = self.app.clock_source
        now = [100.0]
        self.app.clock_source = lambda: now[0]
        try:
            self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
            view = self.app.view
            view._answer(view.active_question.correct_answer)
            self.assertEqual(101.0, view.advance_at)
            now[0] = 100.99
            view.update(0.016)
            self.assertEqual(1, view.active_question_number)
            now[0] = 101.0
            view.update(0.016)
            self.assertEqual(2, view.active_question_number)
        finally:
            self.app.clock_source = previous_clock

    def test_incorrect_answer_feedback_is_visible_for_one_and_half_seconds(self):
        previous_clock = self.app.clock_source
        now = [100.0]
        self.app.clock_source = lambda: now[0]
        try:
            self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
            view = self.app.view
            view._answer("__wrong__")
            self.assertEqual(101.5, view.advance_at)
            now[0] = 101.49
            view.update(0.016)
            self.assertEqual(1, view.active_question_number)
            now[0] = 101.5
            view.update(0.016)
            self.assertEqual(2, view.active_question_number)
        finally:
            self.app.clock_source = previous_clock

    def test_header_tracks_only_last_ten_answers(self):
        self.app.start_game(GameConfig(["flags"], ["Europe"], 25))
        view = self.app.view
        for index in range(12):
            question = view.session.current
            answer = question.correct_answer if index % 2 else "__wrong__"
            view.session.answer(answer, 1.0)
        self.assertEqual(
            [RED, GREEN, RED, GREEN, RED, GREEN, RED, GREEN, RED, GREEN],
            view._recent_answer_colours(),
        )

    def test_map_camera_keyboard_and_mouse_controls(self):
        self.app.start_game(GameConfig(["countries"], ["Europe"], 10))
        view = self.app.view
        initial_zoom = view.map_camera.zoom
        view.handle_event(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_PLUS}))
        self.assertGreater(view.map_camera.zoom, initial_zoom)
        start = view.map_rect.center
        end = (start[0] + 80, start[1] + 40)
        view.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": start, "button": 1})
        )
        view.handle_event(
            pygame.event.Event(
                pygame.MOUSEMOTION,
                {"pos": end, "rel": (80, 40), "buttons": (1, 0, 0)},
            )
        )
        view.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": end, "button": 1})
        )
        self.assertNotEqual((0, 0), tuple(view.map_camera.offset))
        offset_after_pan = view.map_camera.offset.copy()
        view.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": start, "button": 3})
        )
        view.handle_event(
            pygame.event.Event(
                pygame.MOUSEMOTION,
                {"pos": end, "rel": (80, 40), "buttons": (0, 0, 1)},
            )
        )
        view.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONUP, {"pos": end, "button": 3})
        )
        self.assertEqual(offset_after_pan, view.map_camera.offset)
        self.assertFalse(hasattr(view.map_camera, "rotation"))
        self.assertFalse(
            any(key.startswith("rotate") for key, _ in view.map_buttons.values())
        )

    def test_atlas_and_mastery_maps_support_pan_zoom_and_country_hover(self):
        for route in ("atlas", "mastery"):
            with self.subTest(route=route):
                self.app.show(route)
                view = self.app.view
                start_zoom = view.map_camera.zoom
                view.handle_event(
                    pygame.event.Event(
                        pygame.MOUSEMOTION,
                        {"pos": view.map_rect.center, "rel": (0, 0)},
                    )
                )
                view.handle_event(
                    pygame.event.Event(
                        pygame.MOUSEWHEEL,
                        {"y": 1, "x": 0},
                    )
                )
                self.assertGreater(view.map_camera.zoom, start_zoom)
                country_position = self.app.map_renderer.project(
                    self.app.map_renderer.centers["RUS"],
                    view.map_rect,
                    view.map_camera,
                )
                self.assertEqual(
                    "RUS",
                    self.app.map_renderer.country_at(
                        country_position,
                        view.map_rect,
                        view.map_camera,
                    ),
                )

    def test_profile_avatar_grid_is_centered(self):
        self.app.show("profile")
        rects = self.app.view.avatar_rects[:5]
        self.assertLessEqual(
            abs((rects[0].left + rects[-1].right) / 2 - CONTENT.centerx),
            2,
        )

    def test_country_highlight_starts_at_nine_x_zoom(self):
        self.app.start_game(GameConfig(["countries"], ["Europe"], 10))
        view = self.app.view
        self.assertIsInstance(view.active_question.content, MapContent)
        self.assertTrue(view.active_question.content.highlight_country)
        self.assertEqual(9.0, view.map_camera.zoom)
        highlighted = view.active_question.content.highlight_country
        centre = self.app.map_renderer.centers[highlighted]
        projected = self.app.map_renderer.project(centre, view.map_rect, view.map_camera)
        self.assertLessEqual(abs(projected[0] - view.map_rect.centerx), 2)
        self.assertLessEqual(abs(projected[1] - view.map_rect.centery), 2)

    def test_map_buttons_and_keyboard_zoom_toward_highlight(self):
        self.app.start_game(GameConfig(["countries"], ["Europe"], 10))
        view = self.app.view
        highlighted = view.active_question.content.highlight_country
        centre = self.app.map_renderer.centers[highlighted]
        view.map_camera.pan(130, -70)

        zoom_in_button = next(
            button
            for button, (key, _) in view.map_buttons.items()
            if key == "zoom_in"
        )
        view.handle_button(zoom_in_button)
        projected = self.app.map_renderer.project(
            centre,
            view.map_rect,
            view.map_camera,
        )
        self.assertLessEqual(abs(projected[0] - view.map_rect.centerx), 2)
        self.assertLessEqual(abs(projected[1] - view.map_rect.centery), 2)

        view.map_camera.pan(-90, 55)
        view._handle_map_key(pygame.K_MINUS)
        projected = self.app.map_renderer.project(
            centre,
            view.map_rect,
            view.map_camera,
        )
        self.assertLessEqual(abs(projected[0] - view.map_rect.centerx), 2)
        self.assertLessEqual(abs(projected[1] - view.map_rect.centery), 2)

    def test_water_region_starts_centered_at_three_x_zoom(self):
        view = self._show_water_question("sea")
        region = view._question_water_region(view.active_question)
        self.assertIsNotNone(region)
        self.assertEqual(3.0, view.map_camera.zoom)
        projected = self.app.map_renderer.project(
            (region.longitude, region.latitude),
            view.map_rect,
            view.map_camera,
        )
        self.assertLessEqual(abs(projected[0] - view.map_rect.centerx), 2)
        self.assertLessEqual(abs(projected[1] - view.map_rect.centery), 2)

    def test_pause_icon_is_drawn_in_game_header(self):
        self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
        with patch.object(
            self.app.assets,
            "icon",
            wraps=self.app.assets.icon,
        ) as icon:
            self.app.render()
        icon.assert_any_call("pause", (24, 24))

    def test_continue_button_resumes_game_and_preserves_elapsed_time(self):
        previous_clock = self.app.clock_source
        now = [100.0]
        self.app.clock_source = lambda: now[0]
        try:
            self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
            view = self.app.view
            now[0] = 105.0
            view._toggle_pause()
            continue_button = view.continue_button
            self.assertTrue(view.paused)
            self.assertIsNotNone(continue_button)

            now[0] = 112.0
            view.handle_button(continue_button)
            self.assertFalse(view.paused)
            self.assertIsNone(view.continue_button)
            self.assertEqual(107.0, view.question_started)
            self.assertEqual(5.0, now[0] - view.question_started)
        finally:
            self.app.clock_source = previous_clock

    def test_game_returns_to_same_question_paused_after_tab_switch(self):
        previous_clock = self.app.clock_source
        now = [100.0]
        self.app.clock_source = lambda: now[0]
        try:
            self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
            for _ in range(3):
                view = self.app.view
                view._answer(view.active_question.correct_answer)
                now[0] += 1.0
                view.update(0.016)
            self.assertEqual(4, self.app.view.active_question_number)

            now[0] = 103.25
            self.app.show("statistics")
            self.assertIsNotNone(self.app.repository.load_active_game())

            now[0] = 120.0
            self.app.show_game()
            restored = self.app.view
            self.assertEqual(4, restored.active_question_number)
            self.assertTrue(restored.paused)
            self.assertIsNotNone(restored.continue_button)

            restored.handle_button(restored.continue_button)
            self.assertFalse(restored.paused)
            self.assertAlmostEqual(
                0.25,
                now[0] - restored.question_started,
                places=3,
            )
        finally:
            self.app.clock_source = previous_clock

    def test_answer_feedback_countdown_stays_paused_between_tabs(self):
        previous_clock = self.app.clock_source
        now = [100.0]
        self.app.clock_source = lambda: now[0]
        try:
            self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
            view = self.app.view
            view._answer(view.active_question.correct_answer)
            now[0] = 100.2
            self.app.show("statistics")

            now[0] = 110.0
            self.app.show_game()
            restored = self.app.view
            self.assertTrue(restored.paused)
            self.assertAlmostEqual(0.8, restored.advance_at - now[0], places=3)
            restored.update(10.0)
            self.assertEqual(1, restored.active_question_number)

            restored.handle_button(restored.continue_button)
            now[0] = 110.79
            restored.update(0.79)
            self.assertEqual(1, restored.active_question_number)
            now[0] = 110.8
            restored.update(0.01)
            self.assertEqual(2, restored.active_question_number)
        finally:
            self.app.clock_source = previous_clock

    def test_saved_game_is_offered_after_application_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "restart.db"
            first_app = AYGeographyApp(
                headless=True,
                repository=GameRepository(database_path),
            )
            first_app.start_game(GameConfig(["flags"], ["Europe"], 10))
            first_app.view._answer(first_app.view.active_question.correct_answer)
            first_app.view.advance_at = 0
            first_app.view.update(0.016)
            first_app.show("statistics")

            restored_app = AYGeographyApp(
                headless=True,
                repository=GameRepository(database_path),
            )
            self.assertIsNotNone(restored_app._confirmation)
            restored_app.show_game()
            self.assertEqual(2, restored_app.view.active_question_number)
            self.assertTrue(restored_app.view.paused)

    def test_active_game_is_saved_when_application_exits(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "exit.db"
            repository = GameRepository(database_path)
            repository.set_setting("confirm_exit", False)
            first_app = AYGeographyApp(headless=True, repository=repository)
            first_app.start_game(GameConfig(["flags"], ["Europe"], 10))

            first_app.request_exit()

            self.assertFalse(first_app.running)
            self.assertTrue(first_app.view.paused)
            self.assertIsNotNone(repository.load_active_game())
            restored_app = AYGeographyApp(
                headless=True,
                repository=GameRepository(database_path),
            )
            self.assertIsNotNone(restored_app._confirmation)

    def test_end_round_saves_answers_and_opens_home(self):
        before = self.app.repository.statistics()["total"]["rounds"]
        self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
        view = self.app.view
        view._answer(view.active_question.correct_answer)
        view.pause()
        end_round_button = view.end_round_button

        view.handle_button(end_round_button)

        after = self.app.repository.statistics()["total"]["rounds"]
        self.assertEqual(before + 1, after)
        self.assertEqual("HomeView", type(self.app.view).__name__)
        self.assertIsNone(self.app.repository.load_active_game())

    def test_pygame_gui_button_navigation(self):
        self.app.show("home")
        position = (400, 480)
        for event_type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self.app.process_event(
                pygame.event.Event(event_type, {"pos": position, "button": 1})
            )
        self.app.update(0.016)
        for event in pygame.event.get():
            self.app.process_event(event)
        self.assertEqual("ModeSelectionView", type(self.app.view).__name__)

    def test_fullscreen_hover_uses_logical_mouse_coordinates(self):
        self.app.show("home")
        view = self.app.view
        play_button = next(
            button for button in view._actions if button.rect == view.play_rect
        )
        previous_display = self.app.display
        self.app.display = pygame.Surface((1920, 1080))
        try:
            physical_inside = (
                round(view.play_rect.centerx * 1.2),
                round(view.play_rect.centery * 1.2),
            )
            with patch("pygame.mouse.get_pos", return_value=physical_inside):
                self.app.update(0.016)
            self.assertTrue(play_button.hovered)

            physical_above = (physical_inside[0], view.play_rect.top + 20)
            with patch("pygame.mouse.get_pos", return_value=physical_above):
                self.app.update(0.016)
            self.assertFalse(play_button.hovered)
        finally:
            self.app.display = previous_display

    def test_fullscreen_uses_native_desktop_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            app = AYGeographyApp(
                headless=True,
                repository=GameRepository(Path(directory) / "fullscreen.db"),
            )
            expected_surface = pygame.Surface((1920, 1080))

            with patch(
                "pygame.display.set_mode",
                return_value=expected_surface,
            ) as set_mode:
                app.set_fullscreen(True)

            set_mode.assert_called_once_with((0, 0), pygame.FULLSCREEN)
            self.assertIs(expected_surface, app.display)

    def test_settings_has_only_fullscreen_toggle(self):
        self.app.show("settings")
        self.assertIn("fullscreen", self.app.view.rows)
        self.assertFalse(hasattr(self.app.view, "resolution_dropdown"))

    def test_settings_blocks_have_equal_height(self):
        self.app.show("settings")
        view = self.app.view

        heights = {
            rect.height
            for rect in (*view.rows.values(), view.reset_answers_rect)
        }

        self.assertEqual({110}, heights)

    def test_settings_reset_statistics_button_opens_confirmation(self):
        self.app._confirmation = None
        self.app._confirmation_action = None
        self.app.show("settings")
        view = self.app.view

        view.handle_button(view.reset_answers_button)

        self.assertIsNotNone(self.app._confirmation)
        self.assertEqual("Сброс статистики", self.app._confirmation.title)
        self.assertTrue(self.app._confirmation.danger)
        self.app.process_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONUP,
                {
                    "button": 1,
                    "pos": self.app._confirmation.cancel_rect.center,
                },
            )
        )

    def test_escape_pauses_active_game(self):
        self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
        previous_fullscreen = self.app._fullscreen
        self.app._fullscreen = True

        try:
            self.app.process_event(
                pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE})
            )

            self.assertTrue(self.app.view.paused)
            self.assertTrue(self.app._fullscreen)
            self.assertIsNotNone(self.app.view.continue_button)
        finally:
            self.app._fullscreen = previous_fullscreen

    def test_escape_on_home_opens_custom_exit_confirmation(self):
        self.app.show("home")
        self.app.running = True

        self.app.process_event(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE})
        )

        modal = self.app._confirmation
        self.assertIsNotNone(modal)
        self.assertEqual("Выход", modal.title)
        self.assertTrue(modal.danger)
        self.assertEqual(LOGICAL_SIZE, self.app.render().get_size())
        self.app.process_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONUP,
                {"button": 1, "pos": modal.cancel_rect.center},
            )
        )
        self.assertIsNone(self.app._confirmation)
        self.assertTrue(self.app.running)

    def test_full_hd_uses_native_render_surface(self):
        previous_display = self.app.display
        self.app.display = pygame.Surface((1920, 1080))
        try:
            frame = self.app.render()
            self.assertEqual((1920, 1080), frame.get_size())
            self.assertIs(frame, self.app.logical)
        finally:
            self.app.display = previous_display
            self.app.render()

    def test_full_hd_map_is_vector_rendered_at_physical_size(self):
        previous_display = self.app.display
        self.app.display = pygame.Surface((1920, 1080))
        try:
            self.app.start_game(GameConfig(["countries"], ["Europe"], 10))
            self.app.render()
            self.assertEqual(
                (1488, 630),
                self.app.map_renderer._view_cache.get_size(),
            )
        finally:
            self.app.display = previous_display
            self.app.show("home")
            self.app.render()

if __name__ == "__main__":
    unittest.main()
