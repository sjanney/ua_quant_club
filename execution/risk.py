"""Pre-trade validation helpers.

These checks are intentionally lightweight so they work in both `dry_run` and
paper/live modes without requiring live quote data.
"""

from __future__ import annotations

import re
from typing import Optional

from execution.orders import Order, OrderSide
from logging_.trade_logger import TradeLogger
from utils.config import CONFIG


class PreTradeCheckError(ValueError):
    """Raised when an order fails pre-trade validation."""


_PAIR_ID_RE = re.compile(r"pair_id=([^|]+)")
_POSITION_RE = re.compile(r"position=(-?\d+)")
_BETA_RE = re.compile(r"beta=(-?\d+(?:\.\d+)?)")


def _extract_pair_id(notes: str) -> Optional[str]:
    if not notes:
        return None
    m = _PAIR_ID_RE.search(notes)
    return m.group(1).strip() if m else None


def _extract_position(notes: str) -> Optional[int]:
    if not notes:
        return None
    m = _POSITION_RE.search(notes)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _extract_beta(notes: str) -> Optional[float]:
    if not notes:
        return None
    m = _BETA_RE.search(notes)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _extract_leg_label(notes: str) -> Optional[str]:
    """Return `leg1` / `leg2` if present in notes."""
    if not notes:
        return None
    if "leg1 " in notes or notes.startswith("leg1"):
        return "leg1"
    if "leg2 " in notes or notes.startswith("leg2"):
        return "leg2"
    return None


def run_pretrade_checks(order: Order, trade_logger: TradeLogger) -> None:
    """Run lightweight validations and duplicate suppression.

    The duplicate-suppression guard is only applied for `leg1` orders because
    entries for a single pair are submitted as two separate orders (leg1/leg2).
    """
    risk_cfg = CONFIG.get("risk", {}) if isinstance(CONFIG, dict) else {}
    max_shares_per_leg = float(risk_cfg.get("max_shares_per_leg", 1_000_000.0))
    notional_per_trade = float(
        CONFIG.get("backtest", {}).get("notional_per_trade", 10_000.0)
    )
    max_notional_factor = float(risk_cfg.get("max_notional_factor", 1.25))

    if order.quantity is None or float(order.quantity) <= 0:
        raise PreTradeCheckError(f"Order quantity must be > 0, got {order.quantity!r}")

    if float(order.quantity) > max_shares_per_leg:
        raise PreTradeCheckError(
            f"Order quantity {order.quantity!r} exceeds max_shares_per_leg={max_shares_per_leg}"
        )

    # Notional consistency: only possible if we have a limit price to estimate.
    if order.limit_price is not None:
        implied_leg_notional = float(order.quantity) * float(order.limit_price)

        leg_label = _extract_leg_label(order.notes)
        beta = _extract_beta(order.notes)
        if leg_label == "leg1":
            expected_notional = notional_per_trade
        elif leg_label == "leg2" and beta is not None:
            expected_notional = notional_per_trade * abs(beta)
        else:
            expected_notional = notional_per_trade

        if expected_notional > 0 and implied_leg_notional > expected_notional * max_notional_factor:
            raise PreTradeCheckError(
                f"Implied notional {implied_leg_notional:.2f} exceeds "
                f"expected {expected_notional:.2f} (factor {max_notional_factor})."
            )

    # Duplicate suppression: only for the leg1 order.
    leg_label = _extract_leg_label(order.notes)
    if leg_label != "leg1":
        return

    pair_id = _extract_pair_id(order.notes)
    position = _extract_position(order.notes)
    if not pair_id or position not in (1, -1):
        return

    expected_leg1_side = OrderSide.BUY if position == 1 else OrderSide.SHORT

    existing = trade_logger.get_trades(strategy_tag=order.strategy_tag)
    if existing is None or existing.empty:
        return

    # `notes` contains `pair_id=...` and also an `order_id=<uuid>|...` prefix.
    mask = (
        (existing["status"] == "FILLED")
        & (existing["side"] == expected_leg1_side.value)
        & existing["notes"].astype(str).str.contains(f"pair_id={pair_id}")
    )
    if bool(mask.any()):
        raise PreTradeCheckError(
            f"Duplicate pair entry blocked: pair_id={pair_id!r} already has a filled leg1."
        )

