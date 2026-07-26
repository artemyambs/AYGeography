from __future__ import annotations

import argparse
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aygeography.catalog import CountryCatalog
from aygeography.config import CONFIGS_DIR, DATABASE_PATH
from aygeography.progression import ProgressionCatalog, ProgressionService
from aygeography.storage import GameRepository


DEMO_TAG = "[AYG_MASTERY_DEMO_V1]"
DEMO_COUNTRIES = {
    "USA": 1,
    "BRA": 1,
    "FRA": 1,
    "DEU": 2,
    "RUS": 2,
    "CHN": 2,
    "IND": 3,
    "ZAF": 3,
    "AUS": 3,
    "JPN": 3,
}


def _remove_demo(db: sqlite3.Connection) -> int:
    answer_rows = db.execute(
        """
        SELECT id, round_id
        FROM answers
        WHERE prompt LIKE ?
        """,
        (f"{DEMO_TAG}%",),
    ).fetchall()
    answer_ids = [int(row[0]) for row in answer_rows]
    round_ids = sorted({int(row[1]) for row in answer_rows})
    if answer_ids:
        placeholders = ",".join("?" for _ in answer_ids)
        db.execute(
            f"DELETE FROM answer_countries "
            f"WHERE answer_id IN ({placeholders})",
            answer_ids,
        )
    db.execute(
        "DELETE FROM answers WHERE prompt LIKE ?",
        (f"{DEMO_TAG}%",),
    )
    if round_ids:
        placeholders = ",".join("?" for _ in round_ids)
        db.execute(
            f"DELETE FROM rounds WHERE id IN ({placeholders})",
            round_ids,
        )
    return len(round_ids)


def _rebuild_achievements(repository: GameRepository) -> None:
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        db.execute("DELETE FROM achievements")
        db.commit()
    countries = CountryCatalog(
        CONFIGS_DIR / "countries_by_iso3.json",
        CONFIGS_DIR / "continents.json",
    )
    catalog = ProgressionCatalog(
        CONFIGS_DIR / "progression.json",
        CONFIGS_DIR / "achievements.json",
    )
    ProgressionService(repository, countries, catalog).sync()


def seed(repository: GameRepository) -> None:
    mastery_modes = ProgressionCatalog(
        CONFIGS_DIR / "progression.json",
        CONFIGS_DIR / "achievements.json",
    ).mastery_modes
    answers = [
        (
            mode,
            iso3,
            f"{DEMO_TAG} {iso3} {mode} {repeat + 1}",
            iso3,
            iso3,
            1,
            60.0,
            0,
        )
        for iso3, stars in DEMO_COUNTRIES.items()
        for repeat in range(stars)
        for mode in mastery_modes
    ]
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        _remove_demo(db)
        cursor = db.execute(
            """
            INSERT INTO rounds(
                started_at, duration, score, correct_count,
                question_count, difficulty
            ) VALUES(?, 0, 0, ?, ?, 'medium')
            """,
            ("2000-01-01T00:00:00", len(answers), len(answers)),
        )
        round_id = int(cursor.lastrowid)
        db.executemany(
            """
            INSERT INTO answers(
                round_id, mode, country_iso, prompt, answer,
                correct_answer, is_correct, seconds, points
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(round_id, *answer) for answer in answers],
        )
        db.execute(
            """
            INSERT INTO answer_countries(answer_id, country_iso)
            SELECT id, country_iso
            FROM answers
            WHERE round_id=?
            """,
            (round_id,),
        )
        db.commit()
    print(
        f"Добавлено {len(answers)} демонстрационных ответов "
        f"для {len(DEMO_COUNTRIES)} стран."
    )


def remove(repository: GameRepository) -> None:
    with closing(sqlite3.connect(DATABASE_PATH)) as db:
        removed_rounds = _remove_demo(db)
        db.commit()
    _rebuild_achievements(repository)
    print(
        f"Удалено демонстрационных раундов: {removed_rounds}. "
        "Достижения пересчитаны по реальной истории."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Добавляет или удаляет данные для проверки карты мастерства."
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="удалить только демонстрационные ответы и пересчитать достижения",
    )
    arguments = parser.parse_args()
    repository = GameRepository(DATABASE_PATH)
    if arguments.remove:
        remove(repository)
    else:
        seed(repository)


if __name__ == "__main__":
    main()
