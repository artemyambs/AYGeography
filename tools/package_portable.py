from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
PACKAGE_DIR = DIST_DIR / "AYGeography"
ARCHIVE_PATH = DIST_DIR / "AYGeography-portable.zip"
README_SOURCE = ROOT / "PORTABLE_README.txt"
README_NAME = "README.txt"


def _validate_package() -> None:
    required = (
        PACKAGE_DIR / "AYGeography.exe",
        PACKAGE_DIR / "_internal" / "assets",
        PACKAGE_DIR / "_internal" / "configs",
    )
    missing = [path for path in required if not path.exists()]
    runtime_dlls = tuple((PACKAGE_DIR / "_internal").glob("python*.dll"))
    if missing or not runtime_dlls:
        details = ", ".join(str(path) for path in missing)
        if not runtime_dlls:
            details = f"{details}, встроенный Python runtime".strip(", ")
        raise FileNotFoundError(f"Неполная автономная сборка: {details}")


def _create_archive() -> None:
    with zipfile.ZipFile(
        ARCHIVE_PATH,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in sorted(PACKAGE_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(DIST_DIR))


def main() -> None:
    _validate_package()
    shutil.copy2(README_SOURCE, PACKAGE_DIR / README_NAME)
    _create_archive()
    print(f"Готово: {ARCHIVE_PATH}")


if __name__ == "__main__":
    main()
