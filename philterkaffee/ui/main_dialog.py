# -*- coding: utf-8 -*-
"""Hauptfenster: Lernplan-Auswahlstapel erstellen.

Links die Einstellungen, rechts die Vorschau. Die Vorschau ist nicht Deko:
solange sie nicht zum aktuellen Stand gehört, ist „Erstellen“ gesperrt. Es
wird nie etwas geschrieben, was nicht vorher gezählt und geprüft wurde.

Lesen läuft in ``QueryOp``, Schreiben in ``CollectionOp`` — nie im UI-Thread,
sonst friert Anki bei 6.000 Karten sichtbar ein.
"""

from __future__ import annotations

import aqt
from anki.collection import SearchNode
from aqt import colors
from anki.decks import FilteredDeckConfig
from aqt.operations import CollectionOp, QueryOp
from aqt.qt import *
from aqt.theme import theme_manager
from aqt.utils import askUser, restoreGeom, saveGeom, showInfo, showWarning, tooltip

from .. import branding
from ..core import builder, config, naming, planner, query, taxonomy, titles
from ..core.config import BuildMode, CleanupScope, OverlapStrategy, Settings
from ..core.query import CardState, PriorityJoin
from . import widgets
from .titles_dialog import TitlesDialog

# Retrievability-Sortierungen brauchen FSRS-Gedächtniswerte; Anki blendet sie
# ohne FSRS selbst aus, ein Addon muss das nachbauen.
FSRS_ONLY_ORDERS = frozenset(
    (
        FilteredDeckConfig.SearchTerm.Order.RETRIEVABILITY_ASCENDING,
        FilteredDeckConfig.SearchTerm.Order.RETRIEVABILITY_DESCENDING,
    )
)


