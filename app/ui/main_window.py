"""主窗口：左侧导航 + 页面堆叠 + 扫描 / 清理全流程接线。"""
from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME
from app.core.fsutils import fmt_size, is_admin_user, resource_path
from app.core.report import write_csv, write_json, write_text
from app.core.scan_service import ScanService
from app.ui.dialogs import CleanCompleteDialog, CleanConfirmDialog, CleanProgressDialog
from app.ui.pages import AboutPage, OverviewPage, ResultPage, ScanPage, SettingsPage
from app.ui.workers import ScanWorker


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(960, 640)
        self.setMinimumSize(840, 560)
        self._settings = QSettings("ClearC", "ClearC")
        self._scan_worker: ScanWorker | None = None
        self._last_report = None
        self._build()
        self._refresh_disk()

    # ---------- 界面构建 ----------
    def _build(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav = QFrame()
        nav.setObjectName("nav")
        nav.setFixedWidth(180)
        nav_lay = QVBoxLayout(nav)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(0)
        logo = QLabel(f"🗑 {APP_NAME}")
        logo.setObjectName("logo")
        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navlist")
        self.nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        for name in ("概览", "扫描", "设置", "关于"):
            self.nav_list.addItem(name)
        self.nav_list.currentRowChanged.connect(self._on_nav)
        nav_lay.addWidget(logo)
        nav_lay.addWidget(self.nav_list, 1)  # 占满侧边栏剩余高度，与窗体同高，避免滚动条

        self.pages = QStackedWidget()
        self.overview = OverviewPage()
        self.scan_page = ScanPage()
        self.result_page = ResultPage()
        self.settings_page = SettingsPage()
        self.about_page = AboutPage()
        for p in (
            self.overview,
            self.scan_page,
            self.result_page,
            self.settings_page,
            self.about_page,
        ):
            self.pages.addWidget(p)

        root.addWidget(nav)
        root.addWidget(self.pages, 1)

        # 流程接线
        self.overview.scan_requested.connect(self.start_scan)
        self.scan_page.scan_requested.connect(self.start_scan)
        self.scan_page.cancel_requested.connect(self.cancel_scan)
        self.result_page.clean_requested.connect(self.start_clean)
        self.result_page.export_requested.connect(self.export_report)
        self.result_page.rescan_requested.connect(self.start_scan)
        self.overview.drives_changed.connect(self._refresh_disk)
        self.overview.set_admin_state(is_admin_user(), self.relaunch_admin)
        self.overview.set_drives(ScanService.list_drives())

        self.nav_list.setCurrentRow(0)
        self.pages.setCurrentIndex(0)

    def _go_page(self, index: int, nav_row: int):
        self.pages.setCurrentIndex(index)
        self.nav_list.blockSignals(True)
        self.nav_list.setCurrentRow(nav_row)
        self.nav_list.blockSignals(False)

    def _on_nav(self, row: int):
        if row == 0:
            self.pages.setCurrentIndex(0)
        elif row == 1:
            self.pages.setCurrentIndex(2 if self._last_report is not None else 1)
        elif row == 2:
            self.pages.setCurrentIndex(3)
        elif row == 3:
            self.pages.setCurrentIndex(4)

    # ---------- 扫描流程 ----------
    def start_scan(self):
        if self._scan_worker and self._scan_worker.isRunning():
            return
        threads = int(self._settings.value("scan/threads", 8))
        drives = self.overview.selected_drives()
        worker = ScanWorker(threads=threads, drives=drives, parent=self)
        worker.category_done.connect(self.scan_page.on_category_done)
        worker.finished_report.connect(self._on_scan_finished)
        worker.failed.connect(self._on_scan_failed)
        self._scan_worker = worker
        total_cats = len(ScanService.build_tasks(drives))
        self.scan_page.reset(total_cats=total_cats, drives=drives)
        self._go_page(1, 1)
        worker.start()

    def cancel_scan(self):
        if self._scan_worker and self._scan_worker.isRunning():
            self._scan_worker.cancel()

    def _on_scan_finished(self, report):
        self._scan_worker = None
        self._last_report = report
        self.scan_page.on_finished(report)
        self.result_page.populate(report)
        self.overview.set_last_scan(
            f"{time.strftime('%H:%M:%S')} · 发现 {fmt_size(report.total_size)}"
        )
        self._go_page(2, 1)
        if self._settings.value("clean/export_backup", True):
            self._auto_backup(report)

    def _on_scan_failed(self, msg: str):
        self._scan_worker = None
        self.scan_page.to_idle(f"扫描失败：{msg}")
        QMessageBox.critical(self, "扫描失败", f"扫描过程中出现错误：\n{msg}")

    def _auto_backup(self, report):
        try:
            out_dir = Path("reports")
            out_dir.mkdir(exist_ok=True)
            write_json(report, out_dir / f"scan_{time.strftime('%Y%m%d_%H%M%S')}.json")
        except Exception:  # noqa: BLE001 备份失败不影响主流程
            pass

    # ---------- 清理流程 ----------
    def start_clean(self):
        if self._last_report is None:
            return
        categories = self.result_page.selected_categories()
        if not categories:
            QMessageBox.information(self, "提示", "请先勾选要清理的分类")
            return
        mode = str(self._settings.value("clean/mode", "recycle"))
        confirm = bool(self._settings.value("clean/confirm", True))
        if confirm or mode == "permanent":
            dlg = CleanConfirmDialog(categories, mode, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
        progress = CleanProgressDialog(categories, mode, self)
        progress.finished_clean.connect(self._on_clean_finished)
        progress.start()
        progress.exec()

    def _on_clean_finished(self, results):
        self._last_report = None  # 清理后结果已过期
        self._refresh_disk()
        self._go_page(0, 0)
        dlg = CleanCompleteDialog(results, self)
        dlg.rescan_requested.connect(self.start_scan)
        dlg.exec()

    # ---------- 其他 ----------
    def export_report(self):
        if self._last_report is None:
            return
        default_name = f"clearC_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出报告", default_name, "JSON 报告 (*.json);;CSV 明细 (*.csv);;文本 (*.txt)"
        )
        if not path:
            return
        suffix = path.lower().rsplit(".", 1)[-1] if "." in path else "json"
        writer = {"json": write_json, "csv": write_csv, "txt": write_text}.get(suffix, write_json)
        try:
            writer(self._last_report, path)
            QMessageBox.information(self, "导出", f"报告已导出：\n{path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "导出失败", str(e))

    def relaunch_admin(self):
        try:
            args = " ".join(f'"{a}"' for a in sys.argv) if sys.argv else f'"{sys.executable}"'
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, args, None, 1)
            QApplication.quit()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "错误", f"提升权限失败：{e}")

    def _refresh_disk(self):
        disk = ScanService.read_disk(self.overview.selected_drives())
        self.overview.set_disk(disk)


def run_gui() -> int:
    import os

    from PySide6.QtGui import QIcon

    from app.ui.theme import STYLESHEET

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("ClearC")
    app.setStyleSheet(STYLESHEET)
    # 运行时窗口图标：打包后从 _MEIPASS 读取，源码运行时从项目根目录读取
    ico = resource_path("app.ico")
    if os.path.exists(ico):
        app.setWindowIcon(QIcon(ico))
    win = MainWindow()
    win.show()
    return app.exec()
