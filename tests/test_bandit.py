from apex.learning.bandit import GaussianThompsonBandit


def test_bandit_shifts_capital_to_the_winner():
    b = GaussianThompsonBandit(["winner", "loser"], halflife=50, seed=1)
    for _ in range(300):
        b.record("winner", 0.001)
        b.record("loser", -0.001)
    # average many samples to smooth Thompson noise
    totals = {"winner": 0.0, "loser": 0.0}
    for _ in range(200):
        w = b.sample_weights()
        totals["winner"] += w["winner"]
        totals["loser"] += w["loser"]
    assert totals["winner"] > totals["loser"] * 5


def test_bandit_adapts_when_regime_flips():
    b = GaussianThompsonBandit(["a", "b"], halflife=20, seed=2)
    for _ in range(200):
        b.record("a", 0.001)
        b.record("b", -0.001)
    # regime flip: a starts losing, b starts winning
    for _ in range(200):
        b.record("a", -0.001)
        b.record("b", 0.001)
    totals = {"a": 0.0, "b": 0.0}
    for _ in range(200):
        w = b.sample_weights()
        totals["a"] += w["a"]
        totals["b"] += w["b"]
    assert totals["b"] > totals["a"], "bandit failed to defund the dead strategy"


def test_bandit_stands_down_when_nothing_works():
    b = GaussianThompsonBandit(["a", "b"], halflife=50, seed=3)
    for _ in range(300):
        b.record("a", -0.002)
        b.record("b", -0.002)
    # with both posteriors clearly negative, most samples should be ~zero weight
    zeroish = sum(1 for _ in range(100)
                  if sum(b.sample_weights().values()) < 0.01)
    assert zeroish > 50
