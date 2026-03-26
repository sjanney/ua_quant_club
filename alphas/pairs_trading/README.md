# Pairs trading alpha

Statistical pairs arbitrage: Engle–Granger cointegration within sector groups, OLS hedge ratio, rolling z-score signals, and backtests with configurable entry, exit, and stop z-scores (see root `config.yaml` under `pairs_trading`).

**Improvements vs a naive backtest**

- **Rolling hedge ratio** (`backtest_pair_rolling_beta`): re-estimate $\beta$ on a past-only window on a fixed schedule (walk-forward; no lookahead).
- **Crossing entries** (`entry_mode: cross`): trade when $z$ *crosses* the entry band, not only when it sits outside it.
- **Optional Bonferroni** on the cointegration scan (`use_bonferroni`) and **half-life** cap (`max_half_life_days`).
- **Train/test evaluation** (`evaluation.walk_forward_coint_then_test`): run the scan on a train window only, then backtest the test window with the **train** $\beta$.

## Run

From the repository root (after `pip install -e .` and `playwright install` if you use the broker):

1. Open `alphas/pairs_trading/notebook.ipynb` in Jupyter or VS Code.
2. Run all cells top to bottom (data is pulled via `data.fetcher` with parquet cache under `data/cache/`).

Strategy logic lives in `strategy.py`; walk-forward helpers in `evaluation.py`. Tests: `tests/test_pairs_strategy.py`.
