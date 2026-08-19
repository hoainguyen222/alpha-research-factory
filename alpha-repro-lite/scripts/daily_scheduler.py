#!/usr/bin/env python3
"""
====================================================================================================
PROJECT: ALPHA RESEARCH FACTORY
MODULE: Daily Scheduler — Tiến trình chạy ngầm lập lịch tự động
FILE: scripts/daily_scheduler.py
====================================================================================================
Tiến trình Python nhẹ nhàng chạy ngầm (daemon), cứ mỗi 60 giây kiểm tra:
- Đọc khung giờ từ bot_settings.json (ví dụ "02:00").
- Nếu đúng giờ → chạy pipeline phù hợp theo chế độ đã cấu hình.
- Chế độ TARGETED_LINKS → gọi web_spider_watchdog.py.
- Chế độ OPEN_DISCOVERY → gọi autonomous_discovery.py (AI tự nghĩ từ khóa).
- Sau đó tự động gọi Alpha Factory để phân tích.
====================================================================================================
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

SETTINGS_PATH = BASE_DIR / "storage" / "bot_settings.json"
SCRIPTS_DIR = BASE_DIR / "scripts"


def load_settings():
    """Đọc cấu hình từ bot_settings.json."""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {"scraping_mode": "TARGETED_LINKS", "schedule_time": "02:00"}


def run_script(script_name, args=None):
    """Chạy một script Python con."""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"[SCHEDULER] ⚠ Script không tồn tại: {script_path}")
        return
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
    print(f"[SCHEDULER] ▶ Đang chạy: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, timeout=600)
        if result.stdout:
            print(result.stdout[-2000:])
        if result.returncode != 0 and result.stderr:
            print(f"[SCHEDULER] ⚠ Lỗi: {result.stderr[-500:]}")
    except subprocess.TimeoutExpired:
        print(f"[SCHEDULER] ⏰ Script timeout (10 phút)")
    except Exception as e:
        print(f"[SCHEDULER] ❌ Lỗi: {e}")


def run_daily_pipeline():
    """Chạy pipeline hàng ngày dựa trên chế độ cấu hình."""
    settings = load_settings()
    mode = settings.get("scraping_mode", "TARGETED_LINKS")

    print(f"\n{'='*60}")
    print(f"  🗓️  DAILY SCHEDULER — Pipeline hàng ngày")
    print(f"  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  📋 Chế độ: {mode}")
    print(f"{'='*60}\n")

    if mode == "OPEN_DISCOVERY":
        # Chế độ AI tự khám phá
        print("[SCHEDULER] 🌍 Chế độ: AI TỰ ĐỘNG KHÁM PHÁ")
        run_script("autonomous_discovery.py")
    else:
        # Chế độ quét Link cố định
        print("[SCHEDULER] 🕷️ Chế độ: QUÉT LINK CỐ ĐỊNH")
        run_script("web_spider_watchdog.py", ["--auto-run"])

    # Sau khi cào xong, tự động gọi Alpha Factory phân tích
    print("\n[SCHEDULER] 🧠 Gọi Alpha Factory phân tích tài liệu mới...")
    run_script("auto_alpha_factory.py")

    print(f"\n[SCHEDULER] ✅ Pipeline hàng ngày hoàn tất lúc {datetime.now().strftime('%H:%M:%S')}")


def main():
    """Vòng lặp chính: kiểm tra mỗi 60 giây xem đã đến giờ chưa."""
    print(f"\n{'='*60}")
    print(f"  🕐 DAILY SCHEDULER — Đang chạy ngầm")
    print(f"  📂 Settings: {SETTINGS_PATH}")
    print(f"{'='*60}\n")

    last_run_date = None

    while True:
        try:
            settings = load_settings()
            schedule_time = settings.get("schedule_time", "02:00")
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")

            # Kiểm tra: đúng giờ + chưa chạy hôm nay
            if current_time == schedule_time and last_run_date != current_date:
                print(f"[SCHEDULER] 🔔 Đến giờ chạy! ({schedule_time})")
                last_run_date = current_date
                run_daily_pipeline()
            
            time.sleep(60)  # Kiểm tra mỗi 60 giây

        except KeyboardInterrupt:
            print("\n[SCHEDULER] 🛑 Đã dừng.")
            break
        except Exception as e:
            print(f"[SCHEDULER] ❌ Lỗi: {e}")
            time.sleep(60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run-now":
        # Chạy pipeline ngay lập tức (không cần đợi đến giờ)
        run_daily_pipeline()
    else:
        main()
