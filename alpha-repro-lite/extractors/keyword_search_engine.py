"""
====================================================================================================
MODULE: Academic & Web Keyword Discovery Engine
FILE: extractors/keyword_search_engine.py
====================================================================================================
CHỨC NĂNG (YÊU CẦU 1):
1. Tự động tìm kiếm tài liệu nghiên cứu học thuật đa nguồn theo Từ khóa (Keywords):
   - arXiv API: Tìm các bài báo preprint mới nhất trên arXiv.
   - CrossRef API: Tìm các công trình khoa học, bài báo tạp chí đã xuất bản.
   - OpenAlex API: Tìm kiếm công trình nghiên cứu kèm chỉ số trích dẫn và link PDF mở.
   - Semantic Scholar API: Tìm bài báo kèm tóm tắt và đánh giá mức độ ảnh hưởng.
2. Tổng hợp báo cáo tổng quan nghiên cứu theo từ khóa (Discovery Report) và cho phép tự động tải/lập chỉ mục.
====================================================================================================
"""

import xml.etree.ElementTree as ET
import requests
from typing import Dict, Any, List, Optional
from urllib.parse import quote_plus

from config import ARXIV_API_URL, CROSSREF_API_URL, OPENALEX_API_URL, DEFAULT_HEADERS, HTTP_TIMEOUT


