"""后台工作线程：扫描与清理。通过 Qt Signal 与 UI 通信。"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.core.clean_service import CleanService
from app.core.models import CleanCategory
from app.core.scan_service import ProgressSink, ScanService


class ScanWorker(QThread):
    """执行一次扫描。category_done 随每个分类完成实时发出。"""

    category_done = Signal(object)      # CleanCategory
    finished_report = Signal(object)    # ScanReport
    failed = Signal(str)

    def __init__(
        self,
        category_ids: list[str] | None = None,
        threads: int = 8,
        drives: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.category_ids = category_ids
        self.threads = threads
        self.drives = drives
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        class _Sink(ProgressSink):
            def __init__(self, worker):
                self._w = worker

            def on_category_done(self, cat: CleanCategory) -> None:
                self._w.category_done.emit(cat)

        try:
            service = ScanService(max_workers=self.threads, progress=_Sink(self))
            report = service.scan(category_ids=self.category_ids, drives=self.drives)
            if self._cancel:
                return
            self.finished_report.emit(report)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))


class CleanWorker(QThread):
    """执行一次清理。item_done 每完成一项发出一次。"""

    item_done = Signal(object)       # CleanResult
    finished_clean = Signal(object)  # list[CleanResult]
    failed = Signal(str)

    def __init__(self, categories: list, mode: str = "recycle", parent=None):
        super().__init__(parent)
        self.categories = categories
        self.mode = mode

    def run(self) -> None:
        try:
            service = CleanService(mode=self.mode)
            results = service.clean(self.categories, on_item=lambda r: self.item_done.emit(r))
            self.finished_clean.emit(results)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
