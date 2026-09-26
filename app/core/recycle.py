"""Windows 回收站删除：通过 SHFileOperationW（FOF_ALLOWUNDO）将文件移到回收站。"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040  # 关键：删除进回收站（可恢复）
FOF_NOERRORUI = 0x0400


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("wFunc", wintypes.UINT),
        ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_ushort),
        ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def delete_to_recycle_bin(paths: list[str]) -> int:
    """把多个路径删除到回收站。返回 SHFileOperationW 错误码（0 = 成功）。"""
    if not paths:
        return 0
    froms = "\x00".join(paths) + "\x00\x00"  # 双空终止的路径列表
    op = _SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = froms
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None
    try:
        ret = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if ret == 0 and op.fAnyOperationsAborted:
            return 2  # 操作被中止（通常因文件被占用），归一化为非 0 错误码
        return int(ret)
    except OSError as e:
        return int(getattr(e, "winerror", 1) or 1)
