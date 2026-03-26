"""Market data fetch and universe definitions."""

from data.fetcher import fetch
from data.universe import get_all_tickers, get_universe_dict

__all__ = ["fetch", "get_all_tickers", "get_universe_dict"]
