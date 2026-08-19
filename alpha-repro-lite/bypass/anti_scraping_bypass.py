"""
====================================================================================================
MODULE: Anti-Scraping & Download-Block Bypass Agent
FILE: bypass/anti_scraping_bypass.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 4 - PHẦN 1):
1. Tự động vượt qua các website chặn tải xuống, chặn Bot (403, 429, Cloudflare, Paywall blog):
   - Tier 1: User-Agent Rotation + Client Hints + Chrome/Firefox Stealth Headers.
   - Tier 2: Jina AI Reader Proxy Engine (https://r.jina.ai/<url>) - giải mã JS & trả về Markdown sạch.
   - Tier 3: Internet Archive Wayback Machine Snapshot API (bản sao lưu lịch sử của trang).
   - Tier 4: Googlebot / Bingbot User-Agent Spoofing (cho các trang mở cửa riêng cho search engine).
2. Tự động chuyển đổi nội dung thu thập được sang dạng Plain Text / Markdown sạch sẽ.
====================================================================================================
"""

import random
import requests
from typing import Dict, Any, Optional, Tuple

from config import USER_AGENTS, DEFAULT_HEADERS, HTTP_TIMEOUT, JINA_READER_PREFIX, WAYBACK_API_URL


class AntiScrapingBypass:
    """Tác tử tự động vượt qua các rào cản chặn tải xuống và chống cào dữ liệu web."""

    def __init__(self):
        self.session = requests.Session()

    def get_stealth_headers(self) -> Dict[str, str]:
        """Tạo bộ HTTP Headers mô phỏng trình duyệt hiện đại nhất."""
        ua = random.choice(USER_AGENTS)
        headers = dict(DEFAULT_HEADERS)
        headers["User-Agent"] = ua
        headers["Sec-Ch-Ua"] = '"Chromium";v="127", "Not)A;Brand";v="99", "Google Chrome";v="127"'
        headers["Sec-Ch-Ua-Mobile"] = "?0"
        headers["Sec-Ch-Ua-Platform"] = '"Windows"'
        headers["Sec-Fetch-Dest"] = "document"
        headers["Sec-Fetch-Mode"] = "navigate"
        headers["Sec-Fetch-Site"] = "none"
        headers["Sec-Fetch-User"] = "?1"
        return headers

    def _handle_potential_binary_response(self, response: requests.Response, url: str) -> Optional[Tuple[str, str]]:
        """Nhận diện và trích xuất đúng định dạng nếu phản hồi là file nhị phân (PDF, DOCX, XLSX, Ảnh)."""
        content_bytes = response.content
        ctype = response.headers.get("Content-Type", "").lower()
        
        # 1. Phát hiện PDF binary
        if content_bytes.startswith(b"%PDF") or "application/pdf" in ctype or url.lower().split("?")[0].endswith(".pdf"):
            try:
                from extractors.pdf_extractor import PDFExtractor
                res = PDFExtractor.extract_from_bytes(content_bytes, filename=url.split("/")[-1] or "paper.pdf")
                if res and res.get("text"):
                    return res["text"], "Direct PDF Binary Extractor"
            except Exception:
                pass

        # 2. Phát hiện DOCX / XLSX / ZIP binary
        if content_bytes.startswith(b"PK\x03\x04") or "officedocument" in ctype:
            try:
                from extractors.office_extractor import OfficeExtractor
                res = OfficeExtractor.extract_from_bytes(content_bytes, filename=url.split("/")[-1] or "document.docx")
                if res and res.get("text"):
                    return res["text"], "Direct Office Binary Extractor"
            except Exception:
                pass

        return None

    def fetch_with_stealth_request(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Chiến lược 1: Thử tải trực tiếp với cơ chế Stealth Header Rotation.
        """
        try:
            headers = self.get_stealth_headers()
            response = self.session.get(url, headers=headers, timeout=HTTP_TIMEOUT, allow_redirects=True)
            if response.status_code == 200:
                # Kiểm tra nếu là file nhị phân (PDF, DOCX, etc.)
                binary_res = self._handle_potential_binary_response(response, url)
                if binary_res:
                    return binary_res

                if len(response.text.strip()) > 100:
                    # Kiểm tra xem có bị dính trang chặn Cloudflare "Please wait..." hay không
                    if "Just a moment..." not in response.text and "Enable JavaScript and cookies" not in response.text:
                        return response.text, "Direct Stealth Headers"
        except Exception as e:
            pass
        return None, None

    def fetch_with_jina_reader(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Chiến lược 2: Sử dụng Jina AI Reader Proxy.
        Jina Reader có khả năng bypass Cloudflare, thực thi JavaScript và trả về Markdown hoàn chỉnh.
        """
        try:
            jina_url = f"{JINA_READER_PREFIX}{url}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "X-Return-Format": "markdown"
            }
            response = self.session.get(jina_url, headers=headers, timeout=HTTP_TIMEOUT + 10)
            if response.status_code == 200 and len(response.text.strip()) > 200:
                return response.text, "Jina AI Reader Proxy"
        except Exception as e:
            pass
        return None, None

    def fetch_with_wayback_machine(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Chiến lược 3: Tìm kiếm bản sao chụp gần nhất trên Internet Archive (Wayback Machine).
        """
        try:
            api_url = f"{WAYBACK_API_URL}?url={url}"
            res = self.session.get(api_url, timeout=12)
            if res.status_code == 200:
                data = res.json()
                closest = data.get("archived_snapshots", {}).get("closest", {})
                if closest.get("available") and closest.get("url"):
                    snapshot_url = closest.get("url")
                    snap_res = self.session.get(snapshot_url, headers=self.get_stealth_headers(), timeout=HTTP_TIMEOUT)
                    if snap_res.status_code == 200 and len(snap_res.text) > 300:
                        return snap_res.text, f"Wayback Machine Archive ({closest.get('timestamp')})"
        except Exception:
            pass
        return None, None

    def fetch_with_search_bot_spoof(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Chiến lược 4: Đóng giả Googlebot / Bingbot (nhiều trang báo mở toàn bộ nội dung cho Bot tìm kiếm).
        """
        try:
            bot_headers = {
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "From": "googlebot(at)googlebot.com"
            }
            response = self.session.get(url, headers=bot_headers, timeout=HTTP_TIMEOUT)
            if response.status_code == 200:
                binary_res = self._handle_potential_binary_response(response, url)
                if binary_res:
                    return binary_res
                if len(response.text.strip()) > 100:
                    return response.text, "Googlebot Emulation Bypass"
        except Exception:
            pass
        return None, None

    def autonomous_fetch(self, url: str) -> Tuple[Optional[str], str, Dict[str, Any]]:
        """
        Quy trình điều phối đa tầng tự động vượt rào cản web:
        Thực hiện lần lượt Tier 1 -> Tier 2 -> Tier 3 -> Tier 4.
        """
        logs = []
        
        # Tier 1: Stealth Headers
        content, method = self.fetch_with_stealth_request(url)
        if content:
            return content, method, {"attempts": ["Stealth Headers (Success)"]}
        logs.append("Stealth Headers: Failed / Blocked")

        # Tier 2: Jina Reader Proxy
        content, method = self.fetch_with_jina_reader(url)
        if content:
            logs.append("Jina AI Reader Proxy: Success")
            return content, method, {"attempts": logs}
        logs.append("Jina AI Reader Proxy: Failed")

        # Tier 3: Wayback Machine
        content, method = self.fetch_with_wayback_machine(url)
        if content:
            logs.append("Wayback Machine: Success")
            return content, method, {"attempts": logs}
        logs.append("Wayback Machine: Failed / No Snapshot")

        # Tier 4: Search Bot Spoof
        content, method = self.fetch_with_search_bot_spoof(url)
        if content:
            logs.append("Search Bot Spoof: Success")
            return content, method, {"attempts": logs}
        logs.append("Search Bot Spoof: Failed")

        return None, "All Bypass Strategies Failed", {"attempts": logs}
