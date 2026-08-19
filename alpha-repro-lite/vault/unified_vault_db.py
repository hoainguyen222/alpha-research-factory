"""
====================================================================================================
MODULE: Unified Vault Database & Search Engine
FILE: vault/unified_vault_db.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 3):
1. Lưu trữ Master Data tập trung hợp nhất:
   - SQLite Database với công nghệ FTS5 (Full-Text Search) Virtual Table: truy xuất tức thì (<5ms).
   - JSONL Stream (unified_vault.jsonl): Định dạng dòng chuẩn tối ưu cho AI/Machine Reading.
   - CSV Summary (unified_vault.csv): Xem nhanh trong Excel / Pandas.
2. Cung cấp API truy xuất siêu tốc:
   - Tìm kiếm theo ID (ví dụ: `get_by_id("RES-20260813-0001")`).
   - Tìm kiếm theo Keyword (toàn văn bản CTX, TITLE, NOTE, WEB) với FTS5 xếp hạng độ liên quan (BM25).
   - Lọc theo TYPE (PAPER, BLOG, VIDEO, FILE_PDF, FILE_EXCEL, etc.) và dải ngày tạo.
3. Cơ chế tạo ID tự động tăng dần: RES-YYYYMMDD-XXXX.
====================================================================================================
"""

import os
import json
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from config import SQLITE_DB_PATH, JSONL_VAULT_PATH, CSV_VAULT_PATH, STRUCTURED_VAULT_DIR


