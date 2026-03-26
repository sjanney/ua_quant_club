from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from execution.orders import Order, OrderSide, OrderStatus
from logging_.trade_logger import TradeLogger
from reports.generator import ReportGenerator


class _DummyPortfolio:
    def __init__(self, total_value: float) -> None:
        self._total_value = float(total_value)

    def summary(self) -> dict[str, float | int]:
        return {
            "total_value": self._total_value,
            "cash": self._total_value,
            "num_positions": 0,
            "total_pnl": 0.0,
        }


def _add_filled_trade(
    *,
    logger: TradeLogger,
    ticker: str,
    side: OrderSide,
    quantity: float,
    filled_price: float,
    filled_at: datetime,
    strategy_tag: str = "pairs_trading",
) -> None:
    o = Order(
        ticker=ticker,
        side=side,
        quantity=quantity,
        filled_price=None,
        filled_at=None,
        strategy_tag=strategy_tag,
        notes="",
    )
    logger.log_order(o)
    o.status = OrderStatus.FILLED
    o.filled_price = float(filled_price)
    o.filled_at = filled_at
    logger.log_fill(o)


def test_trade_logger_signed_cash_flow_buy_and_short(tmp_path: Path) -> None:
    db_path = tmp_path / "trades.db"
    logger = TradeLogger(db_path=db_path)

    filled_at = datetime.now(timezone.utc) - timedelta(days=1)

    # BUY => negative cash flow
    o_buy = Order(
        ticker="AAA",
        side=OrderSide.BUY,
        quantity=2.0,
        strategy_tag="t1",
        notes="",
    )
    logger.log_order(o_buy)
    o_buy.status = OrderStatus.FILLED
    o_buy.filled_price = 10.0
    o_buy.filled_at = filled_at
    logger.log_fill(o_buy)

    # SHORT => positive cash flow
    o_short = Order(
        ticker="BBB",
        side=OrderSide.SHORT,
        quantity=2.0,
        strategy_tag="t1",
        notes="",
    )
    logger.log_order(o_short)
    o_short.status = OrderStatus.FILLED
    o_short.filled_price = 10.0
    o_short.filled_at = filled_at
    logger.log_fill(o_short)

    df = logger.get_trades(strategy_tag="t1")
    assert "signed_cash_flow" in df.columns

    # Order of rows is by id; last two should correspond to the two fills.
    cashflows = list(df["signed_cash_flow"].tail(2).astype(float))
    assert cashflows[0] == -20.0
    assert cashflows[1] == 20.0


def test_trade_logger_schema_migration_adds_signed_cash_flow(tmp_path: Path) -> None:
    """If trades table exists without signed_cash_flow, TradeLogger should migrate it."""
    db_path = tmp_path / "trades.db"

    # Create the *old* schema (no signed_cash_flow column).
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                limit_price REAL,
                filled_price REAL,
                status TEXT NOT NULL,
                strategy_tag TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                filled_at TEXT
            );
            """
        )

    # Instantiating TradeLogger should add the new column automatically.
    logger = TradeLogger(db_path=db_path)
    cols = {
        row[1] for row in sqlite3.connect(db_path).execute("PRAGMA table_info(trades)").fetchall()
    }
    assert "signed_cash_flow" in cols

    # Also verify inserts/updates work with the migrated column.
    filled_at = datetime.now(timezone.utc) - timedelta(days=1)
    _add_filled_trade(
        logger=logger,
        ticker="AAA",
        side=OrderSide.SELL,
        quantity=123.0,
        filled_price=1.0,
        filled_at=filled_at,
        strategy_tag="migrate_test",
    )
    df = logger.get_trades(strategy_tag="migrate_test")
    assert float(df.iloc[-1]["signed_cash_flow"]) == 123.0


def _extract_metric(html: str, key: str) -> float:
    pat = rf"<tr><td>{re.escape(key)}</td><td>([^<]+)</td></tr>"
    m = re.search(pat, html)
    assert m, f"Could not find metric {key} in html"
    return float(m.group(1))


def test_report_generator_equity_proxy_changes_with_signed_cash_flow(tmp_path: Path) -> None:
    """If signed cashflow changes daily dynamics, report metrics should change too."""
    base_dir = tmp_path / "reports"
    base_dir.mkdir(parents=True, exist_ok=True)

    end_day = datetime.now(timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)

    def make_report(db_name: str, daily_cashflows: list[float]) -> float:
        db_path = tmp_path / db_name
        logger = TradeLogger(db_path=db_path)

        # Add cashflow events on consecutive days within the last 60 days.
        start_offset_days = 30
        for i, cf in enumerate(daily_cashflows):
            day = end_day - timedelta(days=start_offset_days + i)
            if cf == 0:
                continue
            if cf > 0:
                side = OrderSide.SELL
                qty = float(cf)
            else:
                side = OrderSide.BUY
                qty = float(abs(cf))
            _add_filled_trade(
                logger=logger,
                ticker="AAA",
                side=side,
                quantity=qty,
                filled_price=1.0,
                filled_at=day,
                strategy_tag="pairs_trading",
            )

        portfolio = _DummyPortfolio(total_value=100_000.0)
        out_dir = base_dir / db_name.replace(".db", "")
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = ReportGenerator(output_dir=out_dir).generate(
            portfolio=portfolio,
            trade_logger=logger,
            strategy_tags=None,
            since=None,
            export_pdf=False,
        )
        html = Path(report_path).read_text(encoding="utf-8")
        return _extract_metric(html, "sharpe_ratio")

    # More volatile daily dynamics than the first set.
    sharpe1 = make_report(
        "a.db",
        daily_cashflows=[100.0, 100.0, 100.0, -50.0, 100.0, -50.0, 100.0, -50.0, 100.0, -50.0],
    )
    sharpe2 = make_report(
        "b.db",
        daily_cashflows=[200.0, -150.0, 200.0, -150.0, 200.0, -150.0, 200.0, -150.0, 200.0, -150.0],
    )

    assert abs(sharpe1 - sharpe2) > 1e-6

