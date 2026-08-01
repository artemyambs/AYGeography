from __future__ import annotations

from dataclasses import dataclass

from ..models import RoundResult
from .ports import ProgressionPort, RoundRepository


@dataclass(slots=True)
class FinishRound:
    repository: RoundRepository
    progression: ProgressionPort

    def execute(self, result: RoundResult) -> list[object]:
        self.repository.save_round(result)
        return list(self.progression.sync())
