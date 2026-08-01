from __future__ import annotations

from typing import Any

from ...domain.session import GameSession
from ...scoring import DEFAULT_SCORE_RULES, ScoreRules


class GameStateCodec:
    """Versioned boundary between a resumable session and its Pygame view."""

    VERSION = 4
    LEGACY_VERSIONS = frozenset({3})

    def encode(
        self,
        session: GameSession,
        view_state: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "session": session.to_state(),
            "view": view_state,
        }

    def decode(
        self,
        state: dict[str, Any],
        score_rules: ScoreRules = DEFAULT_SCORE_RULES,
    ) -> tuple[GameSession, dict[str, Any]]:
        version = int(state.get("version", 0))
        if version != self.VERSION and version not in self.LEGACY_VERSIONS:
            raise ValueError("Неподдерживаемая версия сохранённой игры")
        raw_view = state.get("view")
        if not isinstance(raw_view, dict):
            raise ValueError("Некорректное состояние игрового экрана")
        return GameSession.from_state(
            state["session"],
            score_rules=score_rules,
        ), dict(raw_view)
