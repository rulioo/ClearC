"""offscreen 冒烟测试：GUI 构建、扫描→结果→选择逻辑、清理核心安全校验。

不删除任何真实用户数据：
- 清理核心只针对临时测试文件 / 黑名单 / 不存在路径。
- GUI 只用同步扫描填充结果页并验证勾选逻辑。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_clean_core() -> None:
    from app.core.clean_service import CleanService, CleanStatus
    from app.core.models import CleanCategory, CleanItem

    # 1) 永久删除测试文件应成功
    tmp = tempfile.mkdtemp(prefix="clearc_test_")
    target = os.path.join(tmp, "junk.txt")
    with open(target, "w", encoding="utf-8") as f:
        f.write("x" * 100)
    item = CleanItem(path=target, size=100, is_dir=False, safe=True)
    cat = CleanCategory(id="test", name="测试", items=[item], total_size=100, is_selected=True)
    res = CleanService(mode="permanent").clean([cat])
    assert len(res) == 1 and res[0].status == CleanStatus.SUCCESS, res
    assert not os.path.exists(target), "测试文件应已被永久删除"
    shutil.rmtree(tmp, ignore_errors=True)
    print("PASS clean permanent")

    # 2) 黑名单路径应被拒绝
    bad_item = CleanItem(path=r"C:\Windows\System32\config", size=1, is_dir=True, safe=True)
    bad_cat = CleanCategory(id="bad", name="坏", items=[bad_item], total_size=1, is_selected=True)
    res = CleanService(mode="permanent").clean([bad_cat])
    assert res[0].status == CleanStatus.SKIP, res
    print("PASS blacklist reject")

    # 3) 不在扫描结果中的路径应被 validate_for_cleanup 拒绝
    from app.core.models import CleanCategory as _Cat
    from app.core.safety import validate_for_cleanup

    ghost = CleanItem(path=r"C:\nonexistent_clearc_xyz", size=1, is_dir=False, safe=True)
    ok, reason = validate_for_cleanup(ghost, [_Cat(id="empty", name="空", items=[])])
    assert ok is False and "扫描结果" in reason, (ok, reason)
    print("PASS not-in-report reject")


def test_drive_scope() -> None:
    """多盘扫描：任务构建规则 + 真实盘上跑一次回收站扫描。"""
    from app.core.models import ScanReport
    from app.core.scan_service import ScanService

    drives = ScanService.list_drives()
    assert drives and "C" in drives, f"应至少包含 C 盘：{drives}"
    print("PASS drives listed:", ",".join(drives))

    # C 盘 = 全部 13 个分类（system + drive 作用域）
    c_tasks = ScanService.build_tasks(["C"])
    assert len(c_tasks) == 13, f"C 盘应有 13 个分类，实际 {len(c_tasks)}"
    assert {t[1] for t in c_tasks} == {"C"}, "C 盘任务都应归属 C"

    # 非 C 盘 = 只跑 drive 作用域分类（回收站 + 大文件），且实例带对应盘符
    other = next((d for d in drives if d != "C"), None)
    if other:
        d_tasks = ScanService.build_tasks([other])
        ids = {sc.id for sc, _ in d_tasks}
        assert ids == {"recyclebin", "large_files"}, f"{other} 盘应只跑 drive 分类：{ids}"
        assert all(sc.drive == other for sc, _ in d_tasks), "drive 作用域实例应携带盘符"
        assert d_tasks[0][1] == other
        print(f"PASS drive-scope tasks on {other}:", ",".join(sorted(ids)))

        # 实际跑一次该盘的回收站扫描（成本低，权限不足也仅产生警告）
        report: ScanReport = ScanService(max_workers=4).scan(
            category_ids=["recyclebin"], drives=[other]
        )
        cats = report.categories
        assert len(cats) == 1, f"应只有一个回收站分类，实际 {len(cats)}"
        assert cats[0].id == f"{other}:recyclebin", cats[0].id
        assert f"{other}盘" in cats[0].name, cats[0].name
        print(f"PASS real scan on {other} ->", f"{len(cats[0].items)} 项, {cats[0].warning or '无警告'}")
    else:
        print("PASS no extra drive (skip real drive scan)")


def test_child_selection() -> None:
    """结果页明细级勾选：子项可单独勾选，父节点三态联动，清理以明细为准。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.core.models import CleanCategory, CleanItem, ScanReport
    from app.ui.pages import ResultPage

    app = QApplication.instance() or QApplication(sys.argv)
    page = ResultPage()
    cat = CleanCategory(
        id="t",
        name="测试",
        items=[
            CleanItem(path=r"C:\a\1.txt", size=100),
            CleanItem(path=r"C:\a\2.txt", size=200),
            CleanItem(path=r"C:\a\3.txt", size=300),
        ],
        total_size=600,
        default_checked=True,
    )
    page.populate(ScanReport(categories=[cat]))
    top = page.tree.topLevelItem(0)
    assert top.checkState(0) == Qt.CheckState.Checked, "默认全选"
    assert top.childCount() == 3

    # 取消一个子项 → 该明细反选，父节点变“部分选中”
    top.child(0).setCheckState(0, Qt.CheckState.Unchecked)
    assert cat.items[0].selected is False, "子项取消应同步到数据模型"
    assert cat.items[1].selected is True
    assert top.checkState(0) == Qt.CheckState.PartiallyChecked, top.checkState(0)
    sel = page.selected_categories()
    assert len(sel) == 1 and len(sel[0].items) == 2, [c.id for c in sel]
    assert sel[0].total_size == 500, sel[0].total_size
    print("PASS child uncheck -> partial parent, cleanup uses 2/3 items")

    # 全部取消 → 父节点全不选，selected_categories 为空
    for j in range(1, top.childCount()):
        top.child(j).setCheckState(0, Qt.CheckState.Unchecked)
    assert top.checkState(0) == Qt.CheckState.Unchecked, top.checkState(0)
    assert page.selected_categories() == []
    print("PASS all uncheck -> empty selection")

    # 勾选父节点 → 子节点全部跟随选中
    top.setCheckState(0, Qt.CheckState.Checked)
    assert all(it.selected for it in cat.items), "父节点勾选应全选子项"
    assert len(page.selected_categories()[0].items) == 3
    print("PASS parent check -> all children follow")
    page.close()


