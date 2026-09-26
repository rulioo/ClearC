"""主窗口的页面：概览 / 扫描 / 结果 / 设置 / 关于。"""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt, Signal
import os
import subprocess

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import APP_NAME, COPYRIGHT, __version__
from app.core.fsutils import drive_label, fmt_size, resource_path
from app.core.models import CleanCategory, DiskInfo, ScanReport
from app.core.protect import is_protected, protect, unprotect
from app.core.recycle import delete_to_recycle_bin
from app.core.safety import is_blacklisted
from app.core.scan_service import ScanService
from app.ui.widgets import DonutChart


class OverviewPage(QWidget):
    """概览页：磁盘环形图 + 盘符选择 + 立即扫描。"""

    scan_requested = Signal()
    drives_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._elevate_cb = None
        self._drives = ["C"]
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)

        title = QLabel(APP_NAME)
        title.setObjectName("h1")
        subtitle = QLabel("扫描并清理系统与各盘垃圾数据，回收磁盘空间")
        subtitle.setObjectName("muted")
        outer.addWidget(title)
        outer.addWidget(subtitle)

        drive_row = QHBoxLayout()
        lbl_drive = QLabel("扫描范围")
        lbl_drive.setObjectName("muted")
        self.cmb_drives = QComboBox()
        self.cmb_drives.setObjectName("drivesel")
        self.cmb_drives.currentIndexChanged.connect(self._on_drive_changed)
        drive_row.addWidget(lbl_drive)
        drive_row.addWidget(self.cmb_drives, 1)
        outer.addLayout(drive_row)

        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        row.setContentsMargins(24, 20, 24, 20)
        self.chart = DonutChart()
        stats = QVBoxLayout()
        stats.setSpacing(10)
        self.lbl_total = QLabel("总容量：--")
        self.lbl_total.setObjectName("stat")
        self.lbl_used = QLabel("已用：--")
        self.lbl_used.setObjectName("stat")
        self.lbl_free = QLabel("可用：--")
        self.lbl_free.setObjectName("stat")
        for lbl in (self.lbl_total, self.lbl_used, self.lbl_free):
            stats.addWidget(lbl)
        stats.addStretch(1)
        row.addWidget(self.chart)
        row.addLayout(stats)
        outer.addWidget(card)

        self.btn_scan = QPushButton("🚀 立即扫描")
        self.btn_scan.setObjectName("primary")
        self.btn_scan.setMinimumHeight(46)
        self.btn_scan.clicked.connect(self.scan_requested)
        outer.addWidget(self.btn_scan)

        self.lbl_last = QLabel("上次扫描：从未")
        self.lbl_last.setObjectName("muted")
        outer.addWidget(self.lbl_last)

        self.lbl_admin = QLabel("当前未以管理员身份运行，回收站等系统目录无法完整扫描。")
        self.lbl_admin.setObjectName("warn")
        self.lbl_admin.setWordWrap(True)
        self.btn_admin = QPushButton("以管理员身份重启")
        self.btn_admin.setObjectName("secondary")
        self.btn_admin.clicked.connect(self._elevate)
        outer.addWidget(self.lbl_admin)
        outer.addWidget(self.btn_admin)
        outer.addStretch(1)

    def set_disk(self, disk: DiskInfo | None):
        if disk:
            self.lbl_total.setText(f"总容量：{fmt_size(disk.total)}")
            self.lbl_used.setText(f"已用：{fmt_size(disk.used)}")
            self.lbl_free.setText(f"可用：{fmt_size(disk.free)}")
            ratio = disk.used / disk.total if disk.total else 0
            self.chart.set_data(ratio, f"{ratio * 100:.0f}%", "已使用", "#2F6FED")
        else:
            self.chart.set_data(0, "--", "无法读取磁盘信息")

    def set_drives(self, drives: list[str]):
        """填充盘符下拉框。首项为「全部磁盘」，随后每项一个盘符。"""
        self._drives = [d.upper() for d in (drives or ["C"])]
        self.cmb_drives.blockSignals(True)
        self.cmb_drives.clear()
        self.cmb_drives.addItem("全部磁盘", None)
        for d in self._drives:
            self.cmb_drives.addItem(f"{d} 盘", d)
        # 默认 C 盘，保持与以往行为一致
        idx = self.cmb_drives.findData("C")
        self.cmb_drives.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_drives.blockSignals(False)

    def selected_drives(self) -> list[str]:
        """返回当前选中的盘符；选「全部磁盘」时返回所有盘符。"""
        data = self.cmb_drives.currentData()
        return self._drives if data is None else [data]

    def _on_drive_changed(self):
        self.drives_changed.emit()

    def set_admin_state(self, is_admin: bool, elevate_cb=None):
        self._elevate_cb = elevate_cb
        self.lbl_admin.setVisible(not is_admin)
        self.btn_admin.setVisible(not is_admin)

    def set_last_scan(self, text: str):
        self.lbl_last.setText(f"上次扫描：{text}")

    def _elevate(self):
        if self._elevate_cb:
            self._elevate_cb()


