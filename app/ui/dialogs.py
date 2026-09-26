"""对话框：清理确认 / 清理进度 / 清理完成。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QVBoxLayout,
)

from app.core.clean_service import CleanResult, CleanStatus
from app.core.fsutils import fmt_size

_STATUS_ICON = {
    CleanStatus.SUCCESS: "✓",
    CleanStatus.SKIP: "⚠",
    CleanStatus.FAILED: "✗",
}
_STATUS_COLOR = {
    CleanStatus.SUCCESS: "#2E9E5B",
    CleanStatus.SKIP: "#E6A23C",
    CleanStatus.FAILED: "#D64545",
}


class CleanConfirmDialog(QDialog):
    """清理前确认：列出选中项、总量与风险提示。"""

    def __init__(self, categories: list, mode: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("确认清理")
        self.setMinimumWidth(520)
        self._mode = mode

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(QLabel("将清理以下项目："))

        selected = [c for c in categories if c.is_selected]
        lst = QListWidget()
        lst.setObjectName("catlist")
        for cat in selected:
            lst.addItem(f"{cat.icon} {cat.name}          {fmt_size(cat.total_size)}")
        layout.addWidget(lst)

        total_items = sum(len(c.items) for c in selected)
        total = sum(c.total_size for c in selected)
        self.lbl_total = QLabel(f"共 {total_items} 项 · 预计释放 {fmt_size(total)}")
        self.lbl_total.setObjectName("h2")
        layout.addWidget(self.lbl_total)

        self.lbl_mode = QLabel()
        if mode == "permanent":
            self.lbl_mode.setText("⚠ 当前为「永久删除」模式，删除后无法恢复！")
            self.lbl_mode.setObjectName("warn")
        else:
            self.lbl_mode.setText("删除方式：回收站（可恢复）")
            self.lbl_mode.setObjectName("muted")
        layout.addWidget(self.lbl_mode)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("确认清理")
        ok.setObjectName("danger" if mode == "permanent" else "primary")
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class CleanProgressDialog(QDialog):
    """清理进行中：进度条 + 逐项状态列表。完成后自动关闭并发送结果。"""

    finished_clean = Signal(object)

    def __init__(self, categories: list, mode: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在清理…")
        self.setMinimumSize(560, 420)
        self.setModal(True)
        self._categories = categories
        self._mode = mode
        self._total = sum(len(c.items) for c in categories if c.is_selected)
        self._done = 0
        self._freed = 0
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        self.bar = QProgressBar()
        self.bar.setRange(0, max(1, self._total))
        self.bar.setValue(0)
        self.lbl_info = QLabel("准备中…")
        self.lbl_freed = QLabel("已释放 0 B")
        self.lbl_freed.setObjectName("h2")
        self.list_status = QListWidget()
        self.list_status.setObjectName("catlist")
        layout.addWidget(self.bar)
        layout.addWidget(self.lbl_info)
        layout.addWidget(self.lbl_freed)
        layout.addWidget(self.list_status, 1)

    def start(self) -> None:
        from app.ui.workers import CleanWorker

        self._worker = CleanWorker(self._categories, self._mode, self)
        self._worker.item_done.connect(self._on_item)
        self._worker.finished_clean.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_item(self, result: CleanResult) -> None:
        self._done += 1
        self._freed += result.freed
        self.bar.setValue(self._done)
        self.lbl_info.setText(f"正在清理：{result.category_name}（{self._done}/{self._total}）")
        self.lbl_freed.setText(f"已释放 {fmt_size(self._freed)}")
        item = QListWidgetItem(
            f"{_STATUS_ICON[result.status]} {result.category_name}  {result.item.path}"
        )
        item.setForeground(QColor(_STATUS_COLOR[result.status]))
        if result.detail:
            item.setToolTip(result.detail)
        self.list_status.addItem(item)
        self.list_status.scrollToBottom()

    def _on_finished(self, results: list) -> None:
        self._worker = None
        self.accept()
        self.finished_clean.emit(results)

    def _on_failed(self, msg: str) -> None:
        self._worker = None
        self.list_status.addItem(f"✗ 清理异常：{msg}")
        self.accept()
        self.finished_clean.emit([])


class CleanCompleteDialog(QDialog):
    """清理完成：释放空间汇总 + 失败/跳过明细。"""

    rescan_requested = Signal()

    def __init__(self, results: list[CleanResult], parent=None):
        super().__init__(parent)
        self.setWindowTitle("清理完成")
        self.setMinimumWidth(480)

        success = [r for r in results if r.status == CleanStatus.SUCCESS]
        skip = [r for r in results if r.status == CleanStatus.SKIP]
        failed = [r for r in results if r.status == CleanStatus.FAILED]
        freed = sum(r.freed for r in success)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        title = QLabel("🎉 清理完成！")
        title.setObjectName("h1")
        layout.addWidget(title)
        freed_lbl = QLabel(f"释放空间：{fmt_size(freed)}")
        freed_lbl.setObjectName("h2")
        layout.addWidget(freed_lbl)
        stats = QLabel(
            f"✓ 成功 {len(success)} 项 · ⚠ 跳过 {len(skip)} 项 · ✗ 失败 {len(failed)} 项"
        )
        stats.setObjectName("muted")
        layout.addWidget(stats)

        detail = [r for r in (failed + skip) if r.detail]
        if detail:
            lst = QListWidget()
            lst.setObjectName("catlist")
            for r in detail:
                it = QListWidgetItem(
                    f"{'✗' if r.status == CleanStatus.FAILED else '⚠'} {r.item.path} — {r.detail}"
                )
                it.setForeground(QColor(_STATUS_COLOR[r.status]))
                lst.addItem(it)
            layout.addWidget(lst, 1)

        buttons = QDialogButtonBox()
        b_done = buttons.addButton("完成", QDialogButtonBox.ButtonRole.AcceptRole)
        b_rescan = buttons.addButton("重新扫描", QDialogButtonBox.ButtonRole.ActionRole)
        b_done.clicked.connect(self.accept)
        b_rescan.clicked.connect(self._rescan)
        layout.addWidget(buttons)

    def _rescan(self) -> None:
        self.accept()
        self.rescan_requested.emit()
