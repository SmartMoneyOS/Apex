"""The trading engine: signal -> learn -> size -> execute, every bar.

Per-bar loop:
1. Ingest the new bar and compute each symbol's realized return.
2. ATTRIBUTE: credit each strategy with the PnL its *previous* signal would
   have earned, and feed that reward to the bandit. This is the live
   learning step - no retraining job, no nightly batch; the capital
   allocation shifts bar by bar toward what is currently making money.
3. COMBINE: per symbol, blend strategy signals using the bandit's weights.
4. SIZE: risk manager converts conviction into a volatility-targeted
   position value, subject to halt/kill switches.
5. EXECUTE: rebalance toward target, skipping dust-sized trades.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass

from .brokers.base import Broker
from .data.feed import PriceFeed
from .journal import Journal
from .learning.bandit import GaussianThompsonBandit
from .risk.manager import RiskManager
from .strategies.base import Strategy


@dataclass
class EngineConfig:
    bars_per_day: int = 5760
    min_trade_value: float = 5.0
    rebalance_threshold: float = 0.02  # fraction of equity
    vol_window: int = 100


class TradingEngine:
    def __init__(self, broker: Broker, feed: PriceFeed, strategies: list[Strategy],
                 bandit: GaussianThompsonBandit, risk: RiskManager,
                 journal: Journal, cfg: EngineConfig | None = None):
        self.broker = broker
        self.feed = feed
        self.strategies = strategies
        self.bandit = bandit
        self.risk = risk
        self.journal = journal
        self.cfg = cfg or EngineConfig()
        self._bar_index = 0
        self._last_price: dict[str, float] = {}
        self._last_signals: dict[str, dict[str, float]] = {}  # strat -> sym -> sig
        self._returns: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=self.cfg.vol_window))

    # -- helpers ---------------------------------------------------------------
    def _realized_vol_annual(self, symbol: str) -> float:
        rets = self._returns[symbol]
        if len(rets) < 10:
            return float("nan")
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        return math.sqrt(var) * math.sqrt(self.cfg.bars_per_day * 365)

    # -- main loop ---------------------------------------------------------------
    def step(self) -> float | None:
        bars = self.feed.next_bars()
        if bars is None:
            return None
        self._bar_index += 1

        # 1. ingest prices, compute realized returns
        sym_return: dict[str, float] = {}
        for sym, bar in bars.items():
            if hasattr(self.broker, "set_price"):
                self.broker.set_price(sym, bar.price)
            prev = self._last_price.get(sym)
            if prev:
                r = bar.price / prev - 1
                sym_return[sym] = r
                self._returns[sym].append(r)
            self._last_price[sym] = bar.price
            for strat in self.strategies:
                strat.update(sym, bar.price)

        # 2. learn: reward each strategy with its attributed PnL from last bar
        for strat in self.strategies:
            prev_sigs = self._last_signals.get(strat.name, {})
            for sym, r in sym_return.items():
                if sym in prev_sigs:
                    self.bandit.record(strat.name, prev_sigs[sym] * r)

        # 3. combine signals under live bandit weights
        weights = self.bandit.sample_weights()
        combined: dict[str, float] = {}
        for sym in bars:
            sig = sum(weights[s.name] * s.signal(sym) for s in self.strategies)
            combined[sym] = max(-1.0, min(1.0, sig))
        self._last_signals = {
            s.name: {sym: s.signal(sym) for sym in bars} for s in self.strategies}

        # 4. risk: equity tracking, kill switches, sizing
        equity = self.broker.equity()
        self.risk.update_equity(self._bar_index, equity)
        self.journal.mark_equity(self._bar_index, equity)
        if not self.risk.can_trade:
            self.broker.flatten()
            self.journal.log("halt", killed=self.risk.killed,
                             halted_today=self.risk.halted_today, bar=self._bar_index)
            if self.risk.killed:
                raise KillSwitchTripped("risk kill switch tripped - see APEX_KILL_SWITCH file")
            return equity

        # 5. execute: rebalance toward targets
        positions = self.broker.get_positions()
        for sym, sig in combined.items():
            px = self._last_price[sym]
            target_val = self.risk.target_value(sig, self._realized_vol_annual(sym), equity)
            target_val = max(target_val, 0.0)  # crypto: long/flat only (no API shorting)
            current_val = positions.get(sym, 0.0) * px
            delta = target_val - current_val
            if abs(delta) < max(self.cfg.min_trade_value,
                                self.cfg.rebalance_threshold * equity):
                continue
            qty = delta / px
            self.broker.market_order(sym, qty)
            self.journal.log("order", symbol=sym, qty=qty, price=px,
                             signal=round(sig, 3), target_value=round(target_val, 2),
                             weights={k: round(v, 3) for k, v in weights.items()})
        return equity

    def run(self, max_steps: int | None = None) -> None:
        steps = 0
        while max_steps is None or steps < max_steps:
            if self.step() is None:
                break
            steps += 1


class KillSwitchTripped(RuntimeError):
    """Raised when max drawdown is breached; the supervisor will NOT restart."""
