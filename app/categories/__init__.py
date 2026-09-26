"""分类注册表：新增分类在此登记即可被扫描器发现。"""
from __future__ import annotations

from app.categories.base import CategoryScanner
from app.categories.browser_cache import BrowserCacheScanner
from app.categories.crash_dump import CrashDumpScanner
from app.categories.dev_cache import DevCacheScanner
from app.categories.hibernate import HibernateScanner
from app.categories.installer_cache import InstallerCacheScanner
from app.categories.large_files import LargeFilesScanner
from app.categories.logs import LogsScanner
from app.categories.old_windows import OldWindowsScanner
from app.categories.recycle_bin import RecycleBinScanner
from app.categories.temp_files import TempSystemScanner, TempUserScanner
from app.categories.thumbcache import ThumbCacheScanner
from app.categories.update_cache import UpdateCacheScanner

_REGISTRY: list[CategoryScanner] = [
    TempUserScanner(),
    TempSystemScanner(),
    UpdateCacheScanner(),
    RecycleBinScanner(),
    ThumbCacheScanner(),
    BrowserCacheScanner(),
    CrashDumpScanner(),
    LogsScanner(),
    DevCacheScanner(),
    InstallerCacheScanner(),
    OldWindowsScanner(),
    HibernateScanner(),
    LargeFilesScanner(),
]


def get_registry() -> list[CategoryScanner]:
    return list(_REGISTRY)


def get_scanner(cat_id: str) -> CategoryScanner | None:
    for s in _REGISTRY:
        if s.id == cat_id:
            return s
    return None


def list_category_ids() -> list[str]:
    return [s.id for s in _REGISTRY]
