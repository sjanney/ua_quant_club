"""SQLite-backed trade journal."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from execution.orders import Order, OrderSide, OrderStatus
from utils.config import CONFIG


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _notes_with_order_id(order: Order) -> str:
    """Prefix notes with order_id for correlation (schema has no order_id column)."""
    base = order.notes or ""
    return f"order_id={order.order_id}|{base}"


def _signed_cash_flow(order: Order) -> Optional[float]:
    """Signed cash flow for a filled order.

    Convention:
    - `BUY` / `COVER`: negative cash flow (cash out)
    - `SELL` / `SHORT`: positive cash flow (cash in)
    """
    if order.filled_price is None:
        return None
    if order.side in (OrderSide.BUY, OrderSide.COVER):
        return -float(order.filled_price) * float(order.quantity)
    return float(order.filled_price) * float(order.quantity)


class TradeLogger:
    """Persist orders and fills to SQLite.

    The ``trades`` table follows ``logging_/schema.sql``. ``Order.order_id`` is stored
    inside the ``notes`` field as ``order_id=<uuid>|...`` because the schema has no
    dedicated column.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Open the journal, creating tables from ``schema.sql`` if needed.

        Args:
            db_path: Path to SQLite file; defaults to ``CONFIG['logging']['db_path']``.
        """
        cfg_path = CONFIG.get("logging", {}).get("db_path", "logs/trades.db")
        self._path = Path(db_path) if db_path is not None else Path(cfg_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        schema_file = Path(__file__).resolve().parent / "schema.sql"
        sql = schema_file.read_text(encoding="utf-8")
        with sqlite3.connect(self._path) as conn:
            conn.executescript(sql)
            self._migrate_signed_cash_flow(conn)

    def _migrate_signed_cash_flow(self, conn: sqlite3.Connection) -> None:
        """Add signed_cash_flow column for existing databases."""
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(trades)").fetchall()
        }
        if "signed_cash_flow" in cols:
            return
        conn.execute("ALTER TABLE trades ADD COLUMN signed_cash_flow REAL")

    def log_order(self, order: Order) -> None:
        """Insert a new row with status PENDING."""
        now = _utc_now_iso()
        notes = _notes_with_order_id(order)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO trades (
                    ticker, side, quantity, limit_price, filled_price,
                    signed_cash_flow,
                    status, strategy_tag, notes, created_at, filled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.ticker,
                    order.side.value,
                    float(order.quantity),
                    order.limit_price,
                    None,
                    None,
                    OrderStatus.PENDING.value,
                    order.strategy_tag,
                    notes,
                    now,
                    None,
                ),
            )

    def log_fill(self, order: Order) -> None:
        """Update the latest matching row for this ``order_id`` to FILLED or REJECTED."""
        like_pat = f"order_id={order.order_id}|%"
        filled_at = order.filled_at.isoformat() if order.filled_at else _utc_now_iso()
        scf = _signed_cash_flow(order)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                UPDATE trades
                SET status = ?,
                    filled_price = ?,
                    signed_cash_flow = ?,
                    filled_at = ?,
                    notes = ?
                WHERE id = (
                    SELECT MAX(id) FROM trades WHERE notes LIKE ?
                )
                """,
                (
                    order.status.value,
                    order.filled_price,
                    scf,
                    filled_at,
                    _notes_with_order_id(order),
                    like_pat,
                ),
            )

    def get_trades(
        self,
        strategy_tag: Optional[str] = None,
        since: Optional[str] = None,
    ) -> pd.DataFrame:
        """Return trades as a DataFrame, optionally filtered."""
        q = "SELECT * FROM trades WHERE 1=1"
        params: list[Any] = []
        if strategy_tag:
            q += " AND strategy_tag = ?"
            params.append(strategy_tag)
        if since:
            q += " AND created_at >= ?"
            params.append(since)
        q += " ORDER BY id"
        with sqlite3.connect(self._path) as conn:
            return pd.read_sql_query(q, conn, params=params)

    def get_open_positions(self) -> pd.DataFrame:
        """Return rows that represent open exposure (best-effort from journal)."""
        with sqlite3.connect(self._path) as conn:
            return pd.read_sql_query(
                """
                SELECT * FROM trades
                WHERE status = 'FILLED'
                ORDER BY id DESC
                """,
                conn,
            )
