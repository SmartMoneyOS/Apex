"""Backtest harness: runs the exact same TradingEngine against replayed data.

There is deliberately no separate "backtest logic" - the engine that trades
live is the engine that backtests. What you validate is what you deploy.
"""
from __future__ import annotations

import os

from ..brokers.paper import PaperBroker
from ..data.feed import PriceFeed
from ..engine import EngineConfig, KillSwitchTripped, TradingEngine
from ..journal import Journal
from ..learning.bandit import GaussianThompsonBandit
from ..risk.manager import RiskConfig, RiskManager
from ..strategies import DEFAULT_STRATEGIES


def run_backtest(feed: PriceFeed, starting_cash: float = 10_000.0,
                 fee_bps: float = 10.0, slippage_bps: float = 5.0,
                 risk: RiskConfig | None = None, run_dir: str | None = None,
                 seed: int | None = 7, bars_per_day: int = 5760) -> dict:
    broker = PaperBroker(starting_cash, fee_bps=fee_bps, slippage_bps=slippage_bps)
    strategies = [make() for make in DEFAULT_STRATEGIES]
    bandit = GaussianThompsonBandit([s.name for s in strategies], seed=seed)
    risk_cfg = risk or RiskConfig(kill_file="APEX_KILL_SWITCH.backtest",
                                  bars_per_day=bars_per_day)
    journal = Journal(run_dir)
    engine = TradingEngine(broker, feed, strategies, bandit,
                           RiskManager(risk_cfg), journal,
                           EngineConfig(bars_per_day=risk_cfg.bars_per_day))
    killed = False
    try:
        engine.run()
    except KillSwitchTripped:
        killed = True  # in a backtest a kill is a result, not an emergency
    summary = journal.summary()
    summary["killed"] = killed
    summary["bandit"] = bandit.stats()
    summary["fills"] = len(broker.fills)
    journal.close()
    # a backtest kill must not poison later runs (or live trading)
    if os.path.exists(risk_cfg.kill_file):
        os.remove(risk_cfg.kill_file)
    return summary