class UnifiedVaultDB:
    """Quản lý Kho lưu trữ dữ liệu nghiên cứu chuẩn hóa hợp nhất."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else SQLITE_DB_PATH
        self.jsonl_path = JSONL_VAULT_PATH
        self.csv_path = CSV_VAULT_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_sqlite_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối SQLite an toàn với WAL mode (Write-Ahead Logging)."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_sqlite_schema(self):
        """Khởi tạo bảng lưu trữ chính và bảng FTS5 Virtual Table."""
        with self._get_connection() as conn:
            # 1. Bảng chính lưu trữ đầy đủ các cột chuẩn
            conn.execute("""
                CREATE TABLE IF NOT EXISTS research_vault (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    ctx TEXT NOT NULL,
                    note TEXT,
                    web TEXT,
                    metadata TEXT,
                    raw_file_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
            """)

            # Tạo index tối ưu lọc theo type và created_at
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON research_vault(type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON research_vault(created_at);")

            # 2. Bảng ảo FTS5 hỗ trợ Full-Text Search siêu tốc
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS research_vault_fts USING fts5(
                        id UNINDEXED,
                        title,
                        ctx,
                        note,
                        web,
                        type UNINDEXED,
                        content='research_vault',
                        content_rowid='rowid'
                    );
                """)

                # Triggers đồng bộ tự động giữa research_vault và research_vault_fts
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS trg_vault_ai AFTER INSERT ON research_vault BEGIN
                        INSERT INTO research_vault_fts(rowid, id, title, ctx, note, web, type)
                        VALUES (new.rowid, new.id, new.title, new.ctx, new.note, new.web, new.type);
                    END;
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS trg_vault_ad AFTER DELETE ON research_vault BEGIN
                        INSERT INTO research_vault_fts(research_vault_fts, rowid, id, title, ctx, note, web, type)
                        VALUES('delete', old.rowid, old.id, old.title, old.ctx, old.note, old.web, old.type);
                    END;
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS trg_vault_au AFTER UPDATE ON research_vault BEGIN
                        INSERT INTO research_vault_fts(research_vault_fts, rowid, id, title, ctx, note, web, type)
                        VALUES('delete', old.rowid, old.id, old.title, old.ctx, old.note, old.web, old.type);
                        INSERT INTO research_vault_fts(rowid, id, title, ctx, note, web, type)
                        VALUES (new.rowid, new.id, new.title, new.ctx, new.note, new.web, new.type);
                    END;
                """)
            except Exception as e:
                # FTS5 fallback nếu môi trường có giới hạn
                print(f"[VAULT DB] FTS5 initialization note: {e}")

            conn.commit()

    def generate_next_id(self) -> str:
        """Tạo mã ID kế tiếp theo cấu trúc RES-YYYYMMDD-XXXX."""
        today_str = datetime.now().strftime("%Y%m%d")
        prefix = f"RES-{today_str}-"
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM research_vault WHERE id LIKE ? ORDER BY id DESC LIMIT 1;", (f"{prefix}%",))
            row = cursor.fetchone()
            if row:
                last_id = row["id"]
                try:
                    last_num = int(last_id.split("-")[-1])
                    next_num = last_num + 1
                except ValueError:
                    next_num = 1
            else:
                next_num = 1
        return f"{prefix}{next_num:04d}"

    def find_existing_entry(self, title: str = "", web: str = "", ctx: str = "") -> Optional[Dict[str, Any]]:
        """
        Kiểm tra xem tài liệu này đã tồn tại trong Vault hay chưa (Deduplication đa tầng).
        Bảo vệ chống tải trùng giữa arXiv, CrossRef, OpenAlex và lọc bài giống nhau > 90%:
        1. Khớp URL nguồn / DOI / arXiv ID tuyệt đối.
        2. Khớp Tiêu đề tuyệt đối và Khớp mờ Tiêu đề (Fuzzy Title Similarity >= 80%).
        3. Khớp vân tay nội dung (Content Similarity >= 85% trên đoạn đầu/abstract).
        """
        import difflib
        import re

        norm_title = re.sub(r'[^a-zA-Z0-9\s]', '', title.lower()).strip() if title else ""
        norm_web = web.strip().lower() if web and not web.startswith("QUERY:") else ""
        def _clean_content(txt: str) -> str:
            txt = re.sub(r'---\s*\[Page\s*\d+\s*/\s*\d+\]\s*---', '', txt)
            txt = re.sub(r'[^a-zA-Z0-9\s]', ' ', txt.lower())
            return re.sub(r'\s+', ' ', txt).strip()

        ctx_sample = _clean_content(ctx)[:400] if ctx and len(ctx.strip()) > 80 else ""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Check theo URL nguồn hoặc DOI cụ thể
            if norm_web and len(norm_web) > 10:
                cursor.execute("SELECT * FROM research_vault WHERE LOWER(web) = ? LIMIT 1;", (norm_web,))
                row = cursor.fetchone()
                if row:
                    return dict(row)

            # 2. Check tất cả bản ghi hiện có trong Vault để so khớp mờ Title & Content
            cursor.execute("SELECT id, title, web, ctx, type, note, raw_file_path FROM research_vault;")
            all_entries = cursor.fetchall()
            
            for ent in all_entries:
                db_title = ent["title"] or ""
                db_norm_title = re.sub(r'[^a-zA-Z0-9\s]', '', db_title.lower()).strip()
                
                # A. Trùng tuyệt đối Title
                if norm_title and db_norm_title and norm_title == db_norm_title:
                    return dict(ent)
                
                # B. Trùng mờ Title (Fuzzy Title Match >= 80%)
                if norm_title and db_norm_title and len(norm_title) > 12 and len(db_norm_title) > 12:
                    ratio = difflib.SequenceMatcher(None, norm_title, db_norm_title).ratio()
                    if ratio >= 0.80:
                        return dict(ent)
                    
                    # Token Jaccard check
                    s1, s2 = set(norm_title.split()), set(db_norm_title.split())
                    if s1 and s2:
                        jaccard = len(s1.intersection(s2)) / len(s1.union(s2))
                        if jaccard >= 0.75:
                            return dict(ent)

                # C. Trùng vân tay nội dung (Content Similarity >= 85% hoặc giống nhau > 90%)
                if ctx_sample:
                    db_ctx = ent["ctx"] or ""
                    db_ctx_sample = _clean_content(db_ctx)[:1200]
                    if db_ctx_sample and len(db_ctx_sample) > 80:
                        # 1. Substring containment
                        if ctx_sample[:120] in db_ctx_sample or db_ctx_sample[:120] in ctx_sample:
                            return dict(ent)
                        # 2. Token Containment ratio (Overlap >= 85%)
                        t1, t2 = set(ctx_sample.split()), set(db_ctx_sample.split())
                        if t1 and t2:
                            overlap = len(t1.intersection(t2)) / min(len(t1), len(t2))
                            if overlap >= 0.85:
                                return dict(ent)
                        # 3. SequenceMatcher ratio
                        ctx_ratio = difflib.SequenceMatcher(None, ctx_sample[:400], db_ctx_sample[:400]).ratio()
                        if ctx_ratio >= 0.85:
                            return dict(ent)

        return None

    def cleanup_duplicates(self) -> int:
        """
        Dọn dẹp các bản ghi trùng lặp trong Vault (chỉ giữ lại bản ghi có ID nhỏ nhất).
        Trả về số lượng bản ghi trùng đã xóa.
        """
        deleted_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Tìm các nhóm bài có title trùng nhau
            cursor.execute("""
                SELECT title, COUNT(*) as cnt 
                FROM research_vault 
                WHERE title IS NOT NULL AND LENGTH(TRIM(title)) > 5
                GROUP BY LOWER(TRIM(title)) 
                HAVING cnt > 1;
            """)
            dup_groups = cursor.fetchall()
            
            for grp in dup_groups:
                title = grp["title"]
                cursor.execute("""
                    SELECT id FROM research_vault 
                    WHERE LOWER(TRIM(title)) = LOWER(TRIM(?))
                    ORDER BY id ASC;
                """, (title,))
                rows = cursor.fetchall()
                if len(rows) > 1:
                    # Giữ lại row đầu tiên (id nhỏ nhất), xóa các row sau
                    keep_id = rows[0]["id"]
                    dup_ids = [r["id"] for r in rows[1:]]
                    for d_id in dup_ids:
                        cursor.execute("DELETE FROM research_vault WHERE id = ?;", (d_id,))
                        deleted_count += 1

            conn.commit()

        if deleted_count > 0:
            self._sync_exports()
            print(f"[VAULT DB] Đã dọn dẹp {deleted_count} bản ghi trùng lặp.")
        return deleted_count

    def insert_entry(self, entry: Dict[str, Any], check_dup: bool = True) -> str:
        """
        Thêm mới 1 bản ghi vào Vault, tự động đồng bộ sang SQLite, JSONL và CSV.
        Nếu check_dup=True, tự động trả về ID đã có nếu phát hiện trùng lặp.
        """
        if check_dup:
            existing = self.find_existing_entry(
                title=entry.get("TITLE", ""),
                web=entry.get("WEB", ""),
                ctx=entry.get("CTX", "")
            )
            if existing:
                print(f"[VAULT DB] Phát hiện trùng lặp với bản ghi {existing['id']}: '{existing['title']}'. Bỏ qua.")
                return existing["id"]

        entry_id = entry.get("ID") or self.generate_next_id()
        entry["ID"] = entry_id
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO research_vault 
                (id, title, type, ctx, note, web, metadata, raw_file_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                entry["ID"],
                entry.get("TITLE", "Untitled"),
                entry.get("TYPE", "OTHER"),
                entry.get("CTX", ""),
                entry.get("NOTE", ""),
                entry.get("WEB", ""),
                entry.get("METADATA", "{}"),
                entry.get("RAW_FILE_PATH", ""),
                entry.get("CREATED_AT", datetime.now().isoformat()),
                entry.get("UPDATED_AT", datetime.now().isoformat())
            ))
            conn.commit()

        # Đồng bộ hóa sang JSONL và CSV
        self._sync_exports()
        return entry_id

    def get_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Truy xuất chính xác 1 bản ghi theo ID duy nhất."""
        if not entry_id:
            return None
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM research_vault WHERE id = ?;", (entry_id.strip(),))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def search(
        self,
        keyword: str = "",
        source_type: str = "",
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Tìm kiếm toàn văn bản theo keyword và/hoặc type.
        Trả về: (Danh sách bản ghi, Tổng số kết quả tìm thấy)
        """
        keyword = keyword.strip() if keyword else ""
        source_type = source_type.strip().upper() if source_type else ""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Kịch bản 1: Tìm kiếm theo Keyword bằng FTS5
            if keyword:
                # Kiểm tra FTS5 khả dụng
                try:
                    # Chuẩn hóa keyword cho cú pháp FTS5
                    safe_query = f'"{keyword}"' if " " in keyword else f"{keyword}*"
                    
                    if source_type and source_type != "ALL":
                        sql_count = """
                            SELECT COUNT(*) as total FROM research_vault_fts 
                            WHERE research_vault_fts MATCH ? AND type = ?;
                        """
                        cursor.execute(sql_count, (safe_query, source_type))
                        total = cursor.fetchone()["total"]

                        sql_data = """
                            SELECT r.* FROM research_vault r
                            JOIN research_vault_fts f ON r.rowid = f.rowid
                            WHERE f.research_vault_fts MATCH ? AND r.type = ?
                            ORDER BY bm25(research_vault_fts) ASC
                            LIMIT ? OFFSET ?;
                        """
                        cursor.execute(sql_data, (safe_query, source_type, limit, offset))
                    else:
                        sql_count = "SELECT COUNT(*) as total FROM research_vault_fts WHERE research_vault_fts MATCH ?;"
                        cursor.execute(sql_count, (safe_query,))
                        total = cursor.fetchone()["total"]

                        sql_data = """
                            SELECT r.* FROM research_vault r
                            JOIN research_vault_fts f ON r.rowid = f.rowid
                            WHERE f.research_vault_fts MATCH ?
                            ORDER BY bm25(research_vault_fts) ASC
                            LIMIT ? OFFSET ?;
                        """
                        cursor.execute(sql_data, (safe_query, limit, offset))

                    results = [dict(r) for r in cursor.fetchall()]
                    return results, total

                except Exception as fts_err:
                    # Fallback sang LIKE search thông thường nếu FTS5 gặp lỗi ký tự
                    like_term = f"%{keyword}%"
                    if source_type and source_type != "ALL":
                        cursor.execute("SELECT COUNT(*) as total FROM research_vault WHERE (title LIKE ? OR ctx LIKE ? OR note LIKE ? OR id LIKE ?) AND type = ?;", (like_term, like_term, like_term, like_term, source_type))
                        total = cursor.fetchone()["total"]
                        cursor.execute("SELECT * FROM research_vault WHERE (title LIKE ? OR ctx LIKE ? OR note LIKE ? OR id LIKE ?) AND type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;", (like_term, like_term, like_term, like_term, source_type, limit, offset))
                    else:
                        cursor.execute("SELECT COUNT(*) as total FROM research_vault WHERE (title LIKE ? OR ctx LIKE ? OR note LIKE ? OR id LIKE ?);", (like_term, like_term, like_term, like_term))
                        total = cursor.fetchone()["total"]
                        cursor.execute("SELECT * FROM research_vault WHERE (title LIKE ? OR ctx LIKE ? OR note LIKE ? OR id LIKE ?) ORDER BY created_at DESC LIMIT ? OFFSET ?;", (like_term, like_term, like_term, like_term, limit, offset))
                    return [dict(r) for r in cursor.fetchall()], total

            # Kịch bản 2: Không có keyword (Lấy tất cả hoặc lọc theo type)
            else:
                if source_type and source_type != "ALL":
                    cursor.execute("SELECT COUNT(*) as total FROM research_vault WHERE type = ?;", (source_type,))
                    total = cursor.fetchone()["total"]
                    cursor.execute("SELECT * FROM research_vault WHERE type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?;", (source_type, limit, offset))
                else:
                    cursor.execute("SELECT COUNT(*) as total FROM research_vault;")
                    total = cursor.fetchone()["total"]
                    cursor.execute("SELECT * FROM research_vault ORDER BY created_at DESC LIMIT ? OFFSET ?;", (limit, offset))

                results = [dict(r) for r in cursor.fetchall()]
                return results, total

    def update_note(self, entry_id: str, new_note: str) -> bool:
        """Cập nhật ghi chú NOTE cho 1 bản ghi."""
        now_iso = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE research_vault SET note = ?, updated_at = ? WHERE id = ?;", (new_note, now_iso, entry_id))
            conn.commit()
            updated = cursor.rowcount > 0
        if updated:
            self._sync_exports()
        return updated

    def delete_entry(self, entry_id: str) -> bool:
        """Xóa 1 bản ghi khỏi cơ sở dữ liệu."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM research_vault WHERE id = ?;", (entry_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        if deleted:
            self._sync_exports()
        return deleted

    def get_statistics(self) -> Dict[str, Any]:
        """Thống kê tổng quan kho dữ liệu."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total_entries FROM research_vault;")
            total_entries = cursor.fetchone()["total_entries"]

            cursor.execute("SELECT type, COUNT(*) as count FROM research_vault GROUP BY type ORDER BY count DESC;")
            type_breakdown = {row["type"]: row["count"] for row in cursor.fetchall()}

            # Tính tổng số từ trong toàn bộ CTX
            cursor.execute("SELECT ctx FROM research_vault;")
            total_words = sum(len((row["ctx"] or "").split()) for row in cursor.fetchall())

        db_size_kb = round(self.db_path.stat().st_size / 1024, 2) if self.db_path.exists() else 0.0

        return {
            "total_entries": total_entries,
            "total_words": total_words,
            "type_breakdown": type_breakdown,
            "db_size_kb": db_size_kb,
            "db_path": str(self.db_path),
            "jsonl_path": str(self.jsonl_path),
            "csv_path": str(self.csv_path)
        }

    def _sync_exports(self):
        """Tự động đồng bộ toàn bộ dữ liệu ra file unified_vault.jsonl và unified_vault.csv."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_vault ORDER BY created_at ASC;")
                rows = [dict(r) for r in cursor.fetchall()]

            # 1. Ghi unified_vault.jsonl (line-delimited JSON)
            with open(self.jsonl_path, "w", encoding="utf-8", errors="replace") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

            # 2. Ghi unified_vault.csv (trích xuất ngắn gọn cho spreadsheet)
            csv_data = []
            for r in rows:
                snippet = (r["ctx"] or "")[:200].replace("\n", " ") + "..." if len(r["ctx"] or "") > 200 else (r["ctx"] or "")
                csv_data.append({
                    "ID": r["id"],
                    "TITLE": r["title"],
                    "TYPE": r["type"],
                    "CTX_PREVIEW": snippet,
                    "NOTE": (r["note"] or "").replace("\n", " | "),
                    "WEB": r["web"],
                    "RAW_FILE_PATH": r["raw_file_path"],
                    "CREATED_AT": r["created_at"]
                })
            
            df = pd.DataFrame(csv_data)
            df.to_csv(self.csv_path, index=False, encoding="utf-8-sig")

        except Exception as e:
            print(f"[VAULT DB] Error syncing exports (JSONL/CSV): {e}")
