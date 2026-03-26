"""Walk-forward and train/test splits for honest pairs backtests."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from alphas.pairs_trading.strategy import (
    backtest_pair,
    backtest_pair_rolling_beta,
    run_coint_scan,
)


def count_pair_tests(universe: Mapping[str, list[str]], prices: pd.DataFrame) -> int:
    """Number of same-sector pairs with enough overlapping history (matches scan skips)."""
    from itertools import combinations

    n = 0
    for tickers in universe.values():
        valid = [t for t in tickers if t in prices.columns]
        for t1, t2 in combinations(valid, 2):
            s1, s2 = prices[t1].dropna(), prices[t2].dropna()
            idx = s1.index.intersection(s2.index)
            if len(idx) >= 200:
                n += 1
    return max(n, 1)


def train_test_by_date(
    prices: pd.DataFrame,
    train_end: str,
    test_start: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split wide price panel into train (inclusive end) and test (inclusive start)."""
    train = prices.loc[: pd.Timestamp(train_end)]
    test = prices.loc[pd.Timestamp(test_start) :]
    return train, test


def evaluate_pair_on_window(
    prices: pd.DataFrame,
    t1: str,
    t2: str,
    beta: float,
    *,
    pairs_cfg: Mapping[str, Any],
    backtest_cfg: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run static-beta backtest with config dicts (used for train-only beta on test window)."""
    return backtest_pair(
        prices,
        t1,
        t2,
        beta,
        zscore_window=int(pairs_cfg["zscore_window"]),
        entry_z=float(pairs_cfg["entry_z"]),
        exit_z=float(pairs_cfg["exit_z"]),
        stop_z=float(pairs_cfg["stop_z"]),
        notional=float(backtest_cfg["notional_per_trade"]),
        transaction_cost=float(backtest_cfg["transaction_cost"]),
        entry_mode=str(pairs_cfg.get("entry_mode", "cross")),
    )


def walk_forward_coint_then_test(
    train_prices: pd.DataFrame,
    test_prices: pd.DataFrame,
    universe: Mapping[str, list[str]],
    pairs_cfg: Mapping[str, Any],
    backtest_cfg: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Cointegration scan on **train** only; backtest each surviving pair on **test** with train beta.

    Avoids selecting pairs using test-period statistics.
    """
    n_tests = count_pair_tests(universe, train_prices)
    use_bonf = bool(pairs_cfg.get("use_bonferroni", False))
    mhl = pairs_cfg.get("max_half_life_days")
    mhl_f = float(mhl) if mhl is not None else None
    scan = run_coint_scan(
        train_prices,
        universe,
        float(pairs_cfg["coint_p_threshold"]),
        n_total_tests=n_tests if use_bonf else None,
        max_half_life_days=mhl_f,
    )
    rows: list[dict[str, Any]] = []
    for _, row in scan[scan["cointegrated"]].iterrows():
        t1, t2 = row["ticker1"], row["ticker2"]
        beta = float(row["beta"])
        if t1 not in test_prices.columns or t2 not in test_prices.columns:
            continue
        tr, eq = evaluate_pair_on_window(
            test_prices, t1, t2, beta, pairs_cfg=pairs_cfg, backtest_cfg=backtest_cfg
        )
        rows.append(
            {
                "pair": f"{t1}/{t2}",
                "sector": row["sector"],
                "train_coint_p": row["coint_p"],
                "beta_train": beta,
                "n_trades": len(tr),
                "test_net_pnl": float(tr["net_pnl"].sum()) if len(tr) else 0.0,
                "trades": tr,
                "equity": eq,
            }
        )
    return rows


def rolling_beta_full_sample(
    prices: pd.DataFrame,
    t1: str,
    t2: str,
    *,
    pairs_cfg: Mapping[str, Any],
    backtest_cfg: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Full-sample backtest with periodically re-estimated hedge ratio (no lookahead in beta)."""
    return backtest_pair_rolling_beta(
        prices,
        t1,
        t2,
        beta_lookback=int(pairs_cfg.get("beta_lookback", 252)),
        rebalance_every=int(pairs_cfg.get("rebalance_every", 21)),
        zscore_window=int(pairs_cfg["zscore_window"]),
        entry_z=float(pairs_cfg["entry_z"]),
        exit_z=float(pairs_cfg["exit_z"]),
        stop_z=float(pairs_cfg["stop_z"]),
        notional=float(backtest_cfg["notional_per_trade"]),
        transaction_cost=float(backtest_cfg["transaction_cost"]),
        entry_mode=str(pairs_cfg.get("entry_mode", "cross")),
    )
