"""文件系统通用工具：目录大小计算、目录子项枚举、人类可读大小格式化。"""
from __future__ import annotations

import os
from pathlib import Path

from .models import CleanItem

FILE_ATTRIBUTE_REPARSE_POINT = 0x0400


def is_reparse_point(path: str | os.PathLike) -> bool:
    """判断路径是否为重解析点（junction / 符号链接）。

    Windows 上 C:\\Documents and Settings、Users\\All Users 等 junction
    会被 is_dir() 判定为目录，若不跳过会导致目录遍历死循环或走到其他盘符。
    """
    try:
        attrs = os.stat(path, follow_symlinks=False).st_file_attributes
        return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except OSError:
        return True  # 无法获取属性时保守跳过


def dir_size(path: str | os.PathLike) -> int:
    """递归计算目录总大小（字节）。遇权限错误 / 重解析点自动跳过，不抛出异常。"""
    total = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if is_reparse_point(entry.path):
                            continue
                        total += dir_size(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        total += entry.stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return total


def scan_dir_children(root: str | os.PathLike) -> list[CleanItem]:
    """枚举目录的直接子项（文件 + 目录），目录项记录其递归总大小。

    重解析点（junction / 符号链接）一律跳过，不作为清理候选。
    """
    items: list[CleanItem] = []
    try:
        with os.scandir(root) as it:
            for entry in it:
                try:
                    if is_reparse_point(entry.path):
                        continue
                    st = entry.stat()
                    is_dir = entry.is_dir(follow_symlinks=False)
                    items.append(
                        CleanItem(
                            path=entry.path,
                            size=dir_size(entry.path) if is_dir else st.st_size,
                            is_dir=is_dir,
                            modified=st.st_mtime,
                        )
                    )
                except OSError:
                    continue
    except OSError:
        return []
    return items


def fmt_size(n: int) -> str:
    """把字节数格式化为人类可读大小，如 12.8 GB。"""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def is_admin_user() -> bool:
    """判断当前进程是否以管理员权限运行。"""
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def resource_path(name: str) -> str:
    """返回随程序分发的资源文件绝对路径。

    PyInstaller onefile 下资源解包到 sys._MEIPASS；源码运行时取项目根目录。
    """
    import sys

    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, name)


def drive_label(drive: str) -> str:
    """读取盘符卷标（如 C 盘的卷标）；读取失败返回空串。"""
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(261)
        fs = ctypes.create_unicode_buffer(261)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(f"{drive}:\\"),
            buf,
            len(buf),
            None,
            None,
            None,
            fs,
            len(fs),
        )
        return buf.value if ok else ""
    except Exception:  # noqa: BLE001
        return ""
