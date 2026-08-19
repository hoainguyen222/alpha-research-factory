"""
====================================================================================================
PROJECT: ALPHA RESEARCH FACTORY
MODULE: Extracted Strategy Components Store (Kho Thành Phần Chiến Lược Đã Bóc Tách)
FILE: vault/strategy_components_db.py
====================================================================================================
CHỨC NĂNG:
1. Lưu trữ riêng biệt các thành phần cốt lõi của chiến lược sau khi bóc tách từ bài báo:
   - Code Snippets (Mã nguồn Python / C++ / Go / Pseudocode)
   - Công thức toán học (Math Formulas / LaTeX)
   - Tín hiệu & Quy tắc giao dịch (Trading Rules: Entry / Exit / Stop Loss)
   - Bảng tham số định lượng (Hyperparameters JSON: Lookback, Threshold...)
   - Kết quả tác giả công bố (Reported Sharpe, Win Rate, Benchmark)
2. Liên kết chặt chẽ với kho tài liệu thô (Foreign Key `vault_id` -> `research_vault.id`).
3. Cung cấp API truy vấn siêu tốc (< 2ms) phục vụ trực tiếp cho Engine Backtest C++ và Bot thực chiến.
====================================================================================================
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import QUANT_DB_PATH


class StrategyComponentsDB:
    """Quản lý cơ sở dữ liệu các thành phần chiến lược định lượng đã bóc tách."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or QUANT_DB_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Khởi tạo bảng extracted_strategy_components trong SQLite."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS extracted_strategy_components (
                    id TEXT PRIMARY KEY,
                    vault_id TEXT NOT NULL,
                    strategy_name TEXT NOT NULL,
                    model_family TEXT NOT NULL,
                    asset_class TEXT DEFAULT 'crypto',
                    timeframe TEXT DEFAULT '1d',
                    code_snippets TEXT DEFAULT '{}',
                    math_formulas TEXT DEFAULT '{}',
                    trading_rules TEXT DEFAULT '{}',
                    parameters TEXT DEFAULT '{}',
                    reported_metrics TEXT DEFAULT '{}',
                    backtest_status TEXT DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_comp_vault_id ON extracted_strategy_components(vault_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_comp_model_family ON extracted_strategy_components(model_family);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_comp_status ON extracted_strategy_components(backtest_status);")
            conn.commit()

    def _seed_foundational_components(self):
        """Khởi tạo một số thành phần mẫu từ các chiến lược đã xác thực."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM extracted_strategy_components;")
            count = cursor.fetchone()["count"]
            if count > 0:
                return

            now_iso = datetime.now().isoformat()
            seeds = [
                {
                    "id": "COMP-20260817-0001",
                    "vault_id": "RES-20260814-0033",
                    "strategy_name": "Attention LSTM Markowitz Pairs Trading",
                    "model_family": "Statistical_Arbitrage",
                    "asset_class": "crypto",
                    "timeframe": "1d",
                    "code_snippets": {
                        "lang": "python",
                        "python": "def generate_signal(spread, zscore):\n    if zscore < -1.5:\n        return 1   # Long Pair Spread\n    elif zscore > 1.5:\n        return -1  # Short Pair Spread\n    return 0",
                        "cpp": "int calculate_signal(double zscore) {\n    if (zscore < -1.5) return 1;\n    if (zscore > 1.5) return -1;\n    return 0;\n}"
                    },
                    "math_formulas": {
                        "spread": "Spread_t = Log(P_A) - beta * Log(P_B)",
                        "zscore": "Z_t = (Spread_t - mu_rolling) / sigma_rolling",
                        "markowitz": "max w^T mu - lambda * w^T Sigma w"
                    },
                    "trading_rules": {
                        "entry_long": "Z-score <= -1.5",
                        "entry_short": "Z-score >= 1.5",
                        "exit_condition": "Z-score crosses 0 OR holding_bars >= 14",
                        "trailing_stop": "1.5x ATR"
                    },
                    "parameters": {
                        "symbol": "BTCUSDT",
                        "pair_symbol": "ETHUSDT",
                        "rolling_window": 21,
                        "threshold_val": 1.5,
                        "is_reversion": True,
                        "holding_period_days": 14,
                        "fee_rate": 0.0008,
                        "slippage_rate": 0.0002
                    },
                    "reported_metrics": {
                        "reported_sharpe": 2.77,
                        "reported_win_rate": 0.9259,
                        "tested_markets": "S&P 500 & CSI 300"
                    },
                    "backtest_status": "VERIFIED"
                },
                {
                    "id": "COMP-20260817-0002",
                    "vault_id": "SSRN-3325656",
                    "strategy_name": "Cross-Sectional Factor Momentum Premium",
                    "model_family": "Momentum",
                    "asset_class": "crypto",
                    "timeframe": "1d",
                    "code_snippets": {
                        "lang": "python",
                        "python": "def calc_momentum_score(returns_60d):\n    return np.mean(returns_60d) / np.std(returns_60d)",
                        "cpp": "double calc_momentum_score(const std::vector<double>& ret) {\n    return compute_mean(ret) / compute_stdev(ret);\n}"
                    },
                    "math_formulas": {
                        "factor_momentum": "MOM_i = (P_{i,t} / P_{i,t-60}) - 1",
                        "weight": "w_i = (Rank(MOM_i) - Median_Rank) / Sum(|Rank - Median|)"
                    },
                    "trading_rules": {
                        "entry_long": "Top 10% Momentum Score",
                        "entry_short": "Bottom 10% Momentum Score",
                        "rebalance_frequency": "Every 30 Days",
                        "exit_condition": "Rank falls below 50th percentile"
                    },
                    "parameters": {
                        "symbol": "ETHUSDT",
                        "rolling_window": 60,
                        "threshold_val": 0.05,
                        "is_reversion": False,
                        "holding_period_days": 30,
                        "fee_rate": 0.0008
                    },
                    "reported_metrics": {
                        "reported_sharpe": 1.85,
                        "annual_return_pct": 34.2
                    },
                    "backtest_status": "VERIFIED"
                }
            ]

            for s in seeds:
                conn.execute("""
                    INSERT INTO extracted_strategy_components
                    (id, vault_id, strategy_name, model_family, asset_class, timeframe, code_snippets, math_formulas, trading_rules, parameters, reported_metrics, backtest_status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    s["id"],
                    s["vault_id"],
                    s["strategy_name"],
                    s["model_family"],
                    s["asset_class"],
                    s["timeframe"],
                    json.dumps(s["code_snippets"]),
                    json.dumps(s["math_formulas"]),
                    json.dumps(s["trading_rules"]),
                    json.dumps(s["parameters"]),
                    json.dumps(s["reported_metrics"]),
                    s["backtest_status"],
                    now_iso,
                    now_iso
                ))
            conn.commit()

    def insert_component(
        self,
        vault_id: str,
        strategy_name: str,
        model_family: str,
        asset_class: str = "crypto",
        timeframe: str = "1d",
        code_snippets: Optional[Dict[str, Any]] = None,
        math_formulas: Optional[Dict[str, Any]] = None,
        trading_rules: Optional[Dict[str, Any]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        reported_metrics: Optional[Dict[str, Any]] = None,
        backtest_status: str = "PENDING"
    ) -> str:
        """Thêm một bản ghi thành phần chiến lược bóc tách mới vào Database."""
        now_iso = datetime.now().isoformat()
        date_str = datetime.now().strftime("%Y%m%d")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Kiểm tra xem vault_id này đã có component chưa
            if vault_id:
                cursor.execute("SELECT id FROM extracted_strategy_components WHERE vault_id = ? LIMIT 1;", (vault_id,))
                existing_row = cursor.fetchone()
                if existing_row:
                    existing_id = existing_row["id"]
                    conn.execute("""
                        UPDATE extracted_strategy_components
                        SET strategy_name = ?, model_family = ?, asset_class = ?, timeframe = ?,
                            code_snippets = ?, math_formulas = ?, trading_rules = ?, parameters = ?,
                            reported_metrics = ?, backtest_status = ?, updated_at = ?
                        WHERE id = ?;
                    """, (
                        strategy_name, model_family, asset_class, timeframe,
                        json.dumps(code_snippets or {}), json.dumps(math_formulas or {}),
                        json.dumps(trading_rules or {}), json.dumps(parameters or {}),
                        json.dumps(reported_metrics or {}), backtest_status, now_iso, existing_id
                    ))
                    conn.commit()
                    return existing_id

            cursor.execute("SELECT id FROM extracted_strategy_components WHERE id LIKE ? ORDER BY id DESC LIMIT 1;", (f"COMP-{date_str}-%",))
            last_row = cursor.fetchone()
            if last_row:
                try:
                    num = int(last_row["id"].split("-")[-1]) + 1
                except Exception:
                    num = 1
            else:
                num = 1

            new_id = f"COMP-{date_str}-{num:04d}"

            conn.execute("""
                INSERT INTO extracted_strategy_components
                (id, vault_id, strategy_name, model_family, asset_class, timeframe, code_snippets, math_formulas, trading_rules, parameters, reported_metrics, backtest_status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                new_id,
                vault_id,
                strategy_name,
                model_family,
                asset_class,
                timeframe,
                json.dumps(code_snippets or {}),
                json.dumps(math_formulas or {}),
                json.dumps(trading_rules or {}),
                json.dumps(parameters or {}),
                json.dumps(reported_metrics or {}),
                backtest_status,
                now_iso,
                now_iso
            ))
            conn.commit()
            return new_id

    def list_components(self, limit: int = 50, model_family: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh sách các thành phần chiến lược đã bóc tách."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if model_family:
                cursor.execute("SELECT * FROM extracted_strategy_components WHERE model_family = ? ORDER BY created_at DESC LIMIT ?;", (model_family, limit))
            else:
                cursor.execute("SELECT * FROM extracted_strategy_components ORDER BY created_at DESC LIMIT ?;", (limit,))

            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                for json_col in ("code_snippets", "math_formulas", "trading_rules", "parameters", "reported_metrics"):
                    try:
                        item[json_col] = json.loads(item[json_col])
                    except Exception:
                        item[json_col] = {}
                results.append(item)
            return results

    def get_component(self, comp_id: str) -> Optional[Dict[str, Any]]:
        """Lấy chi tiết 1 thành phần chiến lược theo ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM extracted_strategy_components WHERE id = ?;", (comp_id,))
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            for json_col in ("code_snippets", "math_formulas", "trading_rules", "parameters", "reported_metrics"):
                try:
                    item[json_col] = json.loads(item[json_col])
                except Exception:
                    item[json_col] = {}
            return item

    def update_backtest_status(self, comp_id: str, status: str):
        """Cập nhật trạng thái kiểm định (PENDING / VERIFIED / FAILED)."""
        with self._get_connection() as conn:
            conn.execute("UPDATE extracted_strategy_components SET backtest_status = ?, updated_at = ? WHERE id = ?;", (status, datetime.now().isoformat(), comp_id))
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        """Thống kê tổng quan các thành phần chiến lược."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_components, COUNT(DISTINCT vault_id) as total_papers, COUNT(CASE WHEN backtest_status = 'VERIFIED' THEN 1 END) as total_verified FROM extracted_strategy_components;")
            row = cursor.fetchone()
            return {
                "total_components": row["total_components"] or 0,
                "total_papers": row["total_papers"] or 0,
                "total_verified": row["total_verified"] or 0
            }