class ScanPage(QWidget):
    """扫描中：环形进度 + 分类实时列表 + 取消/开始。"""

    cancel_requested = Signal()
    scan_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._total = 1
        self._done = 0
        self._cat_rows: dict[str, int] = {}
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        self.lbl_title = QLabel("扫描垃圾数据")
        self.lbl_title.setObjectName("h1")
        outer.addWidget(self.lbl_title)
        self.lbl_drive_info = QLabel("")
        self.lbl_drive_info.setObjectName("muted")
        self.lbl_drive_info.setWordWrap(True)
        outer.addWidget(self.lbl_drive_info)
        self.lbl_state = QLabel("点击「开始扫描」开始")
        self.lbl_state.setObjectName("muted")
        outer.addWidget(self.lbl_state)

        self.ring = DonutChart()
        outer.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignCenter)

        self.lbl_counts = QLabel("已扫描文件：0 · 已发现垃圾：0 B")
        self.lbl_counts.setObjectName("h2")
        outer.addWidget(self.lbl_counts)

        self.list_cats = QListWidget()
        self.list_cats.setObjectName("catlist")
        outer.addWidget(self.list_cats, 1)

        self.btn_start = QPushButton("开始扫描")
        self.btn_start.setObjectName("primary")
        self.btn_cancel = QPushButton("取消扫描")
        self.btn_cancel.setObjectName("secondary")
        self.btn_start.clicked.connect(self.scan_requested)
        self.btn_cancel.clicked.connect(self.cancel_requested)
        outer.addWidget(self.btn_start)
        outer.addWidget(self.btn_cancel)

    def reset(self, total_cats: int = 0, drives: list[str] | None = None):
        self._drives = list(drives or [])
        if drives:
            label = "、".join(f"{d} 盘" for d in drives)
            self.lbl_title.setText(f"扫描 {label} 垃圾")
        else:
            self.lbl_title.setText("扫描垃圾数据")
        self._set_drive_info(drives)
        self._set_capacity_ring()
        self._total = max(1, total_cats)
        self._done = 0
        self._cat_rows.clear()
        self.list_cats.clear()
        self.lbl_state.setText("正在扫描…")
        self.lbl_counts.setText("已扫描文件：0 · 已发现垃圾：0 B")
        self.ring.set_data(0, "0%", "扫描中")
        self.btn_start.setVisible(False)
        self.btn_cancel.setVisible(True)

    def _set_drive_info(self, drives: list[str] | None):
        """显示当前扫描盘的基本信息：盘符、卷标、容量。"""
        lines = []
        for d in (drives or []):
            label = drive_label(d)
            u = ScanService.disk_for(d)
            head = f"{d}: {label}" if label else f"{d} 盘"
            if u:
                lines.append(
                    f"{head} · 总 {fmt_size(u.total)} · 可用 {fmt_size(u.free)}"
                )
            else:
                lines.append(f"{head} · 无法读取容量")
        self.lbl_drive_info.setText("\n".join(lines))

    def _set_capacity_ring(self):
        """外环显示扫描盘容量使用率（多盘累加）。"""
        total = used = 0
        for d in self._drives:
            u = ScanService.disk_for(d)
            if u:
                total += u.total
                used += u.used
        ratio = used / total if total else 0
        self.ring.set_capacity(ratio, f"容量 {ratio * 100:.0f}%")

    def _drive_summary(self) -> str:
        """简短盘信息用于完成提示：如 'C: 1系统'；多盘用、连接。"""
        parts = []
        for d in self._drives:
            label = drive_label(d)
            parts.append(f"{d}: {label}" if label else f"{d} 盘")
        return "、".join(parts)

    def on_category_done(self, cat):
        text = (
            f"{'✓' if not cat.warning else '⚠'} {cat.name}  "
            f"{len(cat.items):,} 项  {fmt_size(cat.total_size)}"
            + (f"  （{cat.warning}）" if cat.warning else "")
        )
        row = self._cat_rows.get(cat.id)
        if row is None:
            self.list_cats.addItem(text)
            self._cat_rows[cat.id] = self.list_cats.count() - 1
        else:
            self.list_cats.item(row).setText(text)
        self._done += 1
        ratio = self._done / self._total
        self.ring.set_data(ratio, f"{int(ratio * 100)}%", "扫描中")
        self.list_cats.scrollToBottom()

    def on_finished(self, report: ScanReport):
        drive_txt = self._drive_summary()
        self.lbl_state.setText("✅ 扫描完成")
        self.lbl_counts.setText(
            (f"{drive_txt} · " if drive_txt else "")
            + f"发现 {len(report.categories)} 个分类 · 共 {fmt_size(report.total_size)} 垃圾"
        )
        self.ring.set_data(1.0, "100%", "完成")
        self.btn_start.setVisible(True)
        self.btn_cancel.setVisible(False)

    def to_idle(self, error: str = ""):
        self.lbl_state.setText(error or "点击「开始扫描」开始")
        self.lbl_counts.setText("")
        self.ring.set_data(0, "--", "未扫描")
        self.btn_start.setVisible(True)
        self.btn_cancel.setVisible(False)


