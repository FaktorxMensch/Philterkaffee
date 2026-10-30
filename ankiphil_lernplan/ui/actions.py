# -*- coding: utf-8 -*-
"""Schnellaktionen fürs Menü — ohne Umweg über ein Fenster.

Neu aufbauen und entleeren braucht man im Lernalltag ständig; dafür soll man
nicht erst das Verwaltungsfenster öffnen müssen.

Beim Neuaufbau ist die **Reihenfolge Teil des Ergebnisses**: eine Karte kann nur
in einem Auswahlstapel liegen, also bekommt sie der zuerst gebaute Stapel.
Sortiert wird deshalb nach Stapelnamen — mit dem voreingestellten Namensmuster
(``{nr2} – {titel}``) ist das genau die Lerntagsreihenfolge.
"""

from __future__ import annotations

from anki.decks import DeckId
from aqt.operations import CollectionOp
from aqt.qt import *
from aqt.utils import askUser, showInfo, tooltip

from ..core import builder, config


def plan_decks(col, parent: str = "") -> list[tuple[DeckId, str]]:
    """Auswahlstapel des Lernplans, in Namensreihenfolge.

    Mit Oberstapel nur die darunter; ohne Oberstapel alle Auswahlstapel des
    Profils. Welcher Fall gilt, steht in jeder Rückfrage.
    """
    folded = parent.casefold()
    found = []
    for deck in col.decks.all():
        if not deck.get("dyn"):
            continue
        name = deck["name"]
        if folded and not (
            name.casefold() == folded or name.casefold().startswith(folded + "::")
        ):
            continue
        found.append((DeckId(deck["id"]), name))
    found.sort(key=lambda item: item[1].casefold())
    return found


def _scope_text(parent: str, count: int) -> str:
    where = f"unter „{parent}“" if parent else "im ganzen Profil"
    return f"{count} Auswahlstapel {where}"


def _no_decks(parent: str, mw) -> None:
    where = f"unter „{parent}“" if parent else "in diesem Profil"
    showInfo(
        f"Es gibt {where} keine Auswahlstapel.\n\n"
        "Über „Auswahlstapel erstellen …“ lässt sich ein Lernplan aufbauen.",
        parent=mw,
    )


def rebuild_all(mw) -> None:
    settings = config.load(mw.col)
    parent = settings.effective_parent
    decks = plan_decks(mw.col, parent)
    if not decks:
        _no_decks(parent, mw)
        return
    if not askUser(
        f"{_scope_text(parent, len(decks))} neu aufbauen?\n\n"
        "Gebaut wird in Namensreihenfolge. Bei Überschneidungen bekommt der "
        "zuerst gebaute Stapel die Karte.",
        parent=mw,
        title="Alle neu aufbauen",
    ):
        return
    _run(mw, [deck_id for deck_id, _ in decks], builder.rebuild_many, "neu aufgebaut")


def rebuild_one(mw, deck_id: DeckId, name: str) -> None:
    _run(mw, [deck_id], builder.rebuild_many, f"neu aufgebaut: {name}")


def empty_all(mw) -> None:
    settings = config.load(mw.col)
    parent = settings.effective_parent
    decks = plan_decks(mw.col, parent)
    if not decks:
        _no_decks(parent, mw)
        return
    if not askUser(
        f"{_scope_text(parent, len(decks))} entleeren?\n\n"
        "Die Karten kehren mit ihrem Lernstand in die Heimatstapel zurück. "
        "Es geht nichts verloren.",
        parent=mw,
        title="Alle entleeren",
    ):
        return
    _run(mw, [deck_id for deck_id, _ in decks], builder.empty_many, "entleert")


def _run(mw, deck_ids: list[DeckId], operation, verb: str) -> None:
    def done(outcome: builder.MaintenanceOutcome) -> None:
        extra = f", {outcome.cards} Karten geholt" if outcome.cards else ""
        tooltip(f"{outcome.touched} Auswahlstapel {verb}{extra}.", parent=mw)

    CollectionOp(parent=mw, op=lambda col: operation(col, deck_ids)).success(
        done
    ).run_in_background()


def fill_rebuild_menu(mw, menu: QMenu) -> None:
    """Füllt das Untermenü „Einzelnen Stapel neu aufbauen“.

    Wird bei jedem Öffnen neu gefüllt, damit es nicht veraltet. Bei sehr vielen
    Stapeln wird auf das Verwaltungsfenster verwiesen, statt ein unbenutzbar
    langes Menü zu bauen.
    """
    menu.clear()
    if mw.col is None:
        return
    settings = config.load(mw.col)
    decks = plan_decks(mw.col, settings.effective_parent)
    if not decks:
        action = menu.addAction("(keine Auswahlstapel vorhanden)")
        action.setEnabled(False)
        return
    limit = 60
    for deck_id, name in decks[:limit]:
        label = name.split("::", 1)[1] if "::" in name else name
        action = menu.addAction(label.replace("&", "&&"))
        action.setToolTip(name)
        qconnect(
            action.triggered,
            lambda _checked=False, d=deck_id, n=label: rebuild_one(mw, d, n),
        )
    if len(decks) > limit:
        menu.addSeparator()
        rest = menu.addAction(
            f"… {len(decks) - limit} weitere — über „Verwalten …“"
        )
        rest.setEnabled(False)
