from __future__ import annotations

from typing import Protocol


class ProgressionRepository(Protocol):
    """Persistence operations required by the progression domain service."""

    def lifetime_rounds(self) -> list[dict[str, object]]: ...

    def lifetime_answers(self) -> list[dict[str, object]]: ...

    def lifetime_answer_countries(self) -> list[dict[str, object]]: ...

    def unlocked_achievements(self) -> dict[str, str]: ...

    def unlock_achievements(self, achievement_ids: list[str]) -> list[str]: ...
