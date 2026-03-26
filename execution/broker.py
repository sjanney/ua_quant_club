"""Investopedia Stock Simulator automation (Playwright).

Selectors are **placeholders** — update :data:`SELECTORS` when the simulator UI changes.
"""

from __future__ import annotations

import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from execution.orders import Order, OrderStatus
from execution.risk import run_pretrade_checks
from logging_.event_logger import get_logger
from logging_.trade_logger import TradeLogger
from data.fetcher import fetch as fetch_prices
from utils.config import CONFIG

_LOGGER = get_logger(__name__)

# --- Update these when Investopedia changes their DOM ---
SELECTORS: dict[str, str] = {
    "login_email": "input[name='email'], input#login-email, input[type='email']",
    "login_password": "input[name='password'], input#login-password, input[type='password']",
    "login_submit": "button[type='submit'], button:has-text('Sign In')",
    "simulator_trade_tab": "a:has-text('Trade'), [data-testid='trade-tab']",
    "order_ticker": "input[name='symbol'], input#symbol",
    "order_side": "select[name='side'], select#order-side",
    "order_quantity": "input[name='quantity'], input#quantity",
    "order_limit": "input[name='limitPrice'], input#limit-price",
    "order_submit": "button:has-text('Preview Order'), button:has-text('Submit')",
    "portfolio_table": "table.positions, table.portfolio, [data-testid='positions-table']",
    "account_value": "[data-testid='account-value'], .account-value",
    "transactions_table": "table.transactions, [data-testid='transactions']",
}

_BASE_URL = "https://www.investopedia.com/simulator"


def _delay() -> None:
    ex = CONFIG.get("execution", {})
    lo = float(ex.get("delay_min_s", 1.0))
    hi = float(ex.get("delay_max_s", 3.0))
    time.sleep(random.uniform(lo, hi))


def _screenshot(page: Page, tag: str) -> None:
    log_dir = Path(CONFIG.get("logging", {}).get("log_dir", "logs"))
    shot_dir = log_dir / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)
    path = shot_dir / f"broker_fail_{tag}_{int(time.time())}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        _LOGGER.error("Saved failure screenshot to %s", path)
    except OSError as e:
        _LOGGER.warning("Could not save screenshot: %s", e)


