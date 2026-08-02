from __future__ import annotations

from typing import Protocol, Sequence, TypeVar

from ..domain.questions import Question
from ..domain.review import ReviewItem, ReviewStatus
from ..models import GameConfig, RoundResult


class Clock(Protocol):
    def __call__(self) -> float: ...


T = TypeVar("T")


class RandomSource(Protocol):
    def shuffle(self, values: list[T]) -> None: ...


class RandomFactory(Protocol):
    def __call__(self) -> RandomSource: ...


class ReviewRepository(Protocol):
    def review_items(
        self,
        status: ReviewStatus | None = None,
        limit: int | None = None,
    ) -> list[ReviewItem]: ...

    def pending_review_count(self) -> int: ...


class RoundRepository(ReviewRepository, Protocol):
    def wrong_country_isos(self) -> list[str]: ...

    def save_round(self, result: RoundResult) -> None: ...


class QuestionFactoryPort(Protocol):
    def build(
        self,
        config: GameConfig,
        catalog: object,
        wrong_isos: list[str] | None = None,
        seed: int | None = None,
    ) -> list[Question]: ...


class ProgressionPort(Protocol):
    def sync(self) -> Sequence[object]: ...
