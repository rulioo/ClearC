"""CLI 入口（M1：扫描 + 报告，用于验证扫描引擎）。

用法示例：
    python -m app list                     # 列出所有垃圾分类
    python -m app drives                    # 列出可扫描的盘符
    python -m app scan                      # 全部分类扫描，终端打印汇总
    python -m app scan --format json        # 输出 JSON 报告到 stdout
    python -m app scan -o report.json       # 写入报告文件（json/csv/txt 按后缀）
    python -m app scan -c temp_user,temp_sys  # 只扫指定分类
    python -m app scan --drives C,D         # 只扫 C、D 盘
    python -m app scan --drives all         # 扫全部盘
    python -m app scan -t 4                 # 指定扫描线程数
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

from app.categories import get_registry, list_category_ids
from app.core.fsutils import fmt_size
from app.core.models import CleanCategory, ScanReport
from app.core.report import write_csv, write_json, write_text
from app.core.scan_service import ProgressSink, ScanService

_SUFFIX_WRITER = {"json": write_json, "csv": write_csv, "txt": write_text}


def _disp_width(s: str) -> int:
    """计算字符串显示宽度（CJK 按 2 个字符宽计）。"""
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _disp_width(s))


class CliProgress(ProgressSink):
    def on_category_start(self, cat: CleanCategory) -> None:
        print(f"  · 扫描 {cat.icon} {cat.name} …", file=sys.stderr, flush=True)

    def on_category_done(self, cat: CleanCategory) -> None:
        print(
            f"  ✓ {cat.name:<22} {len(cat.items):>8,} 项  {fmt_size(cat.total_size):>10}"
            + (f"   ({cat.warning})" if cat.warning else ""),
            file=sys.stderr,
            flush=True,
        )


def _print_summary(report: ScanReport) -> None:
    print("\n" + "=" * 70)
    print(
        f"✅ 扫描完成：{len(report.categories)} 个分类，可清理垃圾共 {fmt_size(report.total_size)}，"
        f"扫描文件 {report.scanned_files:,} 个，耗时 {report.duration:.1f}s"
    )
    if report.disk:
        print(
            f"   磁盘：总容量 {fmt_size(report.disk.total)} · "
            f"已用 {fmt_size(report.disk.used)} · 可用 {fmt_size(report.disk.free)}"
        )
    for w in report.warnings:
        print(f"   ⚠ {w}")
    print("=" * 70)

    headers = ("分类", "风险", "项数", "大小", "说明")
    rows = []
    for c in report.categories:
        note = c.warning or c.description
        rows.append((f"{c.icon} {c.name}", c.risk, f"{len(c.items):,}", fmt_size(c.total_size), note))

    widths = [max(_disp_width(h), *( _disp_width(r[i]) for r in rows )) for i, h in enumerate(headers)]
    total_w = sum(widths) + len(headers) * 3 + 1

    print("┌" + "─" * (total_w - 2) + "┐")
    print("│ " + " │ ".join(_pad(h, widths[i]) for i, h in enumerate(headers)) + " │")
    print("├" + "─" * (total_w - 2) + "┤")
    for r in rows:
        print("│ " + " │ ".join(_pad(r[i], widths[i]) for i in range(len(headers))) + " │")
    print("└" + "─" * (total_w - 2) + "┘")


def cmd_list(_args: argparse.Namespace) -> int:
    print(f"{'ID':<20} {'名称':<24} {'风险':<8} {'作用域':<8} 说明")
    print("-" * 100)
    for s in get_registry():
        scope_label = "任意盘" if s.scope == "drive" else "仅C盘"
        print(f"{s.id:<20} {s.name:<24} {s.risk:<8} {scope_label:<8} {s.description}")
    return 0


def cmd_drives(_args: argparse.Namespace) -> int:
    drives = ScanService.list_drives()
    if not drives:
        print("未发现可扫描的磁盘分区", file=sys.stderr)
        return 1
    for d in drives:
        u = ScanService.disk_for(d)
        if u:
            print(
                f"{d}: 总 {fmt_size(u.total)} · 已用 {fmt_size(u.used)} · 可用 {fmt_size(u.free)}"
            )
        else:
            print(f"{d}: 无法读取容量信息")
    return 0


def _parse_drives(raw: str | None) -> list[str] | None:
    """解析 --drives：逗号分隔的盘符，all 表示全部（返回 None）。"""
    if not raw:
        return None
    parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
    if not parts or "ALL" in parts:
        return None
    return parts


def cmd_scan(args: argparse.Namespace) -> int:
    category_ids = [c for item in (args.categories or []) for c in item.split(",")]
    if category_ids:
        invalid = [c for c in category_ids if c not in list_category_ids()]
        if invalid:
            print(f"未知分类：{', '.join(invalid)}。可用：{', '.join(list_category_ids())}", file=sys.stderr)
            return 2
    else:
        print(
            "提示：将以当前权限扫描。建议用管理员终端运行以完整扫描（含回收站）。",
            file=sys.stderr,
        )

    drives = _parse_drives(args.drives)
    if drives:
        avail = ScanService.list_drives()
        missing = [d for d in drives if d not in avail]
        if missing:
            print(f"警告：以下盘符不存在，将忽略：{', '.join(missing)}", file=sys.stderr)
        drives = [d for d in drives if d in avail] or None
        print(f"扫描范围：{'、'.join(drives)} 盘", file=sys.stderr)

    service = ScanService(max_workers=args.threads, progress=CliProgress())
    report = service.scan(category_ids=category_ids or None, drives=drives)

    out = args.output
    if out:
        suffix = Path(out).suffix.lower().lstrip(".") if args.format == "auto" else args.format
        writer = _SUFFIX_WRITER.get(suffix)
        if writer is None:
            print(f"不支持的输出格式：{suffix}（支持 json/csv/txt）", file=sys.stderr)
            return 2
        writer(report, out)
        print(f"\n报告已写入：{out}")
    elif args.format == "json":
        from app.core.report import report_to_dict
        import json

        print(json.dumps(report_to_dict(report), ensure_ascii=False, indent=2))
    else:
        _print_summary(report)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clearC",
        description="C 盘垃圾清理工具 — M1 扫描引擎 CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="列出所有垃圾分类")
    p_list.set_defaults(func=cmd_list)

    p_drives = sub.add_parser("drives", help="列出可扫描的盘符及容量")
    p_drives.set_defaults(func=cmd_drives)

    p_scan = sub.add_parser("scan", help="扫描垃圾（可指定盘符）")
    p_scan.add_argument("-o", "--output", help="报告输出文件（按后缀识别 json/csv/txt）")
    p_scan.add_argument(
        "-f", "--format", default="auto", choices=["auto", "json", "csv", "txt"],
        help="输出格式（配合 --output；auto=按文件后缀）",
    )
    p_scan.add_argument(
        "-c", "--categories", nargs="*", help="只扫描指定分类（逗号或空格分隔，见 list 命令）"
    )
    p_scan.add_argument(
        "--drives", help="要扫描的盘符（逗号分隔，如 C,D；all 表示全部，默认全部）"
    )
    p_scan.add_argument("-t", "--threads", type=int, default=8, help="扫描线程数（默认 8）")
    p_scan.set_defaults(func=cmd_scan)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
