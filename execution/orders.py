"""Order types for paper trading."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4


class OrderSide(Enum):
    """Direction of an order."""

    BUY = "BUY"
    SELL = "SELL"
    SHORT = "SHORT"
    COVER = "COVER"


class OrderStatus(Enum):
    """Lifecycle state of an order."""

    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class Order:
    """Single broker order with optional limit price and fill metadata.

    Attributes:
        ticker: Equity symbol.
        side: Buy, sell, short, or cover.
        quantity: Number of shares (positive).
        limit_price: Limit price, or ``None`` for market.
        strategy_tag: Label for attribution in logs and reports.
        order_id: Unique id (UUID4 string).
        status: Current status.
        filled_price: Executed price when filled.
        filled_at: Execution timestamp when filled.
        notes: Free-form notes (e.g. pair id, risk flags).
    """

    ticker: str
    side: OrderSide
    quantity: float
    limit_price: Optional[float] = None
    strategy_tag: str = ""
    order_id: str = field(default_factory=lambda: str(uuid4()))
    status: OrderStatus = OrderStatus.PENDING
    filled_price: Optional[float] = None
    filled_at: Optional[datetime] = None
    notes: str = ""
