"""自定义控件：环形图（概览页占比 + 扫描进度，可叠加同心圆容量环）。"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

PRIMARY = QColor("#2F6FED")
SUCCESS = QColor("#2E9E5B")
TRACK = QColor("#E4E7EF")
TEXT = QColor("#1F2937")
TEXT_MUTED = QColor("#6B7280")


class DonutChart(QWidget):
    """环形图：绘制占比弧线 + 中心文字。

    支持叠加同心圆：外环 = 容量使用率（蓝），内环 = 主指标（绿），底部图例标注。
    未调用 set_capacity 时行为与单环完全一致（概览页磁盘占比）。
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._ratio = 0.0  # 主指标（内环），如扫描进度
        self._center = "--"
        self._sub = ""
        self._arc_width = 16
        self._main_color = SUCCESS  # 内环弧颜色（概览页容量用蓝色，扫描进度用绿色）
        self._cap_ratio: float | None = None  # 外环容量使用率；None 表示不绘制
        self._cap_label = ""
        self.setMinimumSize(220, 220)

    def set_data(
        self, ratio: float, center: str, sub: str = "", color=None
    ) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self._center = center
        self._sub = sub
        if color is not None:
            self._main_color = QColor(color)
        self.update()

    def set_capacity(self, ratio: float, label: str = "") -> None:
        """设置外环容量使用率（0~1）与图例文字；ratio 为 None 可关闭外环。"""
        self._cap_ratio = max(0.0, min(1.0, ratio)) if ratio is not None else None
        self._cap_label = label
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        has_cap = self._cap_ratio is not None
        legend_h = 24 if has_cap else 0
        avail_h = self.height() - legend_h
        side = min(self.width(), avail_h) - 16
        rect = QRectF((self.width() - side) / 2, (avail_h - side) / 2, side, side)

        # 外环：容量使用率（蓝）
        if has_cap:
            outer_w = 22
            pen = QPen(TRACK, outer_w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, 0, 360 * 16)
            if self._cap_ratio > 0:
                pen = QPen(PRIMARY, outer_w)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawArc(rect, 90 * 16, int(-self._cap_ratio * 360 * 16))
            rect = rect.adjusted(outer_w + 6, outer_w + 6, -(outer_w + 6), -(outer_w + 6))

        # 内环：主指标（绿）
        pen = QPen(TRACK, self._arc_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)
        if self._ratio > 0:
            pen = QPen(self._main_color, self._arc_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, 90 * 16, int(-self._ratio * 360 * 16))

        # 中心主文字
        painter.setPen(TEXT)
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._center)

        # 中心副文字
        if self._sub:
            painter.setPen(TEXT_MUTED)
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(
                rect.adjusted(0, 44, 0, 0),
                Qt.AlignmentFlag.AlignCenter,
                self._sub,
            )

        # 底部图例：容量 · 扫描
        if has_cap:
            y = self.height() - 12
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            half = self.width() / 2
            # 左：容量
            x = half - 96
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(PRIMARY)
            painter.drawEllipse(QPointF(x, y), 4, 4)
            painter.setPen(TEXT_MUTED)
            painter.drawText(QPointF(x + 10, y + 4), self._cap_label)
            # 右：扫描
            x = half + 8
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(SUCCESS)
            painter.drawEllipse(QPointF(x, y), 4, 4)
            painter.setPen(TEXT_MUTED)
            scan_txt = f"扫描 {self._center}" if str(self._center).endswith("%") else "扫描"
            painter.drawText(QPointF(x + 10, y + 4), scan_txt)
