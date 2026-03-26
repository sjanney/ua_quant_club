# UA Quant Club (`ua-quant-club`)

Research-to-execution tooling for systematic alphas, including:

- Pairs trading research (Engle-Granger cointegration, OLS hedge ratio, rolling z-scores)
- Paper trading on Investopedia’s Stock Simulator (Playwright automation)
- A SQLite trade journal with derived `signed_cash_flow`
- HTML/PDF performance reports and portfolio metrics

## Repo Layout

```text
ua-quant-club/
├── alphas/
│   ├── _template/
│   │   └── alpha_template.ipynb
│   └── pairs_trading/
│       ├── notebook.ipynb
│       ├── strategy.py
│       └── README.md
├── execution/
│   ├── broker.py
│   ├── orders.py
│   ├── portfolio.py
│   ├── sizing.py
│   └── risk.py
├── data/
│   ├── fetcher.py
│   └── universe.py
├── logging_/
│   ├── trade_logger.py
│   ├── event_logger.py
│   └── schema.sql
├── reports/
│   ├── generator.py
│   ├── metrics.py
│   └── templates/
│       └── report.html.j2
├── utils/
│   ├── config.py
│   └── notify.py
└── tests/
    └── (pytest suite)
```

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e . -r requirements.txt
cp .env.example .env

# Only needed if you use live broker automation
playwright install

# Run the pairs trading notebook
jupyter notebook alphas/pairs_trading/notebook.ipynb
```

WeasyPrint (optional PDF export) may require extra system libraries on macOS/Linux; see the [WeasyPrint first steps](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html).

## Desk Workflow (Research -> Paper Trade -> Report)

### 1) Research / Backtest

Start with `alphas/pairs_trading/notebook.ipynb`. Strategy logic lives in `alphas/pairs_trading/strategy.py`, and reporting/backtest config comes from `config.yaml`.

### 2) Paper Trade (Investopedia simulator)

`execution.dry_run` defaults to `true` in `config.yaml`. Set it to `false` only when you are ready to submit orders to the simulator.

Login is done via environment variables:

- `INVESTOPEDIA_EMAIL`
- `INVESTOPEDIA_PASSWORD`

Example:

```python
from execution import InvestopediaBroker
from execution.orders import Order, OrderSide

broker = InvestopediaBroker(headless=True)  # reads execution.dry_run from config.yaml
broker.login()

order = Order(
    ticker="JPM",
    side=OrderSide.BUY,
    quantity=10,
    strategy_tag="pairs_trading",
)

broker.place_order(order)
```

For pair trades, prefer using `execution.sizing.build_pair_leg_orders()` so live legs match your pair “position” conventions.

### 3) Generate a report

Reports use the trade journal (SQLite) plus broker portfolio totals to compute metrics from an equity-like curve derived from `signed_cash_flow`.

```python
from execution.portfolio import Portfolio
from logging_.trade_logger import TradeLogger
from reports.generator import ReportGenerator

portfolio = Portfolio()
portfolio.sync(broker)

path = ReportGenerator().generate(
    portfolio=portfolio,
    trade_logger=TradeLogger(),
    export_pdf=False,
)
print(path)
```

## Logging / Journal

- Trade journal: `logging_.trade_logger.TradeLogger` writes to `config.yaml -> logging.db_path` (default `logs/trades.db`)
- Operational events: `logs/events.log` (rotating)
- The SQLite schema includes `signed_cash_flow` (computed from order side + fill price/quantity)

## Add a New Alpha

1. Copy `alphas/_template/alpha_template.ipynb` to `alphas/<your_alpha>/notebook.ipynb`
2. Keep the notebook layout used by this repo (signals, backtest, metrics, OOS, sensitivity, execution plan)
3. Put reusable logic into `alphas/<your_alpha>/strategy.py` and import from the notebook

## Tests

```bash
pytest -q
```

All tests are designed to run without Playwright credentials (no live browser required).
