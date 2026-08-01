from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


ReviewStatus = Literal["pending", "resolved"]


@dataclass(frozen=True, slots=True)
class ReviewItem:
    """Persisted learning state for one exact question."""

    question_key: str
    mode: str
    failed_at: datetime
    status: ReviewStatus
    question_state: dict[str, Any]
    failure_count: int = 1
    resolved_at: datetime | None = None

    @property
    def pending(self) -> bool:
        return self.status == "pending"
