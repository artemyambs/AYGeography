from __future__ import annotations

from ..domain.session import GameSession
from ..models import AnswerRecord


class AnswerQuestion:
    def execute(
        self,
        session: GameSession,
        value: str,
        elapsed_seconds: float,
    ) -> AnswerRecord:
        return session.answer(value, elapsed_seconds)
