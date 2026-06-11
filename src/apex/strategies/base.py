"""Strategy interface: consume prices, emit a conviction signal in [-1, 1]."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict, deque


class Strategy(ABC):
    """A signal generator. Signals are conviction, not orders: +1 = fully long,
    0 = flat, -1 = fully short. The engine combines signals across strategies
    using the bandit's live capital weights; the risk manager does the sizing.
    """

    #: history bars retained per symbol
    lookback: int = 500

    def __init__(self) -> None:
        self.prices: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.lookback)
        )

    @property
    def name(self) -> str:
        return repr(self)

    def update(self, symbol: str, price: float) -> None:
        self.prices[symbol].append(price)

    @abstractmethod
    def signal(self, symbol: str) -> float:
        """Return conviction in [-1, 1] for the symbol at the current bar."""

    @staticmethod
    def _clip(x: float) -> float:
        return max(-1.0, min(1.0, x))
