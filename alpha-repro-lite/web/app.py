"""
====================================================================================================
PROJECT: ALPHA RESEARCH FACTORY — Unified Dashboard
MODULE: Flask Web Application & REST API Server
FILE: web/app.py
====================================================================================================
Dashboard hợp nhất trên Port 5060:
- Tab Leaderboard: Bảng xếp hạng chiến lược Quant (từ quant_platform.db)
- Tab Paper Vault: Kho tài liệu FTS5 (từ research_vault.db)
- Tab Spider Control: Điều khiển Spider & Alpha Factory
- Tab Upload: Kéo thả file vào hệ thống
- REST API endpoints cho tất cả chức năng
====================================================================================================
"""

import os
import sys
import io
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response

# Ensure proper encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import (WEB_HOST, WEB_PORT, SECRET_KEY, QUANT_DB_PATH,
                     JSONL_VAULT_PATH, CSV_VAULT_PATH, SQLITE_DB_PATH,
                     INBOX_DIR, REPORTS_DIR)

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / "templates"),
    static_folder=str(Path(__file__).resolve().parent / "static")
)
app.secret_key = SECRET_KEY
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.jinja_env.auto_reload = True

# Lazy imports for coordinator & vault (only when needed)
_coordinator = None
_vault_db = None
_raw_manager = None

def get_coordinator():
    global _coordinator
    if _coordinator is None:
        from research_coordinator import ResearchCoordinator
        _coordinator = ResearchCoordinator()
    return _coordinator

def get_vault_db():
    global _vault_db
    if _vault_db is None:
        from vault.unified_vault_db import UnifiedVaultDB
        _vault_db = UnifiedVaultDB()
    return _vault_db

def get_raw_manager():
    global _raw_manager
    if _raw_manager is None:
        from vault.raw_archive_manager import RawArchiveManager
        _raw_manager = RawArchiveManager()
    return _raw_manager


# ─── Quant Leaderboard Helpers ───────────────────────────────────────────────
def get_leaderboard_data():
    """Fetch strategy leaderboard from quant_platform.db"""
    if not Path(QUANT_DB_PATH).exists():
        return []
    conn = sqlite3.connect(str(QUANT_DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT paper_id, symbol, timeframe, sharpe_ratio, sortino_ratio, calmar_ratio,
               profit_factor, hit_rate_pct, total_return_pct, max_drawdown_pct,
               annualized_return_pct, alpha_pct, beta, total_ticks, throughput_ticks_sec
        FROM backtest_metrics ORDER BY sharpe_ratio DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_quant_stats():
    """Get summary stats from quant_platform.db"""
    if not Path(QUANT_DB_PATH).exists():
        return {"total_strategies": 0, "avg_sharpe": 0, "best_return": 0, "total_papers": 0}
    conn = sqlite3.connect(str(QUANT_DB_PATH))
    row = conn.execute("""
        SELECT COUNT(*) as cnt, COALESCE(AVG(sharpe_ratio),0) as avg_sharpe,
               COALESCE(MAX(total_return_pct),0) as best_ret
        FROM backtest_metrics
    """).fetchone()
    
    # Đếm số lượng thành phần chiến lược
    comp_row = conn.execute("SELECT COUNT(*) FROM extracted_strategy_components").fetchone() if _table_exists(conn, "extracted_strategy_components") else (0,)
    conn.close()

    # Đếm số lượng Paper đã quét và thu thập từ Web/Academic trong Vault
    scraped_count = 0
    try:
        vault_db_file = BASE_DIR / "storage" / "structured_vault" / "research_vault.db"
        c_vault = sqlite3.connect(str(vault_db_file))
        total_vault = c_vault.execute("SELECT COUNT(*) FROM research_vault").fetchone()[0]
        # Các bài do Spider & Discovery Agent tự động quét và tải về từ Internet
        scraped_count = max(0, total_vault - 1) if total_vault > 1 else 0
        c_vault.close()
    except Exception:
        scraped_count = 0

    return {
        "total_strategies": comp_row[0] if comp_row else row[0],
        "avg_sharpe": round(row[1], 2),
        "best_return": round(row[2], 2),
        "total_papers": comp_row[0] if comp_row else 0,
        "scraped_papers": scraped_count
    }

def _table_exists(conn, table_name):
    r = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
    return r is not None


# ─── Pages ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Dashboard trang chủ."""
    quant_stats = get_quant_stats()
    try:
        vault_stats = get_vault_db().get_statistics()
    except Exception:
        vault_stats = {"total_entries": 0, "total_words": 0, "db_size_kb": 0}
    try:
        from vault.learned_rule_engine import LearnedRuleEngine
        rule_stats = LearnedRuleEngine().get_stats()
    except Exception:
        rule_stats = {"total_rules": 0, "total_hits": 0}
    return render_template("index.html", quant_stats=quant_stats, vault_stats=vault_stats, rule_stats=rule_stats, port=WEB_PORT)


# ─── Leaderboard API ────────────────────────────────────────────────────────
@app.route("/api/leaderboard", methods=["GET"])
def api_leaderboard():
    """API lấy bảng xếp hạng chiến lược Quant."""
    data = get_leaderboard_data()
    return jsonify({"status": "success", "strategies": data, "total": len(data)})


# ─── Spider Control API ─────────────────────────────────────────────────────
@app.route("/api/spider/run", methods=["POST"])
def api_spider_run():
    """API kích hoạt Spider Watchdog."""
    data = request.get_json(silent=True) or {}
    dry_run = data.get("dry_run", False)
    auto_run = data.get("auto_run", False)
    use_ai = data.get("use_ai", False)

    spider_script = str(BASE_DIR / "scripts" / "web_spider_watchdog.py")
    cmd = [sys.executable, spider_script]
    if dry_run:
        cmd.append("--dry-run")
    if auto_run:
        cmd.append("--auto-run")
    if use_ai:
        cmd.append("--use-ai")

    try:
        result = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=300)
        return jsonify({
            "status": "success",
            "exit_code": result.returncode,
            "output": result.stdout[-3000:] if result.stdout else "",
            "errors": result.stderr[-1000:] if result.stderr else ""
        })
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "message": "Spider timed out (5 min limit)"}), 504
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/spider/status", methods=["GET"])
def api_spider_status():
    """API lấy trạng thái Spider (số bài đã quét)."""
    if not Path(QUANT_DB_PATH).exists():
        return jsonify({"status": "success", "scraped_total": 0, "downloaded": 0})
    conn = sqlite3.connect(str(QUANT_DB_PATH))
    if _table_exists(conn, "scraped_papers"):
        total = conn.execute("SELECT COUNT(*) FROM scraped_papers").fetchone()[0]
        downloaded = conn.execute("SELECT COUNT(*) FROM scraped_papers WHERE downloaded=1").fetchone()[0]
    else:
        total, downloaded = 0, 0
    conn.close()
    return jsonify({"status": "success", "scraped_total": total, "downloaded": downloaded})


