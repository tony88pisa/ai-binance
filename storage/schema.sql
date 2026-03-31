CREATE TABLE IF NOT EXISTS market_data (
    asset TEXT PRIMARY KEY,
    price REAL NOT NULL,
    rsi_5m REAL,
    rsi_1h REAL,
    macd_5m REAL,
    macd_1h REAL,
    atr_5m REAL,
    decision TEXT,
    confidence INTEGER,
    regime TEXT,
    consensus_score REAL,
    position_size_pct REAL,
    atr_stop_distance REAL,
    why_not_trade TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    asset TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence INTEGER,
    size_pct REAL,
    thesis TEXT,
    regime TEXT,
    timestamp TEXT NOT NULL,
    entry_price REAL DEFAULT 0.0,
    atr_stop_distance REAL DEFAULT 0.0,
    status TEXT DEFAULT 'OPEN'
);

CREATE TABLE IF NOT EXISTS trade_outcomes (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL UNIQUE,
    realized_pnl_pct REAL NOT NULL,
    was_profitable BOOLEAN NOT NULL,
    closed_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_trade_outcomes_decision_id ON trade_outcomes(decision_id);

CREATE TABLE IF NOT EXISTS service_state (
    service TEXT PRIMARY KEY,
    status TEXT DEFAULT 'active',
    last_heartbeat TEXT NOT NULL,
    state_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_candidates (
    skill_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL,
    skill_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    passed INTEGER NOT NULL,
    win_rate REAL NOT NULL,
    max_drawdown REAL NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_promotions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    promoted_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS supervisor_controls (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    emergency_stop INTEGER DEFAULT 0,
    max_open_trades INTEGER DEFAULT 3,
    min_confidence INTEGER DEFAULT 70,
    close_losers_threshold REAL DEFAULT -5.0,
    regime_filter_active INTEGER DEFAULT 1,
    last_update TEXT NOT NULL,
    ai_reasoning TEXT
);

CREATE TABLE IF NOT EXISTS supervisor_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    wallet_state TEXT NOT NULL,
    ai_assessment TEXT NOT NULL,
    actions_taken TEXT NOT NULL
);
