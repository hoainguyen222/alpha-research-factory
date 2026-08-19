#!/usr/bin/env python3
"""
HOAI_CODE Web Spider Watchdog — Autonomous Paper Discovery & Download
=====================================================================
Automatically scrapes configured web sources (arXiv RSS, SSRN HTML, Quantocracy RSS),
uses a SQLite Fingerprint Ledger to track already-downloaded papers (Hit-and-Stop algorithm),
downloads new PDFs to inbox/, and optionally chains into auto_alpha_factory.py.

Usage:
    python3 scripts/web_spider_watchdog.py                     # Scrape & download only
    python3 scripts/web_spider_watchdog.py --auto-run           # Scrape + run Alpha Factory
    python3 scripts/web_spider_watchdog.py --auto-run --use-ai  # Scrape + run with AI
    python3 scripts/web_spider_watchdog.py --dry-run            # Preview only, no downloads
"""

import os
import sys
import json
import yaml
import hashlib
import sqlite3
import argparse
import subprocess
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from datetime import datetime

# ─── Paths ───────────────────────────────────────────────────────────────────
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INBOX_DIR = os.path.join(ROOT_DIR, "inbox")
SOURCES_DIR = os.path.join(ROOT_DIR, "sources")
REGISTRY_PATH = os.path.join(SOURCES_DIR, "web_registry.yaml")
DB_PATH = os.path.join(ROOT_DIR, "quant_platform.db")
ALPHA_FACTORY = os.path.join(ROOT_DIR, "scripts", "auto_alpha_factory.py")

MAX_NEW_PER_SOURCE = 20  # Safety cap: max papers to download per source per run
HTTP_TIMEOUT = 30        # seconds

# ─── Logging ─────────────────────────────────────────────────────────────────
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [Spider] {msg}")

