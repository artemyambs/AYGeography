from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import cast

from .config import CONFIGS_DIR
from .difficulty import DIFFICULTY_KEYS
from .domain.review import ReviewItem, ReviewStatus
from .models import AnswerRecord, RoundResult
from .persistence import SQLiteDatabase
from .profile_progress import ProfileProgression


class GameRepository:
    """SQLite-репозиторий локального профиля, настроек и статистики."""

    BEST_SCORE_QUESTION_COUNT = 25
    BEST_SCORE_QUESTION_COUNTS = (10, 25, 50, 100)
    BEST_SCORE_PERIOD_DAYS = 7
    DEFAULT_SETTINGS = {
        "fullscreen": False,
        "confirm_exit": True,
    }

    def __init__(
        self,
        database_path: Path,
        profile_progression: ProfileProgression | None = None,
    ) -> None:
        self._database = SQLiteDatabase(
            database_path,
            self.DEFAULT_SETTINGS,
        )
        self._database.initialize()
        self._profile_progression = profile_progression or ProfileProgression(
            CONFIGS_DIR / "progression.json"
        )
        self._profile_cache: dict[str, int | str] | None = None

    def _connect(self) -> sqlite3.Connection:
        return self._database.connect()

    def profile(self) -> dict[str, int | str]:
        if self._profile_cache is not None:
            return self._profile_cache.copy()
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT nickname, avatar, level, xp FROM profile WHERE id=1"
            ).fetchone()
        self._profile_cache = dict(row)
        return self._profile_cache.copy()

    def update_profile(self, nickname: str, avatar: int) -> None:
        with closing(self._connect()) as db:
            db.execute(
                "UPDATE profile SET nickname=?, avatar=? WHERE id=1",
                (nickname.strip()[:24] or "ExplorerAY", avatar),
            )
            db.commit()
        self._profile_cache = None

    def settings(self) -> dict[str, bool | str]:
        with closing(self._connect()) as db:
            rows = db.execute("SELECT key, value FROM settings").fetchall()
        values = self.DEFAULT_SETTINGS.copy()
        values.update(
            {
                row["key"]: json.loads(row["value"])
                for row in rows
                if row["key"] in self.DEFAULT_SETTINGS
            }
        )
        return values

    def set_setting(self, key: str, value: bool | str) -> None:
        if key not in self.DEFAULT_SETTINGS:
            raise KeyError(key)
        expected_type = type(self.DEFAULT_SETTINGS[key])
        if type(value) is not expected_type:
            raise TypeError(f"{key} ожидает значение типа {expected_type.__name__}")
        with closing(self._connect()) as db:
            db.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)",
                (key, json.dumps(value)),
            )
            db.commit()

    def save_round(self, result: RoundResult) -> None:
        with closing(self._connect()) as db:
            cursor = db.execute(
                """
                INSERT INTO rounds(
                    started_at, duration, score, correct_count,
                    question_count, difficulty, completed
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.started_at,
                    result.duration_seconds,
                    result.score,
                    result.correct_count,
                    len(result.answers),
                    result.difficulty,
                    int(result.completed),
                ),
            )
            round_id = int(cursor.lastrowid)
            for item in result.answers:
                answer_cursor = db.execute(
                    """
                    INSERT INTO answers(
                        round_id, mode, country_iso, prompt, answer,
                        correct_answer, is_correct, seconds, points,
                        question_key, question_payload
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        round_id,
                        item.mode,
                        item.country_iso,
                        item.prompt,
                        item.answer,
                        item.correct_answer,
                        int(item.is_correct),
                        item.seconds,
                        item.points,
                        item.question_key,
                        json.dumps(
                            item.question_state,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    ),
                )
                answer_id = int(answer_cursor.lastrowid)
                db.executemany(
                    """
                    INSERT INTO answer_countries(answer_id, country_iso)
                    VALUES(?, ?)
                    """,
                    [
                        (answer_id, country_iso)
                        for country_iso in dict.fromkeys(item.subjects)
                    ],
                )
                self._update_review_item(db, item)
            profile = db.execute(
                "SELECT level, xp FROM profile WHERE id=1"
            ).fetchone()
            progress = self._profile_progression.add_score(
                int(profile["level"]),
                int(profile["xp"]),
                result.score,
            )
            db.execute(
                "UPDATE profile SET level=?, xp=? WHERE id=1",
                (progress.level, progress.xp),
            )
            db.commit()
        self._profile_cache = None

    @staticmethod
    def _update_review_item(
        db: sqlite3.Connection,
        answer: AnswerRecord,
    ) -> None:
        """Update learning state in the same transaction as the answer."""
        if not answer.question_key or not answer.question_state:
            return
        now = datetime.now().isoformat(timespec="seconds")
        if answer.is_correct:
            db.execute(
                """
                UPDATE review_items
                SET status='resolved', resolved_at=?, updated_at=?
                WHERE question_key=? AND status='pending'
                """,
                (now, now, answer.question_key),
            )
            return
        payload = json.dumps(
            answer.question_state,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        db.execute(
            """
            INSERT INTO review_items(
                question_key, mode, question_payload, failed_at,
                status, failure_count, resolved_at, updated_at
            ) VALUES(?, ?, ?, ?, 'pending', 1, NULL, ?)
            ON CONFLICT(question_key) DO UPDATE SET
                mode=excluded.mode,
                question_payload=excluded.question_payload,
                failed_at=excluded.failed_at,
                status='pending',
                failure_count=review_items.failure_count + 1,
                resolved_at=NULL,
                updated_at=excluded.updated_at
            """,
            (answer.question_key, answer.mode, payload, now, now),
        )

    def review_items(
        self,
        status: ReviewStatus | None = None,
        limit: int | None = None,
    ) -> list[ReviewItem]:
        if limit is not None and limit <= 0:
            raise ValueError("Лимит элементов повторения должен быть положительным")
        parameters: tuple[object, ...] = ()
        where = ""
        if status is not None:
            if status not in ("pending", "resolved"):
                raise ValueError(f"Неизвестный статус повторения: {status}")
            where = "WHERE status=?"
            parameters = (status,)
        limit_clause = ""
        if limit is not None:
            limit_clause = "LIMIT ?"
            parameters += (limit,)
        with closing(self._connect()) as db:
            rows = db.execute(
                f"""
                SELECT question_key, mode, question_payload, failed_at,
                       status, failure_count, resolved_at
                FROM review_items
                {where}
                ORDER BY failed_at, question_key
                {limit_clause}
                """,
                parameters,
            ).fetchall()
        result: list[ReviewItem] = []
        for row in rows:
            try:
                payload = json.loads(row["question_payload"])
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError(
                    f"Повреждено состояние вопроса: {row['question_key']}"
                ) from error
            if not isinstance(payload, dict):
                raise ValueError(
                    f"Повреждено состояние вопроса: {row['question_key']}"
                )
            review_status = str(row["status"])
            if review_status not in ("pending", "resolved"):
                raise ValueError(
                    f"Поврежден статус вопроса: {row['question_key']}"
                )
            result.append(
                ReviewItem(
                    question_key=str(row["question_key"]),
                    mode=str(row["mode"]),
                    failed_at=datetime.fromisoformat(str(row["failed_at"])),
                    status=cast(ReviewStatus, review_status),
                    question_state=payload,
                    failure_count=int(row["failure_count"]),
                    resolved_at=(
                        datetime.fromisoformat(str(row["resolved_at"]))
                        if row["resolved_at"]
                        else None
                    ),
                )
            )
        return result

    def pending_review_count(self) -> int:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT COUNT(*) count FROM review_items WHERE status='pending'"
            ).fetchone()
        return int(row["count"])

    def lifetime_rounds(self) -> list[dict[str, object]]:
        """All rounds, including data hidden by a statistics reset."""
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT id, started_at, duration, score, correct_count,
                       question_count, difficulty, completed
                FROM rounds
                ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def lifetime_answers(self) -> list[dict[str, object]]:
        """All answers used by permanent achievements and country mastery."""
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT id, round_id, mode, country_iso, is_correct,
                       seconds, points, question_key
                FROM answers
                ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def lifetime_answer_countries(self) -> list[dict[str, object]]:
        """Country associations used by mastery without duplicating attempts."""
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT answers.id answer_id, answers.round_id, answers.mode,
                       answer_countries.country_iso, answers.is_correct
                FROM answers
                JOIN answer_countries
                  ON answer_countries.answer_id = answers.id
                ORDER BY answers.id, answer_countries.country_iso
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def unlocked_achievements(self) -> dict[str, str]:
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT achievement_id, unlocked_at FROM achievements"
            ).fetchall()
        return {
            str(row["achievement_id"]): str(row["unlocked_at"])
            for row in rows
        }

    def unlock_achievements(self, achievement_ids: list[str]) -> list[str]:
        """Persist unlocks once and return only achievements unlocked now."""
        if not achievement_ids:
            return []
        unlocked_at = datetime.now().isoformat(timespec="seconds")
        created: list[str] = []
        with closing(self._connect()) as db:
            for achievement_id in achievement_ids:
                cursor = db.execute(
                    """
                    INSERT OR IGNORE INTO achievements(
                        achievement_id, unlocked_at
                    ) VALUES(?, ?)
                    """,
                    (achievement_id, unlocked_at),
                )
                if cursor.rowcount:
                    created.append(achievement_id)
            db.commit()
        return created

    def save_active_game(self, state: dict[str, object]) -> None:
        payload = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        with closing(self._connect()) as db:
            db.execute(
                "INSERT OR REPLACE INTO active_game(id, payload) VALUES(1, ?)",
                (payload,),
            )
            db.commit()

    def load_active_game(self) -> dict[str, object] | None:
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT payload FROM active_game WHERE id=1"
            ).fetchone()
        if row is None:
            return None
        try:
            state = json.loads(row["payload"])
        except (json.JSONDecodeError, TypeError):
            self.clear_active_game()
            return None
        return state if isinstance(state, dict) else None

    def clear_active_game(self) -> None:
        with closing(self._connect()) as db:
            db.execute("DELETE FROM active_game WHERE id=1")
            db.commit()

    def reset_answer_statistics(self) -> None:
        """Reset answer statistics and the review queue without losing time or XP."""
        with closing(self._connect()) as db:
            latest_round = db.execute(
                "SELECT COALESCE(MAX(id), 0) id FROM rounds"
            ).fetchone()
            db.execute(
                """
                UPDATE statistics_state
                SET reset_after_round_id=?, reset_at=?
                WHERE id=1
                """,
                (
                    latest_round["id"],
                    datetime.now().isoformat(),
                ),
            )
            db.execute("DELETE FROM review_items")
            db.commit()

    @staticmethod
    def _statistics_reset_state(
        db: sqlite3.Connection,
    ) -> tuple[int, str]:
        row = db.execute(
            """
            SELECT reset_after_round_id, reset_at
            FROM statistics_state
            WHERE id=1
            """
        ).fetchone()
        return int(row["reset_after_round_id"]), str(row["reset_at"])

    @staticmethod
    def _statistics_period_bounds(
        period: str,
    ) -> tuple[str | None, str | None]:
        today = date.today()
        starts = {
            "today": today,
            "yesterday": today - timedelta(days=1),
            "3_days": today - timedelta(days=2),
            "week": today - timedelta(days=6),
            "month": today - timedelta(days=29),
            "all": None,
        }
        if period not in starts:
            raise ValueError(f"Неизвестный период статистики: {period}")
        start = starts[period]
        if start is None:
            return None, None
        end = today if period == "yesterday" else today + timedelta(days=1)
        return start.isoformat(), end.isoformat()

    @staticmethod
    def _statistics_date_bounds(
        start_date: date | str | None,
        end_date: date | str | None,
    ) -> tuple[str | None, str | None]:
        def parse(value: date | str | None) -> date | None:
            if value is None:
                return None
            return value if isinstance(value, date) else date.fromisoformat(value)

        start = parse(start_date)
        end = parse(end_date)
        if start is None and end is None:
            return None, None
        start = start or end
        end = end or start
        if start is None or end is None:
            raise ValueError("Не удалось определить период статистики")
        if start > end:
            raise ValueError("Начальная дата не может быть позже конечной")
        return start.isoformat(), (end + timedelta(days=1)).isoformat()

    @staticmethod
    def _active_round_matches(
        payload: str | None,
        *,
        period_start: str | None,
        period_end: str | None,
        difficulties: frozenset[str] | None,
        reset_at: str,
    ) -> bool:
        if not payload:
            return False
        try:
            state = json.loads(payload)
            session = state["session"]
            started_at = str(session["started_at"])
            active_difficulty = str(session.get("difficulty", "medium"))
        except (AttributeError, json.JSONDecodeError, KeyError, TypeError):
            return False
        return not (
            started_at < reset_at
            or (period_start is not None and started_at < period_start)
            or (period_end is not None and started_at >= period_end)
            or (
                difficulties is not None
                and active_difficulty not in difficulties
            )
        )

    @staticmethod
    def _statistics_difficulties(
        difficulty: str | None,
        difficulties: Iterable[str] | None,
    ) -> frozenset[str] | None:
        if difficulty is not None and difficulties is not None:
            raise ValueError("Переданы два фильтра сложности")
        if difficulties is None:
            if difficulty is None:
                return None
            selected = frozenset({difficulty})
        else:
            selected = frozenset(difficulties)
            if not selected:
                raise ValueError("Выберите хотя бы один уровень сложности")
        unknown = selected.difference(DIFFICULTY_KEYS)
        if unknown:
            raise ValueError(
                f"Неизвестные уровни сложности: {', '.join(sorted(unknown))}"
            )
        return None if selected == frozenset(DIFFICULTY_KEYS) else selected

    def statistics(
        self,
        period: str = "all",
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        difficulty: str | None = None,
        difficulties: Iterable[str] | None = None,
    ) -> dict[str, object]:
        today = date.today()
        difficulty_filter = self._statistics_difficulties(
            difficulty,
            difficulties,
        )
        if start_date is None and end_date is None:
            period_start, period_end = self._statistics_period_bounds(period)
        else:
            period_start, period_end = self._statistics_date_bounds(
                start_date,
                end_date,
            )
        best_score_first_day = today - timedelta(
            days=self.BEST_SCORE_PERIOD_DAYS - 1
        )
        with closing(self._connect()) as db:
            reset_after_round_id, reset_at = self._statistics_reset_state(db)
            parameters: dict[str, object] = {
                "reset_id": reset_after_round_id,
                "reset_at": reset_at,
                "question_count": self.BEST_SCORE_QUESTION_COUNT,
            }
            period_sql = ""
            if period_start is not None and period_end is not None:
                period_sql = (
                    " AND rounds.started_at >= :period_start"
                    " AND rounds.started_at < :period_end"
                )
                parameters.update(
                    period_start=period_start,
                    period_end=period_end,
                )
            difficulty_sql = ""
            if difficulty_filter is not None:
                placeholders = []
                for index, value in enumerate(sorted(difficulty_filter)):
                    parameter_name = f"difficulty_{index}"
                    placeholders.append(f":{parameter_name}")
                    parameters[parameter_name] = value
                difficulty_sql = (
                    " AND rounds.difficulty IN ("
                    + ", ".join(placeholders)
                    + ")"
                )
            total = db.execute(
                f"""
                SELECT
                    COUNT(*) rounds,
                    COALESCE(SUM(completed), 0) rounds_completed,
                    COALESCE(SUM(duration), 0) duration,
                    COALESCE(SUM(question_count), 0) question_count,
                    COALESCE(SUM(correct_count), 0) correct_count
                FROM rounds
                WHERE rounds.id > :reset_id
                  AND rounds.started_at >= :reset_at
                  {period_sql}
                  {difficulty_sql}
                """,
                parameters,
            ).fetchone()
            play_time = db.execute(
                f"""
                SELECT COALESCE(SUM(duration), 0) duration
                FROM rounds
                WHERE 1=1
                  {period_sql}
                  {difficulty_sql}
                """,
                parameters,
            ).fetchone()
            comparable_best = db.execute(
                f"""
                SELECT COALESCE(MAX(score), 0) best_score
                FROM rounds
                WHERE rounds.id > :reset_id
                  AND rounds.started_at >= :reset_at
                  AND completed = 1
                  AND question_count = :question_count
                  {period_sql}
                  {difficulty_sql}
                """,
                parameters,
            ).fetchone()
            best_score_rows = db.execute(
                f"""
                SELECT question_count, COALESCE(MAX(score), 0) best_score
                FROM rounds
                WHERE rounds.id > :reset_id
                  AND rounds.started_at >= :reset_at
                  AND completed = 1
                  AND question_count IN (10, 25, 50, 100)
                  {period_sql}
                  {difficulty_sql}
                GROUP BY question_count
                """,
                parameters,
            ).fetchall()
            last_week_best = db.execute(
                f"""
                SELECT COALESCE(MAX(score), 0) best_score
                FROM rounds
                WHERE rounds.id > :reset_id
                  AND rounds.started_at >= :reset_at
                  AND completed = 1
                  AND question_count = :question_count
                  AND date(started_at) BETWEEN :week_start AND :today
                  {difficulty_sql}
                """,
                {
                    **parameters,
                    "week_start": best_score_first_day.isoformat(),
                    "today": today.isoformat(),
                },
            ).fetchone()
            modes = db.execute(
                f"""
                SELECT answers.mode, COUNT(*) total,
                       SUM(answers.is_correct) correct
                FROM answers
                JOIN rounds ON rounds.id = answers.round_id
                WHERE rounds.id > :reset_id
                  AND rounds.started_at >= :reset_at
                  {period_sql}
                  {difficulty_sql}
                GROUP BY answers.mode
                """,
                parameters,
            ).fetchall()
            continents = db.execute(
                f"""
                SELECT answer_countries.country_iso, COUNT(*) total,
                       SUM(answers.is_correct) correct
                FROM answers
                JOIN rounds ON rounds.id = answers.round_id
                JOIN answer_countries
                  ON answer_countries.answer_id = answers.id
                WHERE rounds.id > :reset_id
                  AND rounds.started_at >= :reset_at
                  {period_sql}
                  {difficulty_sql}
                GROUP BY answer_countries.country_iso
                """,
                parameters,
            ).fetchall()
            first_day = today - timedelta(days=364)
            recent_rows = db.execute(
                f"""
                SELECT date(started_at) day, COUNT(*) count,
                       COALESCE(SUM(duration), 0) duration
                FROM rounds
                WHERE date(started_at) >= :first_day
                  {period_sql}
                  {difficulty_sql}
                GROUP BY date(started_at)
                """,
                {**parameters, "first_day": first_day.isoformat()},
            ).fetchall()
            active_round = db.execute(
                "SELECT payload FROM active_game WHERE id=1"
            ).fetchone()
        recent_by_day = {row["day"]: dict(row) for row in recent_rows}
        recent = []
        for offset in range(365):
            day = (first_day + timedelta(days=offset)).isoformat()
            recent.append(
                recent_by_day.get(
                    day,
                    {"day": day, "count": 0, "duration": 0.0},
                )
            )
        total_stats = dict(total)
        active_round_count = int(
            self._active_round_matches(
                str(active_round["payload"]) if active_round else None,
                period_start=period_start,
                period_end=period_end,
                difficulties=difficulty_filter,
                reset_at=reset_at,
            )
        )
        total_stats["rounds_total"] = (
            int(total_stats["rounds"]) + active_round_count
        )
        total_stats["duration"] = play_time["duration"]
        total_stats["best_score_25_questions"] = comparable_best["best_score"]
        total_stats["best_score_last_7_days_25_questions"] = (
            last_week_best["best_score"]
        )
        return {
            "total": total_stats,
            "best_scores": {
                question_count: next(
                    (
                        int(row["best_score"])
                        for row in best_score_rows
                        if int(row["question_count"]) == question_count
                    ),
                    0,
                )
                for question_count in self.BEST_SCORE_QUESTION_COUNTS
            },
            "modes": [dict(row) for row in modes],
            "countries": [dict(row) for row in continents],
            "recent": recent,
        }

    def wrong_country_isos(self) -> list[str]:
        with closing(self._connect()) as db:
            reset_after_round_id, reset_at = self._statistics_reset_state(db)
            rows = db.execute(
                """
                SELECT DISTINCT answer_countries.country_iso
                FROM answers
                JOIN rounds ON rounds.id = answers.round_id
                JOIN answer_countries
                  ON answer_countries.answer_id = answers.id
                WHERE answers.is_correct=0
                  AND rounds.id > ?
                  AND rounds.started_at >= ?
                """,
                (
                    reset_after_round_id,
                    reset_at,
                ),
            ).fetchall()
        return [row["country_iso"] for row in rows]
