import os

from apex.risk.manager import RiskConfig, RiskManager


def _cfg(tmp_path, **kw):
    return RiskConfig(kill_file=str(tmp_path / "KILL"), bars_per_day=100, **kw)


def test_daily_loss_halts_but_resets_next_day(tmp_path):
    rm = RiskManager(_cfg(tmp_path, daily_loss_limit_pct=3.0, max_drawdown_pct=50.0))
    rm.update_equity(1, 10_000)
    assert rm.can_trade
    rm.update_equity(2, 9_600)  # -4% intraday
    assert not rm.can_trade and not rm.killed
    rm.update_equity(101, 9_600)  # next "day"
    assert rm.can_trade


def test_drawdown_kill_is_permanent_and_on_disk(tmp_path):
    cfg = _cfg(tmp_path, max_drawdown_pct=10.0)
    rm = RiskManager(cfg)
    rm.update_equity(1, 10_000)
    rm.update_equity(2, 8_900)  # -11% from peak
    assert rm.killed and not rm.can_trade
    assert os.path.exists(cfg.kill_file)
    # a fresh manager (i.e. after a process restart) must stay killed
    rm2 = RiskManager(cfg)
    assert rm2.killed, "restart must not bypass the kill switch"


def test_vol_targeting_shrinks_size_in_wild_markets(tmp_path):
    rm = RiskManager(_cfg(tmp_path, target_vol_annual=0.35, max_position_frac=0.5))
    rm.update_equity(1, 10_000)
    calm = rm.target_value(1.0, realized_vol_annual=0.20, equity=10_000)
    wild = rm.target_value(1.0, realized_vol_annual=1.40, equity=10_000)
    assert calm == 5_000  # capped at max_position_frac
    assert wild == 2_500  # 0.35/1.40 = 25% of equity
