-- Quantitative Research Platform Database Schema (Institutional Quant Standard)

CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT,
    url TEXT,
    asset_class TEXT NOT NULL,       -- 'crypto', 'equities', 'forex', 'commodities'
    target_timeframe TEXT NOT NULL,  -- '1m', '5m', '15m', '1h', '1d'
    status TEXT NOT NULL,            -- 'intake', 'audited', 'coding', 'backtested', 'rejected', 'production'
    feasibility_score INTEGER,       -- 1 to 100
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL,
    stage_number INTEGER NOT NULL,   -- 0 to 10
    stage_name TEXT NOT NULL,        -- e.g., 'Source Intake', 'Logic Audit', 'Stress Test'
    status TEXT NOT NULL,            -- 'completed', 'failed', 'blocked'
    execution_time_ms REAL,
    audit_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(paper_id) REFERENCES papers(id)
);

CREATE TABLE IF NOT EXISTS backtest_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    total_ticks INTEGER NOT NULL,
    execution_time_ms REAL NOT NULL,
    throughput_ticks_sec REAL NOT NULL,
    events_triggered INTEGER NOT NULL,
    
    -- Comprehensive Financial Performance Metrics
    total_return_pct REAL,       -- Total Return (%)
    annualized_return_pct REAL,  -- Annualized Return (%)
    max_drawdown_pct REAL,       -- Maximum Drawdown (%)
    sharpe_ratio REAL,           -- Sharpe Ratio (Risk-adjusted return)
    sortino_ratio REAL,          -- Sortino Ratio (Downside risk-adjusted return)
    calmar_ratio REAL,           -- Calmar Ratio (Annualized Return / Max Drawdown)
    profit_factor REAL,          -- Profit Factor (Gross Profit / Gross Loss)
    hit_rate_pct REAL,           -- Hit Rate / Win Rate (%)
    win_loss_ratio REAL,         -- Win/Loss Avg Ratio (Avg Win / Avg Loss)
    alpha_pct REAL,              -- Alpha vs Benchmark (%)
    beta REAL,                   -- Beta vs Market
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(paper_id) REFERENCES papers(id)
);

-- Web Spider Watchdog: Fingerprint Ledger (Sổ Cái Vân Tay)
CREATE TABLE IF NOT EXISTS scraped_papers (
    fingerprint TEXT PRIMARY KEY,        -- URL hoặc Hash(title+date) làm vân tay duy nhất
    title TEXT NOT NULL,                 -- Tiêu đề bài báo
    source_name TEXT NOT NULL,           -- Nguồn (arXiv, SSRN, Quantocracy...)
    source_url TEXT NOT NULL,            -- URL gốc của bài báo
    pdf_url TEXT,                        -- Link tải PDF (nếu có)
    downloaded BOOLEAN DEFAULT 0,        -- Đã tải PDF thành công chưa
    processed BOOLEAN DEFAULT 0,         -- Đã đưa qua Alpha Factory chưa
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
