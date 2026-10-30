# -*- coding: utf-8 -*-
"""Karten im AnkiPhil-Stapel nach Tag ein- und ausschließen.

Für den Fall „ich habe mehr Zeit und will mehr Karten lernen“ (oder weniger).
Gearbeitet wird mit Suspendieren und Reaktivieren — das wirkt auf die ganze
Sammlung und synchronisiert auf alle Geräte, anders als der Lerntiefe-Filter
der Auswahlstapel, der nur bestimmt, was in die Tagesstapel wandert.

Zwei Dinge, die hier nie passieren:

* Es wird nichts außerhalb des AnkiPhil-Tagbaums angefasst. Der Umfang ist
  immer ``tag:<Basis>`` (das erfasst in Anki den Tag und alle Untertags).
* Es wird nichts geschrieben, was nicht vorher gezählt und angezeigt wurde.

Die Zahlen im Baum kommen aus **einem** Datenbankzugriff, nicht aus einer Suche
pro Tag — bei über 3.000 Tags wäre das sonst minutenlang.
"""

from __future__ import annotations

from collections import Counter
from enum import Enum

from anki.collection import SearchNode
from aqt.operations import CollectionOp, QueryOp
from aqt.qt import *
from aqt.utils import askUser, restoreGeom, saveGeom, showWarning, tooltip

from .. import branding
from ..core import query, taxonomy, titles
from ..core.taxonomy import Taxonomy
from . import widgets

SUSPENDED_QUEUE = -1


class Mode(Enum):
    UNSUSPEND = "unsuspend"
    SUSPEND = "suspend"
    EXACT = "exact"

    @property
    def label(self) -> str:
        return {
            Mode.UNSUSPEND: "Auswahl einschließen (reaktivieren)",
            Mode.SUSPEND: "Auswahl ausschließen (suspendieren)",
            Mode.EXACT: "Nur die Auswahl aktiv lassen (alles andere ausschließen)",
        }[self]

    @property
    def explanation(self) -> str:
        return {
            Mode.UNSUSPEND: (
                "Suspendierte Karten der gewählten Tags werden wieder aktiv. "
                "Alles andere bleibt, wie es ist. Das ist der Weg, wenn du mehr "
                "lernen willst."
            ),
            Mode.SUSPEND: (
                "Aktive Karten der gewählten Tags werden suspendiert. Alles "
                "andere bleibt, wie es ist."
            ),
            Mode.EXACT: (
                "Setzt den Zustand hart: nur die gewählten Tags bleiben aktiv, "
                "alles andere im AnkiPhil-Stapel wird suspendiert. Mit Bedacht "
                "benutzen — das kann sehr viele Karten betreffen."
            ),
        }[self]


