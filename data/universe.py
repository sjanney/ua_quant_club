"""Ticker universe grouped by sector from configuration."""

from __future__ import annotations

from typing import Iterator

from utils.config import CONFIG


def get_universe_dict() -> dict[str, list[str]]:
    """Return the sector → tickers mapping from ``CONFIG['universe']``.

    Returns:
        Copy of the universe dict with string keys and upper-case tickers as stored.
    """
    u = CONFIG.get("universe", {})
    return {str(k): list(v) for k, v in u.items()}


def get_all_tickers() -> list[str]:
    """Return a deduplicated ordered list of all tickers across sectors."""
    seen: set[str] = set()
    out: list[str] = []
    for tickers in get_universe_dict().values():
        for t in tickers:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def iter_sectors() -> Iterator[tuple[str, list[str]]]:
    """Yield ``(sector_name, tickers)`` pairs."""
    for sector, tickers in get_universe_dict().items():
        yield sector, tickers
