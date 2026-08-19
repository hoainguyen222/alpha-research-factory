#!/usr/bin/env python3
"""
====================================================================================================
PROJECT: ALPHA RESEARCH FACTORY
MODULE: Smart Auto Runner — Tự động chạy quét bài thông minh theo lịch hẹn & Chạy bù khi mở máy
FILE: scripts/smart_auto_runner.py
====================================================================================================
Cơ chế bảo vệ:
1. Đọc lịch hẹn từ storage/bot_settings.json (Ví dụ: "10:00" hoặc "02:00").
2. So sánh:
   - Nếu mở máy lúc 8h sáng mà lịch là 10h sáng (Chưa đến giờ): -> Chờ đến đúng 10h mới chạy.
   - Nếu mở máy lúc 10h30 mà lịch là 10h sáng (Đã qua giờ): -> Chạy bù ngay 1 lần duy nhất trong ngày.
   - Nếu hôm nay đã chạy rồi: -> Tuyệt đối không chạy lại để tiết kiệm Token và tài nguyên.
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
STATE_PATH = BASE_DIR / "storage" / "scheduler_state.json"
SCRIPTS_DIR = BASE_DIR / "scripts"


def load_settings():
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"scraping_mode": "TARGETED_LINKS", "schedule_time": "02:00"}


def load_state():
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_run_date": "", "last_run_time": ""}


def save_state(date_str, time_str):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"last_run_date": date_str, "last_run_time": time_str}, f, indent=2)


def execute_pipeline():
    """Thực thi chuỗi cào dữ liệu và phân tích Alpha Factory."""
    settings = load_settings()
    mode = settings.get("scraping_mode", "TARGETED_LINKS")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n{'='*70}")
    print(f"  🚀 SMART AUTO RUNNER — Bắt đầu Pipeline tự động")
    print(f"  ⏰ Thời gian: {now_str}")
    print(f"  📋 Chế độ: {mode}")
    print(f"{'='*70}\n")

    # 1. Cào bài báo
    if mode == "OPEN_DISCOVERY":
        script = SCRIPTS_DIR / "autonomous_discovery.py"
        cmd = [sys.executable, str(script)]
    else:
        script = SCRIPTS_DIR / "web_spider_watchdog.py"
        cmd = [sys.executable, str(script), "--auto-run"]

    print(f"[SMART-RUNNER] ▶ Đang cào tài liệu mới...")
    try:
        subprocess.run(cmd, cwd=str(BASE_DIR), timeout=600)
    except Exception as e:
        print(f"[SMART-RUNNER] ⚠ Lỗi Spider: {e}")

    # 2. Phân tích bóc tách và Backtest
    print(f"[SMART-RUNNER] 🧠 Đang gọi Alpha Factory phân tích và Backtest...")
    try:
        factory_script = SCRIPTS_DIR / "auto_alpha_factory.py"
        subprocess.run([sys.executable, str(factory_script)], cwd=str(BASE_DIR), timeout=600)
    except Exception as e:
        print(f"[SMART-RUNNER] ⚠ Lỗi Alpha Factory: {e}")

    # 3. Ghi nhớ đã chạy thành công hôm nay
    today = datetime.now().strftime("%Y-%m-%d")
    cur_time = datetime.now().strftime("%H:%M:%S")
    save_state(today, cur_time)
    print(f"\n[SMART-RUNNER] ✅ Đã hoàn tất và lưu trạng thái ngày {today} lúc {cur_time}!\n")


def main():
    print("[SMART-RUNNER] Khởi động trình theo dõi lịch trình thông minh...")
    while True:
        try:
            settings = load_settings()
            state = load_state()

            schedule_time = settings.get("schedule_time", "02:00")  # Ví dụ "10:00"
            last_run_date = state.get("last_run_date", "")

            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            current_hm = now.strftime("%H:%M")

            # KIỂM TRA ĐIỀU KIỆN CHẠY:
            # 1. Hôm nay CHƯA chạy lần nào (last_run_date != today)
            # 2. VÀ giờ hiện tại ĐÃ ĐẾN HOẶC ĐÃ QUA giờ hẹn (current_hm >= schedule_time)
            if last_run_date != today:
                if current_hm >= schedule_time:
                    print(f"[SMART-RUNNER] 🔔 Kích hoạt chạy! (Giờ hẹn: {schedule_time} | Hiện tại: {current_hm})")
                    execute_pipeline()
                else:
                    # Chưa đến giờ hẹn (ví dụ hẹn 10:00 mà hiện tại mới 08:00) -> Chờ tiếp
                    pass
            
            time.sleep(30)  # Quét kiểm tra mỗi 30 giây

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[SMART-RUNNER] Lỗi: {e}")
            time.sleep(30)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run-now":
        execute_pipeline()
    else:
        main()
