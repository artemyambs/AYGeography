from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
import zipfile
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .profile_progress import ProfileProgression
from .persistence import SQLiteDatabase
from .storage import GameRepository


@dataclass(frozen=True, slots=True)
class LocalProfile:
    id: str
    nickname: str
    avatar: int
    level: int
    xp: int


class ProfileManager:
    """Owns isolated local profile databases and portable profile bundles."""

    BUNDLE_VERSION = 1
    MAX_IMPORT_BYTES = 100 * 1024 * 1024
    REQUIRED_TABLES = {
        "profile",
        "settings",
        "rounds",
        "answers",
        "answer_countries",
        "active_game",
        "statistics_state",
        "achievements",
    }

    def __init__(
        self,
        save_dir: Path,
        progression: ProfileProgression,
    ) -> None:
        self._profiles_dir = save_dir / "profiles"
        self._state_path = save_dir / "profiles.json"
        self._progression = progression
        self._profiles_dir.mkdir(parents=True, exist_ok=True)

    def ensure_default(self) -> LocalProfile:
        profiles = self.profiles()
        if profiles:
            return profiles[0]
        return self.create("ExplorerAY", 0)

    def profiles(self) -> list[LocalProfile]:
        result: list[LocalProfile] = []
        for path in sorted(self._profiles_dir.glob("*.db")):
            try:
                profile = GameRepository(path, self._progression).profile()
            except (OSError, RuntimeError, sqlite3.DatabaseError):
                continue
            result.append(
                LocalProfile(
                    path.stem,
                    str(profile["nickname"]),
                    int(profile["avatar"]),
                    int(profile["level"]),
                    int(profile["xp"]),
                )
            )
        return sorted(result, key=lambda item: item.nickname.casefold())

    def create(self, nickname: str, avatar: int) -> LocalProfile:
        profile_id = uuid.uuid4().hex
        repository = self.repository(profile_id)
        repository.update_profile(nickname, avatar)
        profile = repository.profile()
        return LocalProfile(
            profile_id,
            str(profile["nickname"]),
            int(profile["avatar"]),
            int(profile["level"]),
            int(profile["xp"]),
        )

    def repository(self, profile_id: str) -> GameRepository:
        return GameRepository(self._profile_path(profile_id), self._progression)

    def delete(self, profile_id: str) -> None:
        profiles = self.profiles()
        if len(profiles) <= 1:
            raise ValueError("Нельзя удалить единственный профиль")
        path = self._profile_path(profile_id)
        if not path.exists():
            raise KeyError(profile_id)
        path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = path.with_name(path.name + suffix)
            if sidecar.exists():
                sidecar.unlink()
        if self.active_profile_id() == profile_id:
            replacement = next(
                item for item in profiles if item.id != profile_id
            )
            self.set_active_profile(replacement.id)

    def active_profile_id(self) -> str | None:
        try:
            state = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        value = state.get("active_profile_id")
        return str(value) if value else None

    def set_active_profile(self, profile_id: str) -> None:
        if not self._profile_path(profile_id).exists():
            raise KeyError(profile_id)
        self._state_path.write_text(
            json.dumps(
                {"active_profile_id": profile_id},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def export_profile(self, profile_id: str, destination: Path) -> Path:
        source = self._profile_path(profile_id)
        if not source.exists():
            raise KeyError(profile_id)
        destination = destination.with_suffix(".ayprofile")
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "profile.db"
            with (
                closing(sqlite3.connect(source)) as source_db,
                closing(sqlite3.connect(snapshot)) as target_db,
            ):
                source_db.backup(target_db)
            manifest = {
                "format": "AYGeography profile",
                "version": self.BUNDLE_VERSION,
            }
            with zipfile.ZipFile(
                destination,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                )
                archive.write(snapshot, "profile.db")
        return destination

    def import_profile(self, source: Path) -> LocalProfile:
        with zipfile.ZipFile(source) as archive:
            names = set(archive.namelist())
            if names != {"manifest.json", "profile.db"}:
                raise ValueError("Некорректная структура файла профиля")
            database_info = archive.getinfo("profile.db")
            if database_info.file_size > self.MAX_IMPORT_BYTES:
                raise ValueError("Файл профиля слишком большой")
            if archive.getinfo("manifest.json").file_size > 32 * 1024:
                raise ValueError("Некорректный файл профиля")
            manifest = json.loads(archive.read("manifest.json"))
            if (
                not isinstance(manifest, dict)
                or manifest.get("format") != "AYGeography profile"
                or int(manifest.get("version", 0)) != self.BUNDLE_VERSION
            ):
                raise ValueError("Неподдерживаемая версия файла профиля")
            with TemporaryDirectory() as directory:
                temporary = Path(directory) / "profile.db"
                temporary.write_bytes(archive.read("profile.db"))
                self._validate_database(temporary)
                profile_id = uuid.uuid4().hex
                destination = self._profile_path(profile_id)
                shutil.copy2(temporary, destination)

        repository = self.repository(profile_id)
        profile = repository.profile()
        return LocalProfile(
            profile_id,
            str(profile["nickname"]),
            int(profile["avatar"]),
            int(profile["level"]),
            int(profile["xp"]),
        )

    def _validate_database(self, path: Path) -> None:
        try:
            with closing(sqlite3.connect(path)) as db:
                integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
                version = int(db.execute("PRAGMA user_version").fetchone()[0])
                tables = {
                    row[0]
                    for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                profile = db.execute(
                    "SELECT nickname, avatar, level, xp FROM profile WHERE id=1"
                ).fetchone()
        except sqlite3.DatabaseError as error:
            raise ValueError("Повреждённый файл профиля") from error
        if (
            integrity != "ok"
            or version > SQLiteDatabase.SCHEMA_VERSION
            or not self.REQUIRED_TABLES <= tables
            or profile is None
        ):
            raise ValueError("Повреждённый файл профиля")

    def _profile_path(self, profile_id: str) -> Path:
        if (
            len(profile_id) != 32
            or not all(character in "0123456789abcdef" for character in profile_id)
        ):
            raise ValueError("Некорректный идентификатор профиля")
        return self._profiles_dir / f"{profile_id}.db"
