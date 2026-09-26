"""软件安装缓存残留。"""
from __future__ import annotations

from pathlib import Path

from app.categories.base import CategoryScanner
from app.core.fsutils import dir_size
from app.core.models import CleanItem

INSTALLER_ROOTS = [
    r"C:\ProgramData\Package Cache",
    r"C:\ProgramData\Microsoft\VisualStudio\Packages",
]


class InstallerCacheScanner(CategoryScanner):
    id = "installer_cache"
    name = "软件安装缓存"
    description = "安装器下载缓存（如 Package Cache），删除后需重新下载对应安装包"
    icon = "📦"
    risk = "medium"

    def scan(self):
        items: list[CleanItem] = []
        for r in INSTALLER_ROOTS:
            p = Path(r)
            if p.is_dir():
                items.append(CleanItem(path=str(p), size=dir_size(p), is_dir=True))
        return items
