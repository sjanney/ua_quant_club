# UA Quant Club (`ua-quant-club`)

The University of Arizona Quantitative Finance Club builds and competes with systematic alphas; this repo supports research, paper trading on Investopedia’s Stock Simulator, and reporting for the intra-club alpha competition.

## Repository structure

```
ua-quant-club/
├── alphas/
│   ├── _template/
│   │   └── alpha_template.ipynb
│   └── pairs_trading/
│       ├── notebook.ipynb
│       ├── strategy.py
│       └── README.md
├── execution/
│   ├── __init__.py
│   ├── broker.py
│   ├── orders.py
│   └── portfolio.py
├── data/
│   ├── __init__.py
│   ├── fetcher.py
│   └── universe.py
├── logging_/
│   ├── __init__.py
│   ├── trade_logger.py
│   ├── event_logger.py
│   └── schema.sql
├── reports/
│   ├── __init__.py
│   ├── metrics.py
│   ├── generator.py
│   └── templates/
│       └── report.html.j2
├── utils/
│   ├── __init__.py
│   ├── config.py
│   └── notify.py
├── tests/
│   ├── test_metrics.py
│   ├── test_orders.py
│   └── test_fetcher.py
├── config.yaml
├── .env.example
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Quickstart

```bash
git clone <your-fork-url> ua-quant-club
cd ua-quant-club
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e . -r requirements.txt
cp .env.example .env        # fill Investopedia + optional Discord webhook
playwright install          # only if you use execution/broker.py live
jupyter notebook alphas/pairs_trading/notebook.ipynb
```

WeasyPrint (optional PDF reports) may require extra system libraries on macOS or Linux; see the [WeasyPrint first steps](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) documentation.

## Add a new alpha

1. Copy `alphas/_template/alpha_template.ipynb` to a new folder under `alphas/<your_alpha>/notebook.ipynb`.
2. Keep the **10-cell** layout: hypothesis, imports + config, data (`data.fetcher` only), signals, backtest, metrics, plots, OOS, sensitivity, live execution plan.
3. Put reusable logic in `alphas/<your_alpha>/strategy.py` and import it from the notebook.

## Execute a trade (Investopedia)

`execution.dry_run` defaults to `true` in `config.yaml`; set `execution.dry_run: false` only when you intend to hit the simulator.

```python
from execution import InvestopediaBroker
from execution.orders import Order, OrderSide

broker = InvestopediaBroker(headless=True)  # dry_run from config.yaml
order = Order(ticker="JPM", side=OrderSide.BUY, quantity=10, strategy_tag="pairs_trading")
broker.login()
filled = broker.place_order(order)
```

## Generate a report

```python
from execution.portfolio import Portfolio
from logging_.trade_logger import TradeLogger
from reports.generator import ReportGenerator

portfolio = Portfolio()
portfolio.sync(broker)  # e.g. InvestopediaBroker from the snippet above
path = ReportGenerator().generate(portfolio, TradeLogger(), export_pdf=False)
```

## Team members

| Name | Role | Contact |
|------|------|---------|
| _TBD_ | Captain | _@arizona.edu_ |
| _TBD_ | Research | _@arizona.edu_ |
| _TBD_ | Execution | _@arizona.edu_ |

## Competition context / scoring

Scoring rules and submission deadlines for the intra-club alpha competition are distributed by club leadership each semester. Replace this section with the official rubric (e.g. risk-adjusted return, robustness checks, presentation) when it is published.
</think>


<｜tool▁calls▁begin｜><｜tool▁call▁begin｜>
StrReplace