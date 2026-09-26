"""资源管理器缩略图缓存。"""
from __future__ import annotations

import os
from pathlib import Path

from app.categories.base import CategoryScanner
from app.core.models import CleanItem


class ThumbCacheScanner(CategoryScanner):
    id = "thumbcache"
    name = "缩略图缓存"
    description = "资源管理器缩略图缓存 thumbcache_*.db，删除后自动重建"
    icon = "🖼"
    risk = "low"

    def scan(self):
        explorer_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Windows" / "Explorer"
        items: list[CleanItem] = []
        if not explorer_dir.is_dir():
            return items
        for f in explorer_dir.glob("thumbcache_*.db"):
            try:
                st = f.stat()
                items.append(CleanItem(path=str(f), size=st.st_size, is_dir=False, modified=st.st_mtime))
            except OSError:
                continue
        return items
