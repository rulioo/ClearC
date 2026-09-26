"""报告导出：JSON / CSV / 文本三种格式。"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from app.core.models import ScanReport


def report_to_dict(report: ScanReport) -> dict:
    return {
        "disk": (
            {
                "total": report.disk.total,
                "used": report.disk.used,
                "free": report.disk.free,
            }
            if report.disk
            else None
        ),
        "total_size": report.total_size,
        "scanned_files": report.scanned_files,
        "duration_seconds": round(report.duration, 2),
        "warnings": report.warnings,
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "risk": c.risk,
                "total_size": c.total_size,
                "item_count": len(c.items),
                "warning": c.warning,
                "items": [
                    {
                        "path": i.path,
                        "size": i.size,
                        "is_dir": i.is_dir,
                        "safe": i.safe,
                    }
                    for i in c.items
                ],
            }
            for c in report.categories
        ],
    }


def write_json(report: ScanReport, path: str | Path) -> None:
    """写 JSON 报告（含全部分类明细）。"""
    Path(path).write_text(
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_csv(report: ScanReport, path: str | Path) -> None:
    """写 CSV 报告，每行一条可清理项。"""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["分类", "分类ID", "风险", "路径", "大小(字节)", "是否目录", "安全"])
        for c in report.categories:
            for i in c.items:
                writer.writerow([c.name, c.id, c.risk, i.path, i.size, i.is_dir, i.safe])


def write_text(report: ScanReport, path: str | Path) -> None:
    """写人类可读文本报告。"""
    from app.core.fsutils import fmt_size

    lines = [
        "=" * 60,
        "C 盘垃圾清理 — 扫描报告",
        "=" * 60,
        f"可清理垃圾总量：{fmt_size(report.total_size)}",
        f"扫描文件数：{report.scanned_files:,}",
        f"耗时：{report.duration:.1f} 秒",
    ]
    if report.disk:
        lines.append(
            f"C盘：总容量 {fmt_size(report.disk.total)} · "
            f"已用 {fmt_size(report.disk.used)} · 可用 {fmt_size(report.disk.free)}"
        )
    if report.warnings:
        lines.append("警告：")
        lines.extend(f"  - {w}" for w in report.warnings)
    lines.append("-" * 60)
    for c in report.categories:
        lines.append(
            f"[{c.risk.upper():<6}] {c.name:<28} {len(c.items):>8,} 项  {fmt_size(c.total_size):>10}"
            + (f"  ({c.warning})" if c.warning else "")
        )
    lines.append("=" * 60)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
