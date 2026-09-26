"""数据模型定义：CleanItem / CleanCategory / DiskInfo / ScanReport。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CleanItem:
    """一个可清理的文件或目录。"""

    path: str
    size: int = 0
    is_dir: bool = False
    modified: float = 0.0
    safe: bool = True  # 是否通过安全校验；大文件等“仅列出”项为 False
    selected: bool = True  # 结果页明细中是否被勾选（清理时以该项为准）


@dataclass
class CleanCategory:
    """一个垃圾分类，包含该分类下所有可清理项。"""

    id: str
    name: str
    description: str = ""
    icon: str = ""
    risk: str = "low"  # low / medium / high
    default_checked: bool = True
    items: list[CleanItem] = field(default_factory=list)
    total_size: int = 0
    is_selected: bool = True
    warning: str = ""  # 例如“需要管理员权限，已跳过”
    drive: str = "C"  # 所属盘符（drive 作用域分类会带盘符）


@dataclass
class DiskInfo:
    total: int
    used: int
    free: int


@dataclass
class ScanReport:
    """一次扫描的完整结果。"""

    categories: list[CleanCategory] = field(default_factory=list)
    disk: DiskInfo | None = None
    total_size: int = 0
    scanned_files: int = 0
    duration: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def category_map(self) -> dict[str, CleanCategory]:
        return {c.id: c for c in self.categories}