class ResultPage(QWidget):
    """结果页：分类列表（可勾选、可展开）+ 底部操作栏。"""

    clean_requested = Signal()
    export_requested = Signal()
    rescan_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._report: ScanReport | None = None
        self._applying = False  # 程序化改勾选状态时的防重入开关
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        self.lbl_header = QLabel("✅ 扫描完成")
        self.lbl_header.setObjectName("h1")
        outer.addWidget(self.lbl_header)

        cards = QHBoxLayout()
        self.card_total, self.lbl_total_v = self._make_card("总容量")
        self.card_used, self.lbl_used_v = self._make_card("已用")
        self.card_free, self.lbl_free_v = self._make_card("可用")
        self.card_clean, self.lbl_clean_v = self._make_card("可清理", accent=True)
        for frame in (self.card_total, self.card_used, self.card_free, self.card_clean):
            cards.addWidget(frame)
        outer.addLayout(cards)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["项目", "大小", "说明"])
        self.tree.setColumnWidth(0, 480)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemChanged.connect(self._on_item_changed)
        outer.addWidget(self.tree, 1)

        bar = QFrame()
        bar.setObjectName("card")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 10, 12, 10)
        self.lbl_selected = QLabel("已选 0 项 · 预计释放 0 B")
        self.lbl_selected.setObjectName("h2")
        self.btn_export = QPushButton("导出报告")
        self.btn_export.setObjectName("secondary")
        self.btn_rescan = QPushButton("重新扫描")
        self.btn_rescan.setObjectName("secondary")
        self.btn_clean = QPushButton("✓ 清理选中项")
        self.btn_clean.setObjectName("primary")
        self.btn_clean.setMinimumWidth(140)
        bar_layout.addWidget(self.lbl_selected)
        bar_layout.addStretch(1)
        bar_layout.addWidget(self.btn_export)
        bar_layout.addWidget(self.btn_rescan)
        bar_layout.addWidget(self.btn_clean)
        outer.addWidget(bar)

        self.btn_clean.clicked.connect(self.clean_requested)
        self.btn_export.clicked.connect(self.export_requested)
        self.btn_rescan.clicked.connect(self.rescan_requested)

    def _make_card(self, title: str, accent: bool = False):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        t = QLabel(title)
        t.setObjectName("muted")
        v = QLabel("--")
        v.setObjectName("h2")
        if accent:
            v.setStyleSheet("color:#2F6FED;")
        lay.addWidget(t)
        lay.addWidget(v)
        return card, v

    def populate(self, report: ScanReport):
        self._report = report
        self.lbl_header.setText(
            f"✅ 扫描完成 · {len(report.categories)} 类垃圾 · 共 {fmt_size(report.total_size)}"
        )
        if report.disk:
            self.lbl_total_v.setText(fmt_size(report.disk.total))
            self.lbl_used_v.setText(fmt_size(report.disk.used))
            self.lbl_free_v.setText(fmt_size(report.disk.free))
        self.lbl_clean_v.setText(fmt_size(report.total_size))

        self.tree.clear()
        for cat in report.categories:
            note = cat.warning or cat.description
            top = QTreeWidgetItem(
                [f"{cat.icon} {cat.name}", fmt_size(cat.total_size), note]
            )
            # 父节点：可勾选 + 支持三态（全选/部分/全不选），由代码控制状态
            top.setFlags(
                top.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsUserTristate
            )
            top.setData(0, Qt.ItemDataRole.UserRole, cat.id)
            top.setData(0, Qt.ItemDataRole.UserRole + 1, cat.risk)
            default = cat.default_checked and bool(cat.items)
            for i, it in enumerate(cat.items):
                locked = is_protected(it.path)
                child = QTreeWidgetItem(
                    [
                        ("🔒 " if locked else "") + it.path,
                        fmt_size(it.size),
                        "目录" if it.is_dir else "文件",
                    ]
                )
                flags = child.flags()
                if locked:
                    flags = flags & ~Qt.ItemFlag.ItemIsUserCheckable  # 加锁项不可勾选
                child.setFlags(flags)
                child.setData(0, Qt.ItemDataRole.UserRole + 2, i)  # 明细下标
                child.setData(0, Qt.ItemDataRole.UserRole + 3, 1 if locked else 0)  # 加锁标记
                child.setCheckState(
                    0,
                    Qt.CheckState.Checked if (default and not locked) else Qt.CheckState.Unchecked,
                )
                top.addChild(child)
            self.tree.addTopLevelItem(top)
        self._sync_from_tree()

    def _confirm_high_risk(self, cat) -> bool:
        """高风险分类被勾选时要求二次确认；低风险直接放行。"""
        if cat.risk != "high":
            return True
        ret = QMessageBox.warning(
            self,
            "高风险项",
            f"「{cat.name}」涉及系统数据，删除后可能无法恢复。确认勾选？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return ret == QMessageBox.StandardButton.Yes

    def _on_context_menu(self, pos):
        """明细记录右键菜单：打开所在文件夹 / 保护(加锁) / 直接删除。"""
        item = self.tree.itemAt(pos)
        if item is None or item.parent() is None or self._report is None:
            return  # 仅对展开的明细记录提供菜单
        cat_id = item.parent().data(0, Qt.ItemDataRole.UserRole)
        cat = self._report.category_map().get(cat_id) if cat_id else None
        idx = item.data(0, Qt.ItemDataRole.UserRole + 2)
        if cat is None or not (0 <= idx < len(cat.items)):
            return
        path = cat.items[idx].path

        menu = QMenu(self)
        act_open = menu.addAction("📂 打开文件所在文件夹")
        if is_protected(path):
            act_lock = menu.addAction("🔓 取消保护")
        else:
            act_lock = menu.addAction("🔒 保护文件（避免被误清理）")
        act_del = menu.addAction("🗑 直接删除")
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_open:
            self._open_containing_folder(path)
        elif chosen is act_lock:
            self._toggle_protect(item, cat, idx)
        elif chosen is act_del:
            self._delete_direct(item, cat, idx)

    def _open_containing_folder(self, path: str):
        folder = os.path.dirname(path)
        try:
            # explorer /select 打开文件夹并选中该文件
            subprocess.Popen(["explorer", "/select," + os.path.normpath(path)])
        except Exception:
            try:
                os.startfile(folder)
            except Exception as e:  # noqa: BLE001
                QMessageBox.warning(self, "无法打开", f"无法打开所在文件夹：{e}")

    def _toggle_protect(self, item, cat, idx):
        """保护 / 取消保护：加锁项不可被勾选，清理时也会被拒绝。"""
        it = cat.items[idx]
        locked = not is_protected(it.path)
        if locked:
            protect(it.path)
        else:
            unprotect(it.path)
        it.selected = not locked

        text = ("🔒 " if locked else "") + it.path
        item.setText(0, text)
        item.setData(0, Qt.ItemDataRole.UserRole + 3, 1 if locked else 0)
        flags = item.flags()
        if locked:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsUserCheckable)
            self._applying = True
            try:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            finally:
                self._applying = False
        else:
            item.setFlags(flags | Qt.ItemFlag.ItemIsUserCheckable)
            parent = item.parent()
            # 解锁后若父节点为全选状态，则恢复勾选
            if parent is not None and parent.checkState(0) == Qt.CheckState.Checked:
                self._applying = True
                try:
                    item.setCheckState(0, Qt.CheckState.Checked)
                    it.selected = True
                finally:
                    self._applying = False
        self._refresh_parent_state(item.parent())
        self._update_selected_summary()

    def _delete_direct(self, item, cat, idx):
        """直接删除所选明细：先做安全校验，移入回收站，并从树中移除。"""
        it = cat.items[idx]
        if is_blacklisted(it.path):
            QMessageBox.warning(self, "无法删除", "该路径命中系统黑名单，不允许删除")
            return
        if is_protected(it.path):
            QMessageBox.warning(self, "无法删除", "该文件已加锁保护，请先取消保护再删除")
            return
        ret = QMessageBox.question(
            self,
            "直接删除",
            f"确定要删除以下项目吗？\n{it.path}\n（将移入回收站，可恢复）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if ret != QMessageBox.StandardButton.Yes:
            return
        try:
            code = delete_to_recycle_bin([it.path])
            if code != 0:
                raise RuntimeError(f"删除失败（错误码 {code}）")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "删除失败", str(e))
            return
        parent = item.parent()
        cat.total_size -= it.size
        cat.items.remove(it)
        parent.removeChild(item)
        parent.setText(1, fmt_size(cat.total_size))
        self._refresh_parent_state(parent)
        self._update_selected_summary()

    def _on_item_changed(self, item, col: int):
        if col != 0 or self._report is None or self._applying:
            return
        self._applying = True
        try:
            state = item.checkState(0)
            is_top = item.parent() is None
            # 分类 id 只存在父节点上，子节点从父节点取
            ref = item if is_top else item.parent()
            cat_id = ref.data(0, Qt.ItemDataRole.UserRole) if ref else None
            cat = self._report.category_map().get(cat_id) if cat_id else None
            if cat is None:
                return
            if is_top:
                # 父节点勾选：三态用户操作可能落到 PartiallyChecked，统一归一为“全选”
                if state != Qt.CheckState.Unchecked:
                    if not self._confirm_high_risk(cat):
                        item.setCheckState(0, Qt.CheckState.Unchecked)
                        return
                    state = Qt.CheckState.Checked
                self._apply_top_state(cat, item, state)
            else:
                # 子节点勾选：只影响该明细，并联动父节点三态
                if state == Qt.CheckState.Checked and not self._confirm_high_risk(cat):
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    return
                idx = item.data(0, Qt.ItemDataRole.UserRole + 2)
                if 0 <= idx < len(cat.items):
                    cat.items[idx].selected = state == Qt.CheckState.Checked
                self._refresh_parent_state(item.parent())
            self._update_selected_summary()
        finally:
            self._applying = False

    def _apply_top_state(self, cat, top, state: Qt.CheckState):
        """父节点状态变化：让全部子节点跟随，并同步数据模型（加锁项除外）。"""
        checked = state == Qt.CheckState.Checked
        for i in range(top.childCount()):
            child = top.child(i)
            if child.data(0, Qt.ItemDataRole.UserRole + 3):
                continue  # 加锁项不参与全选
            child.setCheckState(0, state)
            if i < len(cat.items):
                cat.items[i].selected = checked
        top.setCheckState(0, state)
        cat.is_selected = checked

    def _refresh_parent_state(self, parent):
        """按子节点勾选情况刷新父节点三态：全选/全不选/部分。"""
        if parent is None:
            return
        n = parent.childCount()
        checked = sum(
            1 for i in range(n) if parent.child(i).checkState(0) == Qt.CheckState.Checked
        )
        if checked == n:
            parent.setCheckState(0, Qt.CheckState.Checked)
        elif checked == 0:
            parent.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
        cat_id = parent.data(0, Qt.ItemDataRole.UserRole)
        cat = self._report.category_map().get(cat_id) if cat_id else None
        if cat is not None:
            cat.is_selected = checked > 0

    def _sync_from_tree(self):
        if self._report is None:
            return
        self._applying = True
        try:
            for i in range(self.tree.topLevelItemCount()):
                top = self.tree.topLevelItem(i)
                cat = self._report.category_map().get(top.data(0, Qt.ItemDataRole.UserRole))
                if cat is None:
                    continue
                n_checked = 0
                for j in range(top.childCount()):
                    child = top.child(j)
                    idx = child.data(0, Qt.ItemDataRole.UserRole + 2)
                    checked = child.checkState(0) == Qt.CheckState.Checked
                    if 0 <= idx < len(cat.items):
                        cat.items[idx].selected = checked
                        if checked:
                            n_checked += 1
                # 父节点三态由子节点推导
                if n_checked == top.childCount():
                    top.setCheckState(0, Qt.CheckState.Checked)
                elif n_checked == 0:
                    top.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    top.setCheckState(0, Qt.CheckState.PartiallyChecked)
                cat.is_selected = n_checked > 0
        finally:
            self._applying = False
        self._update_selected_summary()

    def _update_selected_summary(self):
        cats = self.selected_categories()
        n = sum(len(c.items) for c in cats)
        total = sum(c.total_size for c in cats)
        self.lbl_selected.setText(f"已选 {n} 项 · 预计释放 {fmt_size(total)}")

    def selected_categories(self) -> list:
        """返回只包含已勾选明细的分类副本——清理时以明细选择为准。"""
        if self._report is None:
            return []
        out = []
        for cat in self._report.categories:
            items = [it for it in cat.items if it.selected]
            if not items:
                continue
            out.append(
                CleanCategory(
                    id=cat.id,
                    name=cat.name,
                    description=cat.description,
                    icon=cat.icon,
                    risk=cat.risk,
                    items=items,
                    total_size=sum(i.size for i in items),
                    is_selected=True,
                    warning=cat.warning,
                    drive=cat.drive,
                )
            )
        return out


