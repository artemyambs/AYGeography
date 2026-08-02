from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Mapping


LOGGER_NAME = "aygeography"


@dataclass(frozen=True, slots=True)
class ErrorLogSettings:
    enabled: bool = True
    file_name: str = "errors.log"
    max_bytes: int = 1_048_576
    backup_count: int = 5

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> ErrorLogSettings:
        enabled = values.get("enabled", True)
        file_name = values.get("file_name", "errors.log")
        max_bytes = values.get("max_bytes", 1_048_576)
        backup_count = values.get("backup_count", 5)
        if not isinstance(enabled, bool):
            raise ValueError("Флаг журнала ошибок должен быть логическим")
        if not isinstance(file_name, str):
            raise ValueError("Имя файла журнала должно быть строкой")
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
            raise ValueError("Размер файла журнала должен быть целым числом")
        if isinstance(backup_count, bool) or not isinstance(backup_count, int):
            raise ValueError("Количество резервных файлов должно быть целым числом")
        settings = cls(
            enabled=enabled,
            file_name=file_name,
            max_bytes=max_bytes,
            backup_count=backup_count,
        )
        if not settings.file_name or Path(settings.file_name).name != settings.file_name:
            raise ValueError("Имя файла журнала не должно содержать путь")
        if settings.max_bytes < 1024:
            raise ValueError("Размер файла журнала должен быть не меньше 1024 байт")
        if settings.backup_count < 1:
            raise ValueError("Количество резервных файлов журнала должно быть положительным")
        return settings


class ErrorJournal:
    """Rotating local journal for application failures."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.logger = logging.getLogger(LOGGER_NAME)

    def configure(self, settings: ErrorLogSettings) -> None:
        self._remove_owned_handlers()
        self.logger.setLevel(logging.ERROR)
        self.logger.propagate = False
        if not settings.enabled:
            handler = logging.NullHandler()
            setattr(handler, "_aygeography_owned", True)
            self.logger.addHandler(handler)
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            self.directory / settings.file_name,
            maxBytes=settings.max_bytes,
            backupCount=settings.backup_count,
            encoding="utf-8",
            delay=True,
        )
        handler.setLevel(logging.ERROR)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            )
        )
        setattr(handler, "_aygeography_owned", True)
        self.logger.addHandler(handler)

    def record_unhandled(
        self,
        error_type: type[BaseException],
        error: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        self.logger.critical(
            "Необработанная ошибка",
            exc_info=(error_type, error, traceback),
        )

    def close(self) -> None:
        self._remove_owned_handlers()

    def _remove_owned_handlers(self) -> None:
        for handler in self.logger.handlers.copy():
            if getattr(handler, "_aygeography_owned", False):
                self.logger.removeHandler(handler)
                handler.close()


def default_error_log_directory() -> Path:
    if getattr(sys, "frozen", False):
        save_directory = (
            Path(os.environ.get("LOCALAPPDATA", Path.home()))
            / "AYGeography"
            / "save"
        )
    else:
        save_directory = Path(__file__).resolve().parents[2] / "save"
    return save_directory / "logs"
