"""Tests for :mod:`data.fetcher`."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import data.fetcher as fetcher


def test_fetch_single_ticker_uses_cache_on_second_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Second fetch with same args does not call Yahoo again within TTL."""
    calls = {"n": 0}

    def fake_download(
        tickers: object,
        start: object = None,
        end: object = None,
        **kwargs: object,
    ) -> pd.DataFrame:
        calls["n"] += 1
        idx = pd.date_range("2021-01-04", periods=4, freq="B")
        return pd.DataFrame({"Close": [100.0, 101.0, 102.0, 103.0]}, index=idx)

    monkeypatch.setattr(fetcher.yf, "download", fake_download)
    monkeypatch.setattr(fetcher, "_cache_dir", lambda: tmp_path)

    out1 = fetcher.fetch(["JPM"], "2021-01-01", "2021-01-31")
    out2 = fetcher.fetch(["JPM"], "2021-01-01", "2021-01-31")
    assert not out1.empty
    assert calls["n"] == 1
    assert len(out2) == len(out1)
