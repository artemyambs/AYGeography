import json
import random
import tempfile
import unittest
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import pygame

from aygeography.catalog import CountryCatalog
from aygeography.config import (
    ANSWER_FEEDBACK_SECONDS,
    BASE_DIR,
    CONFIGS_DIR,
    MODE_NAMES,
    QUESTION_TIME_SECONDS,
    WONDER_CATEGORY_WEIGHTS,
)
from aygeography.difficulty import DIFFICULTY_KEYS, DifficultyCatalog
from aygeography.formatting import format_population
from aygeography.models import AnswerRecord, GameConfig, RoundResult
from aygeography.quiz import (
    CapitalQuestionStrategy,
    CountryMapQuestionStrategy,
    FlagQuestionStrategy,
    GameSession,
    PopulationPairSelector,
    QuestionFactory,
    WaterQuestionStrategy,
)
from aygeography.scoring import DEFAULT_SCORE_RULES, ScoreRules
from aygeography.storage import GameRepository
from aygeography.waters import WATER_REGIONS
from aygeography.wonders import (
    EXPECTED_COUNTS,
    WonderCatalog,
    WonderCategory,
)


class QuizTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = CountryCatalog(
            CONFIGS_DIR / "countries_by_iso3.json",
            CONFIGS_DIR / "continents.json",
        )
        cls.wonders = WonderCatalog(
            CONFIGS_DIR / "wonders",
            cls.catalog.all(),
            BASE_DIR / "assets",
        )

    def test_wonders_catalog_has_exact_content_distribution(self):
        items = self.wonders.all()
        self.assertEqual(250, len(items))
        self.assertEqual(
            Counter(EXPECTED_COUNTS),
            Counter(item.category for item in items),
        )
        self.assertEqual(
            {"easy": 84, "medium": 83, "hard": 83},
            dict(Counter(item.difficulty for item in items)),
        )
        self.assertEqual(
            {"landmark": 3, "peak": 1, "river": 2, "fact": 2},
            WONDER_CATEGORY_WEIGHTS,
        )
        self.assertEqual("Чудеса света", MODE_NAMES["wonders"])

    def test_wonders_builds_unique_weighted_round_with_six_options(self):
        questions = QuestionFactory(
            wonder_catalog=self.wonders
        ).build(
            GameConfig(
                ["wonders"],
                list(self.catalog.continents),
                100,
                difficulty="medium",
            ),
            self.catalog,
            seed=44,
        )
        self.assertEqual(100, len({question.key for question in questions}))
        self.assertEqual(
            {"landmark": 38, "peak": 12, "river": 25, "fact": 25},
            dict(Counter(
                question.metadata["wonder_category"]
                for question in questions
            )),
        )
        for question in questions:
            self.assertEqual(6, len(question.options))
            self.assertEqual(6, len(set(question.options)))
            self.assertIn(question.correct_answer, question.options)
            self.assertTrue(question.explanation)

    def test_wonders_extension_has_requested_content_and_image_sizes(self):
        facts = self.wonders.by_category(WonderCategory.FACT)[-100:]
        landmarks = self.wonders.by_category(WonderCategory.LANDMARK)[-30:]

        self.assertEqual(100, len({item.prompt for item in facts}))
        self.assertEqual(
            {"easy": 34, "medium": 33, "hard": 33},
            dict(Counter(item.difficulty for item in facts)),
        )
        self.assertEqual(
            {"easy": 10, "medium": 10, "hard": 10},
            dict(Counter(item.difficulty for item in landmarks)),
        )
        self.assertEqual(
            {(960, 540)},
            {
                pygame.image.load(BASE_DIR / "assets" / item.image).get_size()
                for item in landmarks
            },
        )

    def test_landmark_format_is_seeded_per_round(self):
        factory = QuestionFactory(wonder_catalog=self.wonders)
        config = GameConfig(
            ["wonders"],
            list(self.catalog.continents),
            120,
            difficulty="medium",
        )
        first = factory.build(config, self.catalog, seed=11)
        repeated = factory.build(config, self.catalog, seed=11)
        changed = factory.build(config, self.catalog, seed=12)
        first_formats = {
            question.key: question.presentation
            for question in first
            if question.metadata["wonder_category"] == "landmark"
        }
        self.assertEqual(
            first_formats,
            {
                question.key: question.presentation
                for question in repeated
                if question.metadata["wonder_category"] == "landmark"
            },
        )
        self.assertNotEqual(
            first_formats,
            {
                question.key: question.presentation
                for question in changed
                if question.metadata["wonder_category"] == "landmark"
            },
        )
        self.assertEqual(
            {
                "wonder_landmark_name",
                "wonder_landmark_country",
            },
            set(first_formats.values()),
        )

    def test_catalog_contains_195_countries(self):
        self.assertEqual(195, len(self.catalog.all()))

    def test_catalog_uses_wpp_2024_midyear_population_values(self):
        self.assertEqual(144_820_423, self.catalog.get("RUS").population)
        self.assertEqual(84_552_242, self.catalog.get("DEU").population)
        self.assertEqual(1_450_935_791, self.catalog.get("IND").population)
        self.assertTrue(
            all(country.population > 0 for country in self.catalog.all())
        )

    def test_configs_directory_replaces_data_directory(self):
        self.assertTrue((CONFIGS_DIR / "app_settings.json").is_file())
        self.assertTrue((CONFIGS_DIR / "scoring.json").is_file())
        self.assertTrue((CONFIGS_DIR / "wonders_settings.json").is_file())
        self.assertEqual(
            {"fact.json", "river.json", "landmark.json", "peak.json"},
            {
                path.name
                for path in (CONFIGS_DIR / "wonders").glob("*.json")
            },
        )
        self.assertFalse((BASE_DIR / "data").exists())

    def test_feedback_delays_are_configured_for_every_mode(self):
        self.assertEqual(set(MODE_NAMES), set(ANSWER_FEEDBACK_SECONDS))
        for mode in MODE_NAMES:
            self.assertEqual(
                {"correct", "incorrect"},
                set(ANSWER_FEEDBACK_SECONDS[mode]),
            )
            self.assertTrue(
                all(
                    seconds > 0
                    for seconds in ANSWER_FEEDBACK_SECONDS[mode].values()
                )
            )

    def test_difficulty_file_partitions_every_country(self):
        levels = DifficultyCatalog(CONFIGS_DIR / "difficulty_levels.json")
        levels.validate_countries(self.catalog.all())

    def test_difficulty_probability_comes_from_json(self):
        levels = DifficultyCatalog(CONFIGS_DIR / "difficulty_levels.json")
        expected = {"easy": 0.9, "medium": 0.8, "hard": 0.7}

        for seed, (selected, probability) in enumerate(expected.items(), 20):
            rng = random.Random(seed)
            counts = Counter(
                levels.choose(selected, rng)
                for _ in range(20_000)
            )
            self.assertAlmostEqual(
                probability,
                counts[selected] / 20_000,
                delta=0.015,
            )
            alternatives = [
                counts[level]
                for level in DIFFICULTY_KEYS
                if level != selected
            ]
            self.assertLess(abs(alternatives[0] - alternatives[1]), 300)

    def test_difficulty_file_partitions_every_water_region(self):
        levels = DifficultyCatalog(CONFIGS_DIR / "difficulty_levels.json")
        levels.validate_water_keys({region.key for region in WATER_REGIONS})

    def test_water_questions_follow_their_sampled_difficulty(self):
        levels = DifficultyCatalog(CONFIGS_DIR / "difficulty_levels.json")
        questions = QuestionFactory().build(
            GameConfig(
                ["waters"],
                list(self.catalog.continents),
                50,
                difficulty="hard",
            ),
            self.catalog,
            seed=31,
        )
        for question in questions:
            region_key = question.metadata.get(
                "water_highlight",
                question.correct_answer,
            )
            self.assertIn(
                region_key,
                levels.water_keys(question.metadata["difficulty"]),
            )

    def test_factory_creates_unique_mixed_questions(self):
        questions = QuestionFactory().build(
            GameConfig(
                ["flags", "capitals", "population", "countries", "waters"],
                ["Europe", "Asia"],
                50,
            ),
            self.catalog,
            seed=7,
        )
        self.assertEqual(50, len(questions))
        self.assertEqual(50, len({question.key for question in questions}))
        self.assertEqual(5, len({question.mode for question in questions}))

    def test_mixed_difficulty_round_has_no_repeats_within_any_mode(self):
        questions = QuestionFactory().build(
            GameConfig(
                ["flags", "capitals", "population", "countries", "waters"],
                list(self.catalog.continents),
                100,
                difficulty="medium",
            ),
            self.catalog,
            seed=37,
        )

        for mode in ("flags", "capitals", "population", "countries", "waters"):
            mode_questions = [
                question for question in questions if question.mode == mode
            ]
            identities = [
                question.metadata["water_highlight"]
                if mode == "waters"
                else question.country_iso
                for question in mode_questions
            ]
            self.assertEqual(len(identities), len(set(identities)), mode)

    def test_every_country_mode_supports_100_unique_questions(self):
        for mode in ("flags", "capitals", "population", "countries"):
            questions = QuestionFactory().build(
                GameConfig(
                    [mode],
                    ["Africa", "Asia", "Europe", "North America", "South America", "Oceania"],
                    100,
                ),
                self.catalog,
                seed=11,
            )
            self.assertEqual(100, len({question.key for question in questions}), mode)

    def test_water_mode_rejects_more_than_its_50_unique_regions(self):
        with self.assertRaisesRegex(
            ValueError,
            "доступно 50 уникальных вопросов",
        ):
            QuestionFactory().build(
                GameConfig(
                    ["waters"],
                    list(self.catalog.continents),
                    51,
                ),
                self.catalog,
                seed=11,
            )

    def test_exhausted_selected_level_falls_back_without_repeats(self):
        raw = json.loads(
            (CONFIGS_DIR / "difficulty_levels.json").read_text(encoding="utf-8")
        )
        raw["hard"]["chance_falling_out"] = "100%"
        with tempfile.TemporaryDirectory() as directory:
            difficulty_path = Path(directory) / "difficulty.json"
            difficulty_path.write_text(
                json.dumps(raw, ensure_ascii=False),
                encoding="utf-8",
            )
            levels = DifficultyCatalog(difficulty_path)
            questions = QuestionFactory(
                difficulty_catalog=levels
            ).build(
                GameConfig(
                    ["countries"],
                    list(self.catalog.continents),
                    100,
                    difficulty="hard",
                ),
                self.catalog,
                seed=17,
            )

        hard_capacity = len(
            levels.countries("hard", self.catalog.all())
        )
        counts = Counter(question.metadata["difficulty"] for question in questions)
        self.assertEqual(hard_capacity, counts["hard"])
        self.assertEqual(100, len({question.country_iso for question in questions}))
        self.assertEqual(
            100 - hard_capacity,
            counts["easy"] + counts["medium"],
        )

    def test_country_can_appear_once_in_each_selected_mode(self):
        questions = QuestionFactory().build(
            GameConfig(
                ["countries", "flags"],
                list(self.catalog.continents),
                390,
            ),
            self.catalog,
            seed=23,
        )
        countries_by_mode = {
            mode: {
                question.country_iso
                for question in questions
                if question.mode == mode
            }
            for mode in ("countries", "flags")
        }

        self.assertEqual(195, len(countries_by_mode["countries"]))
        self.assertEqual(195, len(countries_by_mode["flags"]))
        self.assertEqual(
            countries_by_mode["countries"],
            countries_by_mode["flags"],
        )

    def test_capital_questions_include_country_flag_layout(self):
        questions = QuestionFactory().build(
            GameConfig(["capitals"], ["Europe"], 25),
            self.catalog,
            seed=19,
        )
        for question in questions:
            country = self.catalog.get(question.country_iso)
            self.assertEqual(country.name, question.prompt)
            self.assertEqual(country.capital, question.correct_answer)
            self.assertEqual(country.iso3, question.visual)
            self.assertTrue(question.metadata["capital_layout"])

    def test_scoring_and_round_result(self):
        questions = QuestionFactory().build(
            GameConfig(["flags"], ["Europe"], 10), self.catalog, seed=3
        )
        session = GameSession(questions)
        answer = session.answer(session.current.correct_answer, 2)
        self.assertTrue(answer.is_correct)
        self.assertEqual(10, answer.points)
        self.assertEqual(10, session.score)
        self.assertEqual(2, session.result().duration_seconds)

    def test_population_feedback_uses_exact_grouped_value(self):
        self.assertEqual("949 999", format_population(949_999))
        self.assertEqual("17 500 000", format_population(17_500_000))

    def test_population_question_compares_two_countries(self):
        question = QuestionFactory().build(
            GameConfig(["population"], ["South America"], 1),
            self.catalog,
            seed=7,
        )[0]
        countries = [
            self.catalog.get(iso3) for iso3 in question.country_isos
        ]
        self.assertEqual(2, len(question.options))
        self.assertEqual(
            max(countries, key=lambda country: country.population).name,
            question.correct_answer,
        )
        self.assertEqual(
            {country.iso3: country.population for country in countries},
            question.metadata["population_values"],
        )
        self.assertEqual(
            "country_comparison",
            question.metadata["presentation"],
        )

    def test_population_pairs_are_unique_and_balanced(self):
        questions = QuestionFactory().build(
            GameConfig(["population"], ["Europe"], 30),
            self.catalog,
            seed=7,
        )
        pairs = {
            tuple(sorted(question.country_isos)) for question in questions
        }
        kinds = Counter(
            question.metadata["pair_kind"] for question in questions
        )
        self.assertEqual(30, len(pairs))
        self.assertEqual({"close": 15, "contrast": 15}, dict(kinds))
        for question in questions:
            first, second = (
                self.catalog.get(iso3) for iso3 in question.country_isos
            )
            ratio = PopulationPairSelector.ratio(first, second)
            if question.metadata["pair_kind"] == "close":
                self.assertGreaterEqual(ratio, 1.15)
                self.assertLess(ratio, 2.0)
            else:
                self.assertGreaterEqual(ratio, 2.0)
                self.assertLessEqual(ratio, 10.0)

    def test_population_difficulty_applies_to_primary_country_only(self):
        levels = DifficultyCatalog(CONFIGS_DIR / "difficulty_levels.json")
        questions = QuestionFactory().build(
            GameConfig(
                ["population"],
                list(self.catalog.continents),
                50,
                difficulty="hard",
            ),
            self.catalog,
            seed=17,
        )
        for question in questions:
            sampled_level = question.metadata["difficulty"]
            allowed_primary = {
                country.iso3
                for country in levels.countries(
                    sampled_level,
                    self.catalog.all(),
                )
            }
            self.assertIn(question.country_iso, allowed_primary)

    def test_country_answer_options_match_germany_continent(self):
        germany = self.catalog.get("DEU")
        pool = self.catalog.all()
        rng = random.Random(23)
        european_names = {
            country.name
            for country in pool
            if country.continent == germany.continent
        }
        european_capitals = {
            country.capital
            for country in pool
            if country.continent == germany.continent
        }

        for strategy in (FlagQuestionStrategy(), CountryMapQuestionStrategy()):
            question = strategy.create(germany, pool, 0, rng)
            self.assertEqual(6, len(question.options))
            self.assertTrue(set(question.options) <= european_names)

        capital_question = CapitalQuestionStrategy().create(
            germany,
            pool,
            0,
            rng,
        )
        self.assertEqual(6, len(capital_question.options))
        self.assertTrue(set(capital_question.options) <= european_capitals)

    def test_wrong_only_keeps_full_continent_option_pool(self):
        question = QuestionFactory().build(
            GameConfig(["countries"], ["Europe"], 1, wrong_only=True),
            self.catalog,
            wrong_isos=["DEU"],
            seed=23,
        )[0]
        european_names = {
            country.name
            for country in self.catalog.all()
            if country.continent == "Europe"
        }

        self.assertEqual("DEU", question.country_iso)
        self.assertEqual(6, len(question.options))
        self.assertTrue(set(question.options) <= european_names)

    def test_water_questions_always_use_six_answer_choices(self):
        strategy = WaterQuestionStrategy()
        country = self.catalog.get("DEU")
        pool = self.catalog.all()
        sea_serial = next(
            index
            for index, region in enumerate(WATER_REGIONS)
            if region.kind == "Море"
        )
        questions = (
            strategy.create(country, pool, 0, random.Random(3)),
            strategy.create(country, pool, sea_serial, random.Random(4)),
        )

        for question in questions:
            self.assertEqual("choices", question.interaction)
            self.assertEqual(6, len(question.options))
            self.assertEqual(6, len(set(question.options)))
            self.assertIn(question.correct_answer, question.options)
            highlighted = question.metadata["water_highlight"]
            expected_kind = next(
                region.kind
                for region in WATER_REGIONS
                if region.key == highlighted
            )
            kind_by_name = {region.name: region.kind for region in WATER_REGIONS}
            matching_kind_count = sum(
                kind_by_name[option] == expected_kind
                for option in question.options
            )
            self.assertGreaterEqual(matching_kind_count, 5)
            expected_prompt = (
                "Какое море выделено?"
                if expected_kind == "Море"
                else "Какой океан выделен?"
            )
            self.assertEqual(expected_prompt, question.prompt)

    def test_water_questions_never_require_clicking_the_map(self):
        questions = QuestionFactory().build(
            GameConfig(
                ["waters"],
                list(self.catalog.continents),
                50,
            ),
            self.catalog,
            seed=31,
        )

        self.assertTrue(all(question.interaction == "choices" for question in questions))
        self.assertTrue(all(len(question.options) == 6 for question in questions))
        self.assertTrue(
            all("water_highlight" in question.metadata for question in questions)
        )

    def test_country_questions_only_use_highlighted_map_choices(self):
        questions = QuestionFactory().build(
            GameConfig(
                ["countries"],
                list(self.catalog.continents),
                100,
                difficulty="hard",
            ),
            self.catalog,
            seed=31,
        )

        self.assertEqual(100, len({question.country_iso for question in questions}))
        self.assertTrue(all(question.interaction == "choices" for question in questions))
        self.assertTrue(all(len(question.options) == 6 for question in questions))
        self.assertTrue(all("highlight" in question.metadata for question in questions))

    def test_scoring_boundaries_match_configuration(self):
        expected = {
            "easy": (
                (57, 60, 6), (53, 56, 5), (49, 52, 4),
                (45, 48, 3), (40, 44, 3), (35, 39, 3),
                (30, 34, 2), (25, 29, 2), (20, 24, 2),
                (15, 19, 1), (10, 14, 1), (5, 9, 1),
                (1, 4, 0), (0, 0, 0),
            ),
            "medium": (
                (57, 60, 10), (53, 56, 9), (49, 52, 8),
                (45, 48, 7), (40, 44, 6), (35, 39, 5),
                (30, 34, 4), (25, 29, 3), (20, 24, 2),
                (15, 19, 2), (10, 14, 1), (5, 9, 1),
                (1, 4, 0), (0, 0, 0),
            ),
            "hard": (
                (57, 60, 13), (53, 56, 12), (49, 52, 11),
                (45, 48, 10), (40, 44, 9), (35, 39, 8),
                (30, 34, 7), (25, 29, 6), (20, 24, 5),
                (15, 19, 4), (10, 14, 3), (5, 9, 2),
                (1, 4, 1), (0, 0, 0),
            ),
        }
        for difficulty, bands in expected.items():
            for minimum, maximum, points in bands:
                for remaining in range(minimum, maximum + 1):
                    self.assertEqual(
                        points,
                        DEFAULT_SCORE_RULES.points(
                            difficulty,
                            remaining,
                        ),
                        (difficulty, remaining),
                    )

    def test_scoring_configuration_covers_every_timer_second(self):
        for difficulty in DIFFICULTY_KEYS:
            for remaining in range(QUESTION_TIME_SECONDS + 1):
                self.assertIsInstance(
                    DEFAULT_SCORE_RULES.points(difficulty, remaining),
                    int,
                )

    def test_scoring_configuration_rejects_a_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            data = json.loads(
                (CONFIGS_DIR / "scoring.json").read_text(encoding="utf-8")
            )
            data["easy"] = data["easy"][:-1]
            path = Path(directory) / "invalid_scoring.json"
            path.write_text(
                json.dumps(data),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                ScoreRules(path)

    def test_scoring_uses_selected_round_difficulty(self):
        question = QuestionFactory().build(
            GameConfig(["flags"], ["Europe"], 1),
            self.catalog,
            seed=18,
        )[0]
        question.metadata["difficulty"] = "hard"
        session = GameSession([question], difficulty="easy")

        answer = session.answer(question.correct_answer, 2)

        self.assertEqual(6, answer.points)

    def test_incorrect_answer_never_scores_points(self):
        question = QuestionFactory().build(
            GameConfig(["flags"], ["Europe"], 1),
            self.catalog,
            seed=21,
        )[0]
        session = GameSession([question], difficulty="hard")

        answer = session.answer("", 0)

        self.assertFalse(answer.is_correct)
        self.assertEqual(0, answer.points)
        self.assertEqual(0, session.score)

    def test_repository_persists_round(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = GameRepository(Path(directory) / "game.db")
            questions = QuestionFactory().build(
                GameConfig(["population"], ["Africa"], 10), self.catalog, seed=2
            )
            session = GameSession(questions)
            session.answer("", 60)
            repository.save_round(session.result())
            stats = repository.statistics()
            self.assertEqual(1, stats["total"]["rounds"])
            self.assertEqual(1, stats["total"]["question_count"])

    def test_population_answer_links_both_countries_once(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = GameRepository(Path(directory) / "population.db")
            question = QuestionFactory().build(
                GameConfig(["population"], ["Europe"], 1),
                self.catalog,
                seed=4,
            )[0]
            session = GameSession([question])
            session.answer("__wrong__", 5)

            repository.save_round(session.result())

            stats = repository.statistics()
            links = repository.lifetime_answer_countries()
            self.assertEqual(1, stats["modes"][0]["total"])
            self.assertEqual(2, len(stats["countries"]))
            self.assertEqual(set(question.country_isos), {
                link["country_iso"] for link in links
            })
            self.assertEqual(
                set(question.country_isos),
                set(repository.wrong_country_isos()),
            )

    def test_repository_returns_exact_30_day_play_time_calendar(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = GameRepository(Path(directory) / "activity.db")
            active_day = date.today() - timedelta(days=2)
            repository.save_round(
                RoundResult(
                    started_at=datetime.combine(
                        active_day,
                        datetime.min.time(),
                    ).isoformat(),
                    duration_seconds=3670,
                    score=0,
                    answers=[],
                )
            )

            recent = repository.statistics()["recent"]

            self.assertEqual(30, len(recent))
            self.assertEqual(
                (date.today() - timedelta(days=29)).isoformat(),
                recent[0]["day"],
            )
            self.assertEqual(date.today().isoformat(), recent[-1]["day"])
            durations = {item["day"]: item["duration"] for item in recent}
            self.assertEqual(3670, durations[active_day.isoformat()])
            self.assertEqual(0, durations[date.today().isoformat()])

    def test_best_score_uses_only_25_question_rounds_from_last_7_days(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = GameRepository(Path(directory) / "best_score.db")
            answer = AnswerRecord(
                mode="countries",
                country_iso="RUS",
                prompt="Вопрос",
                answer="Россия",
                correct_answer="Россия",
                is_correct=True,
                seconds=1,
                points=10,
            )
            rounds = (
                (date.today(), 10, 999),
                (date.today(), 25, 250),
                (date.today(), 50, 888),
                (date.today() - timedelta(days=6), 25, 300),
                (date.today() - timedelta(days=7), 25, 777),
            )
            for started_on, question_count, score in rounds:
                repository.save_round(
                    RoundResult(
                        started_at=datetime.combine(
                            started_on,
                            datetime.min.time(),
                        ).isoformat(),
                        duration_seconds=1,
                        score=score,
                        answers=[answer] * question_count,
                    )
                )

            total = repository.statistics()["total"]

            self.assertEqual(
                300,
                total["best_score_last_7_days_25_questions"],
            )

    def test_answer_statistics_reset_preserves_time_activity_and_xp(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = GameRepository(Path(directory) / "reset_stats.db")
            old_answer = AnswerRecord(
                mode="countries",
                country_iso="RUS",
                prompt="Вопрос",
                answer="Ошибка",
                correct_answer="Россия",
                is_correct=False,
                seconds=5,
                points=0,
            )
            repository.save_round(
                RoundResult(
                    started_at=datetime.now().isoformat(),
                    duration_seconds=125,
                    score=250,
                    answers=[old_answer] * 25,
                )
            )
            before = repository.statistics()
            xp_before = repository.profile()["xp"]

            repository.reset_answer_statistics()
            reset = repository.statistics()

            self.assertEqual(0, reset["total"]["rounds"])
            self.assertEqual(0, reset["total"]["question_count"])
            self.assertEqual(0, reset["total"]["best_score_last_7_days_25_questions"])
            self.assertEqual(before["total"]["duration"], reset["total"]["duration"])
            self.assertEqual(before["recent"], reset["recent"])
            self.assertEqual([], reset["modes"])
            self.assertEqual([], reset["countries"])
            self.assertEqual([], repository.wrong_country_isos())
            self.assertEqual(xp_before, repository.profile()["xp"])

            new_answer = AnswerRecord(
                mode="flags",
                country_iso="FRA",
                prompt="Новый вопрос",
                answer="Франция",
                correct_answer="Франция",
                is_correct=True,
                seconds=4,
                points=10,
            )
            repository.save_round(
                RoundResult(
                    started_at=datetime.now().isoformat(),
                    duration_seconds=40,
                    score=100,
                    answers=[new_answer] * 10,
                )
            )
            restarted = repository.statistics()

            self.assertEqual(1, restarted["total"]["rounds"])
            self.assertEqual(10, restarted["total"]["question_count"])
            self.assertEqual(10, restarted["modes"][0]["total"])

    def test_game_session_state_round_trip(self):
        questions = QuestionFactory().build(
            GameConfig(["flags", "population"], ["Europe"], 10),
            self.catalog,
            seed=13,
        )
        session = GameSession(questions)
        session.answer(session.current.correct_answer, 3.5)

        restored = GameSession.from_state(session.to_state())

        self.assertEqual(session.index, restored.index)
        self.assertEqual(session.score, restored.score)
        self.assertEqual(session.streak, restored.streak)
        self.assertEqual(session.difficulty, restored.difficulty)
        self.assertEqual(session.current.key, restored.current.key)
        self.assertEqual(session.answers, restored.answers)
        self.assertEqual(session.started_at, restored.started_at)

    def test_legacy_session_state_restores_single_country_subjects(self):
        question = QuestionFactory().build(
            GameConfig(["flags"], ["Europe"], 1),
            self.catalog,
            seed=3,
        )[0]
        session = GameSession([question])
        session.answer(question.correct_answer, 2)
        state = session.to_state()
        state["questions"][0].pop("country_isos")
        state["answers"][0].pop("country_isos")

        restored = GameSession.from_state(state)

        self.assertEqual(
            (restored.questions[0].country_iso,),
            restored.questions[0].subjects,
        )
        self.assertEqual(
            (restored.answers[0].country_iso,),
            restored.answers[0].subjects,
        )

    def test_repository_persists_and_clears_active_game(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = GameRepository(Path(directory) / "game.db")
            state = {"version": 1, "view": {"displayed_index": 3}}

            repository.save_active_game(state)
            self.assertEqual(state, repository.load_active_game())

            repository.clear_active_game()
            self.assertIsNone(repository.load_active_game())

if __name__ == "__main__":
    unittest.main()
