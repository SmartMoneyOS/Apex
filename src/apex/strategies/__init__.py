from .base import Strategy
from .momentum import Momentum
from .mean_reversion import MeanReversion
from .vol_breakout import VolBreakout

DEFAULT_STRATEGIES = [
    lambda: Momentum(fast=20, slow=80),
    lambda: Momentum(fast=60, slow=240),
    lambda: MeanReversion(window=120),
    lambda: VolBreakout(window=200),
]

__all__ = ["Strategy", "Momentum", "MeanReversion", "VolBreakout", "DEFAULT_STRATEGIES"]
