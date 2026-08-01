from __future__ import annotations

import random
from dataclasses import dataclass

from ..domain.questions import Question
from ..domain.session import GameSession
from ..scoring import DEFAULT_SCORE_RULES, ScoreRules
from .ports import RandomFactory, RoundRepository


@dataclass(slots=True)
class StartReviewRound:
    repository: RoundRepository
    random_factory: RandomFactory = random.Random
    score_rules: ScoreRules = DEFAULT_SCORE_RULES
    question_time_seconds: int = 60

    def pending_count(self) -> int:
        return self.repository.pending_review_count()

    def execute(self) -> GameSession:
        items = self.repository.review_items("pending")
        if not items:
            raise ValueError("Очередь повторения пуста")
        rng = self.random_factory()
        questions: list[Question] = []
        for item in items:
            question = Question.from_state(item.question_state)
            if question.key != item.question_key or question.mode != item.mode:
                raise ValueError(
                    f"Повреждена запись повторения: {item.question_key}"
                )
            if question.options:
                rng.shuffle(question.options)
            question.scoring_difficulty = "medium"
            questions.append(question)
        return GameSession(
            questions,
            difficulty="medium",
            score_rules=self.score_rules,
            question_time_seconds=self.question_time_seconds,
        )
