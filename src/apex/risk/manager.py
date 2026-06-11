"""Risk management: volatility-targeted sizing plus hard kill switches.

The single biggest reason retail algos die is not bad signals - it's sizing
and the absence of a stop condition. Apex enforces three layers:

1. Vol targeting   - position size shrinks automatically when the market gets
                     wild, so one violent candle can't end the account.
2. Daily loss halt - down `daily_loss_limit_pct` on the day: flatten, stop
                     trading until the next session.
3. Drawdown kill   - down `max_drawdown_pct` from peak equity: flatten and
                     write a kill file to disk. The supervisor REFUSES to
                     restart while the kill file exists, so a crash-restart
                     loop can never override a risk stop. A human must delete
                     the file to re-arm the system.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass

KILL_FILE = "APEX_KILL_SWITCH"


@dataclass
class RiskConfig:
    max_position_frac: float = 0.5
    target_vol_annual: float = 0.35
    daily_loss_limit_pct: float = 3.0
    max_drawdown_pct: float = 10.0
    bars_per_day: int = 5760
    kill_file: str = KILL_FILE


class RiskManager:
    def __init__(self, cfg: RiskConfig):
        self.cfg = cfg
        self.peak_equity: float | None = None
        self.day_start_equity: float | None = None
        self._day_index: int | None = None
        self.halted_today = False
        self.killed = os.path.exists(cfg.kill_file)

    # -- equity tracking ----------------------------------------------------
    def update_equity(self, bar_index: int, equity: float) -> None:
        day = bar_index // self.cfg.bars_per_day
        if day != self._day_index:
            self._day_index = day
            self.day_start_equity = equity
            self.halted_today = False
        self.peak_equity = equity if self.peak_equity is None else max(self.peak_equity, equity)

        if self.day_start_equity and equity < self.day_start_equity * (
                1 - self.cfg.daily_loss_limit_pct / 100):
            self.halted_today = True
        if self.peak_equity and equity < self.peak_equity * (
                1 - self.cfg.max_drawdown_pct / 100):
            self.kill(f"drawdown {self._dd(equity):.1f}% breached "
                      f"{self.cfg.max_drawdown_pct}% limit at equity {equity:.2f}")

    def _dd(self, equity: float) -> float:
        return 100 * (1 - equity / self.peak_equity) if self.peak_equity else 0.0

    def kill(self, reason: str) -> None:
        self.killed = True
        with open(self.cfg.kill_file, "w") as f:
            f.write(reason + "\n")

    @property
    def can_trade(self) -> bool:
        return not (self.killed or self.halted_today)

    # -- sizing --------------------------------------------------------------
    def target_value(self, signal: float, realized_vol_annual: float, equity: float) -> float:
        """Convert a conviction signal into a target position value (USD)."""
        if not self.can_trade or math.isnan(realized_vol_annual):
            return 0.0
        if realized_vol_annual <= 0:
            frac = self.cfg.max_position_frac
        else:
            frac = min(self.cfg.max_position_frac,
                       self.cfg.target_vol_annual / realized_vol_annual)
        return signal * frac * equity
