"""Paper trading execution via Investopedia simulator."""

from __future__ import annotations

from typing import Any

from execution.orders import Order, OrderSide, OrderStatus
from execution.portfolio import Portfolio

__all__ = [
    "InvestopediaBroker",
    "Order",
    "OrderSide",
    "OrderStatus",
    "Portfolio",
]


def __getattr__(name: str) -> Any:
    """Lazy-load :class:`InvestopediaBroker` so ``playwright`` is optional until used."""
    if name == "InvestopediaBroker":
        from execution.broker import InvestopediaBroker

        return InvestopediaBroker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
