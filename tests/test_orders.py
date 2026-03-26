"""Tests for :mod:`execution.orders`."""

from __future__ import annotations

import uuid

from execution.orders import Order, OrderSide, OrderStatus


def test_order_generates_uuid() -> None:
    """Each order gets a UUID4 ``order_id``."""
    o = Order(ticker="MSFT", side=OrderSide.BUY, quantity=10.0)
    uuid.UUID(o.order_id)


def test_order_defaults_and_enums() -> None:
    """Status defaults to PENDING; enums use string values."""
    o = Order(ticker="AAPL", side=OrderSide.SHORT, quantity=1.0, strategy_tag="t1")
    assert o.status == OrderStatus.PENDING
    assert o.side == OrderSide.SHORT
    assert o.side.value == "SHORT"
    assert o.limit_price is None
