"""浏览器缓存：Chrome / Edge 的 Cache、Code Cache、GPUCache。"""
from __future__ import annotations

import os
from pathlib import Path

from app.categories.base import CategoryScanner
from app.core.fsutils import dir_size
from app.core.models import CleanItem

BROWSERS = [
    ("Chrome", "Google\\Chrome\\User Data"),
    ("Edge", "Microsoft\\Edge\\User Data"),
]

CACHE_SUBDIRS = ("Cache", "Code Cache", "GPUCache")


class BrowserCacheScanner(CategoryScanner):
    id = "browser_cache"
    name = "浏览器缓存"
    description = "Chrome / Edge 的缓存目录，可安全清除"
    icon = "🌐"
    risk = "low"

    def scan(self):
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        items: list[CleanItem] = []
        for _label, rel in BROWSERS:
            base = local / rel
            if not base.is_dir():
                continue
            for profile in sorted(base.iterdir()):
                if not profile.is_dir() or profile.name.startswith(".") or profile.name == "System Profile":
                    continue
                for sub in CACHE_SUBDIRS:
                    d = profile / sub
                    if d.is_dir():
                        try:
                            items.append(
                                CleanItem(path=str(d), size=dir_size(d), is_dir=True, modified=d.stat().st_mtime)
                            )
                        except OSError:
                            continue
        return items
