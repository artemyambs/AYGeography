from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

from aygeography.config import CONFIGS_DIR
from aygeography.models import AnswerRecord, RoundResult
from aygeography.profile_progress import ProfileProgression
from aygeography.profiles import ProfileManager
from aygeography.storage import GameRepository


class ProfileProgressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.progression = ProfileProgression(
            CONFIGS_DIR / "progression.json"
        )

    def test_configured_level_thresholds_and_titles(self):
        self.assertEqual(1000, self.progression.required_xp(1))
        self.assertEqual(1500, self.progression.required_xp(2))
        self.assertEqual(30000, self.progression.required_xp(15))
        self.assertEqual(40000, self.progression.required_xp(16))
        self.assertEqual(40000, self.progression.required_xp(100))
        self.assertEqual("Новичок", self.progression.title(3))
        self.assertEqual("Троечник", self.progression.title(4))
        self.assertEqual("Ударник", self.progression.title(11))
        self.assertEqual("Профессионал", self.progression.title(12))
        self.assertEqual("Эксперт", self.progression.title(16))

    def test_xp_resets_when_level_is_received(self):
        progress = self.progression.add_score(1, 990, 20)
        self.assertEqual((2, 0), (progress.level, progress.xp))


class LocalProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.progression = ProfileProgression(
            CONFIGS_DIR / "progression.json"
        )
        self.manager = ProfileManager(self.root, self.progression)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _round(started_at: str, score: int = 10) -> RoundResult:
        answer = AnswerRecord(
            mode="flags",
            country_iso="RUS",
            prompt="Вопрос",
            answer="Россия",
            correct_answer="Россия",
            is_correct=True,
            seconds=2,
            points=score,
        )
        return RoundResult(started_at, 10, score, [answer])

    def test_profiles_are_isolated_and_portable(self):
        first = self.manager.create("Первый", 2)
        second = self.manager.create("Второй", 5)
        first_repository = self.manager.repository(first.id)
        first_repository.set_setting("fullscreen", True)
        first_repository.save_round(
            self._round(datetime.now().isoformat(), 1000)
        )
        first_repository.unlock_achievements(["first_round"])

        self.assertEqual(0, self.manager.repository(second.id).profile()["xp"])
        self.assertEqual(2, first_repository.profile()["level"])

        bundle = self.manager.export_profile(
            first.id,
            self.root / "player",
        )
        imported = self.manager.import_profile(bundle)
        imported_repository = self.manager.repository(imported.id)

        self.assertEqual("Первый", imported.nickname)
        self.assertTrue(imported_repository.settings()["fullscreen"])
        self.assertEqual(1, imported_repository.statistics()["total"]["rounds"])
        self.assertIn(
            "first_round",
            imported_repository.unlocked_achievements(),
        )

    def test_statistics_periods_use_calendar_days(self):
        profile = self.manager.create("Статистика", 0)
        repository = self.manager.repository(profile.id)
        today = date.today()
        for offset in (0, 1, 4):
            started = datetime.combine(
                today - timedelta(days=offset),
                datetime.min.time(),
            ).replace(hour=12)
            repository.save_round(self._round(started.isoformat()))

        self.assertEqual(1, repository.statistics("today")["total"]["rounds"])
        self.assertEqual(
            1,
            repository.statistics("yesterday")["total"]["rounds"],
        )
        self.assertEqual(2, repository.statistics("3_days")["total"]["rounds"])
        self.assertEqual(3, repository.statistics("week")["total"]["rounds"])
        self.assertEqual(3, repository.statistics("all")["total"]["rounds"])

    def test_statistics_filters_by_date_range_and_difficulty(self):
        profile = self.manager.create("Фильтры", 0)
        repository = self.manager.repository(profile.id)
        today = date.today()
        for offset, difficulty in ((0, "easy"), (1, "hard"), (2, "easy")):
            result = self._round(
                datetime.combine(
                    today - timedelta(days=offset),
                    datetime.min.time(),
                )
                .replace(hour=12)
                .isoformat()
            )
            result.difficulty = difficulty
            repository.save_round(result)

        stats = repository.statistics(
            start_date=today - timedelta(days=1),
            end_date=today,
            difficulty="easy",
        )

        self.assertEqual(1, stats["total"]["rounds"])
        self.assertEqual(1, stats["total"]["question_count"])
        self.assertEqual(
            3,
            repository.statistics(
                difficulties={"easy", "hard"}
            )["total"]["rounds"],
        )

    def test_statistics_counts_active_round_in_total(self):
        profile = self.manager.create("Активный раунд", 0)
        repository = self.manager.repository(profile.id)
        repository.save_active_game(
            {
                "session": {
                    "started_at": datetime.now().isoformat(),
                    "difficulty": "hard",
                }
            }
        )

        total = repository.statistics(difficulty="hard")["total"]

        self.assertEqual(0, total["rounds_completed"])
        self.assertEqual(1, total["rounds_total"])
        self.assertEqual(
            0,
            repository.statistics(difficulty="easy")["total"]["rounds_total"],
        )

    def test_empty_manager_does_not_create_a_profile(self):
        self.assertEqual([], self.manager.profiles())

    def test_the_only_profile_can_be_deleted(self):
        profile = self.manager.create("Один", 0)
        self.manager.set_active_profile(profile.id)

        self.manager.delete(profile.id)

        self.assertEqual([], self.manager.profiles())
        self.assertIsNone(self.manager.active_profile_id())


if __name__ == "__main__":
    unittest.main()
