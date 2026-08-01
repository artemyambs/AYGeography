from __future__ import annotations

from dataclasses import dataclass

from ..domain.session import GameSession
from ..models import GameConfig
from ..scoring import DEFAULT_SCORE_RULES, ScoreRules
from .ports import QuestionFactoryPort, RoundRepository


@dataclass(slots=True)
class StartRound:
    question_factory: QuestionFactoryPort
    catalog: object
    repository: RoundRepository
    score_rules: ScoreRules = DEFAULT_SCORE_RULES
    question_time_seconds: int = 60

    def execute(self, config: GameConfig) -> GameSession:
        questions = self.question_factory.build(
            config,
            self.catalog,
            self.repository.wrong_country_isos(),
        )
        return GameSession(
            questions,
            difficulty=config.difficulty or "medium",
            score_rules=self.score_rules,
            question_time_seconds=self.question_time_seconds,
        )
