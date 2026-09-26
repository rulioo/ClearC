"""休眠文件 hiberfil.sys，高风险、默认不勾选。

注意：不能直接删除该文件，需通过 `powercfg /h off` 关闭休眠来释放空间。
清理逻辑在 M3 实现，扫描阶段仅报告其占用量。
"""
from __future__ import annotations

from pathlib import Path

from app.categories.base import CategoryScanner
from app.core.models import CleanItem


class HibernateScanner(CategoryScanner):
    id = "hibernate"
    name = "休眠文件 hiberfil.sys"
    description = "启用休眠时的内存镜像文件；关闭休眠可释放同等大小空间"
    icon = "😴"
    risk = "high"
    default_checked = False

    def scan(self):
        p = Path(r"C:\hiberfil.sys")
        try:
            if p.exists():
                return [
                    CleanItem(
                        path=str(p),
                        size=p.stat().st_size,
                        is_dir=False,
                        safe=False,  # 不可直接删除，仅提示
                    )
                ]
        except OSError:
            pass
        return []
