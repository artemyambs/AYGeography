from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from aygeography.catalog import CountryCatalog
from aygeography.config import CONFIGS_DIR
from aygeography.models import AnswerRecord, RoundResult
from aygeography.persistence import SQLiteDatabase
from aygeography.progression import ProgressionCatalog, ProgressionService
from aygeography.storage import GameRepository


class ProgressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "progress.db"
        self.repository = GameRepository(self.database_path)
        self.countries = CountryCatalog(CONFIGS_DIR / "countries_by_iso3.json")
        self.catalog = ProgressionCatalog(
            CONFIGS_DIR / "progression.json",
            CONFIGS_DIR / "achievements.json",
        )
        self.service = ProgressionService(
            self.repository,
            self.countries,
            self.catalog,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_database_enables_integrity_and_versioned_migrations(self):
        with closing(self.repository._connect()) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            foreign_keys = db.execute("PRAGMA foreign_keys").fetchone()[0]
            indexes = {
                row[0]
                for row in db.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type='index' AND name LIKE 'idx_%'
                    """
                ).fetchall()
            }

        self.assertEqual(SQLiteDatabase.SCHEMA_VERSION, version)
        self.assertEqual(1, foreign_keys)
        self.assertIn("idx_rounds_started_at", indexes)
        self.assertIn("idx_answers_round_id", indexes)
        self.assertIn("idx_review_items_status_failed_at", indexes)
        self.assertEqual(
            {"fullscreen", "confirm_exit"},
            set(self.repository.settings()),
        )

    @staticmethod
    def _answer(
        mode: str,
        iso3: str = "RUS",
        is_correct: bool = True,
    ) -> AnswerRecord:
        return AnswerRecord(
            mode=mode,
            country_iso=iso3,
            prompt="Вопрос",
            answer="Ответ",
            correct_answer="Ответ",
            is_correct=is_correct,
            seconds=2.0,
            points=10,
        )

    def _save_mastery_round(self, repeats: int, modes=None) -> None:
        modes = modes or self.catalog.mastery_modes
        answers = [
            self._answer(mode)
            for _ in range(repeats)
            for mode in modes
        ]
        self.repository.save_round(
            RoundResult(
                started_at="2026-07-26T12:00:00",
                duration_seconds=10,
                score=100,
                answers=answers,
                difficulty="hard",
            )
        )

    def test_mastery_does_not_include_wonders(self):
        self.assertNotIn("wonders", self.catalog.mastery_modes)
        self._save_mastery_round(1)
        self.repository.save_round(
            RoundResult(
                "2026-07-26T12:10:00",
                3,
                0,
                [self._answer("wonders", is_correct=False)],
            )
        )
        mastery = self.service.country_mastery()["RUS"]
        self.assertEqual(1, mastery.rating)
        self.assertNotIn("wonders", mastery.rating_by_mode)

    def test_mastery_awards_poor_good_and_excellent_ratings(self):
        for expected, correct_count in ((1, 1), (2, 3), (3, 8)):
            with self.subTest(expected=expected):
                repository = GameRepository(
                    Path(self.temporary.name) / f"rating_{expected}.db"
                )
                service = ProgressionService(
                    repository,
                    self.countries,
                    self.catalog,
                )
                repository.save_round(
                    RoundResult(
                        "2026-07-20T12:00:00",
                        10,
                        100,
                        [
                            self._answer(mode)
                            for _ in range(correct_count)
                            for mode in self.catalog.mastery_modes
                        ],
                    )
                )
                self.assertEqual(
                    service.country_mastery()["RUS"].rating,
                    expected,
                )

    def test_mastery_resets_only_current_streak(self):
        def save_attempts(count: int, is_correct: bool = True) -> None:
            self.repository.save_round(
                RoundResult(
                    "2026-07-26T12:00:00",
                    10,
                    100,
                    [
                        self._answer(mode, is_correct=is_correct)
                        for _ in range(count)
                        for mode in self.catalog.mastery_modes
                    ],
                )
            )

        save_attempts(1)
        mastery = self.service.country_mastery()["RUS"]
        self.assertEqual(1, mastery.rating)
        self.assertTrue(all(value == 0 for value in mastery.streak_by_mode.values()))

        save_attempts(1)
        save_attempts(1, is_correct=False)
        mastery = self.service.country_mastery()["RUS"]
        self.assertEqual(1, mastery.rating)
        self.assertTrue(all(value == 0 for value in mastery.streak_by_mode.values()))

        save_attempts(2)
        mastery = self.service.country_mastery()["RUS"]
        self.assertEqual(2, mastery.rating)
        self.assertTrue(all(value == 0 for value in mastery.streak_by_mode.values()))

        save_attempts(4)
        save_attempts(1, is_correct=False)
        save_attempts(5)
        mastery = self.service.country_mastery()["RUS"]
        self.assertEqual(3, mastery.rating)

    def test_population_mastery_tracks_each_answer_for_both_countries(self):
        answer = AnswerRecord(
            mode="population",
            country_iso="RUS",
            country_isos=("RUS", "DEU"),
            prompt="В какой стране население больше?",
            answer="Россия",
            correct_answer="Россия",
            is_correct=True,
            seconds=2.0,
            points=10,
        )
        self.repository.save_round(
            RoundResult(
                "2026-07-26T12:00:00",
                4,
                20,
                [answer, answer],
            )
        )

        mastery = self.service.country_mastery()

        self.assertEqual(1, mastery["RUS"].rating_by_mode["population"])
        self.assertEqual(1, mastery["DEU"].rating_by_mode["population"])
        self.assertEqual(1, mastery["RUS"].streak_by_mode["population"])
        self.assertEqual(1, mastery["DEU"].streak_by_mode["population"])

    def test_new_mastery_mode_is_required_without_code_changes(self):
        progression = json.loads(
            (CONFIGS_DIR / "progression.json").read_text(encoding="utf-8")
        )
        progression["country_mastery"]["modes"].append("future_mode")
        path = Path(self.temporary.name) / "progression.json"
        path.write_text(
            json.dumps(progression, ensure_ascii=False),
            encoding="utf-8",
        )
        future_catalog = ProgressionCatalog(
            path,
            CONFIGS_DIR / "achievements.json",
        )
        service = ProgressionService(
            self.repository,
            self.countries,
            future_catalog,
        )
        self._save_mastery_round(3)
        self.assertEqual(service.country_mastery()["RUS"].rating, 0)
        self.repository.save_round(
            RoundResult(
                "2026-07-26T12:10:00",
                3,
                3,
                [self._answer("future_mode")],
            )
        )
        self.assertEqual(service.country_mastery()["RUS"].rating, 1)

    def test_reset_does_not_remove_mastery_or_achievements(self):
        self._save_mastery_round(1)
        unlocked = self.service.sync()
        self.assertTrue(unlocked)
        before_mastery = self.service.country_mastery()["RUS"].rating
        before_unlocks = self.repository.unlocked_achievements()
        self.repository.reset_answer_statistics()
        self.assertEqual(
            self.service.country_mastery()["RUS"].rating,
            before_mastery,
        )
        self.assertEqual(
            self.repository.unlocked_achievements(),
            before_unlocks,
        )

    def test_achievement_unlock_is_idempotent(self):
        self._save_mastery_round(1)
        self.assertTrue(self.service.sync())
        self.assertEqual(self.service.sync(), [])

    def test_new_exploration_achievements_are_data_driven(self):
        definitions = {
            item.id: item
            for item in self.catalog.achievements
        }
        self.assertEqual(
            "unique_country_correct",
            definitions["country_explorer_25"].rule["type"],
        )
        self.assertEqual(
            "balanced_mode_correct",
            definitions["balanced_modes_10"].rule["type"],
        )
        removed = {
            "rounds_10",
            "correct_1000",
            "accuracy_95",
            "streak_25",
            "hard_accuracy_80",
            "days_3",
        }
        self.assertTrue(removed.isdisjoint(definitions))

    def test_exploration_achievements_unlock_from_history(self):
        answers = [
            self._answer("flags", country.iso3)
            for country in self.countries.all()[:25]
        ]
        answers.extend(
            self._answer(mode)
            for mode in self.service.mode_registry.keys
            for _ in range(10)
        )
        self.repository.save_round(
            RoundResult(
                "2026-07-30T12:00:00",
                120,
                1000,
                answers,
            )
        )

        unlocked = {
            item.id
            for item in self.service.sync()
        }

        self.assertIn("country_explorer_25", unlocked)
        self.assertIn("balanced_modes_10", unlocked)

    def test_old_database_receives_difficulty_column(self):
        old_path = Path(self.temporary.name) / "old.db"
        with closing(sqlite3.connect(old_path)) as db:
            db.execute(
                """
                CREATE TABLE rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    duration REAL NOT NULL,
                    score INTEGER NOT NULL,
                    correct_count INTEGER NOT NULL,
                    question_count INTEGER NOT NULL
                )
                """
            )
            db.execute(
                """
                INSERT INTO rounds(
                    started_at, duration, score, correct_count, question_count
                ) VALUES('2026-07-20T12:00:00', 10, 5, 1, 1)
                """
            )
            db.commit()
        repository = GameRepository(old_path)
        self.assertEqual(repository.lifetime_rounds()[0]["difficulty"], "medium")

    def test_old_answers_are_backfilled_into_country_links(self):
        old_path = Path(self.temporary.name) / "old_answers.db"
        with closing(sqlite3.connect(old_path)) as db:
            db.executescript(
                """
                CREATE TABLE rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    duration REAL NOT NULL,
                    score INTEGER NOT NULL,
                    correct_count INTEGER NOT NULL,
                    question_count INTEGER NOT NULL
                );
                CREATE TABLE answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    country_iso TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    is_correct INTEGER NOT NULL,
                    seconds REAL NOT NULL,
                    points INTEGER NOT NULL
                );
                INSERT INTO rounds(
                    started_at, duration, score, correct_count, question_count
                ) VALUES('2026-07-20T12:00:00', 2, 10, 1, 1);
                INSERT INTO answers(
                    round_id, mode, country_iso, prompt, answer,
                    correct_answer, is_correct, seconds, points
                ) VALUES(1, 'flags', 'RUS', 'Вопрос', 'Россия',
                         'Россия', 1, 2, 10);
                """
            )
            db.commit()

        repository = GameRepository(old_path)

        self.assertEqual(
            "RUS",
            repository.lifetime_answer_countries()[0]["country_iso"],
        )
        with closing(repository._connect()) as db:
            answer_columns = {
                row["name"]
                for row in db.execute("PRAGMA table_info(answers)").fetchall()
            }
            review_table = db.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='review_items'
                """
            ).fetchone()
        self.assertIn("question_key", answer_columns)
        self.assertIn("question_payload", answer_columns)
        self.assertIsNotNone(review_table)


if __name__ == "__main__":
    unittest.main()
