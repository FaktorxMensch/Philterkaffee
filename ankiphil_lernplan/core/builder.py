# -*- coding: utf-8 -*-
"""Der einzige Ort, an dem geschrieben wird.

Alles läuft in **einer** Rückgängig-Stufe: ``add_custom_undo_entry()`` einmal am
Anfang, ``merge_undo_entries()`` nach jedem Teilschritt. 43 Stapel anzulegen
darf nicht 43 Mal Strg+Z bedeuten.

Reihenfolge ist nicht beliebig:

1. aktuellen Stapel wechseln, falls er gleich gelöscht wird
2. alte Auswahlstapel entfernen (die Karten gehen heim)
3. erst *danach* suspendieren — Karten in einem Auswahlstapel zu suspendieren
   ist unnötig riskant
4. Oberstapel sicherstellen
5. Auswahlstapel in Planreihenfolge anlegen (bei „frühester Tag gewinnt“ ist
   die Reihenfolge Teil des Ergebnisses)
6. jeden angelegten Stapel gegen die echten Notiz-Tags prüfen
"""

from __future__ import annotations

from dataclasses import dataclass, field

from anki.collection import OpChanges, SearchNode
from anki.decks import DeckId

from . import query
from .config import Settings
from .planner import PlanResult

UNDO_NAME = "AnkiPhil Lernplan-Auswahlstapel"


@dataclass
class BuildOutcome:
    changes: OpChanges
    deleted: int = 0
    created: int = 0
    suspended: int = 0
    unsuspended: int = 0
    verified: int = 0
    empty: int = 0
    report: list[str] = field(default_factory=list)


def _safe_normal_deck(col, removing_names: set[str]) -> DeckId | None:
    """Ein normaler Stapel, der nicht unter einem zu löschenden Stapel liegt."""
    folded = {name.casefold() for name in removing_names}
    for deck in col.decks.all():
        if deck.get("dyn"):
            continue
        name = deck["name"].casefold()
        if any(name == f or name.startswith(f + "::") for f in folded):
            continue
        return DeckId(deck["id"])
    return None


def _apply_filtered_deck(col, proposal, settings: Settings) -> DeckId:
    """Legt einen Auswahlstapel an und gibt seine ID zurück."""
    deck = col.sched.get_or_create_filtered_deck(DeckId(0))
    deck.name = proposal.deck_name
    deck.allow_empty = settings.allow_empty

    config = deck.config
    config.reschedule = settings.reschedule
    # Lernschritte kommen beim Auswahlstapel immer aus dem Heimatdeck.
    del config.delays[:]
    if not settings.reschedule:
        # Ohne Neuplanung läuft der Stapel im Vorschaumodus; dann brauchen
        # Again/Hard/Good eigene Verzögerungen (Sekunden).
        config.preview_again_secs = 60
        config.preview_hard_secs = 600
        config.preview_good_secs = 0

    del config.search_terms[:]
    config.search_terms.add(
        search=proposal.search,
        limit=proposal.limit,
        order=proposal.order,
    )
    return DeckId(col.sched.add_or_update_filtered_deck(deck).id)


def _verify(col, proposal, settings: Settings) -> list[str]:
    """Prüft einen fertigen Stapel gegen die tatsächlichen Notiz-Tags.

    Mengenvergleich statt Schleife über jede Karte: drei Suchen pro Stapel
    statt zweier Datenbankzugriffe pro Karte.
    """
    problems: list[str] = []
    deck_node = SearchNode(deck=proposal.deck_name)
    in_deck = set(col.find_cards(query.build(col, deck_node)))

    if proposal.group is None:
        if in_deck:
            problems.append(
                f"{proposal.deck_name}: sollte leer sein, enthält aber "
                f"{len(in_deck)} Karten."
            )
        return problems

    unexpected = in_deck - set(proposal.card_ids)
    if unexpected:
        problems.append(
            f"{proposal.deck_name}: {len(unexpected)} Karten außerhalb der "
            f"geprüften Auswahl (z. B. {sorted(unexpected)[:5]})."
        )

    wrong_tag = col.find_cards(
        query.build(
            col,
            deck_node,
            SearchNode(negated=query.tag_node(proposal.group.tag)),
        )
    )
    if wrong_tag:
        problems.append(
            f"{proposal.deck_name}: {len(wrong_tag)} Karten ohne den Lerntag "
            f"{proposal.group.tag}."
        )

    priority = query.priority_node(
        col, list(settings.priority_tags), settings.priority_join_enum
    )
    if priority is not None:
        wrong_priority = col.find_cards(
            query.build(col, deck_node, SearchNode(negated=priority))
        )
        if wrong_priority:
            problems.append(
                f"{proposal.deck_name}: {len(wrong_priority)} Karten ohne den "
                "gewählten Lerntiefe-Tag."
            )
    return problems


