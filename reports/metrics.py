"""Performance metrics for daily returns and trade lists."""

from __future__ import annotations

import numpy as np
import pandas as pd

_TRADING_DAYS = 252


def _daily_rf(risk_free_annual: float) -> float:
    return (1.0 + risk_free_annual) ** (1.0 / _TRADING_DAYS) - 1.0


def sharpe_ratio(returns: pd.Series, risk_free: float = 0.05) -> float:
    """Annualized Sharpe ratio from daily simple returns.

    Args:
        returns: Daily return series.
        risk_free: Annual risk-free rate (default 5%).

    Returns:
        Sharpe ratio (float). Returns ``0.0`` if volatility is zero.
    """
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    rf_d = _daily_rf(risk_free)
    ex = r - rf_d
    std = float(ex.std(ddof=1))
    if std <= 0 or np.isnan(std):
        return 0.0
    return float(ex.mean() / std * np.sqrt(_TRADING_DAYS))


def sortino_ratio(returns: pd.Series, risk_free: float = 0.05) -> float:
    """Annualized Sortino ratio using downside deviation of daily returns.

    Args:
        returns: Daily simple returns.
        risk_free: Annual risk-free rate.

    Returns:
        Sortino ratio, or ``0.0`` if downside deviation is zero.
    """
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    rf_d = _daily_rf(risk_free)
    ex = r - rf_d
    downside = ex[ex < 0]
    if len(downside) < 1:
        return 999.0 if ex.mean() > 0 else 0.0
    dstd = float(downside.std(ddof=1))
    if dstd <= 0 or np.isnan(dstd):
        return 0.0
    return float(ex.mean() / dstd * np.sqrt(_TRADING_DAYS))


def max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum drawdown as a negative fraction of peak (e.g. -0.2 for -20%).

    Args:
        equity_curve: Account equity or cumulative P&L level series.

    Returns:
        Maximum drawdown (non-positive scalar).
    """
    s = equity_curve.dropna()
    if len(s) < 2:
        return 0.0
    roll_max = s.cummax()
    dd = (s - roll_max) / roll_max.replace(0, np.nan)
    return float(dd.min()) if len(dd) else 0.0


def calmar_ratio(returns: pd.Series) -> float:
    """Calmar ratio: annualized return divided by absolute max drawdown on cumulated equity.

    Args:
        returns: Daily simple returns.

    Returns:
        Calmar ratio, or ``0.0`` if drawdown is zero.
    """
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    equity = (1.0 + r).cumprod()
    mdd = max_drawdown(equity)
    if mdd >= -1e-12:
        return 0.0
    years = len(r) / _TRADING_DAYS
    if years <= 0:
        return 0.0
    ann_ret = float((equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1.0)
    return ann_ret / abs(mdd)


def win_rate(trades: pd.DataFrame) -> float:
    """Fraction of trades with positive ``net_pnl`` (0–1).

    Args:
        trades: Must include column ``net_pnl``.
    """
    if trades is None or len(trades) == 0 or "net_pnl" not in trades.columns:
        return 0.0
    wins = (trades["net_pnl"] > 0).sum()
    return float(wins / len(trades))


def profit_factor(trades: pd.DataFrame) -> float:
    """Gross profits divided by gross losses (absolute).

    Args:
        trades: Must include ``net_pnl``.
    """
    if trades is None or len(trades) == 0 or "net_pnl" not in trades.columns:
        return 0.0
    pnl = trades["net_pnl"]
    gains = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    if losses <= 0:
        return 999.0 if gains > 0 else 0.0
    return float(gains / losses)


def avg_hold_days(trades: pd.DataFrame) -> float:
    """Average holding period in days.

    Args:
        trades: Must include ``hold_days``.
    """
    if trades is None or len(trades) == 0 or "hold_days" not in trades.columns:
        return 0.0
    return float(trades["hold_days"].mean())


def performance_summary(
    equity_curve: pd.Series,
    trades: pd.DataFrame,
    starting_capital: float | None = None,
) -> dict[str, float | str]:
    """Aggregate key metrics for reporting.

    Args:
        equity_curve: Levels or cumulative P&L indexed by date.
        trades: Trade blotter with ``net_pnl`` and ``hold_days`` (from strategy backtest).
        starting_capital: Denominator used to convert daily equity deltas into daily simple returns.
            If ``None``, uses the first non-null equity value as a safe default.

    Returns:
        Dict of metric names to values.
    """
    eq = equity_curve.dropna()
    if len(eq):
        daily_delta_equity = eq.diff().fillna(0.0)
        denom = float(starting_capital) if starting_capital is not None else float(eq.iloc[0])
        if abs(denom) < 1e-12:
            daily_ret = daily_delta_equity
        else:
            daily_ret = daily_delta_equity / denom
    else:
        daily_ret = pd.Series(dtype=float)
    mdd = max_drawdown(eq) if len(eq) else 0.0
    pf = profit_factor(trades)
    pf_out = round(pf, 4) if np.isfinite(pf) else 999.0
    return {
        "sharpe_ratio": round(sharpe_ratio(daily_ret), 4),
        "sortino_ratio": round(sortino_ratio(daily_ret), 4),
        "calmar_ratio": round(calmar_ratio(daily_ret), 4),
        "max_drawdown": round(mdd, 6),
        "win_rate": round(win_rate(trades), 4),
        "profit_factor": pf_out,
        "avg_hold_days": round(avg_hold_days(trades), 2),
        "n_trades": int(len(trades)) if trades is not None else 0,
    }
