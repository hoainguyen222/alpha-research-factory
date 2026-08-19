"""
====================================================================================================
MODULE: Structured Data Preformatter
FILE: vault/structured_formatter.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 3):
1. Preformat/chuẩn hóa dữ liệu trích xuất từ file text thô thành cấu trúc cột quy chuẩn:
   - ID: Mã định danh duy nhất (RES-YYYYMMDD-XXXX), tối ưu sắp xếp và lập chỉ mục.
   - TITLE: Tiêu đề rõ ràng, loại bỏ ký tự rác.
   - TYPE: Phân loại nguồn (PAPER, BLOG, VIDEO, FILE_PDF, FILE_DOCX, FILE_EXCEL, FILE_CSV, IMAGE, WEB_PAGE).
   - CTX: Toàn bộ ngữ cảnh/văn bản đã làm sạch theo định dạng Markdown chuẩn (tiêu đề, bảng biểu, công thức, code).
   - NOTE: Tóm tắt thông minh, công thức định lượng, tham số phát hiện, bài học rút ra, ghi chú phân tích.
   - WEB: Đường link nguồn, DOI, URL hoặc đường dẫn file gốc.
   - METADATA: Chuỗi JSON thông tin chi tiết (tác giả, ngày xuất bản, số từ, ngôn ngữ, phương thức bypass...).
   - CREATED_AT: Thời gian tạo chuẩn ISO 8601.
2. Cân đối giữa: Cực nhẹ (nhanh gọn), Dễ truy xuất (tìm kiếm theo ID hoặc từ khóa), Dễ đọc (ưu tiên máy đọc và AI pipeline).
====================================================================================================
"""

import re
import json
from datetime import datetime
from typing import Dict, Any, Optional, List


from vault.text_analyzer import TextAnalyzer


class StructuredFormatter:
    """Module tiền xử lý và chuẩn hóa dữ liệu nghiên cứu thành cấu trúc cột tiêu chuẩn."""

    @staticmethod
    def clean_text(text: str) -> str:
        """Làm sạch văn bản, loại bỏ khoảng trắng thừa và ký tự điều khiển lạ."""
        if not text:
            return ""
        # Chuẩn hóa ngắt dòng
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Xóa các chuỗi khoảng trắng lặp vô nghĩa (giữ tối đa 2 dòng trống liên tiếp)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Loại bỏ các ký tự điều khiển phi in ấn ngoại trừ \n, \t
        text = "".join(ch for ch in text if ch.isprintable() or ch in ('\n', '\t'))
        return text.strip()

    @staticmethod
    def extract_key_notes(title: str, text: str, source_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Đọc và phân tích TOÀN BỘ văn bản để tạo Tóm tắt nội dung cốt lõi (Key Insights & Findings).
        """
        return TextAnalyzer.analyze_full_text(title, text, source_type, metadata)

    @classmethod
    def format_entry(
        cls,
        entry_id: str,
        title: str,
        source_type: str,
        raw_text: str,
        source_url: str = "",
        custom_note: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        raw_file_path: str = ""
    ) -> Dict[str, Any]:
        """
        Chuẩn hóa toàn bộ dữ liệu thành 1 dictionary record thống nhất theo cấu trúc cột chuẩn.
        """
        metadata = metadata or {}
        clean_ctx = cls.clean_text(raw_text)
        clean_title = cls.clean_text(title) or f"Untitled Research {entry_id}"
        
        # Đọc toàn bộ full text và phân tích sâu
        auto_summary = TextAnalyzer.analyze_full_text(clean_title, clean_ctx, source_type, metadata)
        
        if auto_summary and "REJECT: Không liên quan đến tài chính" in auto_summary:
            raise ValueError("Bị từ chối: Tài liệu rác hoặc không liên quan đến Tài chính / Định lượng (Topic Filtered).")

        if custom_note and custom_note.strip():
            final_note = f"📝 Ghi chú người dùng: {custom_note.strip()}\n\n" + auto_summary
        else:
            final_note = auto_summary

        now_iso = datetime.now().isoformat()
        
        # Cập nhật các thống kê vào metadata
        metadata["word_count"] = len(clean_ctx.split()) if clean_ctx else 0
        metadata["char_count"] = len(clean_ctx)
        metadata["sanitized_at"] = now_iso

        return {
            "ID": entry_id,
            "TITLE": clean_title,
            "TYPE": source_type.upper(),
            "CTX": clean_ctx,
            "NOTE": final_note,
            "WEB": source_url or "LOCAL_UPLOAD",
            "METADATA": json.dumps(metadata, ensure_ascii=False, indent=2),
            "RAW_FILE_PATH": raw_file_path,
            "CREATED_AT": now_iso,
            "UPDATED_AT": now_iso
        }