# ─── Settings API (Toggle & Scheduler) ──────────────────────────────────────
SETTINGS_PATH = BASE_DIR / "storage" / "bot_settings.json"

def _load_settings():
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {"scraping_mode": "TARGETED_LINKS", "schedule_time": "02:00"}

def _save_settings(settings):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

def _update_crontab(settings):
    schedule_time = settings.get("schedule_time", "02:00")
    try:
        hour, minute = schedule_time.split(":")
    except ValueError:
        return
    # Use curl to trigger the API via OS cron
    cron_cmd = f"{minute} {hour} * * * curl -s -X POST http://127.0.0.1:5055/api/spider/run-pipeline > /dev/null 2>&1 # AlphaResearchCron"
    
    try:
        # Get current crontab
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        current_cron = result.stdout if result.returncode == 0 else ""
        
        # Remove old AlphaResearchCron
        new_cron_lines = [line for line in current_cron.splitlines() if "AlphaResearchCron" not in line]
        
        # Add new one
        new_cron_lines.append(cron_cmd)
        new_cron = "\n".join(new_cron_lines) + "\n"
        
        # Write to crontab
        subprocess.run(["crontab", "-"], input=new_cron, text=True, check=True)
    except Exception as e:
        print(f"Error updating crontab: {e}")

@app.route("/api/spider/settings", methods=["GET"])
def api_get_settings():
    """API đọc cấu hình toggle & scheduler."""
    return jsonify({"status": "success", "settings": _load_settings()})

@app.route("/api/spider/settings", methods=["POST"])
def api_save_settings():
    """API lưu cấu hình toggle & scheduler."""
    data = request.get_json(silent=True) or {}
    settings = _load_settings()
    if "scraping_mode" in data:
        settings["scraping_mode"] = data["scraping_mode"]
    if "schedule_time" in data:
        settings["schedule_time"] = data["schedule_time"]
    _save_settings(settings)
    _update_crontab(settings)
    return jsonify({"status": "success", "message": "Settings saved & OS Crontab updated", "settings": settings})

@app.route("/api/scheduler/status", methods=["GET"])
def api_scheduler_status():
    """API lấy trạng thái hoạt động thực tế của Scheduler và lần chạy gần nhất."""
    state_file = BASE_DIR / "storage" / "scheduler_state.json"
    state = {}
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            pass
    
    # Kiểm tra daemon status
    is_active = False
    try:
        res = subprocess.run(["systemctl", "--user", "is-active", "alpha_scheduler.service"], capture_output=True, text=True)
        is_active = (res.stdout.strip() == "active")
    except Exception:
        pass

    return jsonify({
        "status": "success",
        "service_active": is_active,
        "last_run_date": state.get("last_run_date", "Chưa chạy"),
        "last_run_time": state.get("last_run_time", "")
    })

