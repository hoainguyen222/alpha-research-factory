"""
====================================================================================================
PROJECT: ALPHA RESEARCH FACTORY
MODULE: Dynamic Rule Learning & Pattern Memory Engine
FILE: vault/learned_rule_engine.py
====================================================================================================
CHỨC NĂNG:
1. Tự động lưu trữ các Rule / Heuristic / Strategy Pattern mới sau mỗi lần bóc tách thành công.
2. Fast-Matching Engine: Khi gặp bài báo/nội dung mới có từ khóa & cấu trúc tương đồng,
   tự động khớp và áp dụng ngay Rule đã học trong 0.001 giây (bỏ qua LLM, tiết kiệm token, 
   tránh bot suy nghĩ linh tinh / hallucination).
3. Đếm số lần tái sử dụng (hit_count) và tính điểm tin cậy (confidence score).
====================================================================================================
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import QUANT_DB_PATH


class LearnedRuleEngine:
    """Hệ thống Bộ Nhớ Tri Thức & Máy Học Luật Tự Động (Continuous Learning)."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or QUANT_DB_PATH)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Khởi tạo bảng learned_rules trong SQLite nếu chưa có."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learned_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    pattern_type TEXT NOT NULL,
                    trigger_keywords TEXT NOT NULL,
                    rule_payload TEXT NOT NULL,
                    confidence REAL DEFAULT 0.90,
                    source_id TEXT,
                    hit_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rule_type ON learned_rules(pattern_type);")
            conn.commit()

    def _seed_foundational_rules(self):
        """Khởi tạo một số luật nền tảng cơ sở nếu bảng còn trống."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM learned_rules;")
            count = cursor.fetchone()["count"]
            if count > 0:
                return

            seed_rules = [
                {
                    "id": "RULE-SEED-0001",
                    "name": "Markowitz Cointegrated Pairs Mean Reversion",
                    "pattern_type": "STRATEGY_MAPPING",
                    "trigger_keywords": ["pairs trading", "cointegrat", "markowitz", "mean reversion", "lstm", "johansen", "engle-granger"],
                    "rule_payload": {
                        "model_type": "Statistical Mean Reversion Z-Score",
                        "symbol": "BTCUSDT",
                        "asset_class": "crypto",
                        "timeframe": "1d",
                        "rolling_window": 21,
                        "threshold_val": 1.5,
                        "is_reversion": True,
                        "holding_period_days": 14,
                        "rationale": "Learned pattern: Cointegration spread with attention LSTM and Markowitz optimization"
                    },
                    "confidence": 0.95,
                    "source_id": "RES-20260814-0033"
                },
                {
                    "id": "RULE-SEED-0002",
                    "name": "Cross-Sectional Long-Short Momentum Anomaly",
                    "pattern_type": "STRATEGY_MAPPING",
                    "trigger_keywords": ["cross-sectional", "momentum", "long-short", "factor investing", "lookback", "asset pricing"],
                    "rule_payload": {
                        "model_type": "Time-Series Momentum & Factor Volatility Premium",
                        "symbol": "ETHUSDT",
                        "asset_class": "crypto",
                        "timeframe": "1d",
                        "rolling_window": 60,
                        "threshold_val": 0.05,
                        "is_reversion": False,
                        "holding_period_days": 30,
                        "rationale": "Learned pattern: 60-day cross-sectional momentum premium"
                    },
                    "confidence": 0.92,
                    "source_id": "SSRN-3325656"
                },
                {
                    "id": "RULE-SEED-0003",
                    "name": "High-Frequency Order Book Imbalance",
                    "pattern_type": "STRATEGY_MAPPING",
                    "trigger_keywords": ["order book", "imbalance", "microstructure", "bid-ask", "high frequency", "limit order"],
                    "rule_payload": {
                        "model_type": "Microstructure Order Flow Imbalance",
                        "symbol": "BTCUSDT",
                        "asset_class": "crypto",
                        "timeframe": "15m",
                        "rolling_window": 10,
                        "threshold_val": 0.25,
                        "is_reversion": True,
                        "holding_period_days": 1,
                        "rationale": "Learned pattern: Order book queue imbalance short-term reversion"
                    },
                    "confidence": 0.90,
                    "source_id": "BASE-MICROSTRUCTURE"
                }
            ]

            now_iso = datetime.now().isoformat()
            for r in seed_rules:
                conn.execute("""
                    INSERT INTO learned_rules 
                    (id, name, pattern_type, trigger_keywords, rule_payload, confidence, source_id, hit_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?);
                """, (
                    r["id"],
                    r["name"],
                    r["pattern_type"],
                    json.dumps(r["trigger_keywords"]),
                    json.dumps(r["rule_payload"]),
                    r["confidence"],
                    r["source_id"],
                    now_iso,
                    now_iso
                ))
            conn.commit()

    def match_rule(self, text_content: str, min_score: float = 0.50) -> Optional[Dict[str, Any]]:
        """
        Quét nhanh văn bản bài báo để tìm Rule đã học phù hợp nhất (Fast-Path).
        Trả về rule_payload và metadata nếu score >= min_score, ngược lại trả về None.
        Tự động tăng hit_count cho rule tương ứng.
        """
        if not text_content or len(text_content.strip()) < 30:
            return None

        text_lower = text_content.lower()
        best_rule = None
        highest_score = 0.0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM learned_rules WHERE pattern_type = 'STRATEGY_MAPPING';")
            rules = cursor.fetchall()

            for row in rules:
                rule_dict = dict(row)
                try:
                    keywords = json.loads(rule_dict["trigger_keywords"])
                except Exception:
                    continue

                if not keywords:
                    continue

                # Đếm số từ khóa xuất hiện
                matched_count = 0
                for kw in keywords:
                    if kw.lower() in text_lower:
                        matched_count += 1

                score = matched_count / len(keywords)
                if score > highest_score and score >= min_score:
                    highest_score = score
                    best_rule = rule_dict

            # Nếu tìm thấy rule xuất sắc, tăng hit_count và trả về
            if best_rule and highest_score >= min_score:
                rule_id = best_rule["id"]
                conn.execute("UPDATE learned_rules SET hit_count = hit_count + 1, updated_at = ? WHERE id = ?;", (datetime.now().isoformat(), rule_id))
                conn.commit()

                try:
                    payload = json.loads(best_rule["rule_payload"])
                except Exception:
                    payload = {}

                return {
                    "matched": True,
                    "rule_id": best_rule["id"],
                    "rule_name": best_rule["name"],
                    "match_score": round(highest_score, 2),
                    "confidence": best_rule["confidence"],
                    "payload": payload,
                    "source_id": best_rule["source_id"]
                }

        return None

    def learn_rule(
        self,
        name: str,
        trigger_keywords: List[str],
        rule_payload: Dict[str, Any],
        source_id: str = "",
        pattern_type: str = "STRATEGY_MAPPING",
        confidence: float = 0.90
    ) -> str:
        """
        Ghi nhận một Rule mới vào cơ sở tri thức để tái sử dụng trong tương lai.
        """
        now_iso = datetime.now().isoformat()
        clean_keywords = list(dict.fromkeys([k.strip().lower() for k in trigger_keywords if len(k.strip()) > 2]))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Kiểm tra xem rule cùng tên hoặc keywords tương tự đã có chưa
            cursor.execute("SELECT id, trigger_keywords, hit_count FROM learned_rules WHERE LOWER(name) = ?;", (name.strip().lower(),))
            existing = cursor.fetchone()

            if existing:
                rule_id = existing["id"]
                conn.execute("""
                    UPDATE learned_rules 
                    SET rule_payload = ?, confidence = ?, source_id = ?, updated_at = ?, hit_count = hit_count + 1
                    WHERE id = ?;
                """, (json.dumps(rule_payload), confidence, source_id, now_iso, rule_id))
                conn.commit()
                return rule_id

            # Sinh mã ID mới (RULE-XXXX)
            cursor.execute("SELECT id FROM learned_rules WHERE id LIKE 'RULE-%' ORDER BY id DESC LIMIT 1;")
            last_row = cursor.fetchone()
            if last_row:
                try:
                    num = int(last_row["id"].split("-")[-1]) + 1
                except Exception:
                    num = 1
            else:
                num = 1

            new_id = f"RULE-{num:04d}"
            conn.execute("""
                INSERT INTO learned_rules 
                (id, name, pattern_type, trigger_keywords, rule_payload, confidence, source_id, hit_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?);
            """, (
                new_id,
                name.strip(),
                pattern_type,
                json.dumps(clean_keywords),
                json.dumps(rule_payload),
                confidence,
                source_id,
                now_iso,
                now_iso
            ))
            conn.commit()
            return new_id

    def list_rules(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy danh sách tất cả các luật đã học."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM learned_rules ORDER BY hit_count DESC, updated_at DESC LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                try:
                    item["trigger_keywords"] = json.loads(item["trigger_keywords"])
                    item["rule_payload"] = json.loads(item["rule_payload"])
                except Exception:
                    pass
                results.append(item)
            return results

    def get_stats(self) -> Dict[str, Any]:
        """Thống kê tổng quan về bộ nhớ luật."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_rules, SUM(hit_count) as total_hits FROM learned_rules;")
            row = cursor.fetchone()
            return {
                "total_rules": row["total_rules"] or 0,
                "total_hits": row["total_hits"] or 0
            }
