"""Tests for pair order sizing helpers."""

from __future__ import annotations

import pytest

from execution.orders import OrderSide
from execution.sizing import build_pair_leg_orders


def test_build_pair_leg_orders_long_spread_beta_positive() -> None:
    o1, o2 = build_pair_leg_orders(
        t1="AAA",
        t2="BBB",
        beta=1.5,
        notional=10_000.0,
        price1=50.0,
        price2=25.0,
        position=1,
        strategy_tag="t",
    )
    assert o1.side == OrderSide.BUY
    assert o2.side == OrderSide.SHORT
    assert o1.ticker == "AAA"
    assert o2.ticker == "BBB"
    assert o1.quantity == pytest.approx(10_000.0 / 50.0)
    assert o2.quantity == pytest.approx(10_000.0 * 1.5 / 25.0)


def test_build_pair_leg_orders_short_spread_beta_positive() -> None:
    o1, o2 = build_pair_leg_orders(
        t1="AAA",
        t2="BBB",
        beta=1.5,
        notional=10_000.0,
        price1=50.0,
        price2=25.0,
        position=-1,
        strategy_tag="t",
    )
    assert o1.side == OrderSide.SHORT
    assert o2.side == OrderSide.COVER
    assert o1.quantity == pytest.approx(10_000.0 / 50.0)
    assert o2.quantity == pytest.approx(10_000.0 * 1.5 / 25.0)


def test_build_pair_leg_orders_long_spread_beta_negative_flips_leg2_side() -> None:
    o1, o2 = build_pair_leg_orders(
        t1="AAA",
        t2="BBB",
        beta=-0.5,
        notional=10_000.0,
        price1=50.0,
        price2=25.0,
        position=1,
        strategy_tag="t",
    )
    assert o1.side == OrderSide.BUY
    assert o2.side == OrderSide.BUY
    assert o2.quantity == pytest.approx(abs(10_000.0 * -0.5 / 25.0))


def test_build_pair_leg_orders_zero_beta_raises() -> None:
    with pytest.raises(ValueError):
        build_pair_leg_orders(
            t1="AAA",
            t2="BBB",
            beta=0.0,
            notional=10_000.0,
            price1=50.0,
            price2=25.0,
            position=1,
            strategy_tag="t",
        )

