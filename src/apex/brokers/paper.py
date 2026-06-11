"""Paper broker: simulates fills with fees and slippage. The default mode.

Robinhood crypto has no explicit commission but a real spread; model it here
honestly or the backtest will lie to you.
"""
from __future__ import annotations

from .base import Broker


class PaperBroker(Broker):
    def __init__(self, starting_cash: float = 10_000.0,
                 fee_bps: float = 10.0, slippage_bps: float = 5.0):
        self._cash = starting_cash
        self._positions: dict[str, float] = {}
        self._prices: dict[str, float] = {}
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.fills: list[dict] = []

    # the engine pushes the latest bar prices in before trading
    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    def get_price(self, symbol: str) -> float:
        return self._prices[symbol]

    def get_cash(self) -> float:
        return self._cash

    def get_positions(self) -> dict[str, float]:
        return dict(self._positions)

    def market_order(self, symbol: str, qty: float) -> None:
        if qty == 0:
            return
        px = self._prices[symbol]
        slip = self.slippage_bps / 10_000
        fill_px = px * (1 + slip) if qty > 0 else px * (1 - slip)
        notional = abs(qty) * fill_px
        fee = notional * self.fee_bps / 10_000
        self._cash -= qty * fill_px + fee
        new_qty = self._positions.get(symbol, 0.0) + qty
        if abs(new_qty) < 1e-12:
            self._positions.pop(symbol, None)
        else:
            self._positions[symbol] = new_qty
        self.fills.append({"symbol": symbol, "qty": qty, "price": fill_px, "fee": fee})
