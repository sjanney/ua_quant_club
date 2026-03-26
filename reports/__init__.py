"""Performance metrics and HTML report generation."""

from reports.generator import ReportGenerator
from reports.metrics import (
    avg_hold_days,
    calmar_ratio,
    max_drawdown,
    performance_summary,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
)

__all__ = [
    "ReportGenerator",
    "avg_hold_days",
    "calmar_ratio",
    "max_drawdown",
    "performance_summary",
    "profit_factor",
    "sharpe_ratio",
    "sortino_ratio",
    "win_rate",
]
