"""回收站。每个 NTFS 盘符下都有 $Recycle.Bin，需管理员权限访问。"""
from __future__ import annotations

from app.categories.base import CategoryScanner
from app.core.fsutils import scan_dir_children


class RecycleBinScanner(CategoryScanner):
    id = "recyclebin"
    name = "回收站"
    description = "删除但尚未清空的文件（可在此彻底释放空间）"
    icon = "🗑"
    risk = "low"
    requires_admin = True
    scope = "drive"  # 适用于任意盘符

    def scan(self):
        return scan_dir_children(rf"{self.drive}:\$Recycle.Bin")
