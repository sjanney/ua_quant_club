"""Load `config.yaml` with optional environment variable overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

import yaml
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_FILE = _REPO_ROOT / "config.yaml"

load_dotenv(_REPO_ROOT / ".env")


def _parse_bool(v: str) -> bool:
    return v.lower() in ("1", "true", "yes", "on")


def _set_nested(cfg: dict[str, Any], path: list[str], value: Any) -> None:
    cur = cfg
    for key in path[:-1]:
        cur = cur.setdefault(key, {})
    cur[path[-1]] = value


def _apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    """Apply known env vars to nested config keys."""
    overrides: list[tuple[str, list[str], Callable[[str], Any]]] = [
        ("BACKTEST_START_DATE", ["backtest", "start_date"], str),
        ("BACKTEST_END_DATE", ["backtest", "end_date"], str),
        ("BACKTEST_OOS_START", ["backtest", "oos_start"], str),
        ("BACKTEST_OOS_END", ["backtest", "oos_end"], str),
        ("BACKTEST_TRANSACTION_COST", ["backtest", "transaction_cost"], float),
        ("BACKTEST_NOTIONAL_PER_TRADE", ["backtest", "notional_per_trade"], float),
        ("PAIRS_TRADING_COINT_P_THRESHOLD", ["pairs_trading", "coint_p_threshold"], float),
        ("PAIRS_TRADING_ZSCORE_WINDOW", ["pairs_trading", "zscore_window"], int),
        ("PAIRS_TRADING_ENTRY_Z", ["pairs_trading", "entry_z"], float),
        ("PAIRS_TRADING_EXIT_Z", ["pairs_trading", "exit_z"], float),
        ("PAIRS_TRADING_STOP_Z", ["pairs_trading", "stop_z"], float),
        ("PAIRS_TRADING_USE_BONFERRONI", ["pairs_trading", "use_bonferroni"], _parse_bool),
        ("PAIRS_TRADING_ENTRY_MODE", ["pairs_trading", "entry_mode"], str),
        ("PAIRS_TRADING_BETA_LOOKBACK", ["pairs_trading", "beta_lookback"], int),
        ("PAIRS_TRADING_REBALANCE_EVERY", ["pairs_trading", "rebalance_every"], int),
        ("PAIRS_TRADING_MAX_HALF_LIFE_DAYS", ["pairs_trading", "max_half_life_days"], float),
        ("EXECUTION_DRY_RUN", ["execution", "dry_run"], _parse_bool),
        ("EXECUTION_DELAY_MIN_S", ["execution", "delay_min_s"], float),
        ("EXECUTION_DELAY_MAX_S", ["execution", "delay_max_s"], float),
        ("EXECUTION_SCREENSHOT_ON_FAILURE", ["execution", "screenshot_on_failure"], _parse_bool),
        ("LOGGING_LOG_DIR", ["logging", "log_dir"], str),
        ("LOGGING_DB_PATH", ["logging", "db_path"], str),
        ("LOGGING_MAX_BYTES", ["logging", "max_bytes"], int),
        ("LOGGING_BACKUP_COUNT", ["logging", "backup_count"], int),
        ("REPORTS_OUTPUT_DIR", ["reports", "output_dir"], str),
        ("REPORTS_INCLUDE_PDF", ["reports", "include_pdf"], _parse_bool),
    ]
    for env_name, path, caster in overrides:
        raw = os.getenv(env_name)
        if raw is None or raw == "":
            continue
        try:
            _set_nested(cfg, path, caster(raw))
        except (TypeError, ValueError):
            continue
    return cfg


def _load_yaml() -> dict[str, Any]:
    if not _CONFIG_FILE.is_file():
        raise FileNotFoundError(f"Missing config file: {_CONFIG_FILE}")
    with _CONFIG_FILE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _deep_copy(d: dict[str, Any]) -> dict[str, Any]:
    import copy

    return copy.deepcopy(d)


_cfg = _load_yaml()
CONFIG: dict[str, Any] = _apply_env_overrides(_deep_copy(_cfg))
