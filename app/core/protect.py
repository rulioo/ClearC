"""受保护（加锁）文件清单：加锁的文件避免被误操作清理。

存储在 %LOCALAPPDATA%\\ClearC\\protected.json，模块级缓存避免重复读盘。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_FILENAME = "protected.json"
_cache: set[str] | None = None


def _store_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "ClearC" / _FILENAME


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def _load() -> set[str]:
    try:
        data = json.loads(_store_path().read_text(encoding="utf-8"))
        return {_norm(p) for p in data.get("paths", [])}
    except Exception:  # noqa: BLE001 文件缺失/损坏视为空清单
        return set()


def _save(paths: set[str]) -> None:
    store = _store_path()
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(
        json.dumps({"paths": sorted(paths)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _cache_set() -> set[str]:
    global _cache
    if _cache is None:
        _cache = _load()
    return _cache


def is_protected(path: str) -> bool:
    return _norm(path) in _cache_set()


def protect(path: str) -> None:
    s = _cache_set()
    s.add(_norm(path))
    _save(s)


def unprotect(path: str) -> None:
    s = _cache_set()
    s.discard(_norm(path))
    _save(s)
