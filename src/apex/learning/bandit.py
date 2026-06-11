"""Real-time capital allocation across strategies via Thompson sampling.

This is the "learn, adapt, improve in real time" core. Every bar, each
strategy's hypothetical PnL (its previous signal x the realized return) is fed
in as a reward. The bandit keeps exponentially-decayed posteriors so it adapts
when regimes change: a strategy that minted money last month but bleeds today
gets defunded within hours, and capital flows to whatever is currently working.
Thompson sampling (sampling from the posterior instead of picking the argmax)
keeps a controlled amount of exploration so a temporarily-cold strategy can
win its allocation back when conditions turn.
"""
from __future__ import annotations

import math
import random


class GaussianThompsonBandit:
    def __init__(self, arms: list[str], halflife: float = 200.0,
                 min_weight: float = 0.0, seed: int | None = None):
        self.arms = list(arms)
        self.decay = 0.5 ** (1.0 / halflife)
        self.min_weight = min_weight
        self._rng = random.Random(seed)
        # exponentially-decayed sufficient statistics per arm
        self._n = {a: 0.0 for a in arms}      # effective sample count
        self._sum = {a: 0.0 for a in arms}    # decayed sum of rewards
        self._sumsq = {a: 0.0 for a in arms}  # decayed sum of squared rewards

    def record(self, arm: str, reward: float) -> None:
        self._n[arm] = self._n[arm] * self.decay + 1.0
        self._sum[arm] = self._sum[arm] * self.decay + reward
        self._sumsq[arm] = self._sumsq[arm] * self.decay + reward * reward

    def _posterior(self, arm: str) -> tuple[float, float]:
        n = self._n[arm]
        if n < 2.0:
            return 0.0, 1.0  # uninformed prior: wide, zero-mean
        mean = self._sum[arm] / n
        var = max(self._sumsq[arm] / n - mean * mean, 1e-12)
        return mean, math.sqrt(var / n)  # std error of the mean

    def sample_weights(self) -> dict[str, float]:
        """Draw one posterior sample per arm; weight = positive part, normalized.
        Arms sampling negative (currently losing money) get min_weight."""
        draws = {}
        for a in self.arms:
            mu, se = self._posterior(a)
            draws[a] = self._rng.gauss(mu, se)
        pos = {a: max(d, 0.0) for a, d in draws.items()}
        total = sum(pos.values())
        if total <= 0:
            # nothing has a positive edge estimate -> stand down (all min_weight)
            return {a: self.min_weight for a in self.arms}
        return {a: max(p / total, self.min_weight) for a, p in pos.items()}

    def stats(self) -> dict[str, dict[str, float]]:
        return {a: {"n_eff": round(self._n[a], 1),
                    "mean": self._posterior(a)[0]} for a in self.arms}
