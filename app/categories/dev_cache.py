"""开发工具缓存：pip / npm 等下载缓存。"""
from __future__ import annotations

import os
from pathlib import Path

from app.categories.base import CategoryScanner
from app.core.fsutils import dir_size
from app.core.models import CleanItem


class DevCacheScanner(CategoryScanner):
    id = "dev_cache"
    name = "开发工具缓存"
    description = "pip / npm 等开发工具下载缓存，可安全清除"
    icon = "🧰"
    risk = "low"

    def scan(self):
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        appdata = Path(os.environ.get("APPDATA", ""))
        targets = [
            local / "pip" / "cache",
            appdata / "npm-cache",
            local / "npm-cache",
        ]
        items: list[CleanItem] = []
        for t in targets:
            if t.is_dir():
                items.append(CleanItem(path=str(t), size=dir_size(t), is_dir=True))
        return items
