"""扫描服务：线程池并行调度各分类扫描器，汇总为 ScanReport。

支持多盘扫描：
  - scope="system" 的分类只对 C 盘运行（临时文件、更新缓存等系统路径）。
  - scope="drive"  的分类对每个被选盘符克隆一份独立实例运行（回收站、大文件）。

进度回调：UI / CLI 通过实现 ProgressSink 接收每个分类的开始与完成事件。
任何单个分类的异常都会被隔离，不影响整体扫描结果。
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import psutil

from app.categories import get_registry
from app.core.fsutils import is_admin_user
from app.core.models import CleanCategory, DiskInfo, ScanReport


class ProgressSink:
    """进度回调接口，CLI / GUI 各自实现。"""

    def on_category_start(self, cat: CleanCategory) -> None:
        """某分类开始扫描。"""

    def on_category_done(self, cat: CleanCategory) -> None:
        """某分类扫描完成（含结果）。"""


class ScanService:
    def __init__(self, max_workers: int = 8, progress: ProgressSink | None = None):
        self.max_workers = max_workers
        self.progress = progress

    @staticmethod
    def list_drives() -> list[str]:
        """列出可扫描的盘符（C 排最前，其余按字母序）。"""
        drives: list[str] = []
        try:
            for part in psutil.disk_partitions(all=False):
                mp = part.mountpoint
                if len(mp) >= 2 and mp[1] == ":":
                    letter = mp[0].upper()
                    if letter not in drives:
                        drives.append(letter)
        except Exception:  # noqa: BLE001
            pass
        drives.sort(key=lambda d: (d != "C", d))
        return drives

    @staticmethod
    def disk_for(drive: str) -> DiskInfo | None:
        """读取单个盘符的容量信息。"""
        try:
            u = psutil.disk_usage(f"{drive}:/")
            return DiskInfo(total=u.total, used=u.used, free=u.free)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def read_disk(drives: list[str]) -> DiskInfo | None:
        """汇总多个盘符的容量信息（多盘时取总和）。"""
        total = used = free = 0
        for d in drives:
            u = ScanService.disk_for(d)
            if u:
                total += u.total
                used += u.used
                free += u.free
        if total <= 0:
            return None
        return DiskInfo(total=total, used=used, free=free)

    @staticmethod
    def build_tasks(
        drives: list[str] | None = None,
        category_ids: list[str] | None = None,
    ) -> list[tuple[object, str]]:
        """生成 (扫描器实例, 盘符) 任务列表，保持确定性顺序。

        - scope="system" 的分类只在 C 盘运行；
        - scope="drive"  的分类对每个被选盘符各克隆一份实例。
        """
        drives = [d.upper() for d in (drives or ScanService.list_drives())]
        id_set = set(category_ids or [])
        tasks = []
        for drive in drives:
            for scanner in get_registry():
                sc = scanner.clone()
                expected = f"{drive}:{scanner.id}" if scanner.scope == "drive" else scanner.id
                if id_set and expected not in id_set and scanner.id not in id_set:
                    continue
                if scanner.scope == "system" and drive != "C":
                    continue  # 系统垃圾分类只在 C 盘运行
                if scanner.scope == "drive":
                    sc.drive = drive
                tasks.append((sc, drive))
        return tasks

    def scan(
        self,
        category_ids: list[str] | None = None,
        is_admin: bool | None = None,
        drives: list[str] | None = None,
    ) -> ScanReport:
        """执行一次扫描。

        category_ids=None 表示扫描全部分类；id 支持盘符限定（如 "D:recyclebin"），
        也支持不限定盘符（如 "recyclebin"，会对每个被选盘符各跑一次）。
        drives=None 表示扫描全部盘符。
        """
        is_admin = is_admin_user() if is_admin is None else is_admin
        drives = [d.upper() for d in (drives or self.list_drives())]
        started = time.time()

        warnings: list[str] = []
        if not is_admin:
            warnings.append(
                "当前未以管理员身份运行，回收站等需权限的目录已跳过（建议以管理员运行以完整扫描）"
            )
        if any(d != "C" for d in drives):
            warnings.append(
                "非 C 盘仅扫描回收站与大文件分析（临时文件、更新缓存等系统垃圾只针对 C 盘）"
            )

        def run_one(scanner, drive) -> CleanCategory:
            if scanner.requires_admin and not is_admin:
                return scanner.to_category([], "需要管理员权限，已跳过", drive=drive)
            try:
                items = scanner.scan() or []
                return scanner.to_category(items, drive=drive)
            except Exception as e:  # noqa: BLE001 单分类异常隔离
                return scanner.to_category([], f"扫描异常：{e}", drive=drive)

        tasks = self.build_tasks(drives, category_ids)
        categories: dict[str, CleanCategory] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for sc, drive in tasks:
                if self.progress:
                    self.progress.on_category_start(sc.to_category([], drive=drive))
                futures[pool.submit(run_one, sc, drive)] = (sc, drive)
            for fut in as_completed(futures):
                sc, drive = futures[fut]
                cat = fut.result()
                categories[cat.id] = cat
                if self.progress:
                    self.progress.on_category_done(cat)

        final_cats = [categories[sc.to_category([], drive=drive).id] for sc, drive in tasks]
        return ScanReport(
            categories=final_cats,
            disk=self.read_disk(drives),
            total_size=sum(c.total_size for c in final_cats),
            scanned_files=sum(len(c.items) for c in final_cats),
            duration=time.time() - started,
            warnings=warnings,
        )
