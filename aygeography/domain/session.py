from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from ..config import QUESTION_TIME_SECONDS
from ..difficulty import DIFFICULTY_KEYS
from ..models import AnswerRecord, RoundResult
from ..scoring import DEFAULT_SCORE_RULES, ScoreRules
from .questions import Question


class GameSession:
    """State and scoring rules for one isolated game round."""

    def __init__(
        self,
        questions: list[Question],
        difficulty: str = "medium",
        score_rules: ScoreRules = DEFAULT_SCORE_RULES,
    ) -> None:
        if difficulty not in DIFFICULTY_KEYS:
            raise ValueError(f"Неизвестный уровень сложности: {difficulty}")
        self.questions = questions
        self.difficulty = (
            "medium"
            if questions
            and all(
                question.scoring_difficulty == "medium"
                for question in questions
            )
            else difficulty
        )
        self._score_rules = score_rules
        self.index = 0
        self.score = 0
        self.streak = 0
        self.answers: list[AnswerRecord] = []
        self.started_at = datetime.now()

    @property
    def current(self) -> Question:
        return self.questions[self.index]

    @property
    def finished(self) -> bool:
        return self.index >= len(self.questions)

    def answer(self, value: str, elapsed_seconds: float) -> AnswerRecord:
        question = self.current
        correct = value == question.correct_answer
        remaining = max(0, QUESTION_TIME_SECONDS - elapsed_seconds)
        points = (
            self._score_rules.points(
                question.scoring_difficulty or self.difficulty,
                remaining,
            )
            if correct
            else 0
        )
        self.score += points
        self.streak = self.streak + 1 if correct else 0
        record = AnswerRecord(
            mode=question.mode,
            country_iso=question.country_iso,
            prompt=question.prompt,
            answer=value,
            correct_answer=question.correct_answer,
            is_correct=correct,
            seconds=elapsed_seconds,
            points=points,
            country_isos=question.subjects,
        )
        self.answers.append(record)
        self.index += 1
        return record

    def result(self) -> RoundResult:
        duration = sum(answer.seconds for answer in self.answers)
        return RoundResult(
            started_at=self.started_at.isoformat(timespec="seconds"),
            duration_seconds=duration,
            score=self.score,
            answers=self.answers.copy(),
            difficulty=self.difficulty,
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "questions": [question.to_state() for question in self.questions],
            "difficulty": self.difficulty,
            "index": self.index,
            "score": self.score,
            "streak": self.streak,
            "answers": [asdict(answer) for answer in self.answers],
            "started_at": self.started_at.isoformat(),
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> GameSession:
        questions = [
            Question.from_state(dict(raw_question))
            for raw_question in state["questions"]
        ]
        session = cls(
            questions,
            difficulty=str(state.get("difficulty", "medium")),
        )
        session.index = int(state["index"])
        if not 0 <= session.index <= len(questions):
            raise ValueError("Некорректный индекс сохранённого вопроса")
        session.score = int(state["score"])
        session.streak = int(state["streak"])
        session.answers = []
        for raw_answer in state["answers"]:
            item = dict(raw_answer)
            item["country_isos"] = tuple(item.get("country_isos", ()))
            session.answers.append(AnswerRecord(**item))
        session.started_at = datetime.fromisoformat(state["started_at"])
        return session
