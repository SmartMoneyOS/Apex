"""Donchian channel breakout: go with the break of recent extremes."""
from __future__ import annotations

from .base import Strategy


class VolBreakout(Strategy):
    def __init__(self, window: int = 200):
        super().__init__()
        self.window = window

    def __repr__(self) -> str:
        return f"breakout_{self.window}"

    def signal(self, symbol: str) -> float:
        hist = self.prices[symbol]
        if len(hist) < self.window:
            return 0.0
        recent = list(hist)[-self.window:-1]
        hi, lo = max(recent), min(recent)
        px = hist[-1]
        if px >= hi:
            return 1.0
        if px <= lo:
            return -1.0
        # decay toward 0 inside the channel
        mid = (hi + lo) / 2
        half = (hi - lo) / 2
        return self._clip(0.5 * (px - mid) / half) if half > 0 else 0.0
