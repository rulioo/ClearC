"""分类扫描器基类：插件式定义。

新增一个垃圾分类 = 继承 CategoryScanner 并实现 scan()，
然后在 categories/__init__.py 的注册表中登记即可。

作用域：
  - scope = "system"：仅 C 盘（Windows 临时文件、更新缓存、缩略图等）。
  - scope = "drive" ：任意盘符（回收站、大文件分析等），扫描前由服务设置 drive。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.models import CleanCategory, CleanItem


class CategoryScanner(ABC):
    id: str = ""
    name: str = ""
    description: str = ""
    icon: str = ""
    risk: str = "low"  # low / medium / high
    default_checked: bool = True
    requires_admin: bool = False
    scope: str = "system"  # "system" | "drive"
    drive: str = "C"       # 当前扫描的盘符（drive 作用域使用）
    warning: str = ""      # 扫描器可在 scan() 中设置的自述警告（如“扫描超时”）
    MAX_SCAN_SECONDS: float = 0.0  # 单分类扫描时间上限（秒），0 表示不限

    @abstractmethod
    def scan(self) -> list[CleanItem]:
        """扫描并返回该分类下可清理的文件 / 目录。

        实现方自行 try/except，任何异常都不得向上抛出（由 ScanService 兜底）。
        """
        raise NotImplementedError

    def clean(self, items: list[CleanItem]) -> None:
        """执行清理（M3 里程碑实现）。"""
        raise NotImplementedError("清理功能将在 M3 里程碑实现")

    def clone(self) -> "CategoryScanner":
        """返回一个配置相同的独立实例（并发扫描每个盘符时需要独立状态）。"""
        return type(self)()

    def to_category(self, items: list[CleanItem], warning: str = "", drive: str | None = None) -> CleanCategory:
        d = (drive or self.drive).upper()
        is_drive_scoped = self.scope == "drive"
        cat_id = f"{d}:{self.id}" if is_drive_scoped else self.id
        name = f"{d}盘：{self.name}" if is_drive_scoped else self.name
        return CleanCategory(
            id=cat_id,
            name=name,
            description=self.description,
            icon=self.icon,
            risk=self.risk,
            default_checked=self.default_checked,
            items=items,
            total_size=sum(i.size for i in items),
            warning=warning or self.warning,
            drive=d,
        )