class SettingsPage(QWidget):
    """设置页：清理方式 / 确认弹窗 / 线程数 / 报告备份。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._settings = QSettings("ClearC", "ClearC")
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)
        title = QLabel("设置")
        title.setObjectName("h1")
        outer.addWidget(title)

        form = QFrame()
        form.setObjectName("card")
        lay = QVBoxLayout(form)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("删除方式"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItem("回收站（可恢复，推荐）", "recycle")
        self.cmb_mode.addItem("永久删除（不可恢复）", "permanent")
        row1.addWidget(self.cmb_mode, 1)
        lay.addLayout(row1)

        self.chk_confirm = QCheckBox("清理前显示确认对话框")
        lay.addWidget(self.chk_confirm)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("扫描线程数"))
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 16)
        row2.addWidget(self.spin_threads, 1)
        lay.addLayout(row2)

        self.chk_export = QCheckBox("清理前自动导出报告备份")
        lay.addWidget(self.chk_export)

        self.btn_save = QPushButton("保存设置")
        self.btn_save.setObjectName("primary")
        self.btn_save.clicked.connect(self.save)
        lay.addWidget(self.btn_save)
        outer.addWidget(form)
        outer.addStretch(1)
        copyright_lbl = QLabel(COPYRIGHT)
        copyright_lbl.setObjectName("muted")
        copyright_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(copyright_lbl)
        self.load()

    def load(self):
        idx = self.cmb_mode.findData(self._settings.value("clean/mode", "recycle"))
        if idx >= 0:
            self.cmb_mode.setCurrentIndex(idx)
        self.chk_confirm.setChecked(self._settings.value("clean/confirm", True, type=bool))
        self.spin_threads.setValue(int(self._settings.value("scan/threads", 8)))
        self.chk_export.setChecked(self._settings.value("clean/export_backup", True, type=bool))

    def save(self):
        self._settings.setValue("clean/mode", self.cmb_mode.currentData())
        self._settings.setValue("clean/confirm", self.chk_confirm.isChecked())
        self._settings.setValue("scan/threads", self.spin_threads.value())
        self._settings.setValue("clean/export_backup", self.chk_export.isChecked())
        QMessageBox.information(self, "设置", "设置已保存")


class AboutPage(QWidget):
    """关于页：软件名称、版本、简介与版权信息。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)
        title = QLabel("关于")
        title.setObjectName("h1")
        outer.addWidget(title)

        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(10)

        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        pix = QPixmap(resource_path("app.ico"))
        if not pix.isNull():
            icon.setPixmap(
                pix.scaled(
                    72,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        lay.addWidget(icon)

        name = QLabel(APP_NAME)
        name.setObjectName("h2")
        name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(name)

        version = QLabel(f"版本 {__version__}")
        version.setObjectName("muted")
        version.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(version)

        desc = QLabel("扫描并清理系统与各磁盘垃圾数据，回收磁盘空间。")
        desc.setObjectName("muted")
        desc.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addSpacing(10)
        copyright_lbl = QLabel(COPYRIGHT)
        copyright_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(copyright_lbl)

        outer.addWidget(card)
        outer.addStretch(1)
