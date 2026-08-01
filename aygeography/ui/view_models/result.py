from __future__ import annotations

from dataclasses import dataclass

from ...domain.result_rating import ResultRatingPolicy
from ...models import RoundResult


@dataclass(frozen=True, slots=True)
class ResultSummary:
    title: str
    accuracy_percent: int
    correct_count: int
    question_count: int
    score: int
    average_seconds: float
    duration_seconds: float
    max_streak: int

    @classmethod
    def create(
        cls,
        result: RoundResult,
        ratings: ResultRatingPolicy,
    ) -> ResultSummary:
        accuracy = round(result.accuracy * 100)
        best = current = 0
        for answer in result.answers:
            current = current + 1 if answer.is_correct else 0
            best = max(best, current)
        return cls(
            title=ratings.title(accuracy),
            accuracy_percent=accuracy,
            correct_count=result.correct_count,
            question_count=len(result.answers),
            score=result.score,
            average_seconds=result.average_seconds,
            duration_seconds=result.duration_seconds,
            max_streak=best,
        )
