"""旧版 Windows（Windows.old），高风险、默认不勾选。"""
from __future__ import annotations

from pathlib import Path

from app.categories.base import CategoryScanner
from app.core.fsutils import dir_size
from app.core.models import CleanItem


class OldWindowsScanner(CategoryScanner):
    id = "old_windows"
    name = "旧版 Windows (Windows.old)"
    description = "系统升级后残留的旧系统目录，删除后不可回滚"
    icon = "📦"
    risk = "high"
    default_checked = False

    def scan(self):
        p = Path(r"C:\Windows.old")
        if p.is_dir():
            return [CleanItem(path=str(p), size=dir_size(p), is_dir=True)]
        return []