def test_clean_partial_selection() -> None:
    """端到端验证：清理只删除被勾选的明细，未勾选的不动。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.core.clean_service import CleanService, CleanStatus
    from app.core.models import CleanCategory, CleanItem, ScanReport
    from app.ui.pages import ResultPage

    app = QApplication.instance() or QApplication(sys.argv)
    tmp = tempfile.mkdtemp(prefix="clearc_partial_")
    paths = [os.path.join(tmp, f"f{i}.txt") for i in range(3)]
    for p in paths:
        with open(p, "w", encoding="utf-8") as f:
            f.write("x")
    cat = CleanCategory(
        id="t",
        name="测试",
        items=[CleanItem(path=p, size=1) for p in paths],
        default_checked=True,
    )
    page = ResultPage()
    page.populate(ScanReport(categories=[cat]))
    page.tree.topLevelItem(0).child(0).setCheckState(0, Qt.CheckState.Unchecked)
    cats = page.selected_categories()
    assert len(cats) == 1 and len(cats[0].items) == 2, len(cats[0].items)
    results = CleanService(mode="permanent").clean(cats)
    assert len(results) == 2 and all(r.status == CleanStatus.SUCCESS for r in results), results
    assert os.path.exists(paths[0]), "未勾选的明细应保留"
    assert not os.path.exists(paths[1]) and not os.path.exists(paths[2]), "勾选的明细应被删除"
    shutil.rmtree(tmp, ignore_errors=True)
    page.close()
    print("PASS clean honors per-item selection (2/3 deleted)")


def test_drive_info() -> None:
    """扫描页显示当前盘信息：盘符、卷标、容量。"""
    from PySide6.QtWidgets import QApplication

    from app.core.fsutils import drive_label
    from app.ui.pages import ScanPage

    app = QApplication.instance() or QApplication(sys.argv)
    page = ScanPage()
    page.reset(total_cats=2, drives=["C"])
    txt = page.lbl_drive_info.text()
    assert "C" in txt and "总" in txt and "可用" in txt, txt
    label = drive_label("C")
    print(f"PASS drive info on scan page: {txt} | label={label!r}")
    page.close()


def test_protect() -> None:
    """加锁保护：受保护文件不可勾选、清理被拒绝、不参与父节点全选；解锁后恢复。"""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.core.clean_service import CleanService, CleanStatus
    from app.core.models import CleanCategory, CleanItem, ScanReport
    from app.core.protect import is_protected, protect, unprotect
    from app.ui.pages import ResultPage

    app = QApplication.instance() or QApplication(sys.argv)
    tmp = tempfile.mkdtemp(prefix="clearc_prot_")
    target = os.path.join(tmp, "prot.txt")
    with open(target, "w", encoding="utf-8") as f:
        f.write("x")

    protect(target)
    try:
        assert is_protected(target)
        # 清理时被拒绝
        item = CleanItem(path=target, size=1)
        cat = CleanCategory(id="t", name="测试", items=[item], total_size=1, is_selected=True)
        res = CleanService(mode="permanent").clean([cat])
        assert res[0].status == CleanStatus.SKIP and "加锁" in res[0].detail, res[0]
        # 结果页标记加锁、不可勾选
        page = ResultPage()
        page.populate(ScanReport(categories=[cat]))
        top = page.tree.topLevelItem(0)
        child = top.child(0)
        assert child.data(0, Qt.ItemDataRole.UserRole + 3) == 1, "应标记加锁"
        assert not (child.flags() & Qt.ItemFlag.ItemIsUserCheckable), "加锁项不可勾选"
        assert page.selected_categories() == [], "加锁项不应进入清理列表"
        # 父节点全选也不能勾上加锁项
        top.setCheckState(0, Qt.CheckState.Checked)
        assert page.selected_categories() == [], "加锁项不参与父节点全选"
        page.close()
    finally:
        unprotect(target)
        shutil.rmtree(tmp, ignore_errors=True)
    assert not is_protected(target), "解锁后不应再受保护"
    print("PASS protect: locked refused by clean, uncheckable, excluded from select-all")


def test_about() -> None:
    """关于页：软件名称 / 版本 / 版权信息，且可从左侧导航进入。"""
    from PySide6.QtWidgets import QApplication, QLabel

    from app import APP_NAME, COPYRIGHT, __version__
    from app.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    nav = [win.nav_list.item(i).text() for i in range(win.nav_list.count())]
    assert nav == ["概览", "扫描", "设置", "关于"], nav
    win.nav_list.setCurrentRow(3)
    app.processEvents()
    assert win.pages.currentWidget() is win.about_page, "「关于」应切到关于页"
    texts = [lbl.text() for lbl in win.about_page.findChildren(QLabel) if lbl.text()]
    assert APP_NAME in texts, texts
    assert COPYRIGHT in texts, texts
    assert any("版本" in t and __version__ in t for t in texts), texts
    win.close()
    print("PASS about page: name/version/copyright, reachable from nav")


def test_gui() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.core.scan_service import ScanService
    from app.ui.dialogs import CleanCompleteDialog, CleanConfirmDialog, CleanProgressDialog
    from app.ui.main_window import MainWindow
    from app.ui.theme import STYLESHEET

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    win = MainWindow()
    win.show()
    app.processEvents()
    assert win.pages.currentIndex() == 0, "初始应在概览页"
    # 概览页应有盘符选择下拉（全部磁盘 + 至少 C）
    assert win.overview.cmb_drives.count() >= 2, "盘符下拉应含「全部磁盘」与具体盘"
    assert "C" in win.overview.selected_drives(), win.overview.selected_drives()
    print("PASS window construct:", win.overview.cmb_drives.currentText())

    # 同步扫描快速分类并填充结果页
    report = ScanService(max_workers=8).scan(category_ids=["temp_user", "thumbcache"])
    win.result_page.populate(report)
    app.processEvents()
    assert win.result_page.tree.topLevelItemCount() == 2, "应有两个分类"
    assert "已选" in win.result_page.lbl_selected.text()
    print("PASS result populate:", win.result_page.lbl_selected.text())

    # 取消勾选第一个分类 → 选中集应只剩 1 个
    first = win.result_page.tree.topLevelItem(0)
    first.setCheckState(0, Qt.CheckState.Unchecked)
    app.processEvents()
    sel = win.result_page.selected_categories()
    assert len(sel) == 1, [c.id for c in sel]
    assert sel[0].id == "thumbcache"
    print("PASS selection logic ->", sel[0].id)

    # 恢复勾选，验证汇总文字
    first.setCheckState(0, Qt.CheckState.Checked)
    app.processEvents()
    assert len(win.result_page.selected_categories()) == 2
    print("PASS selection re-check")

    # 各对话框可正常构造（不 exec）
    d1 = CleanConfirmDialog(sel, "recycle", win)
    d2 = CleanCompleteDialog([], win)
    d3 = CleanProgressDialog(sel, "recycle", win)
    assert d1 is not None and d2 is not None and d3 is not None
    print("PASS dialogs construct")

    win.close()
    app.processEvents()


if __name__ == "__main__":
    test_clean_core()
    test_drive_scope()
    test_child_selection()
    test_clean_partial_selection()
    test_drive_info()
    test_protect()
    test_about()
    test_gui()
    print("\n[OK] smoke test all passed")
