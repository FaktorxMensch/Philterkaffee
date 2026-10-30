# -*- coding: utf-8 -*-
"""Titel der Lerntage bearbeiten.

Die Lerntags-Tags von AnkiPhil tragen keinen Namen, also werden die Titel aus
den Fach-Tags abgeleitet. Hier lassen sie sich überschreiben — und mit
„Zurücksetzen“ wieder auf die Ableitung bringen, etwa nach einem
Stapel-Update.
"""

from __future__ import annotations

from aqt.qt import *
from aqt.utils import restoreGeom, saveGeom

from .. import branding
from ..core.taxonomy import Group
from . import widgets


class TitlesDialog(QDialog):
    GEOMETRY_KEY = "philterkaffeeTitles"

    def __init__(
        self,
        parent: QWidget,
        *,
        groups: list[Group],
        titles: dict[str, str],
        derived: dict[str, str],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Titel der Lerntage")
        self.setWindowIcon(branding.icon())
        self._groups = groups
        self._derived = derived
        self.titles: dict[str, str] = dict(titles)

        layout = QVBoxLayout(self)
        layout.addWidget(
            widgets.hint(
                "Links steht der Lerntag, rechts der Titel für den Stapelnamen. "
                "Abgeleitete Titel stammen aus den #Fächer-Tags der enthaltenen "
                "Karten; eigene Eingaben bleiben erhalten."
            )
        )

        self._table = QTableWidget(len(groups), 3, self)
        self._table.setHorizontalHeaderLabels(["Lerntag", "Titel", "Abgeleitet"])
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for row, group in enumerate(groups):
            key_item = QTableWidgetItem(group.key)
            key_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row, 0, key_item)

            value = titles.get(group.key) or derived.get(group.key, "")
            self._table.setItem(row, 1, QTableWidgetItem(value))

            derived_item = QTableWidgetItem(derived.get(group.key, ""))
            derived_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            derived_item.setForeground(QBrush(QColor(128, 128, 128)))
            self._table.setItem(row, 2, derived_item)

        layout.addWidget(self._table, 1)

        buttons = QHBoxLayout()
        reset_all = QPushButton("Alle auf abgeleitete Titel zurücksetzen")
        qconnect(reset_all.clicked, self._reset_all)
        reset_selected = QPushButton("Auswahl zurücksetzen")
        qconnect(reset_selected.clicked, self._reset_selected)
        buttons.addWidget(reset_all)
        buttons.addWidget(reset_selected)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        qconnect(box.accepted, self.accept)
        qconnect(box.rejected, self.reject)
        layout.addWidget(box)

        restoreGeom(self, self.GEOMETRY_KEY, default_size=(640, 520))

    def _reset_all(self) -> None:
        for row, group in enumerate(self._groups):
            self._table.item(row, 1).setText(self._derived.get(group.key, ""))

    def _reset_selected(self) -> None:
        for index in self._table.selectionModel().selectedRows():
            group = self._groups[index.row()]
            self._table.item(index.row(), 1).setText(self._derived.get(group.key, ""))

    def accept(self) -> None:
        result: dict[str, str] = {}
        for row, group in enumerate(self._groups):
            text = self._table.item(row, 1).text().strip()
            # Nur Abweichungen von der Ableitung speichern — so greift eine
            # neue Ableitung nach einem Stapel-Update automatisch.
            if text and text != self._derived.get(group.key, ""):
                result[group.key] = text
        self.titles = result
        saveGeom(self, self.GEOMETRY_KEY)
        super().accept()
