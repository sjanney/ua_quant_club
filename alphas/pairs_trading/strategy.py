"""Pairs trading: Engle–Granger cointegration, OLS hedge ratio, z-score signals."""

from __future__ import annotations

from itertools import combinations
from typing import Any, Mapping

import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant
from statsmodels.tsa.stattools import adfuller, coint


def hedge_ratio_ols(s1: pd.Series, s2: pd.Series) -> float:
    """OLS hedge ratio: regress leg1 on leg2 (with intercept)."""
    s1 = s1.dropna()
    s2 = s2.dropna()
    idx = s1.index.intersection(s2.index)
    if len(idx) < 30:
        return 1.0
    y = s1.loc[idx].values
    x = add_constant(s2.loc[idx].values)
    model = OLS(y, x).fit()
    return float(model.params[1])


def spread_half_life_days(spread: pd.Series) -> float | None:
    """AR(1) half-life of the spread in days; ``None`` if not stable mean-reversion."""
    y = spread.dropna()
    if len(y) < 60:
        return None
    y0 = y.iloc[1:].values
    y1 = y.shift(1).iloc[1:].values
    x = add_constant(y1)
    try:
        model = OLS(y0, x).fit()
        rho = float(model.params[1])
    except (ValueError, FloatingPointError):
        return None
    if rho <= 0 or rho >= 1:
        return None
    return float(-np.log(2.0) / np.log(rho))


def run_coint_scan(
    prices: pd.DataFrame,
    universe: Mapping[str, list[str]],
    coint_p_threshold: float,
    *,
    n_total_tests: int | None = None,
    max_half_life_days: float | None = None,
) -> pd.DataFrame:
    """Run Engle–Granger tests on all same-sector pairs.

    Optional Bonferroni adjustment: if ``n_total_tests`` is set, require
    ``p < coint_p_threshold / n_total_tests`` for the cointegration test.

    If ``max_half_life_days`` is set, adds ``half_life_days`` and sets
    ``cointegrated`` False when half-life exceeds the cap (computed spreads only).
    """
    alpha = float(coint_p_threshold)
    if n_total_tests is not None and n_total_tests > 0:
        alpha = alpha / float(n_total_tests)

    results: list[dict[str, Any]] = []
    for sector, tickers in universe.items():
        valid = [t for t in tickers if t in prices.columns]
        for t1, t2 in combinations(valid, 2):
            s1, s2 = prices[t1].dropna(), prices[t2].dropna()
            idx = s1.index.intersection(s2.index)
            if len(idx) < 200:
                continue
            _score, pval, _crit = coint(s1.loc[idx], s2.loc[idx])
            beta = hedge_ratio_ols(s1.loc[idx], s2.loc[idx])
            spread = s1.loc[idx] - beta * s2.loc[idx]
            adf_p = float(adfuller(spread)[1])
            hl = spread_half_life_days(spread)
            coint_ok = pval < alpha and adf_p < alpha
            if max_half_life_days is not None and hl is not None:
                if hl > float(max_half_life_days):
                    coint_ok = False

            results.append(
                {
                    "sector": sector,
                    "ticker1": t1,
                    "ticker2": t2,
                    "coint_p": round(pval, 4),
                    "adf_p": round(adf_p, 4),
                    "beta": round(beta, 4),
                    "half_life_days": round(hl, 2) if hl is not None else np.nan,
                    "cointegrated": coint_ok,
                }
            )
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values("coint_p")
    return df


def compute_spread(
    prices: pd.DataFrame,
    t1: str,
    t2: str,
    beta: float,
    zscore_window: int,
) -> tuple[pd.Series, pd.Series]:
    """Compute dollar spread and rolling z-score of the spread."""
    spread = prices[t1] - beta * prices[t2]
    mean = spread.rolling(zscore_window).mean()
    std = spread.rolling(zscore_window).std()
    zscore = (spread - mean) / std
    return spread, zscore


