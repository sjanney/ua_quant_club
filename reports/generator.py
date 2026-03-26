"""HTML (and optional PDF) performance reports."""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from execution.portfolio import Portfolio
from logging_.trade_logger import TradeLogger
from reports import metrics as metrics_mod
from utils.config import CONFIG


class ReportGenerator:
    """Build dated HTML reports under ``reports/output/``."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        """Initialize with output directory from config if not provided.

        Args:
            output_dir: Override for ``CONFIG['reports']['output_dir']``.
        """
        cfg = CONFIG.get("reports", {})
        self.output_dir = Path(output_dir or cfg.get("output_dir", "reports/output"))
        self._template_dir = Path(__file__).resolve().parent / "templates"

    def generate(
        self,
        portfolio: Portfolio,
        trade_logger: TradeLogger,
        strategy_tags: Optional[list[str]] = None,
        since: Optional[str] = None,
        export_pdf: bool = False,
    ) -> str:
        """Render a new HTML report (and optional PDF).

        Args:
            portfolio: Synced portfolio instance.
            trade_logger: Journal to read trades from.
            strategy_tags: Optional filter (not applied if None).
            since: ISO date string filter for trades.
            export_pdf: If True, also write PDF via WeasyPrint when available.

        Returns:
            Path to the written HTML file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
        out_html = self.output_dir / f"{ts}_report.html"

        summ = portfolio.summary()
        st_one = strategy_tags[0] if strategy_tags and len(strategy_tags) == 1 else None
        trades = trade_logger.get_trades(strategy_tag=st_one, since=since)
        if strategy_tags and len(strategy_tags) > 1:
            trades = trades[trades["strategy_tag"].isin(strategy_tags)]

        last30 = trades.tail(30)
        trade_columns = list(last30.columns) if len(last30.columns) else []

        starting_capital = float(summ.get("total_value", 0.0))
        end_day = pd.Timestamp.now(tz=timezone.utc).floor("D")
        dates = pd.date_range(end=end_day, periods=60, freq="D", tz=timezone.utc)

        # Build an equity-like curve from signed cashflows. We anchor the final day
        # to `starting_capital` (from the broker) so the curve reflects P&L changes
        # without double-counting.
        if len(trades) and "signed_cash_flow" in trades.columns and "filled_at" in trades.columns:
            filled_at = pd.to_datetime(trades["filled_at"], utc=True, errors="coerce")
            days = filled_at.dt.floor("D")
            scf = pd.to_numeric(trades["signed_cash_flow"], errors="coerce").fillna(0.0)
            daily_flow = scf.groupby(days).sum()
            daily_flow = daily_flow.reindex(dates, fill_value=0.0)
            cum_flow = daily_flow.cumsum()
            curve = pd.Series(starting_capital + (cum_flow - float(cum_flow.iloc[-1])), index=dates)
            eq_note = (
                "Equity proxy is `starting_capital` anchored to broker current value, "
                "then adjusted by journal signed cashflows aggregated per day."
            )
        else:
            curve = pd.Series(starting_capital, index=dates)
            eq_note = (
                "Equity proxy uses broker current total value as a flat series "
                "when the journal does not have signed cashflow data."
            )

        fig, ax = plt.subplots(figsize=(8, 3))
        curve.plot(ax=ax, color="#1c5d99", linewidth=1.5)
        ax.set_title("Portfolio level (proxy)")
        ax.set_ylabel("Value ($)")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        b64 = base64.standard_b64encode(buf.read()).decode("ascii")

        trades_for_metrics = trades.copy()
        if "net_pnl" not in trades_for_metrics.columns:
            trades_for_metrics["net_pnl"] = 0.0
        if "hold_days" not in trades_for_metrics.columns:
            trades_for_metrics["hold_days"] = 0.0

        perf = metrics_mod.performance_summary(
            curve, trades_for_metrics, starting_capital=starting_capital
        )

        strat_rows: list[dict[str, Any]] = []
        if "strategy_tag" in trades.columns:
            for tag, g in trades.groupby("strategy_tag"):
                flow = 0.0
                if "signed_cash_flow" in g.columns:
                    flow = float(pd.to_numeric(g["signed_cash_flow"], errors="coerce").fillna(0.0).sum())
                elif "filled_price" in g.columns and "quantity" in g.columns:
                    flow = float((g["filled_price"].fillna(0) * g["quantity"]).sum())
                strat_rows.append({"tag": str(tag), "n": len(g), "flow": flow})

        env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        tpl = env.get_template("report.html.j2")
        html = tpl.render(
            portfolio_summary=summ,
            metrics=perf,
            equity_png_base64=b64,
            equity_note=eq_note,
            trades_recent=last30.to_dict("records"),
            trade_columns=trade_columns,
            strategy_rows=strat_rows,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        out_html.write_text(html, encoding="utf-8")

        want_pdf = export_pdf or bool(CONFIG.get("reports", {}).get("include_pdf", False))
        if want_pdf:
            try:
                from weasyprint import HTML

                HTML(string=html, base_url=str(self.output_dir)).write_pdf(
                    str(out_html.with_suffix(".pdf"))
                )
            except OSError:
                pass

        return str(out_html)
