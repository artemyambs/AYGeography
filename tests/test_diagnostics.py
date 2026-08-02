import logging
import tempfile
import unittest
from pathlib import Path

from aygeography.infrastructure.diagnostics import ErrorJournal, ErrorLogSettings


class ErrorJournalTests(unittest.TestCase):
    def test_records_traceback_in_utf8_log(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = ErrorJournal(Path(directory))
            journal.configure(ErrorLogSettings())
            try:
                raise RuntimeError("проверочная ошибка")
            except RuntimeError as error:
                journal.record_unhandled(type(error), error, error.__traceback__)
            journal.close()

            content = (Path(directory) / "errors.log").read_text(encoding="utf-8")
            self.assertIn("Необработанная ошибка", content)
            self.assertIn("RuntimeError: проверочная ошибка", content)

    def test_disabled_journal_does_not_create_log(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = ErrorJournal(Path(directory))
            journal.configure(ErrorLogSettings(enabled=False))
            logging.getLogger("aygeography.test").error("не записывать")
            journal.close()

            self.assertFalse((Path(directory) / "errors.log").exists())

    def test_rejects_path_in_file_name(self):
        with self.assertRaises(ValueError):
            ErrorLogSettings.from_mapping({"file_name": "nested/errors.log"})


if __name__ == "__main__":
    unittest.main()
