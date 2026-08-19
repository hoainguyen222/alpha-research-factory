"""
====================================================================================================
MODULE: PDF Document & Academic Paper Extractor
FILE: extractors/pdf_extractor.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 1 & 2):
1. Trích xuất toàn bộ nội dung văn bản từ tài liệu PDF và bài báo nghiên cứu khoa học:
   - Trích xuất từng trang, bảo toàn cấu trúc phân đoạn (Abstract, Intro, Methods, Tables, References).
   - Tự động tích hợp FileDecryptor nếu file bị mã hóa hoặc hạn chế quyền copy.
   - Tự động tích hợp AcademicPaywallBypass nếu là link DOI / arXiv / Paywalled Paper.
2. Trích xuất Metadata bài báo: Tiêu đề, Tác giả, Ngày công bố, Số trang, Tạp chí.
====================================================================================================
"""

import io
import re
from pathlib import Path
from typing import Dict, Any, Optional, Union, Tuple
import pypdf

from bypass.file_decryptor import FileDecryptor
from bypass.academic_paywall_bypass import AcademicPaywallBypass
from extractors.content_cleaner import ContentCleaner


class PDFExtractor:
    """Module trích xuất chuyên sâu tài liệu PDF và bài báo học thuật."""

    @classmethod
    def extract_from_bytes(cls, pdf_bytes: bytes, filename: str = "document.pdf") -> Dict[str, Any]:
        """Trích xuất toàn bộ nội dung từ bytes của file PDF."""
        # 1. Thử mở và giải mã PDF nếu bị khóa
        reader, unlock_status, unlock_meta = FileDecryptor.unlock_pdf(pdf_bytes)

        if not reader:
            # Nếu mở thất bại, thử chiến lược cứu hộ luồng nhị phân (salvage)
            salvaged = FileDecryptor.salvage_text_from_corrupted_binary(pdf_bytes)
            return {
                "title": Path(filename).stem,
                "text": salvaged,
                "page_count": 0,
                "metadata": {"salvaged": True, "unlock_status": unlock_status, **unlock_meta},
                "extraction_method": "Corrupted Binary Stream Salvage",
                "bypass_status": unlock_status
            }

        # 2. Đọc metadata từ PDF header
        pdf_meta = {}
        title = Path(filename).stem
        try:
            if reader.metadata:
                for k, v in reader.metadata.items():
                    clean_k = str(k).lstrip("/").lower()
                    pdf_meta[clean_k] = str(v)
                if pdf_meta.get("title") and len(pdf_meta["title"].strip()) > 3:
                    title = pdf_meta["title"].strip()
        except Exception:
            pass

        # 3. Trích xuất văn bản & hình ảnh/biểu đồ nhúng từng trang
        pages_text = []
        num_pages = len(reader.pages)
        has_embedded_images = False
        video_links_found = []

        for idx, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
                
                # 3a. Bóc tách ảnh/biểu đồ nhúng trong trang và chạy OCR
                img_ocr_texts = []
                try:
                    if hasattr(page, "images") and page.images:
                        from extractors.media_extractor import MediaExtractor
                        for img_name, img_bytes in page.images.items():
                            has_embedded_images = True
                            ocr_res = MediaExtractor.extract_from_image(img_bytes, filename=img_name)
                            if ocr_res.get("text") and len(ocr_res["text"].strip()) > 15:
                                img_ocr_texts.append(f"[BIỂU ĐỒ/ẢNH NHÚNG '{img_name}' OCR]: {ocr_res['text'].strip()}")
                except Exception as img_err:
                    pass

                # 3b. Quét link Video / YouTube trong trang
                try:
                    text_to_scan = page_text
                    yt_matches = re.findall(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+))', text_to_scan)
                    if yt_matches:
                        for yt_url in yt_matches:
                            if yt_url not in video_links_found:
                                video_links_found.append(yt_url)
                except Exception:
                    pass

                # Hợp nhất nội dung trang
                combined_page = page_text.strip()
                if img_ocr_texts:
                    combined_page += "\n\n" + "\n".join(img_ocr_texts)

                if combined_page.strip():
                    pages_text.append(f"--- [Page {idx + 1} / {num_pages}] ---\n{combined_page}")
            except Exception as e:
                pages_text.append(f"--- [Page {idx + 1} / {num_pages} - Extraction Note: {str(e)} ---")

        # 3c. Xử lý video transcript nếu có link video được tìm thấy trong PDF
        if video_links_found:
            try:
                from extractors.video_extractor import VideoExtractor
                for v_url in video_links_found[:2]: # Tối đa 2 video
                    v_res = VideoExtractor.extract_from_youtube(v_url)
                    if v_res.get("text") and len(v_res["text"].strip()) > 30:
                        pages_text.append(f"--- [PHỤ ĐỀ VIDEO ĐÍNH KÈM: {v_url}] ---\n{v_res['text'].strip()}")
            except Exception:
                pass

        raw_combined = "\n\n".join(pages_text)
        full_text = ContentCleaner.clean_article_text(raw_combined)

        # 4. Nếu tiêu đề chưa có hoặc là tên file chung chung, tìm tiêu đề từ trang đầu tiên
        if title == Path(filename).stem and pages_text:
            first_lines = [line.strip() for line in pages_text[0].split("\n") if len(line.strip()) > 5]
            valid_candidates = [l for l in first_lines if not l.startswith("--- [Page")]
            if valid_candidates:
                title = valid_candidates[0][:120]

        # 5. Lưu Kỹ Năng / Hồ sơ xử lý tài liệu phức tạp vào learned_rules nếu có OCR hoặc Video
        extraction_method = "PyPDF + Academic De-Noiser"
        if has_embedded_images or video_links_found:
            extraction_method = "Multimodal In-line Fusion (PDF + Chart OCR + Video Transcript)"
            try:
                from vault.learned_rule_engine import LearnedRuleEngine
                LearnedRuleEngine().learn_rule(
                    name=f"Recipe: Multimodal PDF [{Path(filename).stem[:30]}]",
                    trigger_keywords=[Path(filename).stem.lower(), "multimodal_pdf", "charts_ocr"],
                    rule_payload={
                        "pipeline": ["PyPDF", "RapidOCR_Charts", "Video_Transcript_Scanner"],
                        "has_images": has_embedded_images,
                        "video_links_count": len(video_links_found)
                    },
                    pattern_type="PROCESSING_RECIPE",
                    confidence=0.98
                )
            except Exception:
                pass

        return {
            "title": title,
            "text": full_text,
            "page_count": num_pages,
            "metadata": {
                "pdf_metadata": pdf_meta,
                "unlock_info": unlock_meta,
                "total_pages": num_pages,
                "has_embedded_images": has_embedded_images,
                "video_links": video_links_found,
                "character_count": len(full_text),
                "word_count": len(full_text.split())
            },
            "extraction_method": extraction_method,
            "bypass_status": unlock_status
        }

    @classmethod
    def extract_from_file(cls, filepath: Union[str, Path]) -> Dict[str, Any]:
        """Trích xuất từ đường dẫn file PDF trên máy cục bộ."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {filepath}")
        
        with open(path, "rb") as f:
            content = f.read()
        return cls.extract_from_bytes(content, filename=path.name)
