from __future__ import annotations

import random
import time


class SystemClock:
    def __call__(self) -> float:
        return time.monotonic()


class PythonRandomFactory:
    def __call__(self) -> random.Random:
        return random.Random()