class InvestopediaBroker:
    """Playwright-driven interface to the Investopedia paper trading simulator."""

    def __init__(self, headless: bool = True, dry_run: Optional[bool] = None) -> None:
        """Create a broker instance.

        Args:
            headless: Run browser headless when True.
            dry_run: If True, never submit real orders (default from ``CONFIG``).
        """
        cfg = CONFIG.get("execution", {})
        if dry_run is None:
            dry_run = bool(cfg.get("dry_run", True))
        self.headless = headless
        self.dry_run = dry_run
        self._pw: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._trade_logger = TradeLogger()
        self._dryrun_quote_cache: dict[str, float] = {}

    def _dryrun_last_quote(self, ticker: str) -> Optional[float]:
        """Get last available adjusted close for `ticker` (best-effort)."""
        ticker = str(ticker).strip().upper()
        if not ticker:
            return None
        if ticker in self._dryrun_quote_cache:
            return self._dryrun_quote_cache[ticker]

        end_date = datetime.now(timezone.utc).date()
        start_date = (end_date - timedelta(days=7))
        df = fetch_prices([ticker], start_date.isoformat(), end_date.isoformat())
        if df is None or df.empty or ticker not in df.columns:
            return None
        s = df[ticker].dropna()
        if len(s) == 0:
            return None
        price = float(s.iloc[-1])
        self._dryrun_quote_cache[ticker] = price
        return price

    def _ensure_page(self) -> Page:
        if self._page is not None:
            return self._page
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._page = self._browser.new_page()
        return self._page

    def close(self) -> None:
        """Close browser and Playwright."""
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        finally:
            self._browser = None
            self._pw = None
            self._page = None

    def login(self) -> None:
        """Log in using ``INVESTOPEDIA_EMAIL`` and ``INVESTOPEDIA_PASSWORD``."""
        email = os.getenv("INVESTOPEDIA_EMAIL")
        password = os.getenv("INVESTOPEDIA_PASSWORD")
        if not email or not password:
            raise ValueError("Set INVESTOPEDIA_EMAIL and INVESTOPEDIA_PASSWORD in the environment.")
        page = self._ensure_page()
        try:
            page.goto(_BASE_URL, wait_until="domcontentloaded", timeout=60_000)
            _delay()
            page.fill(SELECTORS["login_email"], email)
            _delay()
            page.fill(SELECTORS["login_password"], password)
            _delay()
            page.click(SELECTORS["login_submit"])
            page.wait_for_load_state("networkidle", timeout=60_000)
        except Exception as e:
            if CONFIG.get("execution", {}).get("screenshot_on_failure", True):
                _screenshot(page, "login")
            _LOGGER.exception("login failed: %s", e)
            raise

    def place_order(self, order: Order) -> Order:
        """Submit an order (or simulate when ``dry_run``).

        Always records the attempt via :class:`TradeLogger` before returning.

        Args:
            order: Order to place.

        Returns:
            Updated ``order`` with status ``FILLED`` or ``REJECTED``.
        """
        run_pretrade_checks(order, self._trade_logger)
        self._trade_logger.log_order(order)
        if self.dry_run:
            order.status = OrderStatus.FILLED
            if order.limit_price is not None:
                order.filled_price = float(order.limit_price)
            else:
                order.filled_price = self._dryrun_last_quote(order.ticker) or 100.0
            order.filled_at = datetime.now(timezone.utc)
            _LOGGER.info("dry_run place_order %s %s %s", order.ticker, order.side, order.quantity)
            self._trade_logger.log_fill(order)
            return order

        page = self._ensure_page()
        try:
            page.goto(_BASE_URL + "/trade", wait_until="domcontentloaded", timeout=90_000)
            _delay()
            page.fill(SELECTORS["order_ticker"], order.ticker)
            _delay()
            try:
                page.select_option(SELECTORS["order_side"], label=order.side.value)
            except Exception:
                page.select_option(SELECTORS["order_side"], value=order.side.value)
            _delay()
            page.fill(SELECTORS["order_quantity"], str(order.quantity))
            if order.limit_price is not None:
                page.fill(SELECTORS["order_limit"], str(order.limit_price))
            _delay()
            page.click(SELECTORS["order_submit"])
            page.wait_for_load_state("networkidle", timeout=60_000)
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(timezone.utc)
            order.filled_price = order.limit_price or 100.0
        except Exception as e:
            if CONFIG.get("execution", {}).get("screenshot_on_failure", True):
                _screenshot(page, "place_order")
            order.status = OrderStatus.REJECTED
            order.filled_at = datetime.now(timezone.utc)
            _LOGGER.exception("place_order failed: %s", e)
            self._trade_logger.log_fill(order)
            raise
        self._trade_logger.log_fill(order)
        return order

    def get_portfolio(self) -> dict[str, Any]:
        """Scrape positions and account value (best-effort structure).

        Returns:
            Dict with keys ``positions`` (list of dicts), ``cash``, ``total_value``,
            ``realized_pnl`` (optional).
        """
        if self.dry_run:
            return {
                "positions": [],
                "cash": 100_000.0,
                "total_value": 100_000.0,
                "realized_pnl": 0.0,
            }
        page = self._ensure_page()
        try:
            page.goto(_BASE_URL + "/portfolio", wait_until="domcontentloaded", timeout=90_000)
            _delay()
            # Placeholder parsing — adapt when selectors match real DOM
            text = page.inner_text(SELECTORS["account_value"]) if page.locator(
                SELECTORS["account_value"]
            ).count() else "0"
            try:
                tv = float("".join(c for c in text if (c.isdigit() or c in ".-")))
            except ValueError:
                tv = 0.0
            return {
                "positions": [],
                "cash": tv,
                "total_value": tv,
                "realized_pnl": 0.0,
            }
        except Exception as e:
            if CONFIG.get("execution", {}).get("screenshot_on_failure", True):
                _screenshot(page, "portfolio")
            _LOGGER.exception("get_portfolio failed: %s", e)
            raise

    def get_transaction_history(self) -> list[dict[str, Any]]:
        """Return parsed transaction rows if the history table is found."""
        if self.dry_run:
            return []
        page = self._ensure_page()
        try:
            page.goto(_BASE_URL + "/history", wait_until="domcontentloaded", timeout=90_000)
            _delay()
            rows = page.locator(f"{SELECTORS['transactions_table']} tr").all()
            out: list[dict[str, Any]] = []
            for r in rows[:200]:
                out.append({"text": r.inner_text()})
            return out
        except Exception as e:
            if CONFIG.get("execution", {}).get("screenshot_on_failure", True):
                _screenshot(page, "history")
            _LOGGER.exception("get_transaction_history failed: %s", e)
            raise
