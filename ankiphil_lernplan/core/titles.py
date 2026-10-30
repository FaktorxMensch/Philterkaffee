# -*- coding: utf-8 -*-
"""Leitet Titel für Lerntage aus den Fach-Tags der enthaltenen Karten ab.

Die Lerntags-Tags von AnkiPhil tragen keinen Namen — ``…::50-Tage::17`` ist
alles, was dasteht. Die Themen stehen aber in den ``#Fächer``- und
``#Organsysteme``-Tags derselben Notizen. Aus deren Häufigkeit entsteht ein
Titel, der Stapel-Updates übersteht (anders als eine hartcodierte Tabelle).

Beispiel aus dem Vorklinik-Stapel v6.0:
``…::50-Tage::17`` -> ``Herz/Kreislauf & Atmung``.
"""

from __future__ import annotations

from collections import Counter

from .taxonomy import Group, prettify

DEFAULT_FACET_DEPTH = 2
DEFAULT_MAX_PARTS = 2
DEFAULT_MIN_RATIO = 0.5
JOINER = " / "


def _facet_component(parts: list[str], root_depth: int, facet_depth: int) -> str | None:
    """Die Komponente ``facet_depth`` Ebenen unter der Facetten-Wurzel.

    Ist der Tag kürzer, wird seine letzte Komponente genommen — ein Tag wie
    ``…::#Fächer::Anatomie`` soll ``Anatomie`` liefern und nicht wegfallen.
    """
    index = root_depth + facet_depth - 1
    if len(parts) > index:
        return parts[index]
    if len(parts) > root_depth:
        return parts[-1]
    return None


def load_note_tags(col, scope_search: str) -> dict[int, list[str]]:
    """Tags aller Notizen im AnkiPhil-Stapel, in einem Datenbankzugriff.

    Lesender Zugriff auf ``col.db`` ist erlaubt; geschrieben wird nirgends über
    die Datenbank. ``get_note()`` pro Notiz wäre bei mehreren Tausend Notizen
    um Größenordnungen langsamer.
    """
    wanted = set(col.find_notes(scope_search))
    if not wanted:
        return {}
    result: dict[int, list[str]] = {}
    for note_id, tags in col.db.all("select id, tags from notes"):
        if note_id in wanted:
            result[note_id] = tags.split()
    return result


def derive_titles(
    col,
    *,
    groups: list[Group],
    facet_root: str,
    note_tags: dict[int, list[str]],
    facet_depth: int = DEFAULT_FACET_DEPTH,
    max_parts: int = DEFAULT_MAX_PARTS,
    min_ratio: float = DEFAULT_MIN_RATIO,
) -> dict[str, str]:
    """Liefert ``{group.key: Titel}``.

    Ein Kandidat fällt weg, wenn er seltener als ``min_ratio`` des häufigsten
    ist oder in einem bereits gewählten Titel enthalten ist — sonst entstünden
    Titel wie „Sinnesorgane & Sprechen / Sinnesorgane“.
    """
    root_depth = len(facet_root.split("::"))
    facet_prefix = facet_root + "::"

    by_group: dict[str, Counter[str]] = {group.key: Counter() for group in groups}
    group_by_tag = {group.tag: group.key for group in groups}

    for tags in note_tags.values():
        keys = [group_by_tag[t] for t in tags if t in group_by_tag]
        if not keys:
            continue
        components: set[str] = set()
        for tag in tags:
            if not tag.startswith(facet_prefix):
                continue
            component = _facet_component(tag.split("::"), root_depth, facet_depth)
            if component:
                components.add(component)
        for key in keys:
            by_group[key].update(components)

    titles: dict[str, str] = {}
    for group in groups:
        counter = by_group[group.key]
        if not counter:
            titles[group.key] = group.label or group.key
            continue
        ranked = counter.most_common()
        threshold = ranked[0][1] * min_ratio
        chosen: list[str] = []
        for component, count in ranked:
            if len(chosen) >= max_parts or count < threshold:
                break
            pretty = prettify(component)
            if not pretty:
                continue
            folded = pretty.casefold()
            if any(folded in existing.casefold() or existing.casefold() in folded
                   for existing in chosen):
                continue
            chosen.append(pretty)
        titles[group.key] = JOINER.join(chosen) or group.label or group.key
    return titles
