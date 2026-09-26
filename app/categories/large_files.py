"""大文件分析：扫描指定盘符 >500MB 的文件。

风险说明：这些文件可能包含用户数据，仅列出供查看，不自动删除
（safe=False，清理时默认拒绝）。

大磁盘文件很多，为避免整盘扫描耗时过长，设置了单盘扫描时间上限
（MAX_SCAN_SECONDS，默认 90 秒），超时后返回已发现的文件并附警告。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from app.categories.base import CategoryScanner
from app.core.fsutils import is_reparse_point
from app.core.models import CleanItem
from app.core.safety import should_skip_scan_dir

MIN_SIZE = 500 * 1024 * 1024  # 500 MB


class LargeFilesScanner(CategoryScanner):
    id = "large_files"
    name = "大文件分析 (>500MB)"
    description = "扫描大于 500MB 的文件（仅列出，不自动删除）"
    icon = "📐"
    risk = "medium"
    default_checked = False
    scope = "drive"  # 适用于任意盘符
    MAX_SCAN_SECONDS = 90.0  # 单盘扫描时间上限，避免大磁盘耗时过长

    def scan(self):
        items: list[CleanItem] = []
        self.warning = ""
        deadline = None
        if self.MAX_SCAN_SECONDS > 0:
            deadline = time.monotonic() + self.MAX_SCAN_SECONDS
        root = Path(f"{self.drive}:/")
        timed_out = False
        if root.is_dir():
            timed_out = not self._walk(root, items, deadline)
        if timed_out:
            self.warning = f"扫描超时，仅列出部分结果（限时 {int(self.MAX_SCAN_SECONDS)}s）"
        return items

    def _walk(self, root: Path, items: list[CleanItem], deadline: float | None) -> bool:
        """深度优先遍历；返回 False 表示已超时需停止。"""
        if deadline is not None and time.monotonic() > deadline:
            return False
        try:
            with os.scandir(root) as it:
                for entry in it:
                    if deadline is not None and time.monotonic() > deadline:
                        return False
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if should_skip_scan_dir(entry.path) or is_reparse_point(entry.path):
                                continue
                            if not self._walk(Path(entry.path), items, deadline):
                                return False
                        elif entry.is_file(follow_symlinks=False):
                            st = entry.stat()
                            if st.st_size >= MIN_SIZE:
                                items.append(
                                    CleanItem(
                                        path=entry.path,
                                        size=st.st_size,
                                        is_dir=False,
                                        modified=st.st_mtime,
                                        safe=False,
                                    )
                                )
                    except OSError:
                        continue
        except OSError:
            pass
        return True
