"""列出打包后 exe 内嵌档案的内容，按体积聚合。

调 PyInstaller 自带的 archive_viewer 拿真实清单，比解析 TOC 可靠（TOC 的结构
随 PyInstaller 版本变化）。裁剪体积或排查「某个 DLL 到底有没有打进去」时用：

    python tools/bundle_report.py

注意读的是 dist/ClearC.exe，得先打包。找不到文件会明确报错而不是静默给空结果。
"""
from __future__ import annotations

import collections
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, "dist", "ClearC.exe")

# position, length, uncompressed_length, is_compressed, typecode, name
LINE = re.compile(r"^\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*'(\w+)',\s*(.+?)\s*$")


def package_of(name: str) -> str:
    """把档案内名称归到来源包，便于看谁占大头。"""
    low = name.lower()
    if low.startswith("pyside6") or "\\pyside6" in low or low.startswith("shiboken"):
        return "PySide6 / shiboken"
    if low.startswith("python3") or low.startswith("python312.dll"):
        return "〈Python 运行时〉"
    if low.startswith("pyimod") or low.startswith("pyi_") or low.startswith("_"):
        return "〈PyInstaller 引导〉"
    return name.replace("\\", "/").split("/")[0]


def read_archive() -> list[tuple[int, str, str]]:
    """返回 [(压缩后字节数, typecode, 名称)]。"""
    out = subprocess.run(
        [sys.executable, "-m", "PyInstaller.utils.cliutils.archive_viewer", "-l", EXE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    rows = []
    for line in out.splitlines():
        m = LINE.match(line)
        if m:
            rows.append((int(m.group(2)), m.group(5), m.group(6).strip("'")))
    return rows


def main() -> int:
    if not os.path.exists(EXE):
        print(f"找不到 {EXE}\n请先执行：python -m PyInstaller --noconfirm ClearC.spec", file=sys.stderr)
        return 1

    rows = read_archive()
    if not rows:
        print("档案为空或解析失败，archive_viewer 输出格式可能变了", file=sys.stderr)
        return 1

    total_exe = os.path.getsize(EXE)
    total_arc = sum(r[0] for r in rows)

    by_pkg: collections.Counter[str] = collections.Counter()
    by_type: collections.Counter[str] = collections.Counter()
    for length, ty, name in rows:
        by_pkg[package_of(name)] += length
        by_type[ty] += length

    print(f"exe 总体积 {total_exe / 1048576:.1f} MiB")
    print(f"内嵌档案   {total_arc / 1048576:.1f} MiB  （{len(rows)} 项，已压缩）")
    print(f"引导头等   {(total_exe - total_arc) / 1048576:.1f} MiB\n")

    print("=== 按来源包（压缩后）===")
    for pkg, s in by_pkg.most_common(18):
        print(f"  {s / 1048576:8.1f} MiB {s / total_arc * 100:5.1f}%  {pkg}")

    print("\n=== 按类型 ===")
    for ty, s in by_type.most_common():
        print(f"  {s / 1048576:8.1f} MiB  typecode={ty}")

    print("\n=== 最大的 30 个条目（压缩后）===")
    for length, ty, name in sorted(rows, reverse=True)[:30]:
        print(f"  {length / 1048576:7.2f} MiB  {ty}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
