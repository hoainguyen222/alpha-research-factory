#!/usr/bin/env python3
"""
Quét thư mục inbox/ và xử lý toàn bộ file bằng ResearchCoordinator.
Sau khi xử lý xong, file gốc sẽ được chuyển vào storage/raw_sources/ 
hoặc bị xóa (vì nội dung đã được lưu vào SQLite và JSONL).
"""

import os
import sys
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import INBOX_DIR
from research_coordinator import ResearchCoordinator

def process_all():
    coordinator = ResearchCoordinator()
    
    inbox = Path(INBOX_DIR)
    if not inbox.exists():
        print(f"Không tìm thấy thư mục {inbox}")
        return

    files = [f for f in inbox.iterdir() if f.is_file() and not f.name.startswith('.')]
    
    if not files:
        print("Inbox trống. Không có gì để xử lý.")
        return

    print(f"Đang xử lý {len(files)} file từ Inbox...")
    
    for f in files:
        print(f"\n[{f.name}] Đang phân tích...")
        try:
            with open(f, "rb") as file_obj:
                file_bytes = file_obj.read()
            result = coordinator.process_file_upload(file_bytes, f.name)
            if result.get("status") == "success":
                print(f"✅ Đã lưu vào Vault với ID: {result.get('id')}")
                # Xóa file inbox sau khi xử lý thành công
                f.unlink()
            else:
                err_msg = result.get('error', 'Unknown Error')
                print(f"❌ Lỗi: {err_msg}")
                if "Bị từ chối" in err_msg:
                    print(f"🗑️ Đã xóa file rác khỏi inbox.")
                    f.unlink()
        except Exception as e:
            print(f"❌ Exception: {e}")
            if "Bị từ chối" in str(e):
                print(f"🗑️ Đã xóa file rác khỏi inbox.")
                f.unlink()

if __name__ == "__main__":
    process_all()
