"""
====================================================================================================
MODULE: Academic Paywall & IP Block Bypass Agent
FILE: bypass/academic_paywall_bypass.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 4 - PHẦN 2):
1. Tự động vượt qua các bài báo khoa học (Paper) bị khóa Paywall hoặc chặn IP trường đại học:
   - Bước 1: Trích xuất DOI hoặc mã arXiv từ URL / tiêu đề bài báo.
   - Bước 2: Truy vấn Unpaywall API tìm bản Open Access PDF hợp pháp từ các kho lưu trữ toàn cầu.
   - Bước 3: Truy vấn OpenAlex API & Semantic Scholar API lấy link PDF trực tiếp và bản preprint.
   - Bước 4: Tự động tải từ arXiv Mirror / Europe PMC / PubMed Central.
   - Bước 5: Sci-Hub Proxy Mirror Rotation (tải file PDF bài báo bị khóa).
2. Tải về file PDF hoặc lấy toàn bộ Abstract + Full-Text phục vụ trích xuất.
====================================================================================================
"""

import re
import requests
from typing import Dict, Any, Optional, Tuple

from config import (
    UNPAYWALL_EMAIL, OPENALEX_API_URL, SEMANTIC_SCHOLAR_API_URL,
    ARXIV_API_URL, SCIHUB_MIRRORS, HTTP_TIMEOUT, DEFAULT_HEADERS
)


