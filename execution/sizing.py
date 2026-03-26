"""Pair order sizing helpers.

This module centralizes the mapping from a pair signal (long/short spread) into
broker `Order` objects with consistent share quantities.
"""

from __future__ import annotations

from typing import Optional, Tuple

from execution.orders import Order, OrderSide


def build_pair_leg_orders(
    *,
    t1: str,
    t2: str,
    beta: float,
    notional: float,
    price1: float,
    price2: float,
    position: int,
    strategy_tag: str = "",
    pair_id: Optional[str] = None,
    notes: str = "",
) -> Tuple[Order, Order]:
    """Build two broker orders representing one pair-spread position.

    Conventions:
    - `position=1` means long spread => leg1 `BUY`, leg2 `SHORT` (when beta>0).
    - `position=-1` means short spread => leg1 `SHORT`, leg2 `COVER` (when beta>0).

    If `beta` is negative, the leg2 order side is flipped to maintain the intended
    hedge exposure direction.
    """
    if position not in (1, -1):
        raise ValueError(f"position must be 1 or -1, got {position!r}")
    if notional <= 0:
        raise ValueError(f"notional must be > 0, got {notional!r}")
    if price1 <= 0 or price2 <= 0:
        raise ValueError(f"prices must be > 0, got price1={price1!r}, price2={price2!r}")

    qty1 = float(notional) / float(price1)
    if qty1 <= 0:
        raise ValueError(f"computed qty1 must be > 0, got {qty1!r}")

    # We use abs(quantity) because `Order.quantity` is defined as a positive number;
    # net exposure direction is represented via `OrderSide`.
    qty2_signed = float(notional) * float(beta) / float(price2)
    if qty2_signed == 0:
        raise ValueError("beta is 0, resulting in a zero-size hedge leg2 order")
    qty2 = abs(qty2_signed)

    # Leg1 exposure direction comes directly from `position`.
    side1 = OrderSide.BUY if position == 1 else OrderSide.SHORT

    # Leg2 net exposure is -position * beta (consistent with `spread = p1 - beta*p2`).
    leg2_signed_exposure = -float(position) * float(beta)
    if leg2_signed_exposure < 0:
        # Net short leg2
        side2 = OrderSide.SHORT
    else:
        # Net long leg2
        side2 = OrderSide.BUY if position == 1 else OrderSide.COVER

    prefix = f"pair_id={pair_id}|" if pair_id else ""
    extra = f"|{notes}" if notes else ""
    leg_notes = f"{prefix}position={position}|beta={beta:.6f}{extra}"

    o1 = Order(
        ticker=t1,
        side=side1,
        quantity=qty1,
        strategy_tag=strategy_tag,
        notes=f"leg1 {leg_notes}",
    )
    o2 = Order(
        ticker=t2,
        side=side2,
        quantity=qty2,
        strategy_tag=strategy_tag,
        notes=f"leg2 {leg_notes}",
    )
    return o1, o2

