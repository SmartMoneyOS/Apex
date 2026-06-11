"""Robinhood STOCKS adapter - read this before enabling it.

Robinhood has NO official API for stock trading. The `robin_stocks` library
works by driving Robinhood's private app endpoints with your username and
password. That means:

- It can break without notice whenever Robinhood changes their app API.
- Automated use of the private API is against Robinhood's terms of service
  and accounts have been restricted for it. This is YOUR account at risk.
- Stock-specific constraints apply that crypto doesn't have: the Pattern Day
  Trader rule (account < $25k -> max 3 day trades per 5 sessions), market
  hours only, no API shorting.

If stocks via a real, supported API matter to you, Alpaca or Interactive
Brokers are the standard choices and Apex's Broker interface makes adding
them a one-file job. This adapter exists so the option is there - disabled
unless you install the extra and opt in explicitly.

    pip install "apex-trader[stocks]"
"""
from __future__ import annotations

from .base import Broker


class RobinhoodStocksBroker(Broker):
    def __init__(self, username: str, password: str, i_accept_the_tos_risk: bool = False):
        if not i_accept_the_tos_risk:
            raise RuntimeError(
                "Unofficial API: pass i_accept_the_tos_risk=True after reading "
                "the warning at the top of this file.")
        try:
            import robin_stocks.robinhood as rh
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "pip install 'apex-trader[stocks]' to enable stock trading") from e
        self._rh = rh
        rh.login(username, password)

    def get_price(self, symbol: str) -> float:
        return float(self._rh.stocks.get_latest_price(symbol)[0])

    def get_cash(self) -> float:
        return float(self._rh.profiles.load_account_profile(info="buying_power"))

    def get_positions(self) -> dict[str, float]:
        out = {}
        for pos in self._rh.account.build_holdings().items():
            sym, info = pos
            out[sym] = float(info["quantity"])
        return out

    def market_order(self, symbol: str, qty: float) -> None:
        if qty > 0:
            self._rh.orders.order_buy_fractional_by_quantity(symbol, round(qty, 6))
        elif qty < 0:
            self._rh.orders.order_sell_fractional_by_quantity(symbol, round(-qty, 6))