class LernplanDialog(QDialog):
    GEOMETRY_KEY = "philterkaffeeMain"
    DIALOG_KEY = "PhilterkaffeeDialog"
    silentlyClose = True

    def __init__(self, mw) -> None:
        super().__init__(mw)
        self.mw = mw
        self.col = mw.col
        mw.garbage_collect_on_dialog_finish(self)
        self.setWindowTitle("Philterkaffee — Auswahlstapel erstellen")
        self.setWindowIcon(branding.icon())

        self.settings: Settings = Settings()
        self.taxonomy: taxonomy.Taxonomy | None = None
        self.result: planner.PlanResult | None = None
        # Das Ergebnis bleibt beim Veralten erhalten — sonst leeren sich
        # Filteranzeige und Browser-Knöpfe, obwohl eine Zeile gewählt ist.
        self._stale = True
        self._pending_action = None
        self._derived_titles: dict[str, str] = {}
        self._note_tags: dict[int, list[str]] = {}
        self._tag_counts: dict[str, int] = {}
        self._effective_titles: dict[str, str] = {}
        self._order_values: list[int] = []
        self._loading = True

        self._build_ui()
        restoreGeom(self, self.GEOMETRY_KEY, default_size=(1180, 760))
        self._load_collection_data()

    # --- Aufbau ----------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(widgets.scroll_area(self._build_settings_panel()))
        splitter.addWidget(self._build_preview_panel())
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        outer.addWidget(splitter, 1)
        outer.addWidget(self._build_buttons())

    def _build_settings_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(self._group_plan())
        layout.addWidget(self._group_depth())
        layout.addWidget(self._group_cards())
        layout.addWidget(self._group_naming())
        layout.addWidget(self._group_order())
        layout.addWidget(self._group_behaviour())
        layout.addWidget(self._group_cleanup())
        layout.addStretch(1)
        return panel

    def _group_plan(self) -> QWidget:
        box, form = widgets.group("1 · Lernplan")

        self.base_combo = QComboBox()
        qconnect(self.base_combo.currentIndexChanged, self._on_base_changed)
        form.addRow("Basis-Tag:", self.base_combo)

        self.plan_combo = QComboBox()
        qconnect(self.plan_combo.currentIndexChanged, self._on_plan_changed)
        form.addRow("Plan:", self.plan_combo)

        self.group_list = widgets.checkable_list()
        self.group_list.setMinimumHeight(150)
        qconnect(self.group_list.itemChanged, self._on_setting_changed)
        form.addRow("Lerntage:", self.group_list)

        row = QHBoxLayout()
        for label, handler in (
            ("Alle", lambda: self._set_groups(True)),
            ("Keine", lambda: self._set_groups(False)),
            ("Bereich…", self._select_range),
        ):
            button = QPushButton(label)
            qconnect(button.clicked, handler)
            row.addWidget(button)
        row.addStretch(1)
        form.addRow("", row)

        self.mode_combo = QComboBox()
        for mode in BuildMode:
            self.mode_combo.addItem(mode.label, mode.value)
        qconnect(self.mode_combo.currentIndexChanged, self._on_mode_changed)
        form.addRow("Modus:", self.mode_combo)

        self.window_widget = QWidget()
        window_layout = QHBoxLayout(self.window_widget)
        window_layout.setContentsMargins(0, 0, 0, 0)
        self.window_start = QDateEdit()
        self.window_start.setCalendarPopup(True)
        self.window_start.setDate(QDate.currentDate())
        qconnect(self.window_start.dateChanged, self._on_setting_changed)
        self.window_days = QSpinBox()
        self.window_days.setRange(1, 60)
        self.window_days.setValue(3)
        qconnect(self.window_days.valueChanged, self._on_setting_changed)
        window_layout.addWidget(QLabel("ab"))
        window_layout.addWidget(self.window_start)
        window_layout.addWidget(QLabel("für"))
        window_layout.addWidget(self.window_days)
        window_layout.addWidget(QLabel("Lerntage"))
        window_layout.addStretch(1)
        form.addRow("", self.window_widget)
        form.addRow(
            "",
            widgets.hint(
                "Im Kalendermodus wird nur das aktuelle Fenster gebaut. Das ist der "
                "verlustfreie Weg bei Plänen mit vielen Überschneidungen (etwa "
                "M1-Fachfokus): Karten, die zu mehreren Lerntagen gehören, "
                "blockieren sich nicht gegenseitig, weil nur wenige Stapel "
                "gleichzeitig gefüllt sind."
            ),
        )
        return box

    def _group_depth(self) -> QWidget:
        box, layout = widgets.vgroup("2 · Lerntiefe")
        layout.addWidget(
            widgets.hint(
                "Ohne Haken kommen alle Karten des Lernplans in die Stapel. "
                "High-Yield liegt im AnkiPhil-Stapel fast vollständig innerhalb "
                "von Physikum; Top30 ist eine eigene Achse und für viele Lerntage "
                "leer."
            )
        )
        self.priority_container = QWidget()
        self.priority_layout = QVBoxLayout(self.priority_container)
        self.priority_layout.setContentsMargins(0, 0, 0, 0)
        self.priority_checks: list[QCheckBox] = []
        layout.addWidget(self.priority_container)

        join_row = QHBoxLayout()
        self.join_any = QRadioButton("mindestens ein Haken (ODER)")
        self.join_all = QRadioButton("alle Haken (UND)")
        self.join_any.setChecked(True)
        qconnect(self.join_any.toggled, self._on_setting_changed)
        join_row.addWidget(self.join_any)
        join_row.addWidget(self.join_all)
        join_row.addStretch(1)
        layout.addLayout(join_row)

        self.apply_all_check = QCheckBox(
            "Diese Auswahl auch auf alle Karten im AnkiPhil-Stapel anwenden"
        )
        qconnect(self.apply_all_check.toggled, self._on_setting_changed)
        layout.addWidget(self.apply_all_check)
        layout.addWidget(
            widgets.hint(
                "Ohne Haken wirkt die Lerntiefe nur in den Auswahlstapeln. Mit "
                "Haken wird alles andere im AnkiPhil-Stapel suspendiert und die "
                "gewählten Karten werden reaktiviert. Das ändert die Sammlung "
                "dauerhaft und synchronisiert auf alle Geräte — Stapel außerhalb "
                "von AnkiPhil bleiben unberührt."
            )
        )
        return box

    def _group_cards(self) -> QWidget:
        box, form = widgets.group("3 · Welche Karten")

        self.state_combo = QComboBox()
        for state in CardState:
            self.state_combo.addItem(state.label, state.value)
        self.state_combo.setToolTip(
            "Nur neue Karten ist die Voreinstellung: fällige Wiederholungen "
            "lernst du im normalen Heimatstapel, damit bleibt die Planung von "
            "SRS/FSRS unberührt.\n\n"
            "Fällige Karten mitzunehmen ist mit „Normal planen“ ebenfalls "
            "unbedenklich — nicht fällige Karten vorzuziehen verzerrt die "
            "Intervalle dagegen."
        )
        qconnect(self.state_combo.currentIndexChanged, self._on_setting_changed)
        form.addRow("Kartenzustand:", self.state_combo)

        self.scope_deck_combo = QComboBox()
        qconnect(self.scope_deck_combo.currentIndexChanged, self._on_setting_changed)
        form.addRow("Nur aus Stapel:", self.scope_deck_combo)

        self.extra_include = QLineEdit()
        self.extra_include.setPlaceholderText("z. B. -is:learn")
        qconnect(self.extra_include.textChanged, self._on_setting_changed)
        form.addRow("Zusätzliche Suche:", self.extra_include)

        self.extra_exclude = QLineEdit()
        self.extra_exclude.setPlaceholderText("z. B. tag:Zurückgestellt")
        qconnect(self.extra_exclude.textChanged, self._on_setting_changed)
        form.addRow("Ausschließen:", self.extra_exclude)
        form.addRow(
            "",
            widgets.hint(
                "Suspendierte und zurückgestellte Karten werden immer "
                "ausgeschlossen — Anki kann sie ohnehin nicht in Auswahlstapel "
                "holen."
            ),
        )
        return box

    def _group_naming(self) -> QWidget:
        box, form = widgets.group("4 · Benennung")

        self.use_parent_check = QCheckBox("Unter einem Oberstapel einsortieren")
        self.use_parent_check.setChecked(True)
        qconnect(self.use_parent_check.toggled, self._on_parent_toggled)
        form.addRow("", self.use_parent_check)

        self.parent_edit = QLineEdit("M1 Intensiv")
        qconnect(self.parent_edit.textChanged, self._on_setting_changed)
        form.addRow("Oberstapel:", self.parent_edit)

        self.prefix_edit = QLineEdit()
        self.prefix_edit.setPlaceholderText("Text vor dem Namen, z. B. „Tag “")
        qconnect(self.prefix_edit.textChanged, self._on_setting_changed)
        form.addRow("Präfix:", self.prefix_edit)

        pattern_row = QHBoxLayout()
        self.pattern_edit = QLineEdit(naming.DEFAULT_PATTERN)
        qconnect(self.pattern_edit.textChanged, self._on_setting_changed)
        placeholders = QPushButton("Platzhalter…")
        qconnect(placeholders.clicked, self._show_placeholders)
        pattern_row.addWidget(self.pattern_edit, 1)
        pattern_row.addWidget(placeholders)
        form.addRow("Namensmuster:", pattern_row)

        self.example_label = QLabel("—")
        self.example_label.setWordWrap(True)
        form.addRow("Beispiel:", self.example_label)

        title_row = QHBoxLayout()
        self.facet_combo = QComboBox()
        qconnect(self.facet_combo.currentIndexChanged, self._on_facet_changed)
        edit_titles = QPushButton("Titel bearbeiten…")
        qconnect(edit_titles.clicked, self._edit_titles)
        title_row.addWidget(self.facet_combo, 1)
        title_row.addWidget(edit_titles)
        form.addRow("Titel ableiten aus:", title_row)
        form.addRow(
            "",
            widgets.hint(
                "Die Lerntags-Tags tragen keinen Namen. Der Titel entsteht aus "
                "den häufigsten Fach-Tags der enthaltenen Karten und lässt sich "
                "überschreiben."
            ),
        )
        return box

    def _group_order(self) -> QWidget:
        box, form = widgets.group("5 · Sortierung und Limit")

        self.order_combo = QComboBox()
        qconnect(self.order_combo.currentIndexChanged, self._on_setting_changed)
        form.addRow("Sortierung:", self.order_combo)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 99999)
        self.limit_spin.setValue(9999)
        qconnect(self.limit_spin.valueChanged, self._on_setting_changed)
        form.addRow("Karten pro Stapel:", self.limit_spin)
        form.addRow(
            "",
            widgets.hint(
                "Die Sortierung entscheidet nicht nur über die Lernreihenfolge, "
                "sondern auch darüber, welche Karten bei erreichtem Limit "
                "wegfallen — abgeschnitten wird am Ende der Sortierung. "
                "Tageslimits der Stapel-Voreinstellungen gelten in "
                "Auswahlstapeln nicht; nur dieses Limit zählt."
            ),
        )
        return box

    def _group_behaviour(self) -> QWidget:
        box, layout = widgets.vgroup("6 · Verhalten")

        self.reschedule_check = QCheckBox("Normal planen (SRS/FSRS wie gewohnt)")
        self.reschedule_check.setChecked(True)
        qconnect(self.reschedule_check.toggled, self._on_setting_changed)
        layout.addWidget(self.reschedule_check)
        layout.addWidget(
            widgets.hint(
                "Empfohlen. Antworten wirken normal auf die Planung, Karten "
                "kehren nach dem Lernen in ihren Heimatstapel zurück. Ohne Haken "
                "läuft der Stapel im Vorschaumodus und ändert nichts an der "
                "Planung."
            )
        )

        self.allow_empty_check = QCheckBox("Leere Stapel anlegen")
        self.allow_empty_check.setChecked(True)
        qconnect(self.allow_empty_check.toggled, self._on_setting_changed)
        layout.addWidget(self.allow_empty_check)
        layout.addWidget(
            widgets.hint(
                "Nötig, weil manche Lerntage mit engem Filter keine Karte haben — "
                "im 50-Tage-Plan etwa alle Wiederholungstage ohne eigene Tags."
            )
        )

        form_row = QFormLayout()
        self.overlap_combo = QComboBox()
        for strategy in OverlapStrategy:
            self.overlap_combo.addItem(strategy.label, strategy.value)
        qconnect(self.overlap_combo.currentIndexChanged, self._on_overlap_changed)
        form_row.addRow("Überschneidungen:", self.overlap_combo)
        layout.addLayout(form_row)
        self.overlap_hint = widgets.hint("")
        layout.addWidget(self.overlap_hint)
        return box

    def _group_cleanup(self) -> QWidget:
        box, form = widgets.group("7 · Aufräumen vor dem Aufbau")

        self.cleanup_combo = QComboBox()
        for scope in CleanupScope:
            self.cleanup_combo.addItem(scope.label, scope.value)
        qconnect(self.cleanup_combo.currentIndexChanged, self._on_cleanup_changed)
        form.addRow("Entfernen:", self.cleanup_combo)

        self.cleanup_prefix_edit = QLineEdit()
        self.cleanup_prefix_edit.setPlaceholderText(
            "Namensanfänge, mit Komma getrennt"
        )
        qconnect(self.cleanup_prefix_edit.textChanged, self._on_setting_changed)
        form.addRow("Namensanfänge:", self.cleanup_prefix_edit)
        form.addRow(
            "",
            widgets.hint(
                "Gelöschte Auswahlstapel schicken ihre Karten in die "
                "Heimatstapel zurück — der Lernstand bleibt erhalten. "
                "Voreinstellung ist bewusst „nur unter dem Oberstapel“, damit "
                "fremde Auswahlstapel nicht mitgelöscht werden."
            ),
        )
        return box

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.summary_label = QLabel("Noch keine Vorschau berechnet.")
        self.summary_label.setWordWrap(True)
        layout.addWidget(widgets.heading("Vorschau"))
        layout.addWidget(self.summary_label)

        self.stale_label = QLabel("")
        self.stale_label.setWordWrap(True)
        layout.addWidget(self.stale_label)

        self.table = widgets.read_only_table(
            ["Auswahlstapel", "Karten", "trifft", "gesperrt", "mehrfach", "Tag"]
        )
        qconnect(self.table.itemSelectionChanged, self._on_row_selected)
        layout.addWidget(self.table, 3)

        row = QHBoxLayout()
        self.show_cards_button = QPushButton("Karten im Browser zeigen")
        qconnect(self.show_cards_button.clicked, self._show_selected_in_browser)
        self.show_blocked_button = QPushButton("Gesperrte Karten zeigen")
        self.show_blocked_button.setToolTip(
            "Öffnet den Browser mit den Karten, die zum Filter passen, aber nicht "
            "geholt werden können: suspendiert, zurückgestellt oder in einem "
            "anderen Auswahlstapel."
        )
        qconnect(self.show_blocked_button.clicked, self._show_blocked_in_browser)
        row.addWidget(self.show_cards_button)
        row.addWidget(self.show_blocked_button)
        row.addStretch(1)
        layout.addLayout(row)

        layout.addWidget(widgets.heading("Filter des gewählten Stapels"))
        self.query_view = QPlainTextEdit()
        self.query_view.setReadOnly(True)
        self.query_view.setMaximumHeight(90)
        layout.addWidget(self.query_view)

        layout.addWidget(widgets.heading("Hinweise"))
        self.messages_view = widgets.message_browser()
        layout.addWidget(self.messages_view, 1)
        return panel

    def _build_buttons(self) -> QWidget:
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)

        self.manage_button = QPushButton("Verwalten…")
        qconnect(self.manage_button.clicked, self._open_manage)
        self.gating_button = QPushButton("Karten ein-/ausschließen…")
        qconnect(self.gating_button.clicked, self._open_gating)
        layout.addWidget(self.manage_button)
        layout.addWidget(self.gating_button)
        layout.addStretch(1)

        self.preview_button = QPushButton("Vorschau berechnen")
        self.preview_button.setDefault(True)
        qconnect(self.preview_button.clicked, self.refresh_preview)
        self.build_button = QPushButton("Erstellen")
        self.build_button.setEnabled(False)
        qconnect(self.build_button.clicked, self._execute)
        close_button = QPushButton("Schließen")
        qconnect(close_button.clicked, self.reject)
        layout.addWidget(self.preview_button)
        layout.addWidget(self.build_button)
        layout.addWidget(close_button)
        return bar

    # --- Daten laden -----------------------------------------------------

    def _load_collection_data(self, override: Settings | None = None) -> None:
        """Liest Tags, Pläne und Stapel der Sammlung neu ein.

        ``override`` setzt die gespeicherten Einstellungen außer Kraft. Beim
        Wechsel des Basis-Tags ist das nötig: sonst würde hier wieder der in
        der Sammlung gespeicherte Basis-Tag gelesen und die eben getroffene
        Auswahl überschrieben.
        """

        def op(col):
            settings = override if override is not None else config.load(col)
            all_tags = col.tags.all()
            bases = taxonomy.discover_bases(all_tags)
            base = settings.base if settings.base in bases else (bases[0] if bases else "")
            tax = taxonomy.build(all_tags, base) if base else taxonomy.Taxonomy(base="")
            counts = {}
            for tag in tax.priority_tags:
                counts[tag] = len(col.find_notes(query.build(col, query.tag_node(tag))))
            note_tags: dict[int, list[str]] = {}
            if base:
                note_tags = titles.load_note_tags(
                    col, query.scope_search(col, base)
                )
            decks = [
                deck.name
                for deck in col.decks.all_names_and_ids(include_filtered=False)
            ]
            order_labels = list(col.sched.filtered_deck_order_labels())
            fsrs = bool(col.get_config("fsrs"))
            return settings, bases, tax, counts, note_tags, decks, order_labels, fsrs

        QueryOp(parent=self, op=op, success=self._on_data_loaded).with_progress(
            "AnkiPhil-Tags werden gelesen…"
        ).failure(self._on_load_failed).run_in_background()

    def _on_load_failed(self, exc: Exception) -> None:
        showWarning(f"Die Sammlung konnte nicht gelesen werden:\n\n{exc}", parent=self)
        self.close()

    def _on_data_loaded(self, payload) -> None:
        (
            settings,
            bases,
            tax,
            counts,
            note_tags,
            decks,
            order_labels,
            fsrs,
        ) = payload
        self.settings = settings
        self.taxonomy = tax
        self._tag_counts = counts
        self._note_tags = note_tags
        self._loading = True

        if not bases:
            showInfo(
                "In dieser Sammlung wurde kein AnkiPhil-Tagbaum gefunden.\n\n"
                "Erwartet wird ein Tag wie „#Ankiphil_Vorklinik_v6.0“ mit einem "
                "Unterast „$Lernpläne“. Ist der Stapel installiert und "
                "synchronisiert?",
                parent=self,
            )
            self._loading = False
            self.show()
            return

        self.base_combo.clear()
        self.base_combo.addItems(bases)
        if tax.base in bases:
            self.base_combo.setCurrentIndex(bases.index(tax.base))

        self._order_values = [
            value
            for value in range(len(order_labels))
            if fsrs or value not in FSRS_ONLY_ORDERS
        ]
        self.order_combo.clear()
        for value in self._order_values:
            self.order_combo.addItem(order_labels[value], value)

        self.scope_deck_combo.clear()
        self.scope_deck_combo.addItem("(alle Stapel)", "")
        for name in decks:
            self.scope_deck_combo.addItem(name, name)

        self.facet_combo.clear()
        self.facet_combo.addItem("(keine Ableitung)", "")
        for facet in tax.facet_roots:
            self.facet_combo.addItem(facet.split("::")[-1], facet)

        self._fill_priority_checks()
        self._fill_plans()
        self._settings_to_ui()
        self._loading = False
        self._refresh_titles()
        self._update_example()
        self._mark_stale("Noch keine Vorschau — auf „Vorschau berechnen“ klicken.")
        self.show()
        self.refresh_preview()

    def _fill_priority_checks(self) -> None:
        while self.priority_layout.count():
            item = self.priority_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.priority_checks = []
        assert self.taxonomy is not None
        for tag in self.taxonomy.priority_tags:
            count = self._tag_counts.get(tag, 0)
            short = tag.split("::")[-1]
            check = QCheckBox(f"{short}  ({count} Notizen)")
            check.setProperty("tag", tag)
            qconnect(check.toggled, self._on_setting_changed)
            self.priority_layout.addWidget(check)
            self.priority_checks.append(check)

    def _fill_plans(self) -> None:
        assert self.taxonomy is not None
        self.plan_combo.blockSignals(True)
        self.plan_combo.clear()
        for name in sorted(self.taxonomy.plans):
            plan = self.taxonomy.plans[name]
            self.plan_combo.addItem(f"{name}  ({len(plan.groups)} Lerntage)", name)
        self.plan_combo.blockSignals(False)

    def _fill_groups(self) -> None:
        assert self.taxonomy is not None
        plan = self.taxonomy.plan(self._current_plan())
        self.group_list.blockSignals(True)
        self.group_list.clear()
        if plan is not None:
            selected = set(self.settings.selected_groups)
            for group in plan.groups:
                title = self.settings.titles.get(group.key) or self._derived_titles.get(
                    group.key, group.label
                )
                suffix = f" — {title}" if title else ""
                item = QListWidgetItem(f"{group.key}{suffix}")
                item.setData(Qt.ItemDataRole.UserRole, group.key)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                checked = not selected or group.key in selected
                item.setCheckState(
                    Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
                self.group_list.addItem(item)
        self.group_list.blockSignals(False)

    def _refresh_titles(self) -> None:
        """Leitet die Titel für den aktuellen Plan neu ab."""
        assert self.taxonomy is not None
        plan = self.taxonomy.plan(self._current_plan())
        facet = self.facet_combo.currentData() or ""
        if plan is None or not facet or not self._note_tags:
            self._derived_titles = {
                group.key: group.label for group in (plan.groups if plan else [])
            }
        else:
            self._derived_titles = titles.derive_titles(
                self.col,
                groups=plan.groups,
                facet_root=facet,
                note_tags=self._note_tags,
            )
        self._fill_groups()

    # --- Einstellungen <-> Oberfläche ------------------------------------

    def _current_plan(self) -> str:
        return self.plan_combo.currentData() or ""

    def _settings_to_ui(self) -> None:
        settings = self.settings
        index = self.plan_combo.findData(settings.plan)
        if index >= 0:
            self.plan_combo.setCurrentIndex(index)

        for check in self.priority_checks:
            check.setChecked(check.property("tag") in settings.priority_tags)
        self.join_all.setChecked(settings.priority_join_enum is PriorityJoin.ALL)
        self.join_any.setChecked(settings.priority_join_enum is PriorityJoin.ANY)
        self.apply_all_check.setChecked(settings.apply_priority_to_all_cards)

        self._set_combo(self.state_combo, settings.card_state)
        self._set_combo(self.scope_deck_combo, settings.scope_deck)
        self.extra_include.setText(settings.extra_include)
        self.extra_exclude.setText(settings.extra_exclude)

        self.use_parent_check.setChecked(settings.use_parent)
        self.parent_edit.setText(settings.parent_deck)
        self.parent_edit.setEnabled(settings.use_parent)
        self.prefix_edit.setText(settings.prefix)
        self.pattern_edit.setText(settings.pattern)

        facet = settings.title_facet_root
        if not facet and self.taxonomy is not None:
            preferred = f"{self.taxonomy.base}::#Fächer"
            facet = preferred if preferred in self.taxonomy.facet_roots else ""
        self._set_combo(self.facet_combo, facet)

        order_index = self.order_combo.findData(settings.order)
        self.order_combo.setCurrentIndex(order_index if order_index >= 0 else 0)
        self.limit_spin.setValue(settings.limit)

        self.reschedule_check.setChecked(settings.reschedule)
        self.allow_empty_check.setChecked(settings.allow_empty)
        self._set_combo(self.overlap_combo, settings.overlap)
        self._set_combo(self.cleanup_combo, settings.cleanup)
        self.cleanup_prefix_edit.setText(", ".join(settings.cleanup_prefixes))

        self._set_combo(self.mode_combo, settings.build_mode)
        if settings.window_start:
            parsed = QDate.fromString(settings.window_start, Qt.DateFormat.ISODate)
            if parsed.isValid():
                self.window_start.setDate(parsed)
        self.window_days.setValue(max(1, settings.window_days))

        self._fill_groups()
        self._on_mode_changed()
        self._on_overlap_changed()
        self._on_cleanup_changed()

    @staticmethod
    def _set_combo(combo: QComboBox, value) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _ui_to_settings(self) -> Settings:
        settings = self.settings
        assert self.taxonomy is not None
        settings.base = self.taxonomy.base
        settings.plan = self._current_plan()

        plan = self.taxonomy.plan(settings.plan)
        total = len(plan.groups) if plan else 0
        checked = widgets.checked_data(self.group_list)
        settings.selected_groups = [] if len(checked) == total else checked

        settings.priority_tags = [
            check.property("tag") for check in self.priority_checks if check.isChecked()
        ]
        settings.priority_join = (
            PriorityJoin.ALL.value if self.join_all.isChecked() else PriorityJoin.ANY.value
        )
        settings.apply_priority_to_all_cards = self.apply_all_check.isChecked()

        settings.card_state = self.state_combo.currentData()
        settings.scope_deck = self.scope_deck_combo.currentData() or ""
        settings.extra_include = self.extra_include.text()
        settings.extra_exclude = self.extra_exclude.text()

        settings.use_parent = self.use_parent_check.isChecked()
        settings.parent_deck = self.parent_edit.text()
        settings.prefix = self.prefix_edit.text()
        settings.pattern = self.pattern_edit.text() or naming.DEFAULT_PATTERN
        settings.title_facet_root = self.facet_combo.currentData() or ""
        settings.auto_titles = bool(settings.title_facet_root)

        settings.order = self.order_combo.currentData() or 0
        settings.limit = self.limit_spin.value()

        settings.reschedule = self.reschedule_check.isChecked()
        settings.allow_empty = self.allow_empty_check.isChecked()
        settings.overlap = self.overlap_combo.currentData()
        settings.cleanup = self.cleanup_combo.currentData()
        settings.cleanup_prefixes = [
            part.strip()
            for part in self.cleanup_prefix_edit.text().split(",")
            if part.strip()
        ]

        settings.build_mode = self.mode_combo.currentData()
        settings.window_start = self.window_start.date().toString(Qt.DateFormat.ISODate)
        settings.window_days = self.window_days.value()

        # Abgeleitete Titel auffüllen, damit die Benennung vollständig ist.
        merged = dict(self._derived_titles)
        merged.update(settings.titles)
        self._effective_titles = merged
        return settings

    # --- Reaktionen ------------------------------------------------------

    def _on_setting_changed(self, *_args) -> None:
        if self._loading:
            return
        self._update_example()
        self._mark_stale("Einstellungen geändert — Vorschau neu berechnen.")

    def _on_base_changed(self, *_args) -> None:
        if self._loading:
            return
        chosen = self.base_combo.currentText()
        if not chosen or (self.taxonomy is not None and chosen == self.taxonomy.base):
            return
        settings = self.settings
        settings.base = chosen
        # Plan, Lerntage, Titel, Facetten-Ast und Prioritäts-Tags tragen den
        # alten Basis-Tag im Namen und wären unter dem neuen wertlos.
        settings.plan = ""
        settings.selected_groups = []
        settings.titles = {}
        settings.title_facet_root = ""
        settings.priority_tags = []
        self._loading = True
        self._load_collection_data(settings)

    def _on_plan_changed(self, *_args) -> None:
        if self._loading:
            return
        self.settings.selected_groups = []
        self.settings.titles = {}
        self._refresh_titles()
        self._on_setting_changed()

    def _on_facet_changed(self, *_args) -> None:
        if self._loading:
            return
        self._refresh_titles()
        self._on_setting_changed()

    def _on_parent_toggled(self, checked: bool) -> None:
        self.parent_edit.setEnabled(checked)
        self._on_setting_changed()

    def _on_mode_changed(self, *_args) -> None:
        window = self.mode_combo.currentData() == BuildMode.WINDOW.value
        self.window_widget.setVisible(window)
        self._on_setting_changed()

    def _on_overlap_changed(self, *_args) -> None:
        value = self.overlap_combo.currentData()
        try:
            self.overlap_hint.setText(OverlapStrategy(value).explanation)
        except ValueError:
            self.overlap_hint.setText("")
        self._on_setting_changed()

    def _on_cleanup_changed(self, *_args) -> None:
        scope = self.cleanup_combo.currentData()
        self.cleanup_prefix_edit.setVisible(scope == CleanupScope.NAME_PREFIX.value)
        if scope == CleanupScope.ALL.value and not self._loading:
            showWarning(
                "„ALLE Auswahlstapel“ entfernt jeden Auswahlstapel im Profil — "
                "auch solche, die nichts mit diesem Lernplan zu tun haben.\n\n"
                "Die Karten gehen dabei nicht verloren, sie kehren in ihre "
                "Heimatstapel zurück. Trotzdem ist „nur unter dem Oberstapel“ "
                "in fast allen Fällen die richtige Wahl.",
                parent=self,
            )
        self._on_setting_changed()

    def _set_groups(self, checked: bool) -> None:
        widgets.set_all_checked(self.group_list, checked)
        self._on_setting_changed()

    def _select_range(self) -> None:
        count = self.group_list.count()
        if not count:
            return
        first, ok = QInputDialog.getInt(self, "Bereich", "Von Lerntag:", 1, 1, count)
        if not ok:
            return
        last, ok = QInputDialog.getInt(self, "Bereich", "Bis Lerntag:", count, 1, count)
        if not ok:
            return
        low, high = sorted((first, last))
        for row in range(count):
            inside = low - 1 <= row <= high - 1
            self.group_list.item(row).setCheckState(
                Qt.CheckState.Checked if inside else Qt.CheckState.Unchecked
            )
        self._on_setting_changed()

    def _show_placeholders(self) -> None:
        lines = "\n".join(
            f"{name:<12} {text}" for name, text in naming.PLACEHOLDER_HELP
        )
        showInfo(
            "Platzhalter für das Namensmuster:\n\n"
            + lines
            + "\n\n„::“ im Muster erzeugt eine weitere Stapelebene. Innerhalb "
            "eines Platzhalterwerts wird „::“ dagegen entschärft, damit ein "
            "Tagname keine unbeabsichtigte Ebene anlegt.",
            parent=self,
            textFormat="plain",
        )

    def _edit_titles(self) -> None:
        assert self.taxonomy is not None
        plan = self.taxonomy.plan(self._current_plan())
        if plan is None:
            return
        dialog = TitlesDialog(
            self,
            groups=plan.groups,
            titles=self.settings.titles,
            derived=self._derived_titles,
        )
        if dialog.exec():
            self.settings.titles = dialog.titles
            self._fill_groups()
            self._on_setting_changed()

    def _update_example(self) -> None:
        if self._loading or self.taxonomy is None:
            return
        plan = self.taxonomy.plan(self._current_plan())
        if plan is None or not plan.groups:
            self.example_label.setText("—")
            return
        group = plan.groups[0]
        merged = dict(self._derived_titles)
        merged.update(self.settings.titles)
        context = naming.NameContext(
            plan=plan.name,
            group=group,
            title=merged.get(group.key) or group.label or group.key,
            prefix=self.prefix_edit.text(),
            priority_label=planner.priority_label(
                self.taxonomy, self._peek_settings()
            ),
            date=self.window_start.date().toString(Qt.DateFormat.ISODate)
            if self.mode_combo.currentData() == BuildMode.WINDOW.value
            else "",
        )
        parent = self.parent_edit.text() if self.use_parent_check.isChecked() else ""
        self.example_label.setText(
            naming.render(self.pattern_edit.text() or naming.DEFAULT_PATTERN, context, parent)
        )

    def _peek_settings(self) -> Settings:
        """Momentaufnahme nur für die Beispielanzeige."""
        snapshot = Settings.from_dict(self.settings.to_dict())
        snapshot.priority_tags = [
            check.property("tag") for check in self.priority_checks if check.isChecked()
        ]
        snapshot.priority_join = (
            PriorityJoin.ALL.value
            if self.join_all.isChecked()
            else PriorityJoin.ANY.value
        )
        return snapshot

    def _mark_stale(self, message: str) -> None:
        """Vorschau als veraltet kennzeichnen — ohne sie wegzuwerfen.

        Die Tabelle und der angezeigte Filter gehören dann zum vorigen Stand;
        wer sie benutzen will, wird vorher gefragt.
        """
        self._stale = True
        self.build_button.setEnabled(False)
        self.stale_label.setText(f"⚠ {message}")
        self._highlight_preview_button(True)

    def _highlight_preview_button(self, active: bool) -> None:
        """Färbt „Vorschau berechnen“ ein, solange sie gedrückt werden muss."""
        if active:
            background = theme_manager.var(colors.BUTTON_PRIMARY_BG)
            self.preview_button.setStyleSheet(
                "QPushButton {"
                f" background-color: {background};"
                " color: white; font-weight: bold;"
                " border: 1px solid rgba(0, 0, 0, 0.25);"
                " border-radius: 5px; padding: 4px 12px; }"
            )
            self.preview_button.setText("Vorschau berechnen ⟳")
        else:
            self.preview_button.setStyleSheet("")
            self.preview_button.setText("Vorschau berechnen")
        self.preview_button.setDefault(active)

    # --- Vorschau --------------------------------------------------------

    def refresh_preview(self) -> None:
        if self.taxonomy is None or not self.taxonomy.base:
            return
        settings = self._ui_to_settings()
        snapshot = Settings.from_dict(settings.to_dict())
        snapshot.titles = dict(self._effective_titles)
        tax = self.taxonomy

        def report(done: int, total: int, name: str) -> None:
            def update() -> None:
                self.mw.progress.update(
                    label=f"Lerntag {min(done + 1, total)} von {total}: {name}",
                    value=done,
                    max=total,
                )

            self.mw.taskman.run_on_main(update)

        def op(col):
            return planner.build_plan(col, tax, snapshot, progress=report)

        QueryOp(parent=self, op=op, success=self._on_preview_ready).with_progress(
            "Vorschau wird berechnet…"
        ).failure(self._on_preview_failed).run_in_background()

    def _on_preview_failed(self, exc: Exception) -> None:
        self._pending_action = None
        self._mark_stale("Die Vorschau ist fehlgeschlagen.")
        showWarning(f"Die Vorschau konnte nicht berechnet werden:\n\n{exc}", parent=self)

    def _on_preview_ready(self, result: planner.PlanResult) -> None:
        self.result = result
        self._stale = False
        self._highlight_preview_button(False)
        config.save(self.col, self.settings)

        previous_row = self.table.currentRow()
        self.table.setRowCount(len(result.proposals))
        for row, proposal in enumerate(result.proposals):
            self.table.setItem(row, 0, widgets.cell(proposal.deck_name))
            self.table.setItem(
                row, 1, widgets.cell(str(proposal.expected), numeric=True)
            )
            self.table.setItem(
                row, 2, widgets.cell(str(proposal.matching_total), numeric=True, dim=True)
            )
            self.table.setItem(
                row,
                3,
                widgets.cell(
                    str(proposal.blocked) if proposal.blocked else "—",
                    numeric=True,
                    dim=not proposal.blocked,
                ),
            )
            self.table.setItem(
                row,
                4,
                widgets.cell(
                    str(proposal.overlap_excluded) if proposal.overlap_excluded else "—",
                    numeric=True,
                    dim=not proposal.overlap_excluded,
                ),
            )
            self.table.setItem(
                row,
                5,
                widgets.cell(proposal.group.key if proposal.group else "—", dim=True),
            )

        parts = [
            f"<b>{len(result.proposals)}</b> Auswahlstapel",
            f"<b>{result.total_cards}</b> Karten",
            f"Lerntiefe: {result.priority_label}",
        ]
        if result.deletions:
            cards = sum(deletion.card_count for deletion in result.deletions)
            parts.append(
                f"<b>{len(result.deletions)}</b> alte Stapel werden entfernt "
                f"({cards} Karten gehen heim)"
            )
        if result.gating.active:
            parts.append(
                f"Suspendieren: <b>{len(result.gating.to_suspend)}</b>, "
                f"reaktivieren: <b>{len(result.gating.to_unsuspend)}</b>"
            )
        self.summary_label.setText(" · ".join(parts))

        self.messages_view.setHtml(self._messages_html(result))
        if result.ok:
            self.build_button.setEnabled(True)
            self.stale_label.setText("✓ Vorschau gehört zum aktuellen Stand.")
        else:
            self.build_button.setEnabled(False)
            self.stale_label.setText("✗ Es gibt Fehler — es wird nichts geschrieben.")

        # Gewählte Zeile möglichst erhalten, damit die Filteranzeige nach dem
        # Neuberechnen nicht springt.
        if result.proposals:
            row = previous_row if 0 <= previous_row < len(result.proposals) else 0
            self.table.selectRow(row)
        self._on_row_selected()

        action, self._pending_action = self._pending_action, None
        if action is not None and result.ok:
            action()

    @staticmethod
    def _messages_html(result: planner.PlanResult) -> str:
        blocks = []
        if result.errors:
            items = "".join(f"<li>{text}</li>" for text in result.errors)
            blocks.append(f"<b>Fehler</b><ul>{items}</ul>")
        if result.warnings:
            items = "".join(f"<li>{text}</li>" for text in result.warnings)
            blocks.append(f"<b>Hinweise</b><ul>{items}</ul>")
        if result.deletions:
            names = "".join(
                f"<li>{deletion.name} ({deletion.card_count} Karten)</li>"
                for deletion in result.deletions[:20]
            )
            more = (
                f"<li>… und {len(result.deletions) - 20} weitere</li>"
                if len(result.deletions) > 20
                else ""
            )
            blocks.append(f"<b>Werden entfernt</b><ul>{names}{more}</ul>")
        return "".join(blocks) or "Keine Auffälligkeiten."

    def _selected_proposal(self) -> planner.Proposal | None:
        if self.result is None:
            return None
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        index = rows[0].row()
        if 0 <= index < len(self.result.proposals):
            return self.result.proposals[index]
        return None

    def _on_row_selected(self) -> None:
        proposal = self._selected_proposal()
        self.query_view.setPlainText(proposal.search if proposal else "")

    def _require_fresh_preview(self, retry) -> bool:
        """Sorgt dafür, dass die Vorschau zum aktuellen Stand gehört.

        Gibt ``True`` zurück, wenn es sofort weitergehen kann. Sonst wird
        gefragt: bei Ja wird neu berechnet und ``retry`` danach aufgerufen, bei
        Nein geschieht gar nichts.
        """
        if not self._stale:
            return True
        if not askUser(
            "Seit der letzten Vorschau wurden Einstellungen geändert — die "
            "angezeigten Stapel und Filter gehören zum vorigen Stand.\n\n"
            "Vorschau jetzt neu berechnen und dann fortfahren?",
            parent=self,
            title="Vorschau veraltet",
        ):
            return False
        self._pending_action = retry
        self.refresh_preview()
        return False

    def _show_selected_in_browser(self) -> None:
        if not self._require_fresh_preview(self._show_selected_in_browser):
            return
        proposal = self._selected_proposal()
        if proposal is None:
            tooltip("Erst einen Stapel in der Vorschau wählen.", parent=self)
            return
        aqt.dialogs.open("Browser", self.mw, search=(proposal.search,))

    def _show_blocked_in_browser(self) -> None:
        """Zeigt genau die Karten, die passen, aber nicht geholt werden können.

        Dasselbe Prinzip wie der Hinweis-Knopf im Anki-Dialog für
        Auswahlstapel.
        """
        if not self._require_fresh_preview(self._show_blocked_in_browser):
            return
        proposal = self._selected_proposal()
        if proposal is None or proposal.group is None:
            tooltip("Erst einen Stapel mit Lerntag in der Vorschau wählen.", parent=self)
            return
        col = self.col
        blockers = col.group_searches(
            SearchNode(card_state=SearchNode.CARD_STATE_SUSPENDED),
            SearchNode(card_state=SearchNode.CARD_STATE_BURIED),
            query.other_filtered_decks_node(col, proposal.deck_name),
            joiner="OR",
        )
        content = query.group_search(
            col,
            group_tag=proposal.group.tag,
            priority=query.priority_node(
                col, list(self.settings.priority_tags), self.settings.priority_join_enum
            ),
            state=self.settings.card_state_enum,
            with_state_guards=False,
        )
        aqt.dialogs.open(
            "Browser", self.mw, search=(query.build(col, content, blockers),)
        )

    # --- Ausführen -------------------------------------------------------

    def _execute(self) -> None:
        result = self.result
        if result is None or not result.ok:
            return
        settings = self.settings

        lines = [
            f"{len(result.proposals)} Auswahlstapel anlegen "
            f"({result.total_cards} Karten).",
        ]
        if result.deletions:
            lines.append(
                f"{len(result.deletions)} bestehende Auswahlstapel entfernen — "
                "ihre Karten kehren in die Heimatstapel zurück."
            )
        if result.gating.active:
            lines.append(
                f"{len(result.gating.to_suspend)} Karten suspendieren und "
                f"{len(result.gating.to_unsuspend)} reaktivieren. Das ändert die "
                "Sammlung dauerhaft und synchronisiert auf alle Geräte."
            )
        lines.append("")
        lines.append(
            "Alles geschieht in einem Rückgängig-Schritt: Strg+Z (⌘Z) nimmt den "
            "gesamten Umbau zurück."
        )
        if not settings.backup_reminder_shown:
            lines.append("")
            lines.append(
                "Tipp fürs erste Mal: über „Datei → Sicherung erstellen“ eine "
                "Sicherung anlegen."
            )

        if not askUser("\n".join(lines), parent=self, title="Umbau ausführen?", defaultno=True):
            return
        settings.backup_reminder_shown = True

        snapshot = Settings.from_dict(settings.to_dict())
        snapshot.titles = dict(self._effective_titles)

        CollectionOp(
            parent=self, op=lambda col: builder.execute(col, snapshot, result)
        ).success(self._on_built).failure(self._on_build_failed).run_in_background()

    def _on_built(self, outcome: builder.BuildOutcome) -> None:
        config.save(self.col, self.settings)
        showInfo(
            "Fertig.\n\n"
            + "\n".join(f"• {line}" for line in outcome.report)
            + "\n\nJede angelegte Karte wurde gegen ihre echten Notiz-Tags "
            "geprüft. Fällige Wiederholungen lernst du weiterhin im "
            "Heimatstapel.",
            parent=self,
        )
        # Fenster schließen statt neu zu berechnen: die Arbeit ist getan, und
        # eine Vorschau, auf die man nur wartet, um danach zu schließen, ist
        # verlorene Zeit.
        self.reject()

    def _on_build_failed(self, exc: Exception) -> None:
        showWarning(
            f"Der Umbau wurde abgebrochen.\n\n{exc}",
            parent=self,
            title="Umbau fehlgeschlagen",
        )
        self.refresh_preview()

    # --- Weitere Fenster -------------------------------------------------

    def _open_manage(self) -> None:
        from .manage_dialog import ManageDialog

        dialog = ManageDialog(self, self.mw, self.settings)
        dialog.exec()
        self.refresh_preview()

    def _open_gating(self) -> None:
        from .gating_dialog import GatingDialog

        if self.taxonomy is None or not self.taxonomy.base:
            return
        dialog = GatingDialog(self, self.mw, self.taxonomy)
        dialog.exec()
        self.refresh_preview()

    # --- Fenster schließen -----------------------------------------------

    def reject(self) -> None:
        if self.taxonomy is not None and self.taxonomy.base:
            try:
                self._ui_to_settings()
                config.save(self.col, self.settings)
            except Exception:
                pass
        saveGeom(self, self.GEOMETRY_KEY)
        try:
            aqt.dialogs.markClosed(self.DIALOG_KEY)
        except KeyError:
            # Nicht registriert — das Schließen darf daran nicht scheitern.
            pass
        super().reject()

    def reopen(self, _mw) -> None:
        self.activateWindow()
        self.raise_()


def show(mw) -> LernplanDialog:
    return aqt.dialogs.open(LernplanDialog.DIALOG_KEY, mw)
