"""磁盘清理大师 — 桌面程序入口（PyInstaller 打包目标）。"""
from __future__ import annotations

import sys


def main() -> int:
    from app.ui.main_window import run_gui

    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
