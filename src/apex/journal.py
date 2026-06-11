"""Trade journal: every decision, fill, and equity mark goes to disk.

You can't improve what you don't measure. The journal is what turns trading
into a feedback loop - it feeds the performance review (and you) the data to
see WHICH strategy made or lost each dollar.
"""
from __future__ import annotations

import json
import math
import os
import time


class Journal:
    def __init__(self, run_dir: str | None = None):
        self.run_dir = run_dir or os.path.join("runs", time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(self.run_dir, exist_ok=True)
        self._f = open(os.path.join(self.run_dir, "events.jsonl"), "a")
        self.equity_curve: list[float] = []

    def log(self, kind: str, **fields) -> None:
        self._f.write(json.dumps({"kind": kind, "ts": time.time(), **fields}) + "\n")
        self._f.flush()

    def mark_equity(self, bar_index: int, equity: float) -> None:
        self.equity_curve.append(equity)
        self.log("equity", bar=bar_index, equity=round(equity, 2))

    def summary(self) -> dict:
        eq = self.equity_curve
        if len(eq) < 2:
            return {"bars": len(eq)}
        rets = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq)) if eq[i - 1] > 0]
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        peak, max_dd = eq[0], 0.0
        for v in eq:
            peak = max(peak, v)
            max_dd = max(max_dd, 1 - v / peak)
        return {
            "bars": len(eq),
            "total_return_pct": round(100 * (eq[-1] / eq[0] - 1), 2),
            "max_drawdown_pct": round(100 * max_dd, 2),
            "sharpe_per_bar": round(mean / math.sqrt(var), 4) if var > 0 else None,
            "final_equity": round(eq[-1], 2),
        }

    def close(self) -> None:
        self.log("summary", **self.summary())
        self._f.close()
