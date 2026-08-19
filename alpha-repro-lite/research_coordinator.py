"""
====================================================================================================
MODULE: Main Research Coordinator & Ingestion Pipeline
FILE: research_coordinator.py
====================================================================================================
CHỨC NĂNG CỐT LÕI (KẾT NỐI TOÀN BỘ 4 YÊU CẦU):
1. Tiếp nhận và phân loại thông minh mọi loại Input:
   - Link URL (Paper, DOI, Blog, YouTube, Web page).
   - Từ khóa (Keywords / Topics) -> Tự động tìm kiếm đa nguồn.
   - File tải lên hoặc đường dẫn cục bộ (PDF, Word, Excel, CSV, TXT, JSON, PPTX).
   - Hình ảnh (PNG, JPG, WEBP...) và Video (.MP4, .MOV...).
2. Điều phối các Extractor chuyên dụng và Tác tử Bypass vượt rào cản:
   - Vượt Paywall/IP block, gỡ mã hóa file, cải thiện ảnh/video mờ.
3. Xuất file Text Raw độc lập tương ứng từng nguồn vào `storage/raw_sources/` (Yêu cầu 2).
4. Preformat và lưu vào Unified Vault (SQLite FTS5 + JSONL + CSV) phân theo ID (Yêu cầu 3).
====================================================================================================
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

from config import RAW_SOURCES_DIR, STRUCTURED_VAULT_DIR, UPLOADS_DIR, ALLOWED_EXTENSIONS
from vault.raw_archive_manager import RawArchiveManager
from vault.structured_formatter import StructuredFormatter
from vault.unified_vault_db import UnifiedVaultDB

from extractors.pdf_extractor import PDFExtractor
from extractors.office_extractor import OfficeExtractor
from extractors.web_extractor import WebExtractor
from extractors.video_extractor import VideoExtractor
from extractors.media_extractor import MediaExtractor
from extractors.keyword_search_engine import KeywordSearchEngine
from bypass.academic_paywall_bypass import AcademicPaywallBypass


class ResearchCoordinator:
    """Bộ điều phối trung tâm tiếp nhận, trích xuất, giải mã và lập chỉ mục nghiên cứu."""

    def __init__(self):
        self.raw_manager = RawArchiveManager()
        self.formatter = StructuredFormatter()
        self.vault_db = UnifiedVaultDB()
        self.paywall_bypass = AcademicPaywallBypass()
        self.web_extractor = WebExtractor()
        self.keyword_engine = KeywordSearchEngine()

    def process_url(self, url: str, custom_note: str = "") -> Dict[str, Any]:
        """
        Quy trình xử lý Link URL (Paper DOI, arXiv, Blog, YouTube, Web Page).
        """
        url = url.strip()
        
        # 1. Phát hiện xem có phải là YouTube Video hay không
        if "youtube.com" in url or "youtu.be" in url:
            extracted = VideoExtractor.extract_from_youtube(url)
            source_type = "VIDEO"

        # 2. Phát hiện xem có phải là Bài báo khoa học (DOI hoặc arXiv hoặc ScienceDirect)
        elif self.paywall_bypass.extract_doi(url) or self.paywall_bypass.extract_arxiv_id(url):
            # Thử lấy PDF bài báo thông qua Paywall Bypass
            pdf_bytes, bypass_method, bypass_meta = self.paywall_bypass.resolve_paywalled_paper(url)
            if pdf_bytes:
                extracted = PDFExtractor.extract_from_bytes(pdf_bytes, filename=f"paper_{bypass_meta.get('doi', 'arxiv')}.pdf")
                extracted["bypass_status"] = bypass_method
                extracted["metadata"].update(bypass_meta)
                source_type = "PAPER"
            else:
                # Fallback sang Web Extractor nếu không tải được PDF
                extracted = self.web_extractor.extract_from_url(url)
                source_type = "PAPER"

        # 3. Mặc định là Web / Blog / Article
        else:
            extracted = self.web_extractor.extract_from_url(url)
            source_type = "BLOG" if ("medium.com" in url or "substack.com" in url or "blog" in url) else "WEB_PAGE"

        return self._finalize_ingestion(
            title=extracted.get("title", "Untitled Web Resource"),
            source_type=source_type,
            raw_text=extracted.get("text", ""),
            source_url=url,
            custom_note=custom_note,
            metadata=extracted.get("metadata", {}),
            extraction_method=extracted.get("extraction_method", "Autonomous Web Extractor"),
            bypass_status=extracted.get("bypass_status", "Direct")
        )

    def process_keyword_query(self, query: str, custom_note: str = "") -> Dict[str, Any]:
        """
        Quy trình xử lý tìm kiếm nghiên cứu theo Từ khóa (Keyword Discovery).
        Tự động tải và bóc tách từng bài báo thành từng thực thể độc lập để chuẩn bị sẵn sàng cho bước Backtest.
        """
        query = query.strip()
        extracted = self.keyword_engine.search_all(query)
        items = extracted.get("items", [])
        
        created_entries = []
        import urllib.request
        
        for item in items:
            title = item.get("title", "Untitled")
            pdf_url = item.get("pdf_url")
            summary = item.get("summary", "")
            raw_url = item.get("url", "")
            
            # Tải full-text PDF nếu có link trực tiếp
            pdf_bytes = None
            if pdf_url:
                try:
                    req = urllib.request.Request(pdf_url, headers={"User-Agent": "Mozilla/5.0 (compatible; AlphaResearchBot/1.0)"})
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        pdf_bytes = resp.read()
                except Exception:
                    pdf_bytes = None
            
            if pdf_bytes and len(pdf_bytes) > 3000:
                safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[:80].strip()
                res = self.process_file_upload(pdf_bytes, filename=f"{safe_title}.pdf", custom_note=f"Từ khóa: {query}")
                created_entries.append(res)
            else:
                # Nạp bản ghi nghiên cứu độc lập kèm Abstract & DOI
                text_content = f"Title: {title}\nAuthors: {item.get('authors', '')}\nPublished: {item.get('published_date', '')}\nSummary/Abstract: {summary}\nDOI/URL: {raw_url}"
                res = self._finalize_ingestion(
                    title=title,
                    source_type="ACADEMIC_SEARCH",
                    raw_text=text_content,
                    source_url=raw_url or f"QUERY:{query}",
                    custom_note=custom_note or f"Từ khóa: {query}",
                    metadata={"authors": item.get("authors"), "published_date": item.get("published_date"), "word_count": len(text_content.split())},
                    extraction_method=f"Academic Discovery Engine ({item.get('source', 'Web')})",
                    bypass_status="Direct"
                )
                # Tự động kích hoạt bóc tách chiến lược
                try:
                    from scripts.auto_alpha_factory import analyze_paper
                    raw_path = res.get("raw_file_path")
                    if raw_path and os.path.exists(raw_path):
                        analyze_paper(raw_path, use_ai=False)
                except Exception:
                    pass
                created_entries.append(res)
        
        # Nếu không có item nào, lưu báo cáo trống
        if not created_entries:
            return self._finalize_ingestion(
                title=extracted.get("title", f"Research: {query}"),
                source_type="KEYWORD_SEARCH",
                raw_text=extracted.get("text", ""),
                source_url=f"QUERY:{query}",
                custom_note=custom_note,
                metadata=extracted.get("metadata", {}),
                extraction_method="Multi-Engine Academic Discovery Agent",
                bypass_status="Direct"
            )

        first_entry = created_entries[0]
        return {
            "status": "success",
            "query": query,
            "id": first_entry.get("id"),
            "title": f"Tìm thấy & Đã nạp {len(created_entries)} bài báo cho từ khóa '{query}'",
            "total_papers": len(created_entries),
            "entries": created_entries
        }

    def process_file_upload(
        self,
        file_bytes: bytes,
        filename: str,
        custom_note: str = ""
    ) -> Dict[str, Any]:
        """
        Quy trình xử lý File tải lên (PDF, Word, Excel, CSV, TXT, JSON, Image, Video).
        """
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        source_type = ALLOWED_EXTENSIONS.get(ext, "FILE_OTHER")

        # 1. PDF
        if ext == "pdf":
            extracted = PDFExtractor.extract_from_bytes(file_bytes, filename=filename)

        # 2. Word
        elif ext in ("docx", "doc"):
            extracted = OfficeExtractor.extract_docx(file_bytes, filename=filename)

        # 3. Excel
        elif ext in ("xlsx", "xls"):
            extracted = OfficeExtractor.extract_excel(file_bytes, filename=filename)

        # 4. CSV
        elif ext in ("csv", "tsv"):
            extracted = OfficeExtractor.extract_csv(file_bytes, filename=filename)

        # 5. TXT / Markdown / JSON
        elif ext in ("txt", "md", "json"):
            extracted = OfficeExtractor.extract_text_or_json(file_bytes, filename=filename)

        # 6. Image
        elif ext in ("png", "jpg", "jpeg", "webp", "bmp", "tiff"):
            extracted = MediaExtractor.extract_from_image(file_bytes, filename=filename)

        # 7. Video
        elif ext in ("mp4", "mov", "mkv", "webm", "avi"):
            # Lưu tạm video file để đọc
            temp_path = UPLOADS_DIR / filename
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            extracted = VideoExtractor.extract_from_local_video(temp_path)

        else:
            extracted = OfficeExtractor.extract_text_or_json(file_bytes, filename=filename)

        return self._finalize_ingestion(
            title=extracted.get("title", Path(filename).stem),
            source_type=source_type,
            raw_text=extracted.get("text", ""),
            source_url=f"FILE:{filename}",
            custom_note=custom_note,
            metadata=extracted.get("metadata", {}),
            extraction_method=extracted.get("extraction_method", "File Ingestion Engine"),
            bypass_status=extracted.get("bypass_status", "Direct")
        )

    def _finalize_ingestion(
        self,
        title: str,
        source_type: str,
        raw_text: str,
        source_url: str = "",
        custom_note: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        extraction_method: str = "Direct",
        bypass_status: str = "None"
    ) -> Dict[str, Any]:
        """
        Quy trình chuẩn hóa cuối cùng:
        1. Tạo ID kế tiếp (RES-YYYYMMDD-XXXX).
        2. Lưu Raw Text Archive độc lập tương ứng (Yêu cầu 2).
        3. Preformat thành record chuẩn (Yêu cầu 3).
        4. Ghi vào SQLite Vault + JSONL + CSV (Yêu cầu 3).
        """
        metadata = metadata or {}
        metadata["extraction_method"] = extraction_method
        metadata["bypass_status"] = bypass_status

        # 0. Kiểm tra trùng lặp trước khi sinh ID và lưu raw file
        existing = self.vault_db.find_existing_entry(title=title, web=source_url, ctx=raw_text)
        if existing:
            print(f"[COORDINATOR] Tài liệu đã tồn tại trong Vault với ID: {existing['id']}. Bỏ qua nạp trùng.")
            return {
                "status": "success",
                "id": existing["id"],
                "title": existing["title"],
                "type": existing["type"],
                "word_count": metadata.get("word_count", 0),
                "raw_file_path": existing.get("raw_file_path", ""),
                "web": existing.get("web", ""),
                "record": existing,
                "is_duplicate": True
            }

        # 1. Tạo ID
        entry_id = self.vault_db.generate_next_id()

        # 2. Lưu file Raw Text độc lập cho từng source
        raw_path = self.raw_manager.save_raw_archive(
            entry_id=entry_id,
            title=title,
            source_type=source_type,
            raw_content=raw_text,
            source_url=source_url,
            metadata=metadata
        )

        # 3. Chuẩn hóa cấu trúc bản ghi
        record = self.formatter.format_entry(
            entry_id=entry_id,
            title=title,
            source_type=source_type,
            raw_text=raw_text,
            source_url=source_url,
            custom_note=custom_note,
            metadata=metadata,
            raw_file_path=str(raw_path)
        )

        # 4. Ghi vào Master Vault Database
        saved_id = self.vault_db.insert_entry(record, check_dup=False)

        return {
            "status": "success",
            "id": saved_id,
            "title": record["TITLE"],
            "type": record["TYPE"],
            "word_count": metadata.get("word_count", 0),
            "raw_file_path": str(raw_path),
            "web": record["WEB"],
            "record": record
        }
