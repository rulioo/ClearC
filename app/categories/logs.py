"""Windows 日志：仅清理 7 天以上的旧日志文件。"""
from __future__ import annotations

import os
import time
from pathlib import Path

from app.categories.base import CategoryScanner
from app.core.models import CleanItem

LOG_ROOT = r"C:\Windows\Logs"
MAX_AGE_DAYS = 7


class LogsScanner(CategoryScanner):
    id = "logs"
    name = "日志文件"
    description = "C:\\Windows\\Logs 中超过 7 天的旧日志"
    icon = "📋"
    risk = "low"

    def scan(self):
        cutoff = time.time() - MAX_AGE_DAYS * 86400
        items: list[CleanItem] = []
        root = Path(LOG_ROOT)
        if not root.is_dir():
            return items
        try:
            with os.scandir(root) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            continue  # 目录本身受保护，只清理其中的旧文件
                        st = entry.stat()
                        if st.st_mtime < cutoff:
                            items.append(
                                CleanItem(path=entry.path, size=st.st_size, is_dir=False, modified=st.st_mtime)
                            )
                    except OSError:
                        continue
        except OSError:
            return items
        return items