def log_ok(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [Spider] ✓ {msg}")

def log_skip(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [Spider] ⊘ {msg}")

def log_warn(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [Spider] ⚠ {msg}")

# ─── Module 1: Registry Loader ──────────────────────────────────────────────
def load_registry():
    """Load web sources from web_registry.yaml"""
    if not os.path.exists(REGISTRY_PATH):
        log_warn(f"Registry not found: {REGISTRY_PATH}")
        return [], {}
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    sources = [s for s in data.get("sources", []) if s.get("enabled", True)]
    watchdog_cfg = data.get("watchdog", {})
    return sources, watchdog_cfg

# ─── Module 4: Fingerprint Ledger (SQLite) ───────────────────────────────────
def init_ledger_db():
    """Create scraped_papers table if not exists"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scraped_papers (
            fingerprint TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            pdf_url TEXT,
            downloaded BOOLEAN DEFAULT 0,
            processed BOOLEAN DEFAULT 0,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_known(fingerprint):
    """Check if a paper fingerprint already exists in the ledger"""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT 1 FROM scraped_papers WHERE fingerprint = ?", (fingerprint,)).fetchone()
    conn.close()
    return row is not None

def mark_known(fingerprint, title, source_name, source_url, pdf_url=None, downloaded=False):
    """Record a paper fingerprint in the ledger"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR IGNORE INTO scraped_papers (fingerprint, title, source_name, source_url, pdf_url, downloaded)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (fingerprint, title, source_name, source_url, pdf_url, 1 if downloaded else 0))
    conn.commit()
    conn.close()

def make_fingerprint(url, title=""):
    """Generate a stable fingerprint from URL (primary) or title hash (fallback)"""
    text = url.strip() if url else title.strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]

# ─── Module 2: RSS Spider (arXiv, Quantocracy) ──────────────────────────────
def fetch_url(url):
    """Fetch URL content as string with proper headers"""
    headers = {
        "User-Agent": "HOAI-AlphaResearch-Spider/1.0 (Academic Research Bot)"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
        log_warn(f"Failed to fetch {url}: {e}")
        return None

def parse_rss_feed(xml_content, source_name):
    """Parse RSS/Atom feed and return list of paper dicts sorted newest-first"""
    papers = []
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        log_warn(f"XML parse error for {source_name}: {e}")
        return papers

    # Handle standard RSS 2.0 (<channel><item>)
    ns = {"atom": "http://www.w3.org/2005/Atom",
          "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
          "dc": "http://purl.org/dc/elements/1.1/",
          "content": "http://purl.org/rss/1.0/modules/content/"}

    # Try RSS 2.0
    items = root.findall(".//item")
    # Try RDF (arXiv uses RDF/RSS 1.0)
    if not items:
        items = root.findall(".//{http://purl.org/rss/1.0/}item")
    # Try Atom
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    for item in items:
        title = ""
        link = ""
        pdf_link = ""

        # RSS 2.0 / RDF / Atom — explicit None checks to avoid DeprecationWarning
        title_el = item.find("title")
        if title_el is None:
            title_el = item.find("{http://purl.org/rss/1.0/}title")
        if title_el is None:
            title_el = item.find("{http://www.w3.org/2005/Atom}title")

        link_el = item.find("link")
        if link_el is None:
            link_el = item.find("{http://purl.org/rss/1.0/}link")
        if link_el is None:
            link_el = item.find("{http://www.w3.org/2005/Atom}link")

        if title_el is not None and title_el.text:
            title = title_el.text.strip()

        if link_el is not None:
            link = (link_el.text or link_el.get("href", "")).strip()

        # arXiv: convert abstract URL to PDF URL
        if "arxiv.org/abs/" in link:
            pdf_link = link.replace("/abs/", "/pdf/") + ".pdf"
        elif link.endswith(".pdf"):
            pdf_link = link

        if title and link:
            papers.append({
                "title": title,
                "url": link,
                "pdf_url": pdf_link,
                "source": source_name
            })

    return papers

# ─── Module 3: HTML Spider (SSRN) ───────────────────────────────────────────
class SSRNParser(HTMLParser):
    """Simple HTML parser to extract paper titles and links from SSRN pages"""
    def __init__(self):
        super().__init__()
        self.papers = []
        self._in_link = False
        self._current_title = ""
        self._current_url = ""

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            # SSRN paper links contain "abstract=" or "sol3/papers.cfm"
            if "ssrn.com/abstract=" in href or "papers.cfm" in href:
                self._in_link = True
                self._current_url = href
                self._current_title = ""

    def handle_data(self, data):
        if self._in_link:
            self._current_title += data.strip()

    def handle_endtag(self, tag):
        if tag == "a" and self._in_link:
            self._in_link = False
            if self._current_title and self._current_url:
                self.papers.append({
                    "title": self._current_title.strip(),
                    "url": self._current_url.strip(),
                    "pdf_url": "",  # SSRN requires login for PDF
                    "source": "SSRN"
                })
            self._current_title = ""
            self._current_url = ""

def parse_ssrn_html(html_content, source_name):
    """Parse SSRN HTML page and return list of paper dicts"""
    parser = SSRNParser()
    parser.papers = []
    try:
        parser.feed(html_content)
    except Exception as e:
        log_warn(f"HTML parse error for {source_name}: {e}")
    # Override source name
    for p in parser.papers:
        p["source"] = source_name
    return parser.papers

# ─── Module 5: Hit-and-Stop Algorithm ───────────────────────────────────────
def scrape_source(source, dry_run=False):
    """
    Scrape a single source using Hit-and-Stop:
    Walk papers newest→oldest. Stop at first known fingerprint.
    Returns list of newly downloaded paper paths.
    """
    name = source.get("name", "Unknown")
    url = source.get("url", "")
    src_type = source.get("type", "rss")

    log(f"━━━ Scanning source: [{name}] ━━━")
    log(f"    URL: {url}")
    log(f"    Type: {src_type}")

    # Fetch content
    content = fetch_url(url)
    if not content:
        log_warn(f"Could not fetch content from [{name}]. Skipping.")
        return []

    # Parse based on type
    if src_type == "rss":
        papers = parse_rss_feed(content, name)
    elif src_type == "html_scrape":
        papers = parse_ssrn_html(content, name)
    else:
        log_warn(f"Unknown source type '{src_type}' for [{name}]. Skipping.")
        return []

    log(f"    Found {len(papers)} paper(s) on page.")

    # Hit-and-Stop: walk newest→oldest
    new_papers = []
    consecutive_known = 0
    HIT_STOP_THRESHOLD = 3  # Stop after seeing 3 consecutive known papers

    for paper in papers:
        fp = make_fingerprint(paper["url"], paper["title"])

        if is_known(fp):
            consecutive_known += 1
            log_skip(f"KNOWN (#{consecutive_known}): {paper['title'][:60]}...")
            if consecutive_known >= HIT_STOP_THRESHOLD:
                log(f"    ⛔ Hit-and-Stop triggered after {HIT_STOP_THRESHOLD} consecutive known papers. Stopping scan.")
                break
            continue

        # Reset counter when we find a new paper
        consecutive_known = 0

        if len(new_papers) >= MAX_NEW_PER_SOURCE:
            log_warn(f"    Safety cap reached ({MAX_NEW_PER_SOURCE} papers). Stopping.")
            break

        # New paper found!
        log_ok(f"NEW: {paper['title'][:70]}")

        if dry_run:
            log(f"    [DRY RUN] Would download: {paper['pdf_url'] or paper['url']}")
            mark_known(fp, paper["title"], name, paper["url"], paper.get("pdf_url"), downloaded=False)
            new_papers.append(paper)
            continue

        # Try to download PDF
        downloaded_path = None
        if paper["pdf_url"]:
            downloaded_path = download_pdf(paper["pdf_url"], paper["title"])

        # Mark in ledger regardless of download success
        mark_known(fp, paper["title"], name, paper["url"], paper.get("pdf_url"),
                   downloaded=(downloaded_path is not None))

        if downloaded_path:
            paper["local_path"] = downloaded_path
            new_papers.append(paper)

    if not new_papers:
        log(f"    No new papers from [{name}].")

    return new_papers

def download_pdf(pdf_url, title):
    """Download a PDF file to inbox/ directory. Returns local path or None."""
    # Sanitize filename
    safe_title = "".join(c if c.isalnum() or c in " -_()" else "_" for c in title)
    safe_title = safe_title[:80].strip()  # Limit length
    filename = f"{safe_title}.pdf"
    filepath = os.path.join(INBOX_DIR, filename)

    if os.path.exists(filepath):
        log(f"    File already exists locally: {filename}")
        return filepath

    log(f"    Downloading PDF: {pdf_url[:80]}...")
    headers = {
        "User-Agent": "HOAI-AlphaResearch-Spider/1.0 (Academic Research Bot)"
    }
    req = urllib.request.Request(pdf_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()

            # Verify it's actually a PDF (check magic bytes)
            if data[:4] != b"%PDF" and "pdf" not in content_type.lower():
                log_warn(f"    Response is not a PDF (Content-Type: {content_type}). Skipping download.")
                return None

            os.makedirs(INBOX_DIR, exist_ok=True)
            with open(filepath, "wb") as f:
                f.write(data)

            size_kb = len(data) / 1024
            log_ok(f"    Saved: {filename} ({size_kb:.1f} KB)")
            return filepath

    except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
        log_warn(f"    Download failed: {e}")
        return None

# ─── Module 6: Auto-Chain ───────────────────────────────────────────────────
def chain_alpha_factory(new_papers, use_ai=False):
    """Run auto_alpha_factory.py on each newly downloaded paper"""
    if not new_papers:
        log("No new papers to process. Alpha Factory not triggered.")
        return

    downloadable = [p for p in new_papers if p.get("local_path")]
    if not downloadable:
        log("No downloaded PDFs available. Alpha Factory not triggered.")
        return

    log(f"━━━ Chaining Alpha Factory on {len(downloadable)} new paper(s) ━━━")

    for paper in downloadable:
        filename = os.path.basename(paper["local_path"])
        cmd = [sys.executable, ALPHA_FACTORY, "--paper", filename]
        if use_ai:
            cmd.append("--use-ai")

        log(f"  Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                log_ok(f"  Alpha Factory completed for: {filename}")
            else:
                log_warn(f"  Alpha Factory returned error for: {filename}")
                if result.stderr:
                    log_warn(f"  stderr: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            log_warn(f"  Alpha Factory timed out for: {filename}")
        except Exception as e:
            log_warn(f"  Alpha Factory error: {e}")

    # Update ledger: mark as processed
    conn = sqlite3.connect(DB_PATH)
    for paper in downloadable:
        fp = make_fingerprint(paper["url"], paper["title"])
        conn.execute("UPDATE scraped_papers SET processed = 1 WHERE fingerprint = ?", (fp,))
    conn.commit()
    conn.close()

# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="HOAI_CODE Web Spider Watchdog — Autonomous Paper Discovery & Download"
    )
    parser.add_argument("--auto-run", action="store_true",
                        help="After scraping, automatically run auto_alpha_factory.py on new papers")
    parser.add_argument("--use-ai", action="store_true",
                        help="Pass --use-ai flag to auto_alpha_factory.py (requires API key in .env)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview mode: scan sources but do NOT download anything")
    args = parser.parse_args()

    log("=" * 60)
    log("  WEB SPIDER WATCHDOG — Starting Autonomous Scan")
    log("=" * 60)

    if args.dry_run:
        log("  🔍 Mode: DRY RUN (preview only, no downloads)")
    elif args.auto_run:
        log("  🚀 Mode: SCRAPE + AUTO-RUN Alpha Factory")
    else:
        log("  📥 Mode: SCRAPE & DOWNLOAD only")

    # Initialize
    init_ledger_db()
    os.makedirs(INBOX_DIR, exist_ok=True)
    sources, watchdog_cfg = load_registry()

    if not sources:
        log_warn("No enabled sources found in web_registry.yaml. Nothing to do.")
        return

    log(f"Loaded {len(sources)} active source(s) from registry.")
    log("")

    # Scrape all sources
    all_new_papers = []
    for source in sources:
        new_papers = scrape_source(source, dry_run=args.dry_run)
        all_new_papers.extend(new_papers)
        log("")  # Blank line between sources

    # Summary
    log("=" * 60)
    log(f"  SCAN COMPLETE — {len(all_new_papers)} new paper(s) discovered")
    log("=" * 60)

    if all_new_papers:
        log("")
        log("New papers found:")
        for i, p in enumerate(all_new_papers, 1):
            status = "📄 Downloaded" if p.get("local_path") else "🔗 Link only"
            log(f"  {i}. [{p['source']}] {p['title'][:60]} — {status}")

    # Auto-chain if requested
    if args.auto_run and not args.dry_run:
        log("")
        chain_alpha_factory(all_new_papers, use_ai=args.use_ai)

    log("")
    log("Spider Watchdog finished. Goodbye! 🕷️")

if __name__ == "__main__":
    main()
