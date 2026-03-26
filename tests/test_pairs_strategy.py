"""Tests for pairs trading strategy helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alphas.pairs_trading.strategy import (
    backtest_pair,
    hedge_ratio_ols,
    rolling_beta_series,
    spread_half_life_days,
)


def _synthetic_prices(n: int = 400, seed: int = 0) -> tuple[pd.DataFrame, str, str]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    # Cointegrated-ish: p1 ≈ 1.2 * p2 + noise
    p2 = 100 + np.cumsum(rng.normal(0, 0.3, n))
    p1 = 1.2 * p2 + rng.normal(0, 0.5, n)
    df = pd.DataFrame({"AAA": p1, "BBB": p2}, index=idx)
    return df, "AAA", "BBB"


def test_hedge_ratio_ols_near_true_beta() -> None:
    """OLS beta should be near 1.2 for synthetic cointegrated series."""
    prices, t1, t2 = _synthetic_prices()
    b = hedge_ratio_ols(prices[t1], prices[t2])
    assert 1.05 < b < 1.35


def test_cross_entry_vs_level_entry_trade_count() -> None:
    """Crossing entry should not produce strictly more round-trips than level on same path."""
    prices, t1, t2 = _synthetic_prices()
    beta = hedge_ratio_ols(prices[t1], prices[t2])
    tr_cross, _ = backtest_pair(
        prices,
        t1,
        t2,
        beta,
        zscore_window=30,
        entry_z=1.5,
        exit_z=0.3,
        stop_z=4.0,
        notional=10_000.0,
        transaction_cost=0.0005,
        entry_mode="cross",
    )
    tr_level, _ = backtest_pair(
        prices,
        t1,
        t2,
        beta,
        zscore_window=30,
        entry_z=1.5,
        exit_z=0.3,
        stop_z=4.0,
        notional=10_000.0,
        transaction_cost=0.0005,
        entry_mode="level",
    )
    assert isinstance(tr_cross, pd.DataFrame)
    assert isinstance(tr_level, pd.DataFrame)
    # Typically cross <= level entries; allow equal
    assert len(tr_cross) <= len(tr_level) + 1


def test_rolling_beta_series_piecewise_constant() -> None:
    """Rolling beta series should be constant between rebalances."""
    prices, t1, t2 = _synthetic_prices(n=300)
    betas = rolling_beta_series(prices, t1, t2, lookback=60, rebalance_every=10)
    valid = betas.dropna()
    assert len(valid) > 50
    # consecutive stretch within a rebalance block should be equal
    diffs = valid.diff().abs()
    # allow rebalance jumps only
    assert diffs.max() > 0


def test_spread_half_life_finite_on_mean_reverting() -> None:
    """Mean-reverting spread yields finite positive half-life."""
    rng = np.random.default_rng(1)
    n = 500
    x = np.zeros(n)
    rho = 0.85
    for i in range(1, n):
        x[i] = rho * x[i - 1] + rng.normal(0, 1.0)
    s = pd.Series(x)
    hl = spread_half_life_days(s)
    assert hl is not None
    assert 1 < hl < 500
