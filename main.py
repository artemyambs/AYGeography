from aygeography.infrastructure.diagnostics import (
    ErrorJournal,
    ErrorLogSettings,
    default_error_log_directory,
)


def main() -> None:
    journal = ErrorJournal(default_error_log_directory())
    journal.configure(ErrorLogSettings())
    try:
        from aygeography.app import run
        from aygeography.config import APP_SETTINGS

        diagnostics = APP_SETTINGS.get("diagnostics", {})
        error_log = (
            diagnostics.get("error_log", {})
            if isinstance(diagnostics, dict)
            else {}
        )
        journal.configure(ErrorLogSettings.from_mapping(error_log))
        run()
    except Exception as error:
        journal.record_unhandled(type(error), error, error.__traceback__)
        raise
    finally:
        journal.close()


if __name__ == "__main__":
    main()
