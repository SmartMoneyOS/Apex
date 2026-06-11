"""Backtest harness: runs the exact same TradingEngine against replayed data.

There is deliberately no separate "backtest logic" - the engine that trades
live is the engine that backtests. What you validate is what you deploy.
"""
from __future__ import annotations

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
                 seed: int | None = 7) -> dict:
    broker = PaperBroker(starting_cash, fee_bps=fee_bps, slippage_bps=slippage_bps)
    strategies = [make() for make in DEFAULT_STRATEGIES]
    bandit = GaussianThompsonBandit([s.name for s in strategies], seed=seed)
    risk_cfg = risk or RiskConfig(kill_file="APEX_KILL_SWITCH.backtest")
    journal = Journal(run_dir)
    engine = TradingEngine(broker, feed, strategies, bandit,
                           RiskManager(risk_cfg), journal,
                           EngineConfig(bars_per_day=risk_cfg.bars_per_day))
    try:
        engine.run()
    except KillSwitchTripped:
        pass  # in a backtest a kill is a result, not an emergency
    summary = journal.summary()
    summary["bandit"] = bandit.stats()
    summary["fills"] = len(broker.fills)
    journal.close()
    return summary
