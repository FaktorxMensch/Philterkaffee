# -*- coding: utf-8 -*-
"""AnkiPhil Lernplan-Auswahlstapel.

Baut aus den Lernplan-Tags eines AnkiPhil-Stapels benannte, priorisierte
Auswahlstapel pro Lerntag — mit Vorschau, Nachkontrolle und einer einzigen
Rückgängig-Stufe.

Einstieg: Extras → „AnkiPhil Lernplan“, oder der Knopf „Lernplan“ unten im
Stapelbrowser.

Copyright (c) 2026 Faktor Mensch MEDIA UG (haftungsbeschränkt),
Emanuel Leube. Lizenz: AGPL-3.0-or-later.
"""

from __future__ import annotations

import aqt
from anki.utils import int_version_to_str, point_version
from aqt import gui_hooks, mw
from aqt.qt import *
from aqt.utils import showWarning

from .branding import MENU_TITLE, icon

MIN_POINT_VERSION = 231000
BOTTOM_BAR_COMMAND = "ankiphil_lernplan"
BOTTOM_BAR_LABEL = "Lernplan"


def _ready() -> bool:
    if point_version() < MIN_POINT_VERSION:
        showWarning(
            "Das Addon „AnkiPhil Lernplan-Auswahlstapel“ braucht mindestens "
            f"Anki {int_version_to_str(MIN_POINT_VERSION)}.\n\n"
            f"Installiert ist {int_version_to_str(point_version())}. Benötigt "
            "werden neuere Bausteine für Auswahlstapel (leere Stapel anlegen, "
            "Sortier-Beschriftungen aus Anki, zusammengefasstes Rückgängig)."
        )
        return False
    if mw is None or mw.col is None:
        showWarning("Es ist keine Sammlung geöffnet.")
        return False
    return True


# --- Fenster -------------------------------------------------------------


def _open_main() -> None:
    if not _ready():
        return
    from .ui.main_dialog import show

    show(mw)


def _open_manage() -> None:
    if not _ready():
        return
    from .core import config
    from .ui.manage_dialog import ManageDialog

    ManageDialog(mw, mw, config.load(mw.col)).exec()


def _open_gating() -> None:
    if not _ready():
        return
    from aqt.operations import QueryOp

    from .core import taxonomy
    from .ui.gating_dialog import GatingDialog

    def show(tax: taxonomy.Taxonomy) -> None:
        if not tax.base:
            showWarning(
                "In dieser Sammlung wurde kein AnkiPhil-Tagbaum gefunden. "
                "Erwartet wird ein Tag wie „#Ankiphil_Vorklinik_v6.0“."
            )
            return
        GatingDialog(mw, mw, tax).exec()

    # col.tags.all() kann bei großen Sammlungen dauern — nicht im UI-Thread.
    QueryOp(
        parent=mw, op=lambda col: taxonomy.from_collection(col), success=show
    ).with_progress("AnkiPhil-Tags werden gelesen…").run_in_background()


# --- Schnellaktionen -----------------------------------------------------


def _rebuild_all() -> None:
    if not _ready():
        return
    from .ui import actions

    actions.rebuild_all(mw)


def _empty_all() -> None:
    if not _ready():
        return
    from .ui import actions

    actions.empty_all(mw)


def _fill_rebuild_menu(menu: QMenu) -> None:
    from .ui import actions

    actions.fill_rebuild_menu(mw, menu)


# --- Einbau in Anki ------------------------------------------------------


def _build_menu() -> None:
    assert mw is not None
    menu = QMenu(MENU_TITLE, mw)
    menu.setIcon(icon())

    create = QAction("Auswahlstapel erstellen …", mw)
    create.setIcon(icon())
    qconnect(create.triggered, _open_main)
    menu.addAction(create)

    manage = QAction("Auswahlstapel verwalten …", mw)
    qconnect(manage.triggered, _open_manage)
    menu.addAction(manage)

    menu.addSeparator()

    rebuild_all = QAction("Alle neu aufbauen", mw)
    qconnect(rebuild_all.triggered, _rebuild_all)
    menu.addAction(rebuild_all)

    rebuild_one = QMenu("Einzelnen Stapel neu aufbauen", mw)
    # Erst beim Öffnen füllen, damit die Liste nie veraltet ist.
    qconnect(rebuild_one.aboutToShow, lambda m=rebuild_one: _fill_rebuild_menu(m))
    rebuild_one.addAction("…").setEnabled(False)
    menu.addMenu(rebuild_one)

    empty_all = QAction("Alle entleeren", mw)
    qconnect(empty_all.triggered, _empty_all)
    menu.addAction(empty_all)

    menu.addSeparator()

    gating = QAction("Karten ein-/ausschließen …", mw)
    qconnect(gating.triggered, _open_gating)
    menu.addAction(gating)

    mw.form.menuTools.addSeparator()
    mw.form.menuTools.addMenu(menu)


def _install_bottom_bar_button() -> None:
    """Knopf unten im Stapelbrowser, neben „Datei importieren“.

    ``drawLinks`` ist eine Klassenvariable, die ``_drawButtons`` tief kopiert —
    anhängen genügt. Der zugehörige Befehl wird im umschlossenen
    ``_linkHandler`` abgefangen, alles andere geht unverändert an Anki weiter.
    """
    # Erst hier importieren: aqt.deckbrowser zieht beim Import Ankis
    # Uebersetzungen, die zur Addon-Ladezeit noch nicht bereitstehen muessen.
    from aqt.deckbrowser import DeckBrowser

    if any(link[1] == BOTTOM_BAR_COMMAND for link in DeckBrowser.drawLinks):
        return

    original = DeckBrowser._linkHandler

    def link_handler(self, url: str):
        if url == BOTTOM_BAR_COMMAND:
            _open_main()
            return False
        return original(self, url)

    DeckBrowser._linkHandler = link_handler
    DeckBrowser.drawLinks = [
        *DeckBrowser.drawLinks,
        ["", BOTTOM_BAR_COMMAND, BOTTOM_BAR_LABEL],
    ]


def _register_dialog() -> None:
    from .ui.main_dialog import LernplanDialog

    aqt.dialogs.register_dialog(LernplanDialog.DIALOG_KEY, LernplanDialog)


def _on_main_window_did_init() -> None:
    # Registrierung braucht aqt.dialogs, das Menü braucht mw.form — beides
    # steht erst nach dem Start des Hauptfensters bereit.
    _register_dialog()
    _build_menu()
    _install_bottom_bar_button()


gui_hooks.main_window_did_init.append(_on_main_window_did_init)