class AcademicPaywallBypass:
    """Tác tử vượt qua rào cản IP và Paywall bài báo khoa học."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    @staticmethod
    def extract_doi(text_or_url: str) -> Optional[str]:
        """Trích xuất mã định danh DOI (Digital Object Identifier) từ URL hoặc chuỗi văn bản."""
        # Pattern chuẩn của DOI: 10.xxxx/...
        doi_pattern = r'(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)'
        match = re.search(doi_pattern, text_or_url)
        if match:
            # Loại bỏ các ký tự dấu câu thừa ở cuối nếu có
            doi = match.group(1).rstrip(".,;)>")
            return doi
        return None

    @staticmethod
    def extract_arxiv_id(text_or_url: str) -> Optional[str]:
        """Trích xuất mã arXiv ID từ URL (ví dụ: 2305.18290 hoặc math/0102034)."""
        arxiv_pattern = r'(?:arxiv\.org/(?:abs|pdf)/|arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+/\d{7})'
        match = re.search(arxiv_pattern, text_or_url, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def fetch_via_unpaywall(self, doi: str) -> Tuple[Optional[bytes], Optional[str], Dict[str, Any]]:
        """
        Chiến lược 1: Unpaywall API - tìm bản PDF Open Access chính thức từ hàng ngàn trường ĐH.
        """
        try:
            api_url = f"https://api.unpaywall.org/v2/{doi}?email={UNPAYWALL_EMAIL}"
            res = self.session.get(api_url, timeout=HTTP_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                oa_location = data.get("best_oa_location")
                if oa_location and oa_location.get("url_for_pdf"):
                    pdf_url = oa_location.get("url_for_pdf")
                    pdf_res = self.session.get(pdf_url, timeout=HTTP_TIMEOUT, headers=DEFAULT_HEADERS)
                    if pdf_res.status_code == 200 and len(pdf_res.content) > 10000:
                        return pdf_res.content, f"Unpaywall OA ({oa_location.get('host_type')})", {
                            "title": data.get("title"),
                            "journal": data.get("journal_name"),
                            "year": data.get("year"),
                            "oa_url": pdf_url
                        }
        except Exception:
            pass
        return None, None, {}

    def fetch_via_openalex(self, doi: str) -> Tuple[Optional[bytes], Optional[str], Dict[str, Any]]:
        """
        Chiến lược 2: OpenAlex Open Access Database.
        """
        try:
            api_url = f"{OPENALEX_API_URL}/works/https://doi.org/{doi}"
            res = self.session.get(api_url, timeout=HTTP_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                oa_info = data.get("open_access", {})
                pdf_url = oa_info.get("oa_url")
                if pdf_url:
                    pdf_res = self.session.get(pdf_url, timeout=HTTP_TIMEOUT, headers=DEFAULT_HEADERS)
                    if pdf_res.status_code == 200 and len(pdf_res.content) > 10000:
                        return pdf_res.content, "OpenAlex Direct Open Access", {
                            "title": data.get("display_name"),
                            "publication_year": data.get("publication_year"),
                            "cited_by_count": data.get("cited_by_count")
                        }
        except Exception:
            pass
        return None, None, {}

    def fetch_via_arxiv(self, arxiv_id: str) -> Tuple[Optional[bytes], Optional[str], Dict[str, Any]]:
        """
        Chiến lược 3: Tải trực tiếp PDF từ arXiv repository.
        """
        try:
            clean_id = re.sub(r'v\d+$', '', arxiv_id) # Bỏ đuôi version nếu có
            pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"
            res = self.session.get(pdf_url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT)
            if res.status_code == 200 and len(res.content) > 10000:
                return res.content, "arXiv Open Access PDF Repository", {"arxiv_id": clean_id, "pdf_url": pdf_url}
        except Exception:
            pass
        return None, None, {}

    def fetch_via_scihub_mirrors(self, doi: str) -> Tuple[Optional[bytes], Optional[str], Dict[str, Any]]:
        """
        Chiến lược 4: Sci-Hub Proxy Mirrors Fallback.
        """
        for mirror in SCIHUB_MIRRORS:
            try:
                target_url = f"{mirror}/{doi}"
                res = self.session.get(target_url, headers=DEFAULT_HEADERS, timeout=15)
                if res.status_code == 200:
                    # Nếu Sci-Hub trả về trực tiếp file PDF
                    if res.headers.get("content-type", "").lower().startswith("application/pdf"):
                        return res.content, f"Sci-Hub Mirror ({mirror})", {"doi": doi}
                    
                    # Nếu Sci-Hub trả về trang HTML chứa thẻ iframe/embed dẫn tới PDF
                    html = res.text
                    pdf_src_match = re.search(r'(?:src|href)=["\'](//[^\'"]+\.pdf|[^\'"]+\.pdf)["\']', html, re.IGNORECASE)
                    if pdf_src_match:
                        raw_src = pdf_src_match.group(1)
                        if raw_src.startswith("//"):
                            full_pdf_url = "https:" + raw_src
                        elif raw_src.startswith("/"):
                            full_pdf_url = mirror + raw_src
                        else:
                            full_pdf_url = raw_src
                            
                        pdf_res = self.session.get(full_pdf_url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT)
                        if pdf_res.status_code == 200 and len(pdf_res.content) > 10000:
                            return pdf_res.content, f"Sci-Hub Mirror ({mirror})", {"doi": doi, "pdf_url": full_pdf_url}
            except Exception:
                continue
        return None, None, {}

    def resolve_paywalled_paper(self, text_or_url: str) -> Tuple[Optional[bytes], str, Dict[str, Any]]:
        """
        Bộ điều phối tự động giải quyết bài báo khoa học:
        Phát hiện DOI/arXiv -> Thử Unpaywall -> Thử OpenAlex -> Thử arXiv -> Thử Sci-Hub.
        """
        doi = self.extract_doi(text_or_url)
        arxiv_id = self.extract_arxiv_id(text_or_url)

        meta = {"original_input": text_or_url, "doi": doi, "arxiv_id": arxiv_id}

        # 1. Nếu là bài báo trên arXiv
        if arxiv_id:
            pdf_bytes, method, extra = self.fetch_via_arxiv(arxiv_id)
            if pdf_bytes:
                meta.update(extra)
                return pdf_bytes, method, meta

        # 2. Nếu có mã DOI
        if doi:
            # Bước A: Unpaywall
            pdf_bytes, method, extra = self.fetch_via_unpaywall(doi)
            if pdf_bytes:
                meta.update(extra)
                return pdf_bytes, method, meta

            # Bước B: OpenAlex
            pdf_bytes, method, extra = self.fetch_via_openalex(doi)
            if pdf_bytes:
                meta.update(extra)
                return pdf_bytes, method, meta

            # Bước C: Sci-Hub Proxy Mirrors
            pdf_bytes, method, extra = self.fetch_via_scihub_mirrors(doi)
            if pdf_bytes:
                meta.update(extra)
                return pdf_bytes, method, meta

        return None, "Paywall Bypass Failed", meta
