"""Z-score mean reversion: fade extremes, expect snap-back to the rolling mean."""
from __future__ import annotations

import statistics

from .base import Strategy


class MeanReversion(Strategy):
    def __init__(self, window: int = 120):
        super().__init__()
        self.window = window

    def __repr__(self) -> str:
        return f"meanrev_{self.window}"

    def signal(self, symbol: str) -> float:
        hist = self.prices[symbol]
        if len(hist) < self.window:
            return 0.0
        recent = list(hist)[-self.window:]
        mean = statistics.fmean(recent)
        sd = statistics.pstdev(recent)
        if sd == 0:
            return 0.0
        z = (hist[-1] - mean) / sd
        # fade the move; full conviction at |z| >= 2
        return self._clip(-z / 2)
