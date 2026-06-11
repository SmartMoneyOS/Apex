"""Replay the committed real BTC sample (Crypto.com exchange, hourly closes)
through the full engine. 50 bars is too short for any strategy to activate -
this guards data-format integrity and the replay path, not profitability."""
import os

from apex.backtest.engine import run_backtest
from apex.data.feed import ReplayFeed

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "data", "samples",
                      "btc_recent_1h.csv")


def test_real_sample_replays_cleanly(tmp_path):
    feed = ReplayFeed(SAMPLE)
    summary = run_backtest(feed, run_dir=str(tmp_path / "run"), bars_per_day=24)
    assert summary["bars"] == 50
    # too few bars for warmup -> the engine must hold cash, not gamble
    assert summary["fills"] == 0
    assert summary["final_equity"] == 10_000.0


def test_sample_prices_are_sane():
    feed = ReplayFeed(SAMPLE)
    prices = []
    while (bars := feed.next_bars()) is not None:
        prices.append(bars["BTC-USD"].price)
    assert len(prices) == 50
    assert all(p > 0 for p in prices)
    # consecutive hourly moves over 10% would mean corrupted data
    assert all(abs(b / a - 1) < 0.10 for a, b in zip(prices, prices[1:]))
