import pytest

from apex.brokers.paper import PaperBroker


def test_buy_and_mark_to_market():
    b = PaperBroker(10_000, fee_bps=0, slippage_bps=0)
    b.set_price("BTC-USD", 100.0)
    b.market_order("BTC-USD", 10)
    assert b.get_cash() == pytest.approx(9_000)
    b.set_price("BTC-USD", 110.0)
    assert b.equity() == pytest.approx(10_100)


def test_fees_and_slippage_cost_money():
    b = PaperBroker(10_000, fee_bps=10, slippage_bps=5)
    b.set_price("BTC-USD", 100.0)
    b.market_order("BTC-USD", 10)   # round trip
    b.market_order("BTC-USD", -10)
    assert b.get_positions() == {}
    assert b.equity() < 10_000  # the spread is never free


def test_flatten():
    b = PaperBroker(10_000, fee_bps=0, slippage_bps=0)
    b.set_price("BTC-USD", 100.0)
    b.market_order("BTC-USD", 5)
    b.flatten()
    assert b.get_positions() == {}
    assert b.equity() == pytest.approx(10_000)
