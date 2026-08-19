"""
====================================================================================================
MODULE: Raw Source Archive Manager
FILE: vault/raw_archive_manager.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 2):
1. Xuất và lưu trữ toàn bộ dữ liệu văn bản thô (raw text) trích xuất được từ từng source input:
   - Paper, Blog, Video (transcript), File (Word, Excel, PDF, CSV, TXT, JSON), Ảnh (OCR).
2. Mỗi nguồn input tạo ra đúng 1 file .txt độc lập lưu trong thư mục `storage/raw_sources/`.
3. Tên file quy chuẩn: `<ID>_<sanitized_title>.txt`.
4. Header chuẩn hóa chứa metadata gốc (ID, Source Type, Original URL/File, Date, Word count, Method).
5. Hỗ trợ đọc lại, đối chiếu, tải về (download raw file) và kiểm toán tính toàn vẹn.
====================================================================================================
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from config import RAW_SOURCES_DIR


class RawArchiveManager:
    """Quản lý lưu trữ và xuất file văn bản thô (Raw text archive) cho từng nguồn dữ liệu."""

    def __init__(self, raw_dir: Optional[Path] = None):
        self.raw_dir = Path(raw_dir) if raw_dir else RAW_SOURCES_DIR
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sanitize_filename(title: str, max_length: int = 50) -> str:
        """Làm sạch tiêu đề để đặt tên file an toàn trên Windows / Linux."""
        if not title:
            return "untitled"
        # Xóa các ký tự cấm của hệ điều hành
        clean = re.sub(r'[\\/*?:"<>|]', "", title)
        # Thay thế khoảng trắng và ký tự đặc biệt thành dấu gạch dưới
        clean = re.sub(r'[\s\t\n\r]+', "_", clean).strip("_")
        # Giới hạn độ dài
        if len(clean) > max_length:
            clean = clean[:max_length].rstrip("_")
        return clean or "document"

    def generate_raw_filepath(self, entry_id: str, title: str) -> Path:
        """Tạo đường dẫn file text raw độc lập cho nguồn dữ liệu."""
        safe_title = self.sanitize_filename(title)
        filename = f"{entry_id}_{safe_title}.txt"
        return self.raw_dir / filename

    def save_raw_archive(
        self,
        entry_id: str,
        title: str,
        source_type: str,
        raw_content: str,
        source_url: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Lưu toàn bộ nội dung văn bản thô ra file text riêng biệt.
        
        Args:
            entry_id: Mã định danh duy nhất (ví dụ: RES-20260813-0001)
            title: Tiêu đề nguồn dữ liệu
            source_type: Phân loại (PAPER, BLOG, VIDEO, FILE_PDF, etc.)
            raw_content: Nội dung trích xuất đầy đủ 100%
            source_url: Đường link nguồn hoặc đường dẫn file gốc
            metadata: Thông tin bổ sung
            
        Returns:
            Path tới file text raw vừa tạo
        """
        metadata = metadata or {}
        filepath = self.generate_raw_filepath(entry_id, title)
        
        now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        word_count = len(raw_content.split()) if raw_content else 0
        char_count = len(raw_content) if raw_content else 0
        
        # Header rõ ràng có cấu trúc phân định
        header_lines = [
            "================================================================================",
            "                   AGENT RESEARCH UPDATE - RAW SOURCE ARCHIVE                   ",
            "================================================================================",
            f"ID:              {entry_id}",
            f"TITLE:           {title}",
            f"TYPE:            {source_type}",
            f"SOURCE / URL:    {source_url}",
            f"INGESTION TIME:  {now_iso}",
            f"WORD COUNT:      {word_count:,} words",
            f"CHARACTER COUNT: {char_count:,} characters",
            f"EXTRACTION:      {metadata.get('extraction_method', 'Direct Autonomous Extractor')}",
            f"BYPASS STATUS:   {metadata.get('bypass_status', 'Direct / None')}",
            "================================================================================",
            "RAW EXTRACTED DATA STREAM BELOW (FULL FIDELITY PRESERVATION):",
            "================================================================================",
            "",
            raw_content or "[EMPTY / NO CONTENT EXTRACTED]",
            "",
            "================================================================================",
            "                               END OF RAW ARCHIVE                               ",
            "================================================================================"
        ]
        
        content_to_write = "\n".join(header_lines)
        
        # Ghi file với encoding UTF-8 đảm bảo tiếng Việt, công thức Toán, ký tự quốc tế
        with open(filepath, "w", encoding="utf-8", errors="replace") as f:
            f.write(content_to_write)
            
        return filepath

    def get_raw_archive_path(self, entry_id: str) -> Optional[Path]:
        """Tìm đường dẫn file raw tương ứng với entry_id."""
        pattern = f"{entry_id}_*.txt"
        matches = list(self.raw_dir.glob(pattern))
        if matches:
            return matches[0]
        # Thử tìm file chính xác bằng entry_id
        exact = self.raw_dir / f"{entry_id}.txt"
        if exact.exists():
            return exact
        return None

    def read_raw_archive(self, entry_id: str) -> Optional[str]:
        """Đọc toàn bộ nội dung file raw archive của một entry."""
        filepath = self.get_raw_archive_path(entry_id)
        if not filepath or not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def list_all_raw_archives(self) -> List[Dict[str, Any]]:
        """Liệt kê danh sách tất cả các file raw archive đang lưu trữ."""
        files = []
        for p in sorted(self.raw_dir.glob("*.txt"), key=os.path.getmtime, reverse=True):
            stat = p.stat()
            # Tách entry_id từ tên file (dạng RES-XXX_title.txt)
            parts = p.stem.split("_", 1)
            entry_id = parts[0] if parts else p.stem
            files.append({
                "entry_id": entry_id,
                "filename": p.name,
                "path": str(p),
                "size_bytes": stat.st_size,
                "size_kb": round(stat.st_size / 1024, 2),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
        return files

    def delete_raw_archive(self, entry_id: str) -> bool:
        """Xóa file raw archive khi xóa bản ghi."""
        filepath = self.get_raw_archive_path(entry_id)
        if filepath and filepath.exists():
            try:
                filepath.unlink()
                return True
            except Exception:
                return False
        return False