@app.route("/api/spider/run-pipeline", methods=["POST"])
def api_run_pipeline():
    """API chạy pipeline ngay lập tức (dựa theo chế độ đang cấu hình)."""
    settings = _load_settings()
    mode = settings.get("scraping_mode", "TARGETED_LINKS")

    if mode == "OPEN_DISCOVERY":
        script = str(BASE_DIR / "scripts" / "autonomous_discovery.py")
    else:
        script = str(BASE_DIR / "scripts" / "web_spider_watchdog.py")

    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=str(BASE_DIR), capture_output=True, text=True, timeout=300
        )
        output = result.stdout[-3000:] if result.stdout else ""
        errors = result.stderr[-1000:] if result.stderr else ""

        # Sau đó xử lý toàn bộ file trong inbox vào Vault
        process_script = str(BASE_DIR / "scripts" / "process_inbox.py")
        process_result = subprocess.run(
            [sys.executable, process_script],
            cwd=str(BASE_DIR), capture_output=True, text=True, timeout=300
        )
        output += "\n\n--- Process Inbox & Vault ---\n" + (process_result.stdout[-2000:] if process_result.stdout else "")

        return jsonify({
            "status": "success", "mode": mode,
            "output": output, "errors": errors
        })
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "message": "Pipeline timed out"}), 504
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ─── Alpha Factory API ──────────────────────────────────────────────────────
@app.route("/api/alpha/run", methods=["POST"])
def api_alpha_run():
    """API kích hoạt xử lý dữ liệu inbox vào Vault."""
    data = request.get_json(silent=True) or {}
    
    factory_script = str(BASE_DIR / "scripts" / "process_inbox.py")
    cmd = [sys.executable, factory_script]

    try:
        result = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=300)
        return jsonify({
            "status": "success",
            "exit_code": result.returncode,
            "output": result.stdout[-3000:] if result.stdout else "",
            "errors": result.stderr[-1000:] if result.stderr else ""
        })
    except subprocess.TimeoutExpired:
        return jsonify({"status": "error", "message": "Alpha Factory timed out"}), 504
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── Vault API (từ đồng nghiệp, đã adapt) ──────────────────────────────────
@app.route("/api/research/url", methods=["POST"])
def api_research_url():
    """API thu thập Link URL (Paper, Blog, YouTube)."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"status": "error", "message": "URL required"}), 400
    try:
        result = get_coordinator().process_url(url, custom_note=data.get("custom_note", ""))
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/research/keyword", methods=["POST"])
def api_research_keyword():
    """API tìm kiếm theo từ khóa."""
    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"status": "error", "message": "Query required"}), 400
    try:
        result = get_coordinator().process_keyword_query(query, custom_note=data.get("custom_note", ""))
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/research/upload", methods=["POST"])
def api_research_upload():
    """API upload file (PDF, DOCX, XLSX, CSV, Image) và tự động kích hoạt bóc tách Full-Pipeline."""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"status": "error", "message": "Empty filename"}), 400
    try:
        result = get_coordinator().process_file_upload(
            file.read(), filename=file.filename, custom_note=request.form.get("custom_note", ""))
        
        # ─── Tự Động Kích Hoạt Bóc Tách Full-Pipeline (A -> Z) ───
        raw_path = result.get("raw_file_path")
        paper_id = result.get("entry_id")
        if raw_path and Path(raw_path).exists():
            try:
                from scripts.auto_alpha_factory import analyze_paper
                print(f"[AUTO-UPLOAD] 🚀 Đang tự động phân tích và trích xuất chuyên sâu cho {paper_id}...")
                analyze_paper(raw_path, use_ai=True)
                print(f"[AUTO-UPLOAD] ✅ Đã hoàn tất bóc tách thành phần chiến lược cho {paper_id}!")
            except Exception as ex:
                print(f"[AUTO-UPLOAD] ⚠ Lỗi trích xuất tự động: {ex}")
                
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/vault/search", methods=["GET"])
def api_vault_search():
    """API tìm kiếm FTS5 trong Vault."""
    keyword = request.args.get("q", "").strip()
    source_type = request.args.get("type", "").strip()
    limit = int(request.args.get("limit", 50))
    try:
        if keyword.startswith("RES-"):
            exact = get_vault_db().get_by_id(keyword)
            if exact:
                return jsonify({"status": "success", "results": [exact], "total": 1})
        results, total = get_vault_db().search(keyword=keyword, source_type=source_type, limit=limit)
        return jsonify({"status": "success", "results": results, "total": total, "query": keyword})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/vault/entry/<entry_id>", methods=["GET"])
def api_vault_entry(entry_id):
    """API xem chi tiết bản ghi."""
    entry = get_vault_db().get_by_id(entry_id)
    if not entry:
        return jsonify({"status": "error", "message": f"Not found: {entry_id}"}), 404
    return jsonify({"status": "success", "entry": entry})

@app.route("/api/vault/stats", methods=["GET"])
def api_vault_stats():
    """API thống kê Vault."""
    try:
        stats = get_vault_db().get_statistics()
        return jsonify({"status": "success", "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/vault/export/<fmt>", methods=["GET"])
def api_vault_export(fmt):
    """API xuất Vault (jsonl/csv/sqlite)."""
    fmt = fmt.lower()
    if fmt == "jsonl" and JSONL_VAULT_PATH.exists():
        return send_file(JSONL_VAULT_PATH, as_attachment=True, download_name="unified_vault.jsonl")
    elif fmt == "csv" and CSV_VAULT_PATH.exists():
        return send_file(CSV_VAULT_PATH, as_attachment=True, download_name="unified_vault.csv")
    elif fmt in ("sqlite", "db") and SQLITE_DB_PATH.exists():
        return send_file(SQLITE_DB_PATH, as_attachment=True, download_name="research_vault.db")
    return jsonify({"status": "error", "message": f"Format '{fmt}' not available"}), 400

@app.route("/api/inbox/list", methods=["GET"])
def api_inbox_list():
    """API liệt kê file trong inbox/."""
    files = []
    inbox = Path(INBOX_DIR)
    if inbox.exists():
        for f in sorted(inbox.iterdir()):
            if f.is_file() and not f.name.startswith("."):
                files.append({"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)})
    return jsonify({"status": "success", "files": files, "total": len(files)})


# ─── Learned Rules Memory API ───────────────────────────────────────────────
@app.route("/api/rules/list", methods=["GET"])
def api_rules_list():
    """API lấy danh sách các Rule AI đã học và tích lũy."""
    try:
        from vault.learned_rule_engine import LearnedRuleEngine
        engine = LearnedRuleEngine()
        rules = engine.list_rules()
        stats = engine.get_stats()
        return jsonify({"status": "success", "rules": rules, "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/rules/stats", methods=["GET"])
def api_rules_stats():
    """API thống kê số lượng Rule và số lần match."""
    try:
        from vault.learned_rule_engine import LearnedRuleEngine
        engine = LearnedRuleEngine()
        stats = engine.get_stats()
        return jsonify({"status": "success", "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── Crawler Site Templates API ─────────────────────────────────────────────
@app.route("/api/templates/list", methods=["GET"])
def api_templates_list():
    """API lấy danh sách các Website Templates đã học."""
    try:
        from vault.site_template_engine import SiteTemplateEngine
        engine = SiteTemplateEngine()
        templates = engine.list_templates()
        stats = engine.get_stats()
        return jsonify({"status": "success", "templates": templates, "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── Extracted Strategy Components API ──────────────────────────────────────
@app.route("/api/components/list", methods=["GET"])
def api_components_list():
    """API lấy danh sách các thành phần chiến lược (Code, Công thức, Tham số) đã bóc tách."""
    try:
        from vault.strategy_components_db import StrategyComponentsDB
        db = StrategyComponentsDB()
        comps = db.list_components()
        stats = db.get_stats()
        return jsonify({"status": "success", "components": comps, "stats": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/components/<comp_id>", methods=["GET"])
def api_components_detail(comp_id):
    """API lấy chi tiết 1 thành phần chiến lược."""
    try:
        from vault.strategy_components_db import StrategyComponentsDB
        db = StrategyComponentsDB()
        comp = db.get_component(comp_id)
        if not comp:
            return jsonify({"status": "error", "message": f"Component '{comp_id}' not found"}), 404
        return jsonify({"status": "success", "component": comp})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── Server Start ────────────────────────────────────────────────────────────
def start_server():
    """Khởi động Dashboard Web Server."""
    print(f"\n{'='*70}")
    print(f"  🚀 ALPHA RESEARCH FACTORY — Dashboard")
    print(f"  🌐 http://{WEB_HOST}:{WEB_PORT}")
    print(f"  📊 Quant DB: {QUANT_DB_PATH}")
    print(f"  📚 Vault DB: {SQLITE_DB_PATH}")
    print(f"{'='*70}\n")

    try:
        from waitress import serve
        serve(app, host=WEB_HOST, port=WEB_PORT)
    except ImportError:
        app.run(host=WEB_HOST, port=WEB_PORT, debug=False)


if __name__ == "__main__":
    start_server()
