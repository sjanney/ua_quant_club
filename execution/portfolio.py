"""Portfolio state synced from a broker scrape."""

from __future__ import annotations

from typing import Any, Optional, Protocol

import pandas as pd


class _SupportsPortfolioSync(Protocol):
    """Minimal broker interface for :meth:`Portfolio.sync`."""

    def get_portfolio(self) -> dict[str, Any]:
        ...


class Portfolio:
    """Holdings and P&L derived from broker ``get_portfolio()`` results."""

    def __init__(self) -> None:
        self._raw: dict[str, Any] = {}
        self._positions: list[dict[str, Any]] = []

    def sync(self, broker: _SupportsPortfolioSync) -> None:
        """Refresh state from the broker.

        Args:
            broker: Connected broker instance.
        """
        self._raw = broker.get_portfolio()
        self._positions = list(self._raw.get("positions", []))

    def get_position(self, ticker: str) -> Optional[dict[str, Any]]:
        """Return position dict for ``ticker``, or ``None``."""
        for p in self._positions:
            if str(p.get("ticker", "")).upper() == ticker.upper():
                return p
        return None

    def get_unrealized_pnl(self) -> float:
        """Sum of broker-reported unrealized P&L if present."""
        total = 0.0
        for p in self._positions:
            v = p.get("unrealized_pnl")
            if v is not None:
                total += float(v)
        return total

    def get_realized_pnl(self) -> float:
        """Realized P&L from last sync if provided by broker dict."""
        v = self._raw.get("realized_pnl")
        return float(v) if v is not None else 0.0

    def to_dataframe(self) -> pd.DataFrame:
        """Positions as a DataFrame."""
        if not self._positions:
            return pd.DataFrame(columns=["ticker", "quantity", "avg_cost", "market_value"])
        return pd.DataFrame(self._positions)

    def summary(self) -> dict[str, Any]:
        """High-level portfolio stats.

        Returns:
            Keys: ``total_value``, ``cash``, ``num_positions``, ``total_pnl``.
        """
        cash = float(self._raw.get("cash", 0.0))
        tv = float(self._raw.get("total_value", cash))
        n = len(self._positions)
        ur = self.get_unrealized_pnl()
        rr = self.get_realized_pnl()
        return {
            "total_value": tv,
            "cash": cash,
            "num_positions": n,
            "total_pnl": ur + rr,
        }
