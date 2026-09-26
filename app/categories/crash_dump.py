"""崩溃转储与错误报告。"""
from __future__ import annotations

import os

from app.categories.base import CategoryScanner
from app.core.fsutils import scan_dir_children

CRASH_ROOTS = [
    r"C:\Windows\Minidump",
    r"C:\Windows\LiveKernelReports",
    r"C:\ProgramData\Microsoft\Windows\WER\ReportArchive",
    r"C:\ProgramData\Microsoft\Windows\WER\ReportQueue",
]


class CrashDumpScanner(CategoryScanner):
    id = "crash_dump"
    name = "崩溃转储与错误报告"
    description = "Windows 及应用程序崩溃产生的转储文件与错误报告"
    icon = "🧾"
    risk = "low"

    def scan(self):
        roots = list(CRASH_ROOTS)
        local = os.environ.get("LOCALAPPDATA")
        if local:
            roots.append(os.path.join(local, "CrashDumps"))
        items = []
        for r in roots:
            items.extend(scan_dir_children(r))
        return items
