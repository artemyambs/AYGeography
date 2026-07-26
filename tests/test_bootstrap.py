import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bootstrap


class BootstrapTests(unittest.TestCase):
    def test_dependencies_install_only_when_fingerprint_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            python_executable = runtime / "Scripts" / "python.exe"
            python_executable.parent.mkdir(parents=True)
            python_executable.touch()

            with (
                patch.object(bootstrap, "runtime_directory", return_value=runtime),
                patch.object(bootstrap.subprocess, "run") as install,
            ):
                self.assertEqual(python_executable, bootstrap.ensure_runtime())
                self.assertEqual(python_executable, bootstrap.ensure_runtime())

            install.assert_called_once()
            self.assertEqual(
                bootstrap.requirements_fingerprint(),
                (runtime / ".requirements.sha256").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
