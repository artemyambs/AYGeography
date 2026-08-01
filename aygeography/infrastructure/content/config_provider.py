from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ConfigProvider:
    """Single validated gateway to versioned JSON configuration files."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def object(
        self,
        name: str,
        *,
        schema_version: int | None = None,
    ) -> dict[str, Any]:
        root = self.directory.resolve()
        path = (root / name).resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"Недопустимый путь конфигурации: {name}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Не удалось загрузить настройки: {path}") from error
        if not isinstance(value, dict):
            raise ValueError(f"{name} должен содержать JSON-объект")
        if schema_version is not None:
            actual = value.get("schema_version")
            if actual != schema_version:
                raise ValueError(
                    f"{name}: ожидается schema_version={schema_version}, "
                    f"получено {actual!r}"
                )
        return value

    def validate_manifest(self, name: str = "config_manifest.json") -> None:
        manifest = self.object(name, schema_version=1)
        documents = manifest.get("documents")
        if not isinstance(documents, list):
            raise ValueError(f"{name}: поле documents должно быть списком")
        for document in documents:
            if not isinstance(document, dict):
                raise ValueError(f"{name}: некорректное описание документа")
            path = document.get("path")
            version = document.get("schema_version")
            if not isinstance(path, str) or not isinstance(version, int):
                raise ValueError(f"{name}: некорректная версия документа")
            self.object(path, schema_version=version)
