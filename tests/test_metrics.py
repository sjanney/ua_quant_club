"""Tests for :mod:`reports.metrics`."""

from __future__ import annotations

import numpy as np
import pandas as pd

from reports.metrics import max_drawdown, profit_factor, sharpe_ratio, win_rate


def test_max_drawdown_known_curve() -> None:
    """Drawdown matches manual peak-to-trough on a simple series."""
    eq = pd.Series([100.0, 110.0, 105.0, 90.0, 95.0])
    mdd = max_drawdown(eq)
    assert mdd < 0
    assert abs(mdd - (90.0 / 110.0 - 1.0)) < 1e-6


def test_sharpe_positive_trending_returns() -> None:
    """Upward-biased daily returns yield positive Sharpe."""
    rng = np.random.default_rng(42)
    r = pd.Series(rng.normal(0.001, 0.01, 500))
    s = sharpe_ratio(r, risk_free=0.0)
    assert s > 0.5


def test_win_rate_and_profit_factor() -> None:
    """Win rate and profit factor match toy trade table."""
    trades = pd.DataFrame(
        {
            "net_pnl": [100.0, -40.0, 50.0, -10.0],
            "hold_days": [1, 2, 3, 4],
        }
    )
    assert abs(win_rate(trades) - 0.5) < 1e-9
    pf = profit_factor(trades)
    assert abs(pf - (150.0 / 50.0)) < 1e-9
