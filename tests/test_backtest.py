from apex.backtest.engine import run_backtest
from apex.data.feed import SyntheticFeed


def test_full_engine_runs_end_to_end(tmp_path):
    feed = SyntheticFeed(["BTC-USD"], steps=2000, seed=42)
    summary = run_backtest(feed, run_dir=str(tmp_path / "run"))
    assert summary["bars"] == 2000
    assert summary["final_equity"] > 0
    assert "bandit" in summary
    # the engine must actually have learned something (rewards recorded)
    assert any(s["n_eff"] > 0 for s in summary["bandit"].values())


def test_multi_symbol(tmp_path):
    feed = SyntheticFeed(["BTC-USD", "ETH-USD"], steps=1000, seed=7)
    summary = run_backtest(feed, run_dir=str(tmp_path / "run2"))
    assert summary["bars"] == 1000
