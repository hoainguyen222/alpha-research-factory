#!/usr/bin/env python3
"""
ALPHA RESEARCH FACTORY — Dashboard Launcher
Khởi động Dashboard Web trên Port 5060.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from web.app import start_server

if __name__ == "__main__":
    start_server()
