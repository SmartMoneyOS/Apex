"""EMA-crossover momentum: ride trends, scale conviction by spread strength."""
from __future__ import annotations

from .base import Strategy


class Momentum(Strategy):
    def __init__(self, fast: int = 20, slow: int = 80):
        super().__init__()
        self.fast = fast
        self.slow = slow
        self._ema_f: dict[str, float] = {}
        self._ema_s: dict[str, float] = {}

    def __repr__(self) -> str:
        return f"momentum_{self.fast}_{self.slow}"

    def update(self, symbol: str, price: float) -> None:
        super().update(symbol, price)
        kf, ks = 2 / (self.fast + 1), 2 / (self.slow + 1)
        self._ema_f[symbol] = price if symbol not in self._ema_f else \
            price * kf + self._ema_f[symbol] * (1 - kf)
        self._ema_s[symbol] = price if symbol not in self._ema_s else \
            price * ks + self._ema_s[symbol] * (1 - ks)

    def signal(self, symbol: str) -> float:
        if len(self.prices[symbol]) < self.slow:
            return 0.0
        spread = (self._ema_f[symbol] - self._ema_s[symbol]) / self._ema_s[symbol]
        # ~1% EMA spread = full conviction
        return self._clip(spread * 100)
