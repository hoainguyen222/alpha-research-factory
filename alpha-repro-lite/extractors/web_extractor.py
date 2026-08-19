"""
====================================================================================================
MODULE: Web & Blog Article Extractor
FILE: extractors/web_extractor.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 1 & 2):
1. Trích xuất bài viết từ Blog, Trang Web, Cổng nghiên cứu định lượng (Medium, Substack, Quantpedia, GitHub...):
   - Sử dụng Trafilatura trích xuất toàn bộ thân bài viết, loại bỏ menu, quảng cáo, sidebar rác.
   - Giữ nguyên cấu trúc phân đoạn, khối mã nguồn (Code blocks), bảng biểu và danh sách.
   - Tự động lấy Tiêu đề, Tác giả, Ngày đăng bài, Tên miền.
2. Tích hợp tự động với AntiScrapingBypass khi gặp các trang web chặn tải hoặc có Cloudflare.
====================================================================================================
"""

import re
import json
import trafilatura
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

from bypass.anti_scraping_bypass import AntiScrapingBypass
from extractors.content_cleaner import ContentCleaner


class WebExtractor:
    """Module trích xuất nội dung bài viết từ Link Web / Blog."""

    def __init__(self):
        self.bypass_agent = AntiScrapingBypass()

    def extract_from_url(self, url: str) -> Dict[str, Any]:
        """
        Trích xuất bài viết hoàn chỉnh từ URL web/blog.
        Tự động kích hoạt cơ chế bypass và bộ lọc nội dung thông minh (loại bỏ ads, nút bấm, rác).
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc or "web"

        # 1. Thu thập nội dung trang thông qua cơ chế Autonomous Fetch
        html_or_md, method, bypass_info = self.bypass_agent.autonomous_fetch(url)

        if not html_or_md:
            return {
                "title": f"Web Content ({domain})",
                "text": f"[FAILED TO FETCH WEB CONTENT FROM {url}]: All bypass mechanisms were unsuccessful.",
                "metadata": {"url": url, "domain": domain, "bypass_info": bypass_info},
                "extraction_method": "Web Fetch Failed",
                "bypass_status": "Failed"
            }

        # 2. Nếu nội dung thu về từ Jina Reader (đã ở dạng Markdown)
        if "Jina" in method:
            # Tách tiêu đề từ dòng đầu tiên nếu có
            lines = [l.strip() for l in html_or_md.split("\n") if l.strip()]
            title = lines[0].lstrip("# ").strip() if lines else f"Article from {domain}"
            
            # Thanh lọc nội dung rác, nút bấm, quảng cáo bằng ContentCleaner
            clean_text = ContentCleaner.clean_article_text(html_or_md)

            return {
                "title": title,
                "text": clean_text,
                "metadata": {"url": url, "domain": domain, "via_jina": True, **bypass_info},
                "extraction_method": "Jina Reader + Smart De-Noiser",
                "bypass_status": method
            }

        # ─── 2.5 Fast-Path: Thử bóc tách qua Site Template Engine (0.002s) ───
        try:
            from vault.site_template_engine import SiteTemplateEngine
            tpl_engine = SiteTemplateEngine()
            matched_tpl = tpl_engine.match_template(url)
            if matched_tpl:
                tpl_res = tpl_engine.extract_with_template(html_or_md, matched_tpl)
                if tpl_res.get("text") and len(tpl_res["text"].strip()) > 80:
                    clean_tpl_text = ContentCleaner.clean_article_text(tpl_res["text"])
                    return {
                        "title": tpl_res.get("title") or f"Article from {domain}",
                        "text": clean_tpl_text,
                        "metadata": {
                            "url": url,
                            "domain": domain,
                            "template_id": matched_tpl.get("id"),
                            "cms_type": matched_tpl.get("cms_type"),
                            "author": tpl_res.get("author"),
                            "publish_date": tpl_res.get("publish_date"),
                            "character_count": len(clean_tpl_text),
                            "word_count": len(clean_tpl_text.split()),
                            **bypass_info
                        },
                        "extraction_method": f"Site Template Engine [{matched_tpl.get('id')}]",
                        "bypass_status": method
                    }
        except Exception as e:
            print(f"[WebExtractor] SiteTemplateEngine warning: {e}")
        extracted_text = trafilatura.extract(
            html_or_md,
            favor_precision=True,
            include_comments=False,
            include_links=False,       # Loại bỏ các link nút bấm [Share], [Like], [Menu]
            include_images=False,
            include_tables=True,
            include_formatting=True,
            output_format="markdown",
            deduplicate=True
        )

        # Trích xuất metadata từ HTML
        meta_dict = {}
        try:
            meta = trafilatura.extract_metadata(html_or_md)
            if meta:
                meta_dict = {
                    "title": meta.title,
                    "author": meta.author,
                    "date": meta.date,
                    "sitename": meta.sitename,
                    "description": meta.description,
                    "categories": meta.categories,
                    "tags": meta.tags
                }
        except Exception:
            pass

        title = meta_dict.get("title")
        if not title:
            t_match = re.search(r'<title[^>]*>(.*?)</title>', html_or_md, re.IGNORECASE | re.DOTALL)
            title = t_match.group(1).strip() if t_match else f"Article from {domain}"

        # 4. Chạy qua bộ lọc thông minh ContentCleaner để loại bỏ 100% rác còn sót lại
        raw_target = extracted_text if extracted_text and len(extracted_text.strip()) > 50 else html_or_md[:15000]
        final_clean_text = ContentCleaner.clean_article_text(raw_target)

        return {
            "title": title,
            "text": final_clean_text,
            "metadata": {
                "url": url,
                "domain": domain,
                "article_meta": meta_dict,
                "bypass_info": bypass_info,
                "character_count": len(final_clean_text),
                "word_count": len(final_clean_text.split())
            },
            "extraction_method": "Trafilatura + Smart Noise Filter",
            "bypass_status": method
        }
