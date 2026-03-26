-- Trade journal schema for SQLite
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    limit_price REAL,
    filled_price REAL,
    signed_cash_flow REAL,
    status TEXT NOT NULL,
    strategy_tag TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    filled_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_tag);
CREATE INDEX IF NOT EXISTS idx_trades_created ON trades(created_at);
