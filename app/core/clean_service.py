"""清理服务：将扫描出的项目删除（默认进回收站，可切换永久删除）。

对每个项目先做二次安全校验（validate_for_cleanup），
结果统一汇总为 CleanResult，方便 UI 逐项展示状态。
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Callable

from app.core.models import CleanCategory, CleanItem
from app.core.recycle import delete_to_recycle_bin
from app.core.safety import validate_for_cleanup


class CleanStatus:
    SUCCESS = "success"
    SKIP = "skip"
    FAILED = "failed"


@dataclass
class CleanResult:
    item: CleanItem
    category_name: str
    status: str
    detail: str = ""
    freed: int = 0


class CleanService:
    def __init__(self, mode: str = "recycle"):
        self.mode = mode  # "recycle" | "permanent"

    def clean(
        self,
        categories: list[CleanCategory],
        only_selected: bool = True,
        on_item: Callable[[CleanResult], None] | None = None,
    ) -> list[CleanResult]:
        """顺序清理。on_item 在每项完成后回调（供 UI 进度显示）。"""
        results: list[CleanResult] = []
        for cat in categories:
            if only_selected and not cat.is_selected:
                continue
            for item in cat.items:
                ok, reason = validate_for_cleanup(item, categories)
                if not ok:
                    result = CleanResult(item, cat.name, CleanStatus.SKIP, reason, 0)
                else:
                    try:
                        if self.mode == "permanent":
                            self._delete_permanent(item)
                        else:
                            ret = delete_to_recycle_bin([item.path])
                            if ret != 0:
                                raise RuntimeError(f"回收站删除失败（错误码 {ret}）")
                        result = CleanResult(item, cat.name, CleanStatus.SUCCESS, "", item.size)
                    except Exception as e:  # noqa: BLE001 单项目异常隔离
                        result = CleanResult(item, cat.name, CleanStatus.FAILED, str(e), 0)
                results.append(result)
                if on_item:
                    on_item(result)
        return results

    @staticmethod
    def _delete_permanent(item: CleanItem) -> None:
        if item.is_dir:
            def _onerror(func, path, exc_info):
                raise RuntimeError(f"删除失败 {path}（{exc_info[1]}）")

            shutil.rmtree(item.path, onerror=_onerror)
        else:
            os.remove(item.path)
