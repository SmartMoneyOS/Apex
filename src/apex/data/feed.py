"""Price feeds: replayable history, synthetic data, and live broker quotes."""
from __future__ import annotations

import csv
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Bar:
    ts: float
    symbol: str
    price: float


class PriceFeed(ABC):
    """Yields one dict of {symbol: Bar} per step, or None when exhausted."""

    @abstractmethod
    def next_bars(self) -> dict[str, Bar] | None: ...


class ReplayFeed(PriceFeed):
    """Replays historical bars from a CSV with columns: ts,symbol,price."""

    def __init__(self, path: str):
        rows: dict[float, dict[str, Bar]] = {}
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                ts = float(row["ts"])
                bar = Bar(ts=ts, symbol=row["symbol"], price=float(row["price"]))
                rows.setdefault(ts, {})[bar.symbol] = bar
        self._steps = [rows[ts] for ts in sorted(rows)]
        self._i = 0

    def next_bars(self) -> dict[str, Bar] | None:
        if self._i >= len(self._steps):
            return None
        bars = self._steps[self._i]
        self._i += 1
        return bars


class SyntheticFeed(PriceFeed):
    """Geometric random walk with regime shifts. For demos and tests only -
    profits against synthetic data prove the plumbing works, not the strategy."""

    def __init__(self, symbols: list[str], steps: int, start_price: float = 50_000.0,
                 vol: float = 0.002, seed: int | None = None):
        self.symbols = symbols
        self.steps = steps
        self.vol = vol
        self._rng = random.Random(seed)
        self._prices = {s: start_price for s in symbols}
        self._drift = {s: 0.0 for s in symbols}
        self._i = 0

    def next_bars(self) -> dict[str, Bar] | None:
        if self._i >= self.steps:
            return None
        self._i += 1
        bars = {}
        for s in self.symbols:
            if self._rng.random() < 0.005:  # occasional regime shift
                self._drift[s] = self._rng.uniform(-0.0005, 0.0005)
            self._prices[s] *= 1.0 + self._drift[s] + self._rng.gauss(0, self.vol)
            bars[s] = Bar(ts=float(self._i), symbol=s, price=self._prices[s])
        return bars


class LiveFeed(PriceFeed):
    """Polls a broker for live quotes at a fixed interval."""

    def __init__(self, broker, symbols: list[str], poll_seconds: float = 15.0):
        self.broker = broker
        self.symbols = symbols
        self.poll_seconds = poll_seconds
        self._last = 0.0

    def next_bars(self) -> dict[str, Bar] | None:
        wait = self._last + self.poll_seconds - time.time()
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        return {s: Bar(ts=self._last, symbol=s, price=self.broker.get_price(s))
                for s in self.symbols}
