"""用户 / 系统临时文件。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.categories.base import CategoryScanner
from app.core.fsutils import scan_dir_children


class TempUserScanner(CategoryScanner):
    id = "temp_user"
    name = "用户临时文件"
    description = "%TEMP% 下的临时文件，可由各软件安全重建"
    icon = "🗂"
    risk = "low"

    def scan(self):
        tmp = Path(os.environ.get("TEMP") or tempfile.gettempdir())
        return scan_dir_children(tmp)


class TempSystemScanner(CategoryScanner):
    id = "temp_sys"
    name = "系统临时文件"
    description = "C:\\Windows\\Temp，系统运行产生的临时文件"
    icon = "🖥"
    risk = "low"

    def scan(self):
        return scan_dir_children(r"C:\Windows\Temp")
