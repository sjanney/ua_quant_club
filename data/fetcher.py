"""Yahoo Finance data with parquet disk cache (24-hour validity)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf

from utils.config import CONFIG

_CACHE_TTL_SEC = 24 * 60 * 60


def _cache_dir() -> Path:
    root = Path(__file__).resolve().parent
    d = root / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(ticker: str, start: str, end: str) -> Path:
    safe_start = start.replace(":", "-")
    safe_end = end.replace(":", "-")
    return _cache_dir() / f"{ticker}_{safe_start}_{safe_end}.parquet"


def _is_fresh(path: Path) -> bool:
    if not path.is_file():
        return False
    age = time.time() - path.stat().st_mtime
    return age < _CACHE_TTL_SEC


def _load_ticker_column(path: Path, ticker: str) -> pd.Series:
    df = pd.read_parquet(path)
    if isinstance(df, pd.DataFrame) and ticker in df.columns:
        return df[ticker].dropna()
    if isinstance(df, pd.DataFrame) and len(df.columns) == 1:
        return df.iloc[:, 0].dropna()
    raise ValueError(f"Unexpected cache format in {path}")


def fetch(tickers: Iterable[str], start: str, end: str) -> pd.DataFrame:
    """Load adjusted close prices for ``tickers`` between ``start`` and ``end`` (inclusive).

    Uses per-ticker parquet files under ``data/cache/``. Files older than 24 hours are
    refreshed. If any ticker needs a refresh, a **single** Yahoo Finance download is
    performed for all requested tickers, then per-ticker caches are written.

    Args:
        tickers: Stock symbols.
        start: Start date ``YYYY-MM-DD``.
        end: End date ``YYYY-MM-DD``.

    Returns:
        DataFrame indexed by date with one column per ticker (Close).
    """
    tick_list = [str(t).strip() for t in tickers if str(t).strip()]
    if not tick_list:
        return pd.DataFrame()

    need_download: list[str] = []
    cached_series: dict[str, pd.Series] = {}

    for t in tick_list:
        cp = _cache_path(t, start, end)
        if _is_fresh(cp):
            try:
                cached_series[t] = _load_ticker_column(cp, t)
            except (OSError, ValueError, KeyError):
                need_download.append(t)
        else:
            need_download.append(t)

    if need_download:
        raw = yf.download(
            need_download,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            group_by="column",
        )
        if raw.empty:
            close = pd.DataFrame()
        else:
            if isinstance(raw.columns, pd.MultiIndex):
                if "Close" in raw.columns.get_level_values(0):
                    close = raw.xs("Close", axis=1, level=0)
                else:
                    close = raw
            elif "Close" in raw.columns:
                close = raw["Close"]
            else:
                close = raw
            if isinstance(close, pd.Series):
                close = close.to_frame(name=need_download[0])

        for t in need_download:
            if t not in close.columns:
                continue
            series = close[t].dropna()
            out_path = _cache_path(t, start, end)
            pd.DataFrame({t: series}).to_parquet(out_path, index=True)
            cached_series[t] = series

    frames: list[pd.Series] = []
    for t in tick_list:
        if t in cached_series:
            frames.append(cached_series[t].rename(t))

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, axis=1)
    out = out.sort_index()
    out = out.loc[(out.index >= pd.Timestamp(start)) & (out.index <= pd.Timestamp(end))]
    return out


def ensure_data_dirs() -> None:
    """Create log directory from config (used by notebooks)."""
    log_dir = CONFIG.get("logging", {}).get("log_dir", "logs")
    Path(log_dir).mkdir(parents=True, exist_ok=True)
