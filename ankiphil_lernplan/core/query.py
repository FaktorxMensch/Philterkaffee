# -*- coding: utf-8 -*-
"""Zusammenbau der Anki-Suchen.

Es wird **nie** ein Suchstring aus Teilstrings zusammengeklebt. Alles läuft über
``SearchNode`` und ``col.build_search_string()``, weil AnkiPhil-Tags Zeichen
enthalten, die in der Suchsyntax etwas bedeuten: ``#``, ``$``, ``§``, ``&``,
``(``, ``)``, ``{`` und literale Backslashes (``Obere\\_Extremität``).

``col.group_searches()`` liefert einen ``SearchNode``, **keinen** String. Wird
so ein Knoten versehentlich in einen Text eingesetzt, landet die
protobuf-Textdarstellung in der Suche. Dieser Fehler ist einmal passiert und
wird deshalb von ``_guard()`` aktiv abgefangen.
"""

from __future__ import annotations

from enum import Enum

from anki.collection import SearchNode

_PROTOBUF_FINGERPRINTS = ("group {", "nodes {", "joiner:", "parsable_text:")


class CardState(Enum):
    """Welche Karten ein Auswahlstapel aufnehmen soll."""

    NEW = "new"
    DUE = "due"
    NEW_AND_DUE = "new_and_due"
    ALL = "all"

    @property
    def label(self) -> str:
        return {
            CardState.NEW: "Nur neue Karten",
            CardState.DUE: "Nur fällige Wiederholungen",
            CardState.NEW_AND_DUE: "Neue Karten und fällige Wiederholungen",
            CardState.ALL: "Alle Karten (auch nicht fällige)",
        }[self]


class PriorityJoin(Enum):
    ANY = "OR"
    ALL = "AND"

    @property
    def label(self) -> str:
        return {
            PriorityJoin.ANY: "mindestens einer der Haken (ODER)",
            PriorityJoin.ALL: "alle gesetzten Haken (UND)",
        }[self]


def _guard(search: str) -> str:
    for fingerprint in _PROTOBUF_FINGERPRINTS:
        if fingerprint in search:
            raise RuntimeError(
                "Ungültige Suche von Anki erhalten (protobuf-Textdarstellung "
                f"statt Suchtext): {search}"
            )
    return search


def tag_node(tag: str) -> SearchNode:
    return SearchNode(tag=tag)


def any_tag(col, tags: list[str]) -> SearchNode | None:
    """``tag:a OR tag:b OR …`` als einzelner Knoten."""
    if not tags:
        return None
    if len(tags) == 1:
        return tag_node(tags[0])
    return col.group_searches(*(tag_node(t) for t in tags), joiner="OR")


def all_tags(col, tags: list[str]) -> SearchNode | None:
    if not tags:
        return None
    if len(tags) == 1:
        return tag_node(tags[0])
    return col.group_searches(*(tag_node(t) for t in tags), joiner="AND")


def priority_node(col, tags: list[str], join: PriorityJoin) -> SearchNode | None:
    """Der Lerntiefe-Filter. Ohne Haken: kein Filter, also alle Plan-Karten."""
    if join is PriorityJoin.ALL:
        return all_tags(col, tags)
    return any_tag(col, tags)


def card_state_node(col, state: CardState) -> SearchNode | None:
    if state is CardState.NEW:
        return SearchNode(card_state=SearchNode.CARD_STATE_NEW)
    if state is CardState.DUE:
        return SearchNode(card_state=SearchNode.CARD_STATE_DUE)
    if state is CardState.NEW_AND_DUE:
        return col.group_searches(
            SearchNode(card_state=SearchNode.CARD_STATE_NEW),
            SearchNode(card_state=SearchNode.CARD_STATE_DUE),
            joiner="OR",
        )
    return None


def not_node(node: SearchNode) -> SearchNode:
    return SearchNode(negated=node)


def build(col, *nodes, joiner: str = "AND") -> str:
    """``build_search_string`` mit Schutz gegen versehentliche protobuf-Strings."""
    usable = [node for node in nodes if node is not None]
    if not usable:
        return ""
    return _guard(col.build_search_string(*usable, joiner=joiner))


def group_search(
    col,
    *,
    group_tag: str,
    priority: SearchNode | None,
    state: CardState,
    excluded_group_tags: list[str] | None = None,
    scope_deck: str | None = None,
    extra_include: str = "",
    extra_exclude: str = "",
    with_state_guards: bool = True,
) -> str:
    """Die Suche, die als Filter im Auswahlstapel gespeichert wird.

    ``with_state_guards`` hängt ``-is:suspended -is:buried`` an. Anki schließt
    beides ohnehin aus, aber im gespeicherten Filter steht dann sichtbar, was
    gilt — und die Vorschau zählt mit derselben Suche richtig.

    ``-deck:filtered`` gehört **nicht** hierher: beim Neuaufbau liegen die
    eigenen Karten noch im Stapel. Für die Vorschau gibt es
    ``blocked_by_other_filtered_search()``.
    """
    nodes: list[SearchNode | str] = [tag_node(group_tag)]
    if priority is not None:
        nodes.append(priority)
    state_node = card_state_node(col, state)
    if state_node is not None:
        nodes.append(state_node)
    if scope_deck:
        nodes.append(SearchNode(deck=scope_deck))
    if excluded_group_tags:
        previous = any_tag(col, excluded_group_tags)
        if previous is not None:
            nodes.append(not_node(previous))
    if with_state_guards:
        nodes.append(not_node(SearchNode(card_state=SearchNode.CARD_STATE_SUSPENDED)))
        nodes.append(not_node(SearchNode(card_state=SearchNode.CARD_STATE_BURIED)))
    if extra_include.strip():
        nodes.append(extra_include.strip())
    if extra_exclude.strip():
        nodes.append(not_node(SearchNode(parsable_text=extra_exclude.strip())))
    return build(col, *nodes)


def and_search(col, base_search: str, *extra) -> str:
    """Verknüpft eine fertige Suche mit weiteren Bedingungen."""
    return build(col, base_search, *extra)


def other_filtered_decks_node(col, own_deck_name: str | None) -> SearchNode:
    """``deck:filtered`` ohne den eigenen Stapel — wie Anki es im Hinweis tut."""
    if own_deck_name:
        return col.group_searches(
            SearchNode(deck="filtered"),
            not_node(SearchNode(deck=own_deck_name)),
            joiner="AND",
        )
    return SearchNode(deck="filtered")


def scope_search(col, base_tag: str, scope_deck: str | None = None) -> str:
    """Alle Karten des AnkiPhil-Stapels — die Grenze für jede Suspendierung.

    ``tag:X`` erfasst in Anki ``X`` **und** ``X::*``, deshalb genügt der
    Basis-Tag.
    """
    nodes: list[SearchNode] = [tag_node(base_tag)]
    if scope_deck:
        nodes.append(SearchNode(deck=scope_deck))
    return build(col, *nodes)