class GatingDialog(QDialog):
    GEOMETRY_KEY = "philterkaffeeGating"

    def __init__(self, parent: QWidget, mw, tax: Taxonomy) -> None:
        super().__init__(parent)
        self.mw = mw
        self.col = mw.col
        self.taxonomy = tax
        self.setWindowTitle("Philterkaffee — Karten ein- und ausschließen")
        self.setWindowIcon(branding.icon())
        self._total: Counter[str] = Counter()
        self._suspended: Counter[str] = Counter()
        self._preview: tuple[list[int], list[int]] | None = None
        self._pending_selection: list[str] = []

        layout = QVBoxLayout(self)
        layout.addWidget(
            widgets.hint(
                f"Umfang: alle Karten mit dem Tag „{tax.base}“ und darunter. "
                "Stapel außerhalb von AnkiPhil werden nie angefasst.\n\n"
                "Ein Haken schließt den Tag mit allen Untertags ein. "
                "Suspendierte Karten können nicht in Auswahlstapel geholt "
                "werden — hier gesetzte Ausschlüsse wirken also auch dort."
            )
        )

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Tag", "Karten", "davon aus"])
        self.tree.setColumnWidth(0, 420)
        self.tree.setAlternatingRowColors(True)
        qconnect(self.tree.itemChanged, self._on_tree_changed)
        layout.addWidget(self.tree, 1)

        tree_buttons = QHBoxLayout()
        for label, handler in (
            ("Alle Haken entfernen", lambda: self._set_all(False)),
            ("Ausklappen", self.tree.expandAll),
            ("Einklappen", self.tree.collapseAll),
        ):
            button = QPushButton(label)
            qconnect(button.clicked, handler)
            tree_buttons.addWidget(button)
        tree_buttons.addStretch(1)
        layout.addLayout(tree_buttons)

        box, form = widgets.group("Was soll geschehen?")
        self.mode_combo = QComboBox()
        for mode in Mode:
            self.mode_combo.addItem(mode.label, mode.value)
        qconnect(self.mode_combo.currentIndexChanged, self._on_mode_changed)
        form.addRow("Aktion:", self.mode_combo)
        self.mode_hint = widgets.hint("")
        form.addRow("", self.mode_hint)
        layout.addWidget(box)

        self.summary_label = QLabel("Noch keine Vorschau berechnet.")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        bar = QHBoxLayout()
        show_button = QPushButton("Im Browser zeigen")
        qconnect(show_button.clicked, self._show_in_browser)
        self.preview_button = QPushButton("Vorschau berechnen")
        qconnect(self.preview_button.clicked, self.refresh_preview)
        self.apply_button = QPushButton("Anwenden")
        self.apply_button.setEnabled(False)
        qconnect(self.apply_button.clicked, self._apply)
        close_button = QPushButton("Schließen")
        qconnect(close_button.clicked, self.reject)
        bar.addWidget(show_button)
        bar.addStretch(1)
        bar.addWidget(self.preview_button)
        bar.addWidget(self.apply_button)
        bar.addWidget(close_button)
        layout.addLayout(bar)

        restoreGeom(self, self.GEOMETRY_KEY, default_size=(820, 760))
        self._on_mode_changed()
        self._load()

    # --- Laden -----------------------------------------------------------

    def _load(self) -> None:
        base = self.taxonomy.base
        # Der Baum wird neu aufgebaut; die Haken dürfen dabei nicht verloren
        # gehen, sonst müsste man nach jedem Anwenden alles neu anklicken.
        self._pending_selection = (
            self.selected_tags() if self.tree.topLevelItemCount() else []
        )

        def op(col):
            scope = query.scope_search(col, base)
            note_tags = titles.load_note_tags(col, scope)
            total: Counter[str] = Counter()
            suspended: Counter[str] = Counter()
            # Ein Zugriff für die ganze Sammlung statt einer Suche pro Tag.
            for note_id, queue in col.db.all("select nid, queue from cards"):
                tags = note_tags.get(note_id)
                if not tags:
                    continue
                prefixes: set[str] = set()
                for tag in tags:
                    if not (tag == base or tag.startswith(base + "::")):
                        continue
                    parts = tag.split("::")
                    for depth in range(1, len(parts) + 1):
                        prefixes.add("::".join(parts[:depth]))
                for prefix in prefixes:
                    total[prefix] += 1
                    if queue == SUSPENDED_QUEUE:
                        suspended[prefix] += 1
            return total, suspended

        QueryOp(parent=self, op=op, success=self._on_loaded).with_progress(
            "Tags und Kartenzustände werden gelesen…"
        ).failure(self._on_load_failed).run_in_background()

    def _on_load_failed(self, exc: Exception) -> None:
        showWarning(f"Die Tags konnten nicht gelesen werden:\n\n{exc}", parent=self)
        self.close()

    def _on_loaded(self, payload) -> None:
        self._total, self._suspended = payload
        self.tree.blockSignals(True)
        self.tree.clear()
        base = self.taxonomy.base
        nodes: dict[str, QTreeWidgetItem] = {}

        for tag in sorted(self._total, key=lambda t: (t.count("::"), t.casefold())):
            if tag == base:
                continue
            parts = tag.split("::")
            parent_tag = "::".join(parts[:-1])
            parent = nodes.get(parent_tag)
            item = QTreeWidgetItem([taxonomy.prettify(parts[-1]) or parts[-1]])
            item.setData(0, Qt.ItemDataRole.UserRole, tag)
            item.setToolTip(0, tag)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setText(1, str(self._total.get(tag, 0)))
            off = self._suspended.get(tag, 0)
            item.setText(2, str(off) if off else "—")
            item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight)
            item.setTextAlignment(2, Qt.AlignmentFlag.AlignRight)
            if off and off == self._total.get(tag, 0):
                item.setForeground(0, QBrush(QColor(150, 150, 150)))
            if tag in self._pending_selection:
                item.setCheckState(0, Qt.CheckState.Checked)
            nodes[tag] = item
            if parent is not None:
                parent.addChild(item)
            else:
                self.tree.addTopLevelItem(item)

        self.tree.blockSignals(False)
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setExpanded(True)
        # Wiederhergestellte Haken sichtbar machen.
        for tag in self._pending_selection:
            item = nodes.get(tag)
            while item is not None:
                item.setExpanded(True)
                item = item.parent()

        active = self._total.get(base, 0) - self._suspended.get(base, 0)
        self.summary_label.setText(
            f"AnkiPhil-Stapel: {self._total.get(base, 0)} Karten, davon "
            f"{active} aktiv und {self._suspended.get(base, 0)} ausgeschlossen."
        )

    # --- Auswahl ---------------------------------------------------------

    def _set_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.tree.blockSignals(True)
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            iterator.value().setCheckState(0, state)
            iterator += 1
        self.tree.blockSignals(False)
        self._mark_stale()

    def selected_tags(self) -> list[str]:
        """Nur die obersten angehakten Tags.

        ``tag:X`` erfasst in Anki auch ``X::*``, ein zusätzlich angehakter
        Untertag wäre also redundant und würde die Suche nur verlängern.
        """
        chosen: list[str] = []
        iterator = QTreeWidgetItemIterator(
            self.tree, QTreeWidgetItemIterator.IteratorFlag.Checked
        )
        while iterator.value():
            tag = iterator.value().data(0, Qt.ItemDataRole.UserRole)
            if tag:
                chosen.append(tag)
            iterator += 1
        chosen.sort(key=lambda t: t.count("::"))
        topmost: list[str] = []
        for tag in chosen:
            if not any(tag.startswith(other + "::") for other in topmost):
                topmost.append(tag)
        return topmost

    def _on_tree_changed(self, *_args) -> None:
        self._mark_stale()

    def _on_mode_changed(self, *_args) -> None:
        try:
            self.mode_hint.setText(Mode(self.mode_combo.currentData()).explanation)
        except ValueError:
            self.mode_hint.setText("")
        self._mark_stale()

    def _mark_stale(self) -> None:
        self._preview = None
        self.apply_button.setEnabled(False)

    # --- Vorschau --------------------------------------------------------

    def _selection_search(self, col) -> str | None:
        tags = self.selected_tags()
        node = query.any_tag(col, tags)
        if node is None:
            return None
        return query.build(col, node)

    def refresh_preview(self) -> None:
        base = self.taxonomy.base
        mode = Mode(self.mode_combo.currentData())
        tags = self.selected_tags()
        if not tags:
            tooltip("Erst mindestens einen Tag anhaken.", parent=self)
            return

        def op(col):
            selection = self._selection_search(col)
            scope = query.scope_search(col, base)
            suspended = SearchNode(card_state=SearchNode.CARD_STATE_SUSPENDED)
            not_suspended = SearchNode(negated=suspended)
            if mode is Mode.UNSUSPEND:
                to_unsuspend = col.find_cards(
                    query.build(col, scope, selection, suspended)
                )
                return list(to_unsuspend), []
            if mode is Mode.SUSPEND:
                to_suspend = col.find_cards(
                    query.build(col, scope, selection, not_suspended)
                )
                return [], list(to_suspend)
            keep_negated = SearchNode(negated=SearchNode(parsable_text=selection))
            to_unsuspend = col.find_cards(
                query.build(col, scope, selection, suspended)
            )
            to_suspend = col.find_cards(
                query.build(col, scope, keep_negated, not_suspended)
            )
            return list(to_unsuspend), list(to_suspend)

        QueryOp(parent=self, op=op, success=self._on_preview).with_progress(
            "Wird gezählt…"
        ).failure(
            lambda exc: showWarning(f"Vorschau fehlgeschlagen:\n\n{exc}", parent=self)
        ).run_in_background()

    def _on_preview(self, payload) -> None:
        to_unsuspend, to_suspend = payload
        self._preview = (to_unsuspend, to_suspend)
        if not to_unsuspend and not to_suspend:
            self.summary_label.setText(
                "Es gibt nichts zu tun — der gewünschte Zustand besteht bereits."
            )
            self.apply_button.setEnabled(False)
            return
        self.summary_label.setText(
            f"<b>{len(to_unsuspend)}</b> Karten werden eingeschlossen "
            f"(reaktiviert), <b>{len(to_suspend)}</b> werden ausgeschlossen "
            "(suspendiert). Umkehrbar mit einem Rückgängig-Schritt."
        )
        self.apply_button.setEnabled(True)

    def _show_in_browser(self) -> None:
        import aqt

        tags = self.selected_tags()
        if not tags:
            tooltip("Erst mindestens einen Tag anhaken.", parent=self)
            return
        search = self._selection_search(self.col)
        aqt.dialogs.open("Browser", self.mw, search=(search,))

    # --- Anwenden --------------------------------------------------------

    def _apply(self) -> None:
        if self._preview is None:
            return
        to_unsuspend, to_suspend = self._preview
        if not askUser(
            f"{len(to_unsuspend)} Karten reaktivieren und {len(to_suspend)} "
            "suspendieren?\n\nDas ändert die Sammlung dauerhaft und "
            "synchronisiert auf alle Geräte. Strg+Z (⌘Z) nimmt es in einem "
            "Schritt zurück.",
            parent=self,
            title="Ein- und ausschließen",
            defaultno=True,
        ):
            return

        def op(col):
            undo_id = col.add_custom_undo_entry("AnkiPhil: Karten ein-/ausschließen")
            changes = col.merge_undo_entries(undo_id)
            if to_unsuspend:
                col.sched.unsuspend_cards(to_unsuspend)
                changes = col.merge_undo_entries(undo_id)
            if to_suspend:
                col.sched.suspend_cards(to_suspend)
                changes = col.merge_undo_entries(undo_id)
            return changes

        CollectionOp(parent=self, op=op).success(self._on_applied).run_in_background()

    def _on_applied(self, _changes) -> None:
        to_unsuspend, to_suspend = self._preview or ([], [])
        tooltip(
            f"{len(to_unsuspend)} reaktiviert, {len(to_suspend)} suspendiert.",
            parent=self,
        )
        self._mark_stale()
        self._load()

    def reject(self) -> None:
        saveGeom(self, self.GEOMETRY_KEY)
        super().reject()
