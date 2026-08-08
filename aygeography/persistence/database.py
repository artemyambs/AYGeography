from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Mapping


class SQLiteDatabase:
    """Owns SQLite connections and ordered, idempotent migrations."""

    SCHEMA_VERSION = 5

    def __init__(
        self,
        path: Path,
        default_settings: Mapping[str, bool | str],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.default_settings = dict(default_settings)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def initialize(self) -> None:
        with closing(self.connect()) as db:
            db.execute("PRAGMA journal_mode = WAL")
            version = int(db.execute("PRAGMA user_version").fetchone()[0])
            if version > self.SCHEMA_VERSION:
                raise RuntimeError(
                    "База данных создана более новой версией AYGeography"
                )
            self._create_schema(db)
            self._migrate_legacy_schema(db)
            self._create_indexes(db)
            self._seed_defaults(db)
            db.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
            db.commit()

    @staticmethod
    def _create_schema(db: sqlite3.Connection) -> None:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                nickname TEXT NOT NULL,
                avatar INTEGER NOT NULL DEFAULT 0,
                level INTEGER NOT NULL DEFAULT 1,
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
                difficulty TEXT NOT NULL DEFAULT 'medium',
                completed INTEGER NOT NULL DEFAULT 1
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
                question_key TEXT NOT NULL DEFAULT '',
                question_payload TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(round_id) REFERENCES rounds(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS answer_countries (
                answer_id INTEGER NOT NULL,
                country_iso TEXT NOT NULL,
                PRIMARY KEY(answer_id, country_iso),
                FOREIGN KEY(answer_id) REFERENCES answers(id) ON DELETE CASCADE
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
            CREATE TABLE IF NOT EXISTS review_items (
                question_key TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                question_payload TEXT NOT NULL,
                failed_at TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'resolved')),
                failure_count INTEGER NOT NULL DEFAULT 1,
                resolved_at TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )

    def _migrate_legacy_schema(self, db: sqlite3.Connection) -> None:
        self._ensure_column(
            db,
            "profile",
            "level",
            "INTEGER NOT NULL DEFAULT 1",
        )
        self._ensure_column(
            db,
            "rounds",
            "difficulty",
            "TEXT NOT NULL DEFAULT 'medium'",
        )
        self._ensure_column(
            db,
            "rounds",
            "completed",
            "INTEGER NOT NULL DEFAULT 1",
        )
        self._ensure_column(
            db,
            "answers",
            "question_key",
            "TEXT NOT NULL DEFAULT ''",
        )
        self._ensure_column(
            db,
            "answers",
            "question_payload",
            "TEXT NOT NULL DEFAULT '{}'",
        )
        db.execute(
            """
            INSERT OR IGNORE INTO answer_countries(answer_id, country_iso)
            SELECT id, country_iso FROM answers
            """
        )
        db.execute(
            "DELETE FROM settings WHERE key IN ('show_correct', 'animations')"
        )

    @staticmethod
    def _create_indexes(db: sqlite3.Connection) -> None:
        db.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_rounds_started_at
                ON rounds(started_at);
            CREATE INDEX IF NOT EXISTS idx_answers_round_id
                ON answers(round_id);
            CREATE INDEX IF NOT EXISTS idx_answers_mode
                ON answers(mode);
            CREATE INDEX IF NOT EXISTS idx_answer_countries_country_iso
                ON answer_countries(country_iso);
            CREATE INDEX IF NOT EXISTS idx_answers_question_key
                ON answers(question_key);
            CREATE INDEX IF NOT EXISTS idx_review_items_status_failed_at
                ON review_items(status, failed_at);
            """
        )

    def _seed_defaults(self, db: sqlite3.Connection) -> None:
        db.execute(
            """
            INSERT OR IGNORE INTO profile(id, nickname, avatar, level, xp)
            VALUES(1, ?, 0, 1, 0)
            """,
            ("ExplorerAY",),
        )
        for key, value in self.default_settings.items():
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