def execute(col, settings: Settings, result: PlanResult) -> BuildOutcome:
    """Führt den geplanten Umbau aus. Gehört in eine ``CollectionOp``.

    Erkennt die Prüfung nach dem Schreiben einen Fehler, bricht sie mit einer
    Ausnahme ab. Weil alles in einer Rückgängig-Stufe liegt, macht ein einzelnes
    Strg+Z den gesamten Umbau zurück.
    """
    if not result.ok:
        raise RuntimeError(
            "Der Plan enthält Fehler und wird nicht ausgeführt:\n- "
            + "\n- ".join(result.errors)
        )

    undo_id = col.add_custom_undo_entry(UNDO_NAME)
    changes = col.merge_undo_entries(undo_id)
    outcome = BuildOutcome(changes=changes)

    removing_names = {deletion.name for deletion in result.deletions}
    removing_ids = {deletion.deck_id for deletion in result.deletions}

    if result.deletions and col.decks.get_current_id() in removing_ids:
        fallback = _safe_normal_deck(col, removing_names)
        if fallback is None:
            raise RuntimeError(
                "Es gibt keinen normalen Stapel, auf den gewechselt werden könnte. "
                "Bitte einen normalen Stapel anlegen und erneut versuchen."
            )
        col.decks.set_current(fallback)
        changes = col.merge_undo_entries(undo_id)

    for deletion in result.deletions:
        deck_id = col.decks.id_for_name(deletion.name)
        if deck_id is None:
            continue
        if not col.decks.is_filtered(deck_id):
            raise RuntimeError(
                f"„{deletion.name}“ ist kein Auswahlstapel mehr. Abbruch, damit "
                "kein normaler Stapel gelöscht wird."
            )
        col.decks.remove([deck_id])
        outcome.deleted += 1
        # Nach JEDER Operation mergen: Ankis Rückgängig-Warteschlange ist
        # begrenzt, und ein eigener Eintrag fällt sonst heraus, bevor wir ihn
        # zusammenfassen können ("target undo op not found").
        changes = col.merge_undo_entries(undo_id)

    gating = result.gating
    if gating.active:
        if gating.to_unsuspend:
            col.sched.unsuspend_cards(gating.to_unsuspend)
            outcome.unsuspended = len(gating.to_unsuspend)
            changes = col.merge_undo_entries(undo_id)
        if gating.to_suspend:
            col.sched.suspend_cards(gating.to_suspend)
            outcome.suspended = len(gating.to_suspend)
            changes = col.merge_undo_entries(undo_id)

    parent = settings.effective_parent
    if parent:
        existing = col.decks.id_for_name(parent)
        if existing is None:
            col.decks.id(parent)
            changes = col.merge_undo_entries(undo_id)
        elif col.decks.is_filtered(existing):
            raise RuntimeError(
                f"„{parent}“ ist ein Auswahlstapel und kann keine Unterstapel haben."
            )

    problems: list[str] = []
    for proposal in result.proposals:
        _apply_filtered_deck(col, proposal, settings)
        outcome.created += 1
        if proposal.count == 0:
            outcome.empty += 1
        changes = col.merge_undo_entries(undo_id)
        problems.extend(_verify(col, proposal, settings))
        outcome.verified += 1

    if problems:
        raise RuntimeError(
            "Der Umbau wurde ausgeführt, aber die Nachkontrolle hat Abweichungen "
            "gefunden. Mit Strg+Z (⌘Z) lässt sich der gesamte Umbau in einem "
            "Schritt zurücknehmen.\n\n- " + "\n- ".join(problems)
        )

    outcome.changes = changes
    outcome.report = [
        f"{outcome.deleted} alte Auswahlstapel entfernt",
        f"{outcome.created} Auswahlstapel angelegt ({outcome.empty} davon leer)",
        f"{result.total_cards} Karten einsortiert",
    ]
    if gating.active:
        outcome.report.append(
            f"{outcome.suspended} Karten suspendiert, "
            f"{outcome.unsuspended} reaktiviert"
        )
    return outcome


# --- Verwaltung vorhandener Stapel ---------------------------------------


@dataclass
class MaintenanceOutcome:
    changes: OpChanges
    touched: int = 0
    cards: int = 0


def rebuild_many(col, deck_ids: list[DeckId]) -> MaintenanceOutcome:
    """Baut mehrere Auswahlstapel in der übergebenen Reihenfolge neu auf.

    Die Reihenfolge ist Teil des Ergebnisses: bei Überschneidungen bekommt der
    zuerst gebaute Stapel die Karte.
    """
    undo_id = col.add_custom_undo_entry("Auswahlstapel neu aufbauen")
    changes = col.merge_undo_entries(undo_id)
    outcome = MaintenanceOutcome(changes=changes)
    for deck_id in deck_ids:
        if not col.decks.is_filtered(deck_id):
            continue
        result = col.sched.rebuild_filtered_deck(deck_id)
        outcome.cards += result.count
        outcome.touched += 1
        changes = col.merge_undo_entries(undo_id)
    outcome.changes = changes
    return outcome


def empty_many(col, deck_ids: list[DeckId]) -> MaintenanceOutcome:
    """Entleert Auswahlstapel — die Karten gehen in ihre Heimatstapel zurück."""
    undo_id = col.add_custom_undo_entry("Auswahlstapel entleeren")
    changes = col.merge_undo_entries(undo_id)
    outcome = MaintenanceOutcome(changes=changes)
    for deck_id in deck_ids:
        if not col.decks.is_filtered(deck_id):
            continue
        col.sched.empty_filtered_deck(deck_id)
        outcome.touched += 1
        changes = col.merge_undo_entries(undo_id)
    outcome.changes = changes
    return outcome


def remove_many(col, deck_ids: list[DeckId]) -> MaintenanceOutcome:
    """Löscht Auswahlstapel. Es gehen keine Karten verloren."""
    undo_id = col.add_custom_undo_entry("Auswahlstapel löschen")
    changes = col.merge_undo_entries(undo_id)
    outcome = MaintenanceOutcome(changes=changes)
    filtered = [deck_id for deck_id in deck_ids if col.decks.is_filtered(deck_id)]
    if filtered:
        current = col.decks.get_current_id()
        if current in filtered:
            names = {
                deck["name"]
                for deck in col.decks.all()
                if DeckId(deck["id"]) in filtered
            }
            fallback = _safe_normal_deck(col, names)
            if fallback is not None:
                col.decks.set_current(fallback)
        col.decks.remove(filtered)
        outcome.touched = len(filtered)
        changes = col.merge_undo_entries(undo_id)
    outcome.changes = changes
    return outcome

