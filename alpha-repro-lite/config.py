"""
====================================================================================================
PROJECT: ALPHA RESEARCH FACTORY (Unified Quant Research Platform)
MODULE: System Configuration & Path Management
FILE: config.py
====================================================================================================
Hợp nhất cấu hình từ agent_research_update + alpha-repro-lite.
Port Dashboard: 5060 (tách biệt hoàn toàn với port 5050 của đồng nghiệp).
====================================================================================================
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
STORAGE_DIR = BASE_DIR / "storage"
RAW_SOURCES_DIR = STORAGE_DIR / "raw_sources"
STRUCTURED_VAULT_DIR = STORAGE_DIR / "structured_vault"
UPLOADS_DIR = STORAGE_DIR / "uploads"
LOGS_DIR = BASE_DIR / "logs"

# Quant Engine Paths (giữ nguyên từ alpha-repro-lite)
INBOX_DIR = BASE_DIR / "inbox"
CASES_DIR = BASE_DIR / "cases"
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
SOURCES_DIR = BASE_DIR / "sources"
QUANT_DB_PATH = BASE_DIR / "quant_platform.db"
ENGINE_BIN = BASE_DIR / "cases" / "ssrn-3325656-lr-momentum" / "bin" / "hoai_engine"

# Ensure all critical directories exist
for d in [STORAGE_DIR, RAW_SOURCES_DIR, STRUCTURED_VAULT_DIR, UPLOADS_DIR, LOGS_DIR,
          INBOX_DIR, CASES_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Vault Storage File Paths
SQLITE_DB_PATH = STRUCTURED_VAULT_DIR / "research_vault.db"
JSONL_VAULT_PATH = STRUCTURED_VAULT_DIR / "unified_vault.jsonl"
CSV_VAULT_PATH = STRUCTURED_VAULT_DIR / "unified_vault.csv"

# Web Server Configuration
WEB_HOST = os.getenv("ALPHA_WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("ALPHA_WEB_PORT", 5055))
SECRET_KEY = os.getenv("SECRET_KEY", "alpha_research_factory_secure_key_2026")
DEBUG_MODE = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Load .env for API Keys
env_path = BASE_DIR / ".env"
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                try:
                    key, val = line.strip().split("=", 1)
                    os.environ[key] = val.strip('"\'')
                except ValueError:
                    pass

# Autonomous Bypass & Academic Open Access Endpoints
UNPAYWALL_EMAIL = os.getenv("UNPAYWALL_EMAIL", "agent_researcher@unpaywall.org")
SEMANTIC_SCHOLAR_API_URL = "https://api.semanticscholar.org/graph/v1"
OPENALEX_API_URL = "https://api.openalex.org"
CROSSREF_API_URL = "https://api.crossref.org/works"
ARXIV_API_URL = "http://export.arxiv.org/api/query"
WAYBACK_API_URL = "https://archive.org/wayback/available"
JINA_READER_PREFIX = "https://r.jina.ai/"

# Academic / Proxy Fallback Mirrors
SCIHUB_MIRRORS = [
    "https://sci-hub.se",
    "https://sci-hub.st",
    "https://sci-hub.ru",
    "https://sci-hub.ren"
]

# User Agent Rotation Pool
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

# Default HTTP Request Headers
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENTS[0],
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    "DNT": "1",
    "Connection": "keep-alive",
}

# Request Timeouts (in seconds)
HTTP_TIMEOUT = 25
MEDIA_DOWNLOAD_TIMEOUT = 60

# Max Upload Size (50 MB)
MAX_CONTENT_LENGTH = 50 * 1024 * 1024

# Supported File Extensions
ALLOWED_EXTENSIONS = {
    "pdf": "FILE_PDF", "docx": "FILE_DOCX", "doc": "FILE_DOCX",
    "xlsx": "FILE_EXCEL", "xls": "FILE_EXCEL",
    "csv": "FILE_CSV", "tsv": "FILE_CSV",
    "txt": "FILE_TEXT", "md": "FILE_MARKDOWN", "json": "FILE_JSON",
    "png": "IMAGE", "jpg": "IMAGE", "jpeg": "IMAGE", "webp": "IMAGE",
    "mp4": "VIDEO", "mov": "VIDEO", "mkv": "VIDEO",
}
