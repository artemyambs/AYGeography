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
from aygeography.progression import ProgressionCatalog, ProgressionService
from aygeography.storage import GameRepository


class ProgressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "progress.db"
        self.repository = GameRepository(self.database_path)
        self.countries = CountryCatalog(
            CONFIGS_DIR / "countries_by_iso3.json",
            CONFIGS_DIR / "continents.json",
        )
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

    @staticmethod
    def _answer(mode: str, iso3: str = "RUS") -> AnswerRecord:
        return AnswerRecord(
            mode=mode,
            country_iso=iso3,
            prompt="Вопрос",
            answer="Ответ",
            correct_answer="Ответ",
            is_correct=True,
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

    def test_mastery_requires_every_configured_mode(self):
        self._save_mastery_round(
            3,
            self.catalog.mastery_modes[:-1],
        )
        self.assertEqual(self.service.country_mastery()["RUS"].stars, 0)

    def test_mastery_awards_one_two_and_three_stars(self):
        for expected in (1, 2, 3):
            with self.subTest(expected=expected):
                repository = GameRepository(
                    Path(self.temporary.name) / f"stars_{expected}.db"
                )
                service = ProgressionService(
                    repository,
                    self.countries,
                    self.catalog,
                )
                repository.save_round(
                    RoundResult(
                        "2026-07-26T12:00:00",
                        10,
                        100,
                        [
                            self._answer(mode)
                            for _ in range(expected)
                            for mode in self.catalog.mastery_modes
                        ],
                    )
                )
                self.assertEqual(
                    service.country_mastery()["RUS"].stars,
                    expected,
                )

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
        self.assertEqual(service.country_mastery()["RUS"].stars, 0)
        self.repository.save_round(
            RoundResult(
                "2026-07-26T12:10:00",
                3,
                3,
                [self._answer("future_mode")],
            )
        )
        self.assertEqual(service.country_mastery()["RUS"].stars, 1)

    def test_reset_does_not_remove_mastery_or_achievements(self):
        self._save_mastery_round(1)
        unlocked = self.service.sync()
        self.assertTrue(unlocked)
        before_mastery = self.service.country_mastery()["RUS"].stars
        before_unlocks = self.repository.unlocked_achievements()
        self.repository.reset_answer_statistics()
        self.assertEqual(
            self.service.country_mastery()["RUS"].stars,
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


if __name__ == "__main__":
    unittest.main()
