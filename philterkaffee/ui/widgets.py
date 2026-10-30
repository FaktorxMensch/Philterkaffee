# -*- coding: utf-8 -*-
"""Kleine Bausteine, die mehrere Fenster teilen."""

from __future__ import annotations

from aqt.qt import *


def hint(text: str) -> QLabel:
    """Erklärender Kleintext unter einem Bedienelement."""
    label = QLabel(text)
    label.setWordWrap(True)
    font = label.font()
    font.setPointSizeF(max(9.0, font.pointSizeF() - 1.5))
    label.setFont(font)
    label.setEnabled(False)
    return label


def heading(text: str) -> QLabel:
    label = QLabel(text)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


def group(title: str) -> tuple[QGroupBox, QFormLayout]:
    box = QGroupBox(title)
    layout = QFormLayout(box)
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return box, layout


def vgroup(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    return box, layout


def scroll_area(inner: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(inner)
    area.setFrameShape(QFrame.Shape.NoFrame)
    return area


def checkable_list() -> QListWidget:
    widget = QListWidget()
    widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    widget.setUniformItemSizes(True)
    return widget


def set_all_checked(widget: QListWidget, checked: bool) -> None:
    state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
    for row in range(widget.count()):
        widget.item(row).setCheckState(state)


def checked_data(widget: QListWidget) -> list:
    return [
        widget.item(row).data(Qt.ItemDataRole.UserRole)
        for row in range(widget.count())
        if widget.item(row).checkState() == Qt.CheckState.Checked
    ]


def read_only_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    for column in range(1, len(headers)):
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
    return table


def cell(text: str, *, numeric: bool = False, dim: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    if numeric:
        item.setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
    if dim:
        item.setForeground(QBrush(QColor(128, 128, 128)))
    return item


def message_browser() -> QTextBrowser:
    browser = QTextBrowser()
    browser.setOpenExternalLinks(False)
    browser.setMinimumHeight(70)
    return browser
