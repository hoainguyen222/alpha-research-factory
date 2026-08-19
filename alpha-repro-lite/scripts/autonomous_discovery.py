#!/usr/bin/env python3
"""
====================================================================================================
PROJECT: ALPHA RESEARCH FACTORY
MODULE: AI Autonomous Discovery Agent
FILE: scripts/autonomous_discovery.py
====================================================================================================
Khi chế độ "OPEN_DISCOVERY" được bật, script này sẽ:
1. Gọi AI (Claude/GPT/Gemini) để TỰ SINH từ khóa nghiên cứu Quant mới lạ nhất.
2. Dùng từ khóa đó truy vấn arXiv API, CrossRef API, OpenAlex API.
3. Tải tài liệu (PDF, Transcript video) về lưu vào Vault.
4. Tự động gọi Alpha Factory để phân tích chiến lược.

Fallback: Nếu không có API key AI, sử dụng danh sách từ khóa mặc định xoay vòng.
====================================================================================================
"""

import os
import sys
import json
import random
import hashlib
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import STORAGE_DIR, INBOX_DIR
from extractors.keyword_search_engine import KeywordSearchEngine
from extractors.video_extractor import VideoExtractor
try:
    from youtubesearchpython import VideosSearch
except ImportError:
    VideosSearch = None

# ─── Danh sách từ khóa xoay vòng (Fallback khi không có AI) ────────────
DEFAULT_KEYWORD_POOL = [
    "quantitative trading strategy cryptocurrency",
    "mean reversion pairs trading equities",
    "momentum factor investing portfolio",
    "machine learning stock prediction",
    "statistical arbitrage market microstructure",
    "options pricing volatility surface",
    "reinforcement learning algorithmic trading",
    "risk parity portfolio optimization",
    "order book imbalance high frequency",
    "sentiment analysis crypto returns",
    "cross-sectional momentum anomaly",
    "LSTM neural network financial forecasting",
    "factor model asset pricing empirical",
    "Bayesian portfolio allocation",
    "fractal analysis cryptocurrency market",
    "Kalman filter pairs trading",
    "GARCH volatility modeling crypto",
    "Elliott wave automated detection",
    "smart beta ETF construction",
    "tail risk hedging derivatives",
]

SETTINGS_PATH = STORAGE_DIR / "bot_settings.json"
DISCOVERY_LOG_PATH = STORAGE_DIR / "discovery_log.json"

def load_env():
    """Load API keys from .env file."""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    try:
                        k, v = line.strip().split("=", 1)
                        os.environ[k] = v.strip("'\"")
                    except ValueError:
                        pass

def ai_generate_keywords():
    import urllib.request
    load_env()
    prompt = (
        "You are a senior quantitative researcher at a top hedge fund. "
        "Generate exactly 3 highly specific, novel academic search queries "
        "for finding quantitative trading strategy papers. "
        "Return ONLY a JSON array of 3 strings."
    )
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if api_key:
        try:
            data = json.dumps({"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]}).encode()
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=data, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                text = json.loads(resp.read().decode())["choices"][0]["message"]["content"]
                return json.loads(text)[:3]
        except Exception: pass
    return None

def fallback_keywords():
    used = set()
    if DISCOVERY_LOG_PATH.exists():
        try:
            with open(DISCOVERY_LOG_PATH) as f:
                for entry in json.load(f)[-10:]: used.update(entry.get("keywords", []))
        except Exception: pass
    available = [kw for kw in DEFAULT_KEYWORD_POOL if kw not in used]
    if len(available) < 3: available = DEFAULT_KEYWORD_POOL
    return random.sample(available, min(3, len(available)))

def search_and_download_youtube(query: str):
    """Tìm video trên YouTube và tải transcript."""
    if not VideosSearch:
        return 0
    try:
        videosSearch = VideosSearch(query, limit=1)
        results = videosSearch.result().get('result', [])
        if not results: return 0
        video_url = results[0]['link']
        title = results[0]['title']
        
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[:80].strip()
        filename = f"YT_{safe_title}.txt"
        filepath = INBOX_DIR / filename
        if filepath.exists(): return 0
        
        print(f"  🎥 YouTube: {title}")
        data = VideoExtractor.extract_from_youtube(video_url)
        if data and data.get("text"):
            with open(filepath, "w") as f:
                f.write(data["text"])
            return 1
    except Exception as e:
        print(f"  ❌ YouTube Error: {e}")
    return 0

def run_discovery():
    """Quy trình chính: AI sinh từ khóa → Tìm bài báo/video → Tải về."""
    print("=" * 60)
    print("  🌍 AUTONOMOUS DISCOVERY AGENT — Bắt đầu khám phá (4 Nguồn)")
    print(f"  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    keywords = ai_generate_keywords()
    if not keywords: keywords = fallback_keywords()
    
    total_found = 0
    total_downloaded = 0
    search_engine = KeywordSearchEngine()

    for kw in keywords:
        print(f"\n🔎 Từ khóa: \"{kw}\"")
        
        # 1. Tìm YouTube (Video)
        total_downloaded += search_and_download_youtube(kw)
        
        # 2. Tìm Academic (arXiv, CrossRef, OpenAlex)
        results = search_engine.search_all(kw, limit_per_source=2)
        papers = results.get("arxiv", []) + results.get("openalex", []) + results.get("crossref", [])
        total_found += len(papers)
        
        for p in papers:
            title = p.get("title", "Untitled")
            pdf_url = p.get("pdf_url")
            if not pdf_url: continue
            
            safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[:80].strip()
            if not safe_title: safe_title = hashlib.sha256(pdf_url.encode()).hexdigest()[:12]
            filepath = INBOX_DIR / f"{safe_title}.pdf"
            
            if filepath.exists(): continue
            print(f"  📄 Academic: {title[:70]}...")
            
            try:
                import urllib.request
                from research_coordinator import ResearchCoordinator
                
                req = urllib.request.Request(pdf_url, headers={"User-Agent": "Mozilla/5.0 (compatible; AlphaResearchBot/1.0)"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    pdf_bytes = resp.read()
                
                if len(pdf_bytes) > 5000:
                    coordinator = ResearchCoordinator()
                    res = coordinator.process_file_upload(pdf_bytes, filename=f"{safe_title}.pdf")
                    print(f"    ⭐ Đã nạp thành công vào Vault: ID {res.get('id')} - {title[:50]}...")
                    total_downloaded += 1
            except Exception as ex:
                print(f"    ⚠ Lỗi tải/nạp bài: {ex}")

    # Log
    log = []
    if DISCOVERY_LOG_PATH.exists():
        try:
            with open(DISCOVERY_LOG_PATH) as f: log = json.load(f)
        except Exception: pass
    log.append({"timestamp": datetime.now().isoformat(), "keywords": keywords, "papers_found": total_found, "papers_downloaded": total_downloaded})
    with open(DISCOVERY_LOG_PATH, "w") as f: json.dump(log[-100:], f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print(f"  ✅ Hoàn tất! Tìm thấy {total_found} bài, tải {total_downloaded} file mới.")
    print(f"{'=' * 60}")

    return {"keywords": keywords, "found": total_found, "downloaded": total_downloaded}


if __name__ == "__main__":
    run_discovery()