class KeywordSearchEngine:
    """Công cụ tìm kiếm tài liệu nghiên cứu tự động theo từ khóa."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def search_arxiv(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Tìm kiếm bài báo trên arXiv theo từ khóa tối ưu cho tài chính định lượng."""
        results = []
        try:
            words = [w.strip() for w in query.split() if len(w.strip()) > 2][:3]
            if words:
                term_str = "+OR+".join([f"all:{quote_plus(w)}" for w in words])
                encoded_q = f"(cat:q-fin*+OR+all:trading+OR+all:finance)+AND+({term_str})"
            else:
                encoded_q = f"all:{quote_plus(query)}"
            url = f"{ARXIV_API_URL}?search_query={encoded_q}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
            res = self.session.get(url, timeout=HTTP_TIMEOUT)
            if res.status_code == 200:
                root = ET.fromstring(res.text)
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                for entry in root.findall('atom:entry', ns):
                    title_elem = entry.find('atom:title', ns)
                    summary_elem = entry.find('atom:summary', ns)
                    id_elem = entry.find('atom:id', ns)
                    published_elem = entry.find('atom:published', ns)
                    
                    authors = []
                    for author in entry.findall('atom:author', ns):
                        name_elem = author.find('atom:name', ns)
                        if name_elem is not None and name_elem.text:
                            authors.append(name_elem.text.strip())

                    pdf_link = ""
                    for link in entry.findall('atom:link', ns):
                        if link.attrib.get('title') == 'pdf':
                            pdf_link = link.attrib.get('href', '')

                    title = title_elem.text.strip().replace('\n', ' ') if title_elem is not None else "Untitled"
                    summary = summary_elem.text.strip().replace('\n', ' ') if summary_elem is not None else ""
                    raw_id = id_elem.text.strip() if id_elem is not None else ""
                    published = published_elem.text.strip()[:10] if published_elem is not None else ""

                    results.append({
                        "source": "arXiv",
                        "title": title,
                        "authors": ", ".join(authors),
                        "summary": summary,
                        "url": raw_id,
                        "pdf_url": pdf_link or (raw_id.replace("abs", "pdf") + ".pdf" if "abs" in raw_id else ""),
                        "published_date": published
                    })
        except Exception as e:
            print(f"[SEARCH] arXiv search error: {e}")
        return results

    def search_crossref(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Tìm kiếm tài liệu trên CrossRef."""
        results = []
        try:
            encoded_q = quote_plus(query)
            url = f"{CROSSREF_API_URL}?query={encoded_q}&rows={max_results}&select=DOI,title,author,abstract,URL,published"
            res = self.session.get(url, timeout=HTTP_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                items = data.get("message", {}).get("items", [])
                for it in items:
                    title_list = it.get("title", [])
                    title = title_list[0] if title_list else "Untitled"
                    doi = it.get("DOI", "")
                    
                    authors = []
                    for a in it.get("author", []):
                        given = a.get("given", "")
                        family = a.get("family", "")
                        authors.append(f"{given} {family}".strip())

                    results.append({
                        "source": "CrossRef",
                        "title": title,
                        "doi": doi,
                        "authors": ", ".join(authors),
                        "summary": (it.get("abstract") or "Abstract available via DOI.")[:400],
                        "url": it.get("URL", f"https://doi.org/{doi}" if doi else ""),
                        "pdf_url": f"https://doi.org/{doi}" if doi else ""
                    })
        except Exception as e:
            print(f"[SEARCH] CrossRef search error: {e}")
        return results

    def search_openalex(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Tìm kiếm công trình nghiên cứu trên OpenAlex."""
        results = []
        try:
            encoded_q = quote_plus(query)
            url = f"{OPENALEX_API_URL}/works?search={encoded_q}&per_page={max_results}"
            res = self.session.get(url, timeout=HTTP_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                for w in data.get("results", []):
                    title = w.get("display_name") or "Untitled"
                    doi = w.get("doi") or ""
                    pub_year = str(w.get("publication_year") or "")
                    oa_url = w.get("open_access", {}).get("oa_url") or ""
                    
                    authors = []
                    for authorship in w.get("authorships", []):
                        author_name = authorship.get("author", {}).get("display_name")
                        if author_name:
                            authors.append(author_name)

                    results.append({
                        "source": "OpenAlex",
                        "title": title,
                        "doi": doi,
                        "authors": ", ".join(authors[:5]),
                        "summary": f"Cited by {w.get('cited_by_count', 0)} papers. Published in {pub_year}.",
                        "url": doi or oa_url or w.get("id", ""),
                        "pdf_url": oa_url,
                        "published_date": pub_year
                    })
        except Exception as e:
            print(f"[SEARCH] OpenAlex search error: {e}")
        return results

    def search_all(self, query: str, limit_per_source: int = 4) -> Dict[str, Any]:
        """
        Tìm kiếm đồng thời trên tất cả các kho dữ liệu nghiên cứu và tổng hợp báo cáo.
        """
        arxiv_items = self.search_arxiv(query, max_results=limit_per_source)
        openalex_items = self.search_openalex(query, max_results=limit_per_source)
        crossref_items = self.search_crossref(query, max_results=limit_per_source)

        all_items = arxiv_items + openalex_items + crossref_items

        # Tạo báo cáo tổng hợp Markdown
        report_lines = []
        report_lines.append(f"# KEYWORD RESEARCH DISCOVERY: \"{query}\"")
        report_lines.append(f"**Total Papers Discovered:** {len(all_items)} across arXiv, OpenAlex, CrossRef.\n")

        for idx, item in enumerate(all_items, 1):
            report_lines.append(f"### {idx}. [{item['source']}] {item['title']}")
            if item.get("authors"):
                report_lines.append(f"- **Authors:** {item['authors']}")
            if item.get("published_date"):
                report_lines.append(f"- **Published:** {item['published_date']}")
            if item.get("url"):
                report_lines.append(f"- **Link / DOI:** {item['url']}")
            if item.get("pdf_url"):
                report_lines.append(f"- **Direct PDF / OA Link:** {item['pdf_url']}")
            if item.get("summary"):
                report_lines.append(f"- **Abstract / Summary:** {item['summary']}")
            report_lines.append("\n---\n")

        full_text = "\n".join(report_lines)

        return {
            "title": f"Keyword Research: {query}",
            "text": full_text,
            "items": all_items,
            "arxiv": arxiv_items,
            "openalex": openalex_items,
            "crossref": crossref_items,
            "metadata": {
                "query": query,
                "total_results": len(all_items),
                "arxiv_count": len(arxiv_items),
                "openalex_count": len(openalex_items),
                "crossref_count": len(crossref_items)
            },
            "extraction_method": "Multi-Engine Academic Discovery Agent",
            "bypass_status": "Direct"
        }
