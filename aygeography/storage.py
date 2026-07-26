from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import RoundResult


class GameRepository:
    """SQLite-репозиторий локального профиля, настроек и статистики."""

    BEST_SCORE_QUESTION_COUNT = 25
    BEST_SCORE_PERIOD_DAYS = 7
    DEFAULT_SETTINGS = {
        "fullscreen": False,
        "confirm_exit": True,
        "show_correct": True,
        "animations": True,
    }

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._path = database_path
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    nickname TEXT NOT NULL,
                    avatar INTEGER NOT NULL DEFAULT 0,
                    xp INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rounds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    duration REAL NOT NULL,
                    score INTEGER NOT NULL,
                    correct_count INTEGER NOT NULL,
                    question_count INTEGER NOT NULL,
                    difficulty TEXT NOT NULL DEFAULT 'medium'
                );
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    country_iso TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    correct_answer TEXT NOT NULL,
                    is_correct INTEGER NOT NULL,
                    seconds REAL NOT NULL,
                    points INTEGER NOT NULL,
                    FOREIGN KEY(round_id) REFERENCES rounds(id)
                );
                CREATE TABLE IF NOT EXISTS active_game (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS statistics_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    reset_after_round_id INTEGER NOT NULL DEFAULT 0,
                    reset_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS achievements (
                    achievement_id TEXT PRIMARY KEY,
                    unlocked_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(
                db,
                "rounds",
                "difficulty",
                "TEXT NOT NULL DEFAULT 'medium'",
            )
            db.execute(
                "INSERT OR IGNORE INTO profile(id, nickname, avatar, xp) VALUES(1, ?, 0, 0)",
                ("ExplorerAY",),
            )
            for key, value in self.DEFAULT_SETTINGS.items():
                db.execute(
                    "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                    (key, json.dumps(value)),
                )
            db.execute(
                """
                INSERT OR IGNORE INTO statistics_state(
                    id, reset_after_round_id, reset_at
                ) VALUES(1, 0, '')
                """
            )
            db.commit()

    @staticmethod
    def _ensure_column(
        db: sqlite3.Connection,
        table: str,
        column: str,
        declaration: str,
    ) -> None:
        columns = {
            row["name"]
            for row in db.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            db.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {declaration}"
            )

    def profile(self) -> dict[str, int | str]:
        with closing(self._connect()) as db:
            row = db.execute("SELECT nickname, avatar, xp FROM profile WHERE id=1").fetchone()
        return dict(row)

    def update_profile(self, nickname: str, avatar: int) -> None:
        with closing(self._connect()) as db:
            db.execute(
                "UPDATE profile SET nickname=?, avatar=? WHERE id=1",
                (nickname.strip()[:24] or "ExplorerAY", avatar),
            )
            db.commit()

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
                    question_count, difficulty
                )
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    result.started_at,
                    result.duration_seconds,
                    result.score,
                    result.correct_count,
                    len(result.answers),
                    result.difficulty,
                ),
            )
            round_id = int(cursor.lastrowid)
            db.executemany(
                """
                INSERT INTO answers(
                    round_id, mode, country_iso, prompt, answer, correct_answer,
                    is_correct, seconds, points
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
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
                    )
                    for item in result.answers
                ],
            )
            db.execute("UPDATE profile SET xp = xp + ? WHERE id=1", (result.score,))
            db.commit()

    def lifetime_rounds(self) -> list[dict[str, object]]:
        """All rounds, including data hidden by a statistics reset."""
        with closing(self._connect()) as db:
            rows = db.execute(
                """
                SELECT id, started_at, duration, score, correct_count,
                       question_count, difficulty
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
                       seconds, points
                FROM answers
                ORDER BY id
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
        """Start round and answer statistics again without losing time or XP."""
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

    def statistics(self) -> dict[str, object]:
        today = date.today()
        best_score_first_day = today - timedelta(
            days=self.BEST_SCORE_PERIOD_DAYS - 1
        )
        with closing(self._connect()) as db:
            reset_after_round_id, reset_at = self._statistics_reset_state(db)
            total = db.execute(
                """
                SELECT
                    COALESCE(SUM(
                        CASE WHEN id > ? AND started_at >= ? THEN 1 ELSE 0 END
                    ), 0) rounds,
                    COALESCE(SUM(duration), 0) duration,
                    COALESCE(SUM(
                        CASE
                            WHEN id > ? AND started_at >= ?
                            THEN question_count
                            ELSE 0
                        END
                    ), 0) question_count
                FROM rounds
                """,
                (
                    reset_after_round_id,
                    reset_at,
                    reset_after_round_id,
                    reset_at,
                ),
            ).fetchone()
            comparable_best = db.execute(
                """
                SELECT COALESCE(MAX(score), 0) best_score
                FROM rounds
                WHERE id > ?
                  AND started_at >= ?
                  AND question_count = ?
                  AND date(started_at) BETWEEN ? AND ?
                """,
                (
                    reset_after_round_id,
                    reset_at,
                    self.BEST_SCORE_QUESTION_COUNT,
                    best_score_first_day.isoformat(),
                    today.isoformat(),
                ),
            ).fetchone()
            modes = db.execute(
                """
                SELECT answers.mode, COUNT(*) total,
                       SUM(answers.is_correct) correct
                FROM answers
                JOIN rounds ON rounds.id = answers.round_id
                WHERE rounds.id > ? AND rounds.started_at >= ?
                GROUP BY answers.mode
                """,
                (reset_after_round_id, reset_at),
            ).fetchall()
            continents = db.execute(
                """
                SELECT answers.country_iso, COUNT(*) total,
                       SUM(answers.is_correct) correct
                FROM answers
                JOIN rounds ON rounds.id = answers.round_id
                WHERE rounds.id > ? AND rounds.started_at >= ?
                GROUP BY answers.country_iso
                """,
                (reset_after_round_id, reset_at),
            ).fetchall()
            first_day = today - timedelta(days=29)
            recent_rows = db.execute(
                """
                SELECT date(started_at) day, COUNT(*) count,
                       COALESCE(SUM(duration), 0) duration
                FROM rounds
                WHERE date(started_at) >= ?
                GROUP BY date(started_at)
                """,
                (first_day.isoformat(),),
            ).fetchall()
        recent_by_day = {row["day"]: dict(row) for row in recent_rows}
        recent = []
        for offset in range(30):
            day = (first_day + timedelta(days=offset)).isoformat()
            recent.append(
                recent_by_day.get(
                    day,
                    {"day": day, "count": 0, "duration": 0.0},
                )
            )
        total_stats = dict(total)
        total_stats["best_score_last_7_days_25_questions"] = (
            comparable_best["best_score"]
        )
        return {
            "total": total_stats,
            "modes": [dict(row) for row in modes],
            "countries": [dict(row) for row in continents],
            "recent": recent,
        }

    def wrong_country_isos(self) -> list[str]:
        with closing(self._connect()) as db:
            reset_after_round_id, reset_at = self._statistics_reset_state(db)
            rows = db.execute(
                """
                SELECT DISTINCT answers.country_iso
                FROM answers
                JOIN rounds ON rounds.id = answers.round_id
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