def _build_dynamic_spread_zscore(
    p1: pd.Series,
    p2: pd.Series,
    beta_series: pd.Series,
    zscore_window: int,
) -> tuple[pd.Series, pd.Series]:
    spread = p1 - beta_series * p2
    mean = spread.rolling(zscore_window).mean()
    std = spread.rolling(zscore_window).std()
    zscore = ((spread - mean) / std).dropna()
    return spread, zscore


def rolling_beta_series(
    prices: pd.DataFrame,
    t1: str,
    t2: str,
    *,
    lookback: int,
    rebalance_every: int,
) -> pd.Series:
    """Piecewise-constant OLS beta, re-estimated every ``rebalance_every`` rows (past-only windows)."""
    p1, p2 = prices[t1], prices[t2]
    idx = prices.index
    n = len(idx)
    betas = np.full(n, np.nan, dtype=float)
    last_reb = -1
    for i in range(lookback, n):
        if (last_reb < 0) or ((i - last_reb) >= rebalance_every):
            w = slice(i - lookback, i)
            betas[i] = hedge_ratio_ols(p1.iloc[w], p2.iloc[w])
            last_reb = i
        else:
            betas[i] = betas[i - 1]
    return pd.Series(betas, index=idx).ffill()


def backtest_pair(
    prices: pd.DataFrame,
    t1: str,
    t2: str,
    beta: float,
    *,
    zscore_window: int,
    entry_z: float,
    exit_z: float,
    stop_z: float,
    notional: float,
    transaction_cost: float,
    entry_mode: str = "cross",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Backtest one pair using z-score entry / exit / stop rules.

    ``entry_mode``:
        - ``cross``: enter when z *crosses* beyond ±entry_z (fewer spurious entries).
        - ``level``: enter whenever z is beyond ±entry_z while flat (legacy).
    """
    p1, p2 = prices[t1], prices[t2]
    spread = p1 - beta * p2
    mean = spread.rolling(zscore_window).mean()
    std = spread.rolling(zscore_window).std()
    zscore = ((spread - mean) / std).dropna()

    p1 = p1.reindex(zscore.index)
    p2 = p2.reindex(zscore.index)

    position = 0
    entry_z_val = 0.0
    entry_p1 = entry_p2 = 0.0
    entry_beta = beta
    entry_date = zscore.index[0]
    trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    cum_pnl = 0.0
    cross = entry_mode.lower() == "cross"

    for i in range(len(zscore)):
        date = zscore.index[i]
        z = float(zscore.iloc[i])
        z_prev = float(zscore.iloc[i - 1]) if i > 0 else np.nan
        cp1 = float(p1.iloc[i])
        cp2 = float(p2.iloc[i])

        if position == 0:
            long_signal = False
            short_signal = False
            if cross:
                if i == 0 or np.isnan(z_prev):
                    pass
                else:
                    long_signal = z_prev >= -entry_z and z < -entry_z
                    short_signal = z_prev <= entry_z and z > entry_z
            else:
                long_signal = z < -entry_z
                short_signal = z > entry_z

            if long_signal:
                position = 1
                entry_p1, entry_p2 = cp1, cp2
                entry_date = date
                entry_z_val = z
                entry_beta = beta
            elif short_signal:
                position = -1
                entry_p1, entry_p2 = cp1, cp2
                entry_date = date
                entry_z_val = z
                entry_beta = beta
        else:
            ret1 = (cp1 - entry_p1) / entry_p1
            ret2 = (cp2 - entry_p2) / entry_p2
            unrealized = position * (ret1 - entry_beta * ret2) * notional

            should_exit = (
                (position == 1 and z >= -exit_z)
                or (position == -1 and z <= exit_z)
                or abs(z) >= stop_z
            )
            if should_exit:
                tc_cost = 2 * notional * transaction_cost
                net_pnl = unrealized - tc_cost
                cum_pnl += net_pnl
                trades.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": date,
                        "pair": f"{t1}/{t2}",
                        "direction": "long" if position == 1 else "short",
                        "entry_z": round(entry_z_val, 3),
                        "exit_z": round(z, 3),
                        "gross_pnl": round(unrealized, 2),
                        "tc_cost": round(tc_cost, 2),
                        "net_pnl": round(net_pnl, 2),
                        "stop_hit": abs(z) >= stop_z,
                        "hold_days": (date - entry_date).days,
                    }
                )
                position = 0

        equity_rows.append({"date": date, "equity": cum_pnl})

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_rows).set_index("date")
    return trades_df, equity_df


def backtest_pair_rolling_beta(
    prices: pd.DataFrame,
    t1: str,
    t2: str,
    *,
    beta_lookback: int,
    rebalance_every: int,
    zscore_window: int,
    entry_z: float,
    exit_z: float,
    stop_z: float,
    notional: float,
    transaction_cost: float,
    entry_mode: str = "cross",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Backtest with hedge ratio re-estimated on a rolling past window (walk-forward style)."""
    p1, p2 = prices[t1], prices[t2]
    beta_series = rolling_beta_series(
        prices, t1, t2, lookback=beta_lookback, rebalance_every=rebalance_every
    )
    _, zscore = _build_dynamic_spread_zscore(p1, p2, beta_series, zscore_window)
    zscore = zscore.dropna()
    p1 = p1.reindex(zscore.index)
    p2 = p2.reindex(zscore.index)
    beta_series = beta_series.reindex(zscore.index)

    position = 0
    entry_z_val = 0.0
    entry_p1 = entry_p2 = 0.0
    entry_beta = 1.0
    entry_date = zscore.index[0]
    trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    cum_pnl = 0.0
    cross = entry_mode.lower() == "cross"

    for i in range(len(zscore)):
        date = zscore.index[i]
        z = float(zscore.iloc[i])
        z_prev = float(zscore.iloc[i - 1]) if i > 0 else np.nan
        cp1 = float(p1.iloc[i])
        cp2 = float(p2.iloc[i])
        beta_now = float(beta_series.iloc[i])

        if position == 0:
            long_signal = False
            short_signal = False
            if cross:
                if i > 0 and not np.isnan(z_prev):
                    long_signal = z_prev >= -entry_z and z < -entry_z
                    short_signal = z_prev <= entry_z and z > entry_z
            else:
                long_signal = z < -entry_z
                short_signal = z > entry_z

            if long_signal:
                position = 1
                entry_p1, entry_p2 = cp1, cp2
                entry_date = date
                entry_z_val = z
                entry_beta = beta_now
            elif short_signal:
                position = -1
                entry_p1, entry_p2 = cp1, cp2
                entry_date = date
                entry_z_val = z
                entry_beta = beta_now
        else:
            ret1 = (cp1 - entry_p1) / entry_p1
            ret2 = (cp2 - entry_p2) / entry_p2
            unrealized = position * (ret1 - entry_beta * ret2) * notional

            should_exit = (
                (position == 1 and z >= -exit_z)
                or (position == -1 and z <= exit_z)
                or abs(z) >= stop_z
            )
            if should_exit:
                tc_cost = 2 * notional * transaction_cost
                net_pnl = unrealized - tc_cost
                cum_pnl += net_pnl
                trades.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": date,
                        "pair": f"{t1}/{t2}",
                        "direction": "long" if position == 1 else "short",
                        "entry_z": round(entry_z_val, 3),
                        "exit_z": round(z, 3),
                        "gross_pnl": round(unrealized, 2),
                        "tc_cost": round(tc_cost, 2),
                        "net_pnl": round(net_pnl, 2),
                        "stop_hit": abs(z) >= stop_z,
                        "hold_days": (date - entry_date).days,
                    }
                )
                position = 0

        equity_rows.append({"date": date, "equity": cum_pnl})

    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_rows).set_index("date")
    return trades_df, equity_df


def build_universe_for_scan(cfg_universe: Mapping[str, list[str]]) -> dict[str, list[str]]:
    """Build sector → tickers dict with human-readable sector keys."""
    labels = {
        "banks": "Banks",
        "big_tech": "Big Tech",
        "energy": "Energy",
        "consumer": "Consumer",
        "semis": "Semis",
    }
    out: dict[str, list[str]] = {}
    for key, tickers in cfg_universe.items():
        label = labels.get(key, key)
        out[label] = list(tickers)
    return out
