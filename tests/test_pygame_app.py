import json
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
from aygeography.config import (
    ANSWER_FEEDBACK_SECONDS,
    ASSETS_DIR,
    WATER_KIND_FEEDBACK_SETTINGS,
)
from aygeography.domain.questions import (
    FlagContent,
    MapContent,
    MapOverlay,
    PopulationContent,
    WonderContent,
)
from aygeography.models import GameConfig
from aygeography.formatting import format_population
from aygeography.profiles import ProfileManager
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
    draw_native_rect,
    font,
)
from aygeography.ui.notifications import AchievementNotificationCenter
from aygeography.ui.screens import (
    CAPITAL_LABEL_FONT_SIZE,
    CONTENT,
    COUNTRY_FLAG_CENTER_Y,
    COUNTRY_FLAG_NAME_FONT_SIZE,
    COUNTRY_FLAG_NAME_TOP,
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

    def test_profile_entry_draws_caret_inside_scaled_field(self):
        self.app.show("profile")
        view = self.app.view
        view.entry.set_text("Test")
        view.entry.edit_position = len("Test")
        view.entry.focus()
        view.entry.cursor_on = True
        expected_x = (
            view.entry_rect.left
            + 15
            + font(17).size("Test")[0]
        )
        expected_rect = (
            expected_x,
            view.entry_rect.centery - 12,
            1,
            24,
        )

        with patch(
            "aygeography.ui.screens.draw_native_rect",
            wraps=draw_native_rect,
        ) as draw_rect:
            view.draw(pygame.Surface((1920, 1080)))

        self.assertTrue(
            any(call.args[2] == expected_rect for call in draw_rect.call_args_list)
        )

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

    def test_requested_action_buttons_share_one_size(self):
        self.app.show("profile")
        profile = self.app.view
        profile_sizes = [
            profile.save_rect.size,
            profile.create_rect.size,
            profile.delete_rect.size,
            profile.export_rect.size,
            profile.import_rect.size,
            profile.switch_rect.size,
        ]
        self.app.show("profile_create")
        create = self.app.view
        self.app.show("question_count")
        difficulty_sizes = [
            rect.size for rect in self.app.view.difficulty_cards.values()
        ]
        self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
        game = self.app.view
        sizes = profile_sizes + [
            create.create_rect.size,
            create.cancel_rect.size,
            game.continue_rect.size,
            game.end_round_rect.size,
        ] + difficulty_sizes
        self.assertEqual([PRIMARY_ACTION_SIZE] * len(sizes), sizes)

    def test_avatar_grids_are_centered_and_use_round_hover(self):
        for name in ("profile", "profile_create"):
            self.app.show(name)
            view = self.app.view
            bounds = view.avatar_rects[0].unionall(view.avatar_rects)
            self.assertEqual(CONTENT.centerx, bounds.centerx)
            self.assertEqual(10, len(view._circular_actions))

    def test_avatar_hover_uses_fill_without_outline(self):
        self.app.show("profile")
        view = self.app.view
        view.set_pointer_position(view.avatar_rects[0].center)
        target = pygame.Surface(LOGICAL_SIZE)

        with patch("aygeography.ui.screens.draw_native_circle") as draw_circle:
            view.draw_interaction_effects(target)

        draw_circle.assert_called_once()
        self.assertEqual(4, len(draw_circle.call_args.args))

    def test_final_setup_and_profile_buttons_use_explicit_labels(self):
        target = pygame.Surface(LOGICAL_SIZE)
        expected = {
            "question_count": {"Начать игру"},
            "profile": {"Экспорт профиля", "Импорт профиля"},
        }
        for route, labels in expected.items():
            with self.subTest(route=route):
                self.app.show(route)
                profile_manager = self.app.profile_manager
                if route == "profile" and profile_manager is None:
                    self.app.profile_manager = object()
                try:
                    with patch(
                        "aygeography.ui.screens.draw_button"
                    ) as draw_button:
                        self.app.view.draw(target)
                finally:
                    self.app.profile_manager = profile_manager
                rendered_labels = {
                    call.args[2]
                    for call in draw_button.call_args_list
                    if len(call.args) >= 3
                }
                self.assertTrue(labels.issubset(rendered_labels))

    def test_settings_toggle_hover_covers_the_whole_field(self):
        self.app.show("settings")
        view = self.app.view
        action_rects = [button.relative_rect for button in view._actions]
        self.assertTrue(all(rect in action_rects for rect in view.rows.values()))

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

    def test_question_count_explains_wonder_difficulty(self):
        self.app.pending_modes = ["wonders"]
        self.app.show("question_count")
        with patch("aygeography.ui.screens.draw_text") as draw_text_mock:
            self.app.render()
        self.assertIn(
            "Не влияется на режим «Чудеса света»",
            [call.args[1] for call in draw_text_mock.call_args_list],
        )

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
        colours = {
            tuple(StatisticsView._activity_colour(seconds))
            for seconds in (60, 20 * 60, 45 * 60, 90 * 60, 3 * 60 * 60)
        }
        self.assertEqual(5, len(colours))
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
            icon = self.app.assets.icon(name)
            self.assertEqual((32, 32), icon.get_size(), name)
            self.assertEqual(0, icon.get_at((0, 0)).a, name)
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

        logo = pygame.image.load(ASSETS_DIR / "logo.png")
        self.assertEqual((1024, 1024), logo.get_size())
        self.assertEqual(0, logo.get_at((0, 0)).a)

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

    def test_achievement_page_uses_standard_transition(self):
        self.app.show("achievements")
        view = self.app.view
        self.app._transition_surface = None
        view._change_page(1)
        self.assertEqual(1, view.page)
        self.assertIsNotNone(self.app._transition_surface)

    def test_achievement_notifications_stack_close_and_expire(self):
        now = [100.0]
        center = AchievementNotificationCenter(
            lambda: now[0],
            self.app.assets.icon,
        )
        definitions = self.app.progression_catalog.achievements[:2]
        center.add(definitions)
        surface = pygame.Surface(LOGICAL_SIZE)
        center.draw(surface)
        self.assertEqual(2, len(center.items))
        first_close = center._close_rects[0][0]
        second_close = center._close_rects[1][0]
        self.assertLess(first_close.top, second_close.top)
        self.assertTrue(center.close_at(first_close.center))
        now[0] += center.ANIMATION_SECONDS + 0.01
        center.update()
        self.assertEqual(1, len(center.items))
        now[0] = 110.01
        center.update()
        self.assertEqual(0, len(center.items))

    def test_achievement_notifications_queue_overflow_cards(self):
        now = [0.0]
        center = AchievementNotificationCenter(
            lambda: now[0],
            self.app.assets.icon,
        )
        center.add(
            self.app.progression_catalog.achievements[
                : center.MAX_VISIBLE + 1
            ]
        )
        active = [item for item in center.items if item.opened_at is not None]
        self.assertEqual(center.MAX_VISIBLE, len(active))
        now[0] = center.DISPLAY_SECONDS + 0.01
        center.update()
        self.assertEqual(1, len(center.items))
        self.assertEqual(now[0], center.items[0].opened_at)

    def test_pause_hotkeys_resume_and_finish_round(self):
        self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
        view = self.app.view
        view.pause()
        self.app.process_event(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE})
        )
        self.assertFalse(view.paused)
        view.pause()
        view.handle_event(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        )
        self.assertNotIsInstance(self.app.view, GameView)

    def test_pause_exposes_only_two_interactive_buttons(self):
        self.app.start_game(GameConfig(["flags"], ["Europe"], 10))
        view = self.app.view
        answer_button = next(iter(view.answer_buttons))
        view.pause()

        self.assertEqual(
            {view.continue_button, view.end_round_button},
            set(view.interaction_actions()),
        )
        self.assertFalse(view.interactive_at(answer_button.relative_rect.center))
        self.assertTrue(view.interactive_at(view.continue_rect.center))
        view.handle_button(answer_button)
        self.assertEqual(0, view.session.index)

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

    def test_wonder_fact_uses_country_flag_true_false_and_standard_feedback(self):
        questions = self.app.question_factory.build(
            GameConfig(
                ["wonders"],
                list(self.app.catalog.continents),
                25,
                difficulty="hard",
            ),
            self.app.catalog,
            seed=17,
        )
        question = next(
            item
            for item in questions
            if isinstance(item.content, WonderContent)
            and item.content.category == "fact"
        )
        self.assertEqual(["Правда", "Ложь"], question.options)
        self.app.manager.clear_and_reset()
        self.app.view = GameView(self.app, GameSession([question], "hard"))
        with (
            patch(
                "aygeography.ui.presenters.draw_question_flag"
            ) as flag_mock,
            patch("aygeography.ui.presenters.draw_text") as text_mock,
        ):
            self.app.render()
        flag_mock.assert_called_once()
        self.assertEqual(question.country_iso, flag_mock.call_args.args[2])
        self.assertIn(
            self.app.catalog.get(question.country_iso).name,
            [call.args[1] for call in text_mock.call_args_list],
        )
        country_call = next(
            call
            for call in text_mock.call_args_list
            if call.args[1] == self.app.catalog.get(question.country_iso).name
        )
        self.assertEqual(
            (CONTENT.centerx, COUNTRY_FLAG_NAME_TOP),
            country_call.args[2],
        )
        self.assertEqual(COUNTRY_FLAG_NAME_FONT_SIZE, country_call.args[3])
        self.assertTrue(country_call.kwargs["bold"])
        self.assertEqual("midtop", country_call.kwargs["anchor"])
        self.assertEqual(
            (CONTENT.centerx, COUNTRY_FLAG_CENTER_Y),
            flag_mock.call_args.args[3],
        )

        view = self.app.view
        view._answer(question.correct_answer)
        self.assertEqual("Верно! +10 очков", view.feedback)
        self.assertEqual(GREEN, view.feedback_colour)
        self.assertEqual((question.country_iso,), view.session.answers[0].subjects)

        incorrect = next(
            value for value in question.options if value != question.correct_answer
        )
        self.app.manager.clear_and_reset()
        self.app.view = GameView(self.app, GameSession([question], "easy"))
        self.app.view._answer(incorrect)
        self.assertEqual(
            f"Неверно. Правильный ответ: {question.correct_answer}",
            self.app.view.feedback,
        )
        self.assertEqual(RED, self.app.view.feedback_colour)

    def test_atlas_uses_new_fact_titles_and_distinctive_stat(self):
        self.app.show("atlas")
        view = self.app.view
        country = self.app.catalog.get("RUS")
        view.selected_country = country.iso3
        title, text = view._distinctive_stat(country)
        scores = {
            "Площадь": min(
                view._area_ranks[country.iso3],
                195 - view._area_ranks[country.iso3],
            ),
            "Население": min(
                view._population_ranks[country.iso3],
                195 - view._population_ranks[country.iso3],
            ),
            "ВВП на душу населения": min(
                view._gdp_ranks[country.iso3],
                195 - view._gdp_ranks[country.iso3],
            ),
        }
        self.assertEqual(min(scores, key=scores.get), title)
        self.assertIn("место в мире", text)

        with (
            patch("aygeography.ui.screens.draw_text") as draw_text_mock,
            patch("aygeography.ui.screens.draw_multiline") as multiline_mock,
        ):
            view.draw(pygame.Surface(LOGICAL_SIZE))
        labels = [call.args[1] for call in draw_text_mock.call_args_list]
        blocks = [
            call.args[1].replace("\n", " ")
            for call in multiline_mock.call_args_list
        ]
        self.assertIn(country.name, labels)
        self.assertNotIn(f"Три факта: {country.name}", labels)
        self.assertIn(country.official_name, blocks)
        self.assertIn(f"{country.capital} (столица)", blocks)

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
                        variant = (
                            view.active_question.content.water_area_kind
                            if isinstance(
                                view.active_question.content,
                                MapContent,
                            )
                            else ""
                        )
                        self.assertEqual(
                            100.0
                            + self.app.mode_registry.feedback_seconds(
                                mode,
                                True,
                                variant,
                            ),
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

    def test_rivers_use_their_own_feedback_timing(self):
        previous_clock = self.app.clock_source
        self.app.clock_source = lambda: 100.0
        try:
            view = self._show_water_question("river")
            view._answer(view.active_question.correct_answer)
            self.assertEqual(
                100.0
                + WATER_KIND_FEEDBACK_SETTINGS["river"]["correct"],
                view.advance_at,
            )
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

    def test_question_count_supports_more_wonder_facts(self):
        self.app.pending_modes = ["wonders"]
        self.app.pending_continents = ["Europe"]
        self.app.pending_count = 100
        self.app.show("question_count")
        view = self.app.view
        self.assertIn(10, view.available_counts)
        self.assertIn(100, view.available_counts)

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
                if route == "atlas":
                    view.handle_event(
                        pygame.event.Event(
                            pygame.MOUSEBUTTONDOWN,
                            {"pos": country_position, "button": 1},
                        )
                    )
                    view.handle_event(
                        pygame.event.Event(
                            pygame.MOUSEBUTTONUP,
                            {"pos": country_position, "button": 1},
                        )
                    )
                    self.assertEqual("RUS", view.selected_country)
                    self.assertEqual(
                        "RUS",
                        view._facts["RUS"].country_iso,
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

    def test_buttons_have_a_visible_hover_effect(self):
        self.app.show("modes")
        self.app._transition_surface = None
        view = self.app.view
        target = next(iter(view._actions)).rect.center
        before = pygame.image.tobytes(self.app.render(), "RGB")
        view.record_pointer_event(
            pygame.event.Event(
                pygame.MOUSEMOTION,
                {
                    "pos": target,
                    "rel": (0, 0),
                    "buttons": (0, 0, 0),
                },
            )
        )
        after = pygame.image.tobytes(self.app.render(), "RGB")

        self.assertNotEqual(before, after)

    def test_hitbox_press_state_is_fully_transparent(self):
        theme = json.loads(
            (ASSETS_DIR / "theme.json").read_text(encoding="utf-8")
        )
        colours = theme["#hitbox"]["colours"]

        self.assertEqual("#00000000", colours["active_bg"])
        self.assertEqual("#00000000", colours["active_border"])

    def test_active_sidebar_item_is_not_a_second_navigation_target(self):
        self.app.show("statistics")
        self.app._transition_surface = None
        view = self.app.view
        active_rect = pygame.Rect(12, 156 + 2 * 54, 181, 44)

        self.assertFalse(view.interactive_at(active_rect.center))
        self.assertIsNone(self.app._transition_surface)

    def test_sidebar_mini_profile_opens_profile_view(self):
        self.app.show("statistics")
        view = self.app.view
        mini_profile_rect = pygame.Rect(12, 746, 181, 96)
        button = next(
            button
            for button in view._actions
            if button.relative_rect == mini_profile_rect
        )

        view.handle_button(button)

        self.assertEqual("profile", self.app.view.active)

    def test_atlas_hover_reuses_cached_world_view(self):
        self.app.show("atlas")
        view = self.app.view
        target = pygame.Surface(LOGICAL_SIZE)
        self.app.map_renderer.draw_atlas_map(
            target,
            view.map_rect,
            view._continents,
            view.map_camera,
            "RUS",
        )
        cached_view = self.app.map_renderer._atlas_view_cache
        cached_layers = self.app.map_renderer._atlas_base_layers

        self.app.map_renderer.draw_atlas_map(
            target,
            view.map_rect,
            view._continents,
            view.map_camera,
            "BRA",
        )

        self.assertIs(cached_view, self.app.map_renderer._atlas_view_cache)
        self.assertIs(cached_layers, self.app.map_renderer._atlas_base_layers)

    def test_atlas_zoom_smooths_fills_and_draws_vector_boundaries(self):
        self.app.show("atlas")
        view = self.app.view
        target = pygame.Surface(LOGICAL_SIZE)
        camera = MapCamera(zoom=4.0)

        with (
            patch.object(
                pygame.transform,
                "smoothscale",
                wraps=pygame.transform.smoothscale,
            ) as smoothscale,
            patch.object(
                pygame.draw,
                "aalines",
                wraps=pygame.draw.aalines,
            ) as draw_boundaries,
        ):
            self.app.map_renderer.draw_atlas_map(
                target,
                view.map_rect,
                view._continents,
                camera,
            )

        smoothscale.assert_called()
        draw_boundaries.assert_called()

    def test_section_change_starts_animation_without_button_press_pulse(self):
        previous_clock = self.app.clock_source
        now = [100.0]
        self.app.clock_source = lambda: now[0]
        try:
            self.app.show("home")
            self.app._transition_surface = None
            view = self.app.view
            view.record_pointer_event(
                pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    {"pos": view.play_rect.center, "button": 1},
                )
            )
            self.assertFalse(hasattr(view, "_press_pulses"))

            self.app.show("statistics")
            self.assertIsNotNone(self.app._transition_surface)
            now[0] += 0.25
            self.app.render()
            self.assertIsNone(self.app._transition_surface)
        finally:
            self.app.clock_source = previous_clock

    def test_profile_selector_uses_equal_cards_for_actions(self):
        previous_manager = self.app.profile_manager
        previous_selected = self.app._profile_selected
        try:
            with tempfile.TemporaryDirectory() as directory:
                manager = ProfileManager(
                    Path(directory),
                    self.app.profile_progression,
                )
                manager.create("ExplorerAY", 0)
                manager.create("Player Two", 1)
                self.app.profile_manager = manager
                self.app._profile_selected = False
                self.app.show("profile_select")
                view = self.app.view

                profile_sizes = {
                    rect.size
                    for _, rect, _ in view.profile_buttons
                }
                action_sizes = {
                    rect.size
                    for _, rect, _ in view.action_buttons
                }
                self.assertEqual({(350, 190)}, profile_sizes)
                self.assertEqual(profile_sizes, action_sizes)
                self.assertFalse(hasattr(view, "create_rect"))
                self.assertFalse(hasattr(view, "import_rect"))
        finally:
            self.app.view = None
            self.app.profile_manager = previous_manager
            self.app._profile_selected = previous_selected
            self.app.show("home")

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
