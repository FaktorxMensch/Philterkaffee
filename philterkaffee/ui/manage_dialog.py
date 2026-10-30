# -*- coding: utf-8 -*-
"""Bestehende Auswahlstapel verwalten.

Neu aufbauen, entleeren, löschen und nachträglich umbauen — ohne das
Hauptfenster neu durchzuklicken.

Beim Neuaufbau ist die **Reihenfolge Teil des Ergebnisses**: eine Karte kann nur
in einem Auswahlstapel liegen, also bekommt sie der zuerst gebaute Stapel.
Deshalb wird immer in Listenreihenfolge (also in Lerntagsreihenfolge) gebaut
und nicht in der Reihenfolge des Anklickens.
"""

from __future__ import annotations

from anki.collection import SearchNode
from anki.decks import DeckId, FilteredDeckConfig
from aqt.operations import CollectionOp, QueryOp
from aqt.qt import *
from aqt.utils import askUser, restoreGeom, saveGeom, tooltip

from .. import branding
from ..core import builder, query
from ..core.config import Settings
from . import widgets


class ManageDialog(QDialog):
    GEOMETRY_KEY = "philterkaffeeManage"

    def __init__(self, parent: QWidget, mw, settings: Settings) -> None:
        super().__init__(parent)
        self.mw = mw
        self.col = mw.col
        self.settings = settings
        self.setWindowTitle("Philterkaffee — Auswahlstapel verwalten")
        self.setWindowIcon(branding.icon())
        self._rows: list[dict] = []
        self._order_values: list[int] = []

        layout = QVBoxLayout(self)
        layout.addWidget(
            widgets.hint(
                "Entleeren schickt die Karten in ihre Heimatstapel zurück — der "
                "Lernstand bleibt erhalten. Genau so markiert man einen "
                "erledigten Lerntag. Löschen tut dasselbe und entfernt zusätzlich "
                "den Stapel. In keinem Fall gehen Karten verloren."
            )
        )

        filter_row = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Nach Name filtern …")
        qconnect(self.filter_edit.textChanged, self._apply_filter)
        self.only_plan_check = QCheckBox("Nur unter dem Oberstapel des Lernplans")
        self.only_plan_check.setChecked(bool(settings.effective_parent))
        self.only_plan_check.setEnabled(bool(settings.effective_parent))
        qconnect(self.only_plan_check.toggled, self.reload)
        filter_row.addWidget(self.filter_edit, 1)
        filter_row.addWidget(self.only_plan_check)
        layout.addLayout(filter_row)

        self.table = widgets.read_only_table(
            ["Auswahlstapel", "Karten", "neu", "fällig", "Limit", "Sortierung"]
        )
        layout.addWidget(self.table, 1)

        select_row = QHBoxLayout()
        for label, handler in (
            ("Alle auswählen", self.table.selectAll),
            ("Auswahl aufheben", self.table.clearSelection),
            ("Leere auswählen", self._select_empty),
        ):
            button = QPushButton(label)
            qconnect(button.clicked, handler)
            select_row.addWidget(button)
        select_row.addStretch(1)
        layout.addLayout(select_row)

        actions, actions_layout = widgets.vgroup("Aktionen auf die Auswahl")
        grid = QGridLayout()
        self._add_action(grid, 0, 0, "Neu aufbauen", self._rebuild_selected,
                         "Holt die Karten passend zum gespeicherten Filter neu.")
        self._add_action(grid, 0, 1, "Entleeren", self._empty_selected,
                         "Karten gehen in ihre Heimatstapel zurück.")
        self._add_action(grid, 0, 2, "Löschen", self._remove_selected,
                         "Entfernt die Stapel. Karten bleiben erhalten.")
        self._add_action(grid, 1, 0, "Alle neu aufbauen", self._rebuild_all,
                         "Baut alle gelisteten Stapel in Listenreihenfolge neu auf.")
        self._add_action(grid, 1, 1, "Alle entleeren", self._empty_all, "")
        self._add_action(grid, 1, 2, "Im Browser zeigen", self._show_in_browser, "")
        actions_layout.addLayout(grid)
        layout.addWidget(actions)

        modify, modify_form = widgets.group("Nachträglich umbauen")
        self.new_limit = QSpinBox()
        self.new_limit.setRange(0, 99999)
        self.new_limit.setSpecialValueText("(unverändert)")
        self.new_limit.setValue(0)
        modify_form.addRow("Limit:", self.new_limit)

        self.new_order = QComboBox()
        self.new_order.addItem("(unverändert)", None)
        modify_form.addRow("Sortierung:", self.new_order)

        self.new_reschedule = QComboBox()
        self.new_reschedule.addItem("(unverändert)", None)
        self.new_reschedule.addItem("Normal planen: ein", True)
        self.new_reschedule.addItem("Normal planen: aus", False)
        modify_form.addRow("Planung:", self.new_reschedule)

        apply_row = QHBoxLayout()
        self.apply_button = QPushButton("Auf Auswahl anwenden und neu aufbauen")
        qconnect(self.apply_button.clicked, self._apply_modifications)
        apply_row.addWidget(self.apply_button)
        apply_row.addStretch(1)
        modify_form.addRow("", apply_row)
        modify_form.addRow(
            "",
            widgets.hint(
                "Ändert nur diese Einstellungen der gewählten Stapel — der "
                "gespeicherte Filter bleibt, wie er ist."
            ),
        )
        layout.addWidget(modify)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        qconnect(box.rejected, self.reject)
        layout.addWidget(box)

        restoreGeom(self, self.GEOMETRY_KEY, default_size=(880, 720))
        self.reload()

    def _add_action(self, grid, row, column, label, handler, tip) -> None:
        button = QPushButton(label)
        if tip:
            button.setToolTip(tip)
        qconnect(button.clicked, handler)
        grid.addWidget(button, row, column)

    # --- Laden -----------------------------------------------------------

    def reload(self, *_args) -> None:
        parent = self.settings.effective_parent
        only_plan = self.only_plan_check.isChecked() and bool(parent)

        def op(col):
            order_labels = list(col.sched.filtered_deck_order_labels())
            rows = []
            for deck in col.decks.all():
                if not deck.get("dyn"):
                    continue
                name = deck["name"]
                if only_plan and not (
                    name.casefold() == parent.casefold()
                    or name.casefold().startswith(parent.casefold() + "::")
                ):
                    continue
                deck_node = SearchNode(deck=name)
                terms = deck.get("terms") or []
                rows.append(
                    {
                        "id": DeckId(deck["id"]),
                        "name": name,
                        "cards": len(col.find_cards(query.build(col, deck_node))),
                        "new": len(
                            col.find_cards(
                                query.build(
                                    col,
                                    deck_node,
                                    SearchNode(card_state=SearchNode.CARD_STATE_NEW),
                                )
                            )
                        ),
                        "due": len(
                            col.find_cards(
                                query.build(
                                    col,
                                    deck_node,
                                    SearchNode(card_state=SearchNode.CARD_STATE_DUE),
                                )
                            )
                        ),
                        "limit": terms[0][1] if terms else 0,
                        "order": terms[0][2] if terms else 0,
                    }
                )
            rows.sort(key=lambda row: row["name"].casefold())
            return rows, order_labels

        QueryOp(parent=self, op=op, success=self._on_loaded).with_progress(
            "Auswahlstapel werden gelesen…"
        ).run_in_background()

    def _on_loaded(self, payload) -> None:
        rows, order_labels = payload
        self._rows = rows
        self._order_labels = order_labels

        if self.new_order.count() <= 1:
            fsrs = bool(self.col.get_config("fsrs"))
            skip = {
                FilteredDeckConfig.SearchTerm.Order.RETRIEVABILITY_ASCENDING,
                FilteredDeckConfig.SearchTerm.Order.RETRIEVABILITY_DESCENDING,
            }
            for value, label in enumerate(order_labels):
                if fsrs or value not in skip:
                    self.new_order.addItem(label, value)

        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            order_label = (
                order_labels[row["order"]]
                if 0 <= row["order"] < len(order_labels)
                else "?"
            )
            self.table.setItem(index, 0, widgets.cell(row["name"]))
            self.table.setItem(index, 1, widgets.cell(str(row["cards"]), numeric=True))
            self.table.setItem(index, 2, widgets.cell(str(row["new"]), numeric=True, dim=True))
            self.table.setItem(index, 3, widgets.cell(str(row["due"]), numeric=True, dim=True))
            self.table.setItem(index, 4, widgets.cell(str(row["limit"]), numeric=True, dim=True))
            self.table.setItem(index, 5, widgets.cell(order_label, dim=True))

        total = sum(row["cards"] for row in rows)
        empty = sum(1 for row in rows if not row["cards"])
        self.status_label.setText(
            f"{len(rows)} Auswahlstapel · {total} Karten · {empty} leer "
            "(leer heißt meist: Lerntag erledigt oder noch nicht aufgebaut)."
        )
        self._apply_filter()

    def _apply_filter(self, *_args) -> None:
        needle = self.filter_edit.text().strip().casefold()
        for index, row in enumerate(self._rows):
            self.table.setRowHidden(index, bool(needle) and needle not in row["name"].casefold())

    # --- Auswahl ---------------------------------------------------------

    def _selected_rows(self) -> list[dict]:
        indexes = sorted(
            index.row() for index in self.table.selectionModel().selectedRows()
        )
        return [self._rows[index] for index in indexes if not self.table.isRowHidden(index)]

    def _visible_rows(self) -> list[dict]:
        return [
            row
            for index, row in enumerate(self._rows)
            if not self.table.isRowHidden(index)
        ]

    def _select_empty(self) -> None:
        self.table.clearSelection()
        for index, row in enumerate(self._rows):
            if not row["cards"] and not self.table.isRowHidden(index):
                self.table.selectRow(index)

    # --- Aktionen --------------------------------------------------------

    def _run(self, rows: list[dict], operation, verb: str) -> None:
        if not rows:
            tooltip("Keine Auswahlstapel ausgewählt.", parent=self)
            return
        deck_ids = [row["id"] for row in rows]
        CollectionOp(parent=self, op=lambda col: operation(col, deck_ids)).success(
            lambda outcome: self._on_done(outcome, verb)
        ).run_in_background()

    def _on_done(self, outcome: builder.MaintenanceOutcome, verb: str) -> None:
        extra = f", {outcome.cards} Karten geholt" if outcome.cards else ""
        tooltip(f"{outcome.touched} Auswahlstapel {verb}{extra}.", parent=self)
        self.reload()

    def _rebuild_selected(self) -> None:
        self._run(self._selected_rows(), builder.rebuild_many, "neu aufgebaut")

    def _rebuild_all(self) -> None:
        rows = self._visible_rows()
        if rows and askUser(
            f"{len(rows)} Auswahlstapel in Listenreihenfolge neu aufbauen?\n\n"
            "Bei Überschneidungen bekommt der zuerst gebaute Stapel die Karte — "
            "die Reihenfolge der Liste entscheidet also.",
            parent=self,
            title="Alle neu aufbauen",
        ):
            self._run(rows, builder.rebuild_many, "neu aufgebaut")

    def _empty_selected(self) -> None:
        self._run(self._selected_rows(), builder.empty_many, "entleert")

    def _empty_all(self) -> None:
        rows = self._visible_rows()
        if rows and askUser(
            f"{len(rows)} Auswahlstapel entleeren? Die Karten kehren in ihre "
            "Heimatstapel zurück, der Lernstand bleibt erhalten.",
            parent=self,
            title="Alle entleeren",
        ):
            self._run(rows, builder.empty_many, "entleert")

    def _remove_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            tooltip("Keine Auswahlstapel ausgewählt.", parent=self)
            return
        names = "\n".join(f"• {row['name']}" for row in rows[:12])
        more = f"\n… und {len(rows) - 12} weitere" if len(rows) > 12 else ""
        if askUser(
            f"{len(rows)} Auswahlstapel löschen?\n\n{names}{more}\n\n"
            "Es gehen keine Karten verloren — sie kehren in ihre Heimatstapel "
            "zurück.",
            parent=self,
            title="Löschen",
            defaultno=True,
        ):
            self._run(rows, builder.remove_many, "gelöscht")

    def _show_in_browser(self) -> None:
        import aqt

        rows = self._selected_rows()
        if not rows:
            tooltip("Keine Auswahlstapel ausgewählt.", parent=self)
            return
        col = self.col
        node = col.group_searches(
            *(SearchNode(deck=row["name"]) for row in rows), joiner="OR"
        )
        aqt.dialogs.open("Browser", self.mw, search=(query.build(col, node),))

    def _apply_modifications(self) -> None:
        rows = self._selected_rows()
        if not rows:
            tooltip("Keine Auswahlstapel ausgewählt.", parent=self)
            return
        new_limit = self.new_limit.value() or None
        new_order = self.new_order.currentData()
        new_reschedule = self.new_reschedule.currentData()
        if new_limit is None and new_order is None and new_reschedule is None:
            tooltip("Es ist keine Änderung eingestellt.", parent=self)
            return

        deck_ids = [row["id"] for row in rows]

        def op(col):
            undo_id = col.add_custom_undo_entry("Auswahlstapel umbauen")
            changes = col.merge_undo_entries(undo_id)
            outcome = builder.MaintenanceOutcome(changes=changes)
            for deck_id in deck_ids:
                if not col.decks.is_filtered(deck_id):
                    continue
                deck = col.sched.get_or_create_filtered_deck(deck_id)
                if new_reschedule is not None:
                    deck.config.reschedule = bool(new_reschedule)
                for term in deck.config.search_terms:
                    if new_limit is not None:
                        term.limit = new_limit
                    if new_order is not None:
                        term.order = new_order
                col.sched.add_or_update_filtered_deck(deck)
                outcome.touched += 1
                changes = col.merge_undo_entries(undo_id)
            outcome.changes = changes
            return outcome

        CollectionOp(parent=self, op=op).success(
            lambda outcome: self._on_done(outcome, "umgebaut und neu aufgebaut")
        ).run_in_background()

    def reject(self) -> None:
        saveGeom(self, self.GEOMETRY_KEY)
        super().reject()
