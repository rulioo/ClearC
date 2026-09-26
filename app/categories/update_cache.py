"""Windows 更新缓存。"""
from __future__ import annotations

from app.categories.base import CategoryScanner
from app.core.fsutils import scan_dir_children


class UpdateCacheScanner(CategoryScanner):
    id = "update_cache"
    name = "Windows 更新缓存"
    description = "C:\\Windows\\SoftwareDistribution\\Download，已安装更新残留"
    icon = "🔄"
    risk = "low"

    def scan(self):
        return scan_dir_children(r"C:\Windows\SoftwareDistribution\Download")
