from __future__ import annotations

from abc import ABC, abstractmethod


class Broker(ABC):
    @abstractmethod
    def get_price(self, symbol: str) -> float: ...

    @abstractmethod
    def get_cash(self) -> float: ...

    @abstractmethod
    def get_positions(self) -> dict[str, float]:
        """symbol -> quantity held"""

    @abstractmethod
    def market_order(self, symbol: str, qty: float) -> None:
        """Positive qty = buy, negative = sell."""

    def equity(self) -> float:
        eq = self.get_cash()
        for sym, qty in self.get_positions().items():
            eq += qty * self.get_price(sym)
        return eq

    def flatten(self) -> None:
        for sym, qty in list(self.get_positions().items()):
            if qty != 0:
                self.market_order(sym, -qty)
