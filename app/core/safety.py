"""安全规则：黑名单路径、整盘扫描跳过集合、清理前二次校验。

所有系统关键路径都按“任意盘符下的顶级目录名”匹配，这样
在扫描 / 清理其他盘（如 D 盘）时同样生效。
"""
from __future__ import annotations

import os

from app.core.protect import is_protected

# 系统关键文件——任何情况下不得作为清理目标（与盘符无关）。
BLACKLISTED_FILES = {
    "pagefile.sys",
    "swapfile.sys",
    "hiberfil.sys",  # 休眠文件由专门分类处理（走 powercfg），不可直接删除
    "bootmgr",
    "BOOTNXT",
}

# 系统关键顶级目录名——禁止进入 / 清理（任意盘符下均生效）。
BLACKLISTED_DIR_NAMES = {
    "windows",
    "program files",
    "program files (x86)",
    "system volume information",
    "recovery",
    "config.msi",
    "perflogs",
    # 注意：$Recycle.Bin 不在此处——回收站由独立分类处理，应允许清理。
}

# C:\\Windows 下允许清理的精确子目录（前缀白名单，仅 C 盘生效）。
WINDOWS_ALLOWED = [
    r"C:\Windows\Temp",
    r"C:\Windows\Prefetch",
    r"C:\Windows\SoftwareDistribution\Download",
    r"C:\Windows\Minidump",
    r"C:\Windows\LiveKernelReports",
    r"C:\Windows\Logs",
]

# 整盘大文件扫描时跳过的顶级目录名（性能 + 安全，任意盘符下均生效）。
SCAN_SKIP_DIR_NAMES = {
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "system volume information",
    "recovery",
    "config.msi",
    "perflogs",
    "$recycle.bin",
}


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _drive_and_top(path: str) -> tuple[str, str]:
    """返回 (盘符, 顶级目录名)。如 'D:\\SomeDir\\x' -> ('d:', 'somedir')。

    相对路径或缺省盘符时盘符为空串。
    """
    parts = [part for part in _norm(path).split(os.sep) if part]
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1]


def is_blacklisted(path: str) -> bool:
    """判断路径是否命中黑名单（系统关键文件 / 目录），命中则不可清理。"""
    p = _norm(path)
    if os.path.basename(p).lower() in BLACKLISTED_FILES:
        return True
    drive, top = _drive_and_top(p)
    if top not in BLACKLISTED_DIR_NAMES:
        return False
    # Windows 目录下允许白名单子目录（仅 C 盘）。
    if top == "windows" and drive == "c:":
        for allowed in WINDOWS_ALLOWED:
            a = _norm(allowed)
            if p == a or p.startswith(a + os.sep):
                return False
    return True


def should_skip_scan_dir(path: str) -> bool:
    """整盘扫描时判断目录是否应跳过（命中任意盘符的系统顶级目录）。"""
    _, top = _drive_and_top(path)
    return top in SCAN_SKIP_DIR_NAMES


def validate_for_cleanup(item, report_categories) -> tuple[bool, str]:
    """清理前二次校验（M3 使用）：黑名单检查 + 必须命中本次扫描结果。"""
    p = _norm(item.path)
    if is_blacklisted(item.path):
        return False, "命中系统黑名单"
    if is_protected(item.path):
        return False, "已加锁保护"
    if not item.safe:
        return False, "标记为不可安全删除"
    for cat in report_categories:
        for it in cat.items:
            if _norm(it.path) == p:
                return True, ""
    return False, "路径不在扫描结果中"
