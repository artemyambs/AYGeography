from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_PATH = PROJECT_DIR / "requirements.txt"


def runtime_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    version = f"py{sys.version_info.major}{sys.version_info.minor}"
    return base / "AYGeography" / "runtime" / version


def requirements_fingerprint() -> str:
    digest = hashlib.sha256()
    digest.update(REQUIREMENTS_PATH.read_bytes())
    digest.update(sys.version.encode("utf-8"))
    return digest.hexdigest()


def ensure_runtime() -> Path:
    environment = runtime_directory()
    python_executable = environment / "Scripts" / "python.exe"
    if not python_executable.exists():
        environment.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(environment)

    marker = environment / ".requirements.sha256"
    fingerprint = requirements_fingerprint()
    if not marker.exists() or marker.read_text(encoding="utf-8") != fingerprint:
        subprocess.run(
            [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--requirement",
                str(REQUIREMENTS_PATH),
            ],
            cwd=PROJECT_DIR,
            check=True,
        )
        marker.write_text(fingerprint, encoding="utf-8")
    return python_executable


def launch_game(python_executable: Path) -> None:
    pythonw = python_executable.with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else python_executable
    subprocess.Popen(
        [str(executable), str(PROJECT_DIR / "main.py")],
        cwd=PROJECT_DIR,
    )


def main() -> int:
    try:
        launch_game(ensure_runtime())
    except (OSError, subprocess.SubprocessError) as error:
        print(f"Не удалось подготовить запуск AYGeography: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
