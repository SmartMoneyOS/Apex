"""Apex CLI and crash supervisor.

    apex backtest --synthetic --steps 5000     # prove the plumbing
    apex backtest --csv data/btc_15s.csv       # validate on real history
    apex paper                                  # live prices, fake money
    apex live --i-understand-the-risks          # real money (crypto only)

The supervisor restarts Apex after a crash with exponential backoff - but it
will NEVER restart past the risk kill switch. A drawdown halt requires a
human to delete the APEX_KILL_SWITCH file. Resilience must not be allowed to
override risk management.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import yaml

from .backtest.engine import run_backtest
from .brokers.paper import PaperBroker
from .data.feed import LiveFeed, ReplayFeed, SyntheticFeed
from .engine import EngineConfig, KillSwitchTripped, TradingEngine
from .journal import Journal
from .learning.bandit import GaussianThompsonBandit
from .risk.manager import KILL_FILE, RiskConfig, RiskManager
from .strategies import DEFAULT_STRATEGIES


def load_config(path: str = "config/config.yaml") -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _risk_config(cfg: dict) -> RiskConfig:
    r = cfg.get("risk", {})
    e = cfg.get("engine", {})
    return RiskConfig(
        max_position_frac=r.get("max_position_frac", 0.5),
        target_vol_annual=r.get("target_vol_annual", 0.35),
        daily_loss_limit_pct=r.get("daily_loss_limit_pct", 3.0),
        max_drawdown_pct=r.get("max_drawdown_pct", 10.0),
        bars_per_day=e.get("bars_per_day", 5760),
    )


def _build_live_engine(cfg: dict, live: bool) -> TradingEngine:
    symbols = cfg.get("symbols", ["BTC-USD"])
    e = cfg.get("engine", {})
    if live:
        from .brokers.robinhood_crypto import RobinhoodCryptoBroker
        rh = cfg.get("robinhood", {})
        broker = RobinhoodCryptoBroker(rh.get("api_key") or None,
                                       rh.get("private_key_b64") or None)
        quote_broker = broker
    else:
        p = cfg.get("paper", {})
        broker = PaperBroker(p.get("starting_cash", 10_000.0),
                             fee_bps=p.get("fee_bps", 10),
                             slippage_bps=p.get("slippage_bps", 5))
        # paper mode still needs live quotes; use the public crypto market data
        from .brokers.robinhood_crypto import RobinhoodCryptoBroker
        try:
            quote_broker = RobinhoodCryptoBroker()
        except (ValueError, ImportError):
            print("No Robinhood credentials/pynacl - paper mode falling back to "
                  "synthetic prices. Add creds for real-quote paper trading.")
            quote_broker = None

    if quote_broker is not None:
        feed = LiveFeed(quote_broker, symbols, e.get("poll_seconds", 15))
    else:
        feed = SyntheticFeed(symbols, steps=10**9)

    strategies = [make() for make in DEFAULT_STRATEGIES]
    learn = cfg.get("learning", {})
    bandit = GaussianThompsonBandit([s.name for s in strategies],
                                    halflife=learn.get("reward_halflife", 200),
                                    min_weight=learn.get("min_weight", 0.0))
    return TradingEngine(
        broker, feed, strategies, bandit, RiskManager(_risk_config(cfg)), Journal(),
        EngineConfig(bars_per_day=e.get("bars_per_day", 5760),
                     min_trade_value=e.get("min_trade_value", 5.0),
                     rebalance_threshold=e.get("rebalance_threshold", 0.02)))


def supervise(run_fn, max_restarts: int = 5) -> int:
    """Restart on crash with exponential backoff. Never restart past a kill."""
    restarts = 0
    while True:
        if os.path.exists(KILL_FILE):
            print(f"Kill switch present ({KILL_FILE}); refusing to start. "
                  "Review the journal, then delete the file to re-arm.")
            return 2
        try:
            run_fn()
            return 0
        except KillSwitchTripped as e:
            print(f"HALTED BY RISK: {e}")
            return 2
        except KeyboardInterrupt:
            print("Stopped by user.")
            return 0
        except Exception as e:  # noqa: BLE001 - supervisor must catch everything
            restarts += 1
            if restarts > max_restarts:
                print(f"Crashed {restarts} times; giving up. Last error: {e!r}")
                return 1
            delay = 2 ** restarts
            print(f"Crash #{restarts}: {e!r} - restarting in {delay}s")
            time.sleep(delay)


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="apex", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    bt = sub.add_parser("backtest", help="run the engine against history")
    bt.add_argument("--csv", help="CSV with columns ts,symbol,price")
    bt.add_argument("--synthetic", action="store_true")
    bt.add_argument("--steps", type=int, default=5000)
    bt.add_argument("--seed", type=int, default=7)
    bt.add_argument("--bars-per-day", type=int, default=5760,
                    help="bars per day in the data (24 for hourly, 5760 for 15s)")

    sub.add_parser("paper", help="live quotes, simulated money (default mode)")

    lv = sub.add_parser("live", help="REAL MONEY - Robinhood crypto")
    lv.add_argument("--i-understand-the-risks", action="store_true")

    args = parser.parse_args(argv)
    cfg = load_config()

    if args.cmd == "backtest":
        if args.csv:
            feed = ReplayFeed(args.csv)
        elif args.synthetic:
            feed = SyntheticFeed(cfg.get("symbols", ["BTC-USD"]),
                                 steps=args.steps, seed=args.seed)
        else:
            bt.error("need --csv or --synthetic")
        print(json.dumps(run_backtest(feed, seed=args.seed,
                                      bars_per_day=args.bars_per_day), indent=2))
        return 0

    if args.cmd == "live" and not args.i_understand_the_risks:
        print("Live trading uses real money and can lose all of it.\n"
              "Run paper mode for at least 30 days first. Then re-run with\n"
              "  apex live --i-understand-the-risks")
        return 1

    engine = _build_live_engine(cfg, live=(args.cmd == "live"))
    return supervise(engine.run)


if __name__ == "__main__":
    sys.exit(cli())
