# -*- coding: utf-8 -*-
"""Entdeckt die Tag-Struktur eines AnkiPhil-Stapels in der geöffneten Sammlung.

Nichts hier ist auf eine Stapelversion festgelegt: der Basis-Tag
(z. B. ``#Ankiphil_Vorklinik_v6.0``), die Lernpläne und deren Lerntage werden
aus den tatsächlich vorhandenen Tags gelesen. Ein Stapel-Update auf v6.1
erfordert damit keine Code-Änderung.

AnkiPhil-Tags enthalten Zeichen, die in Anki-Suchen Sonderbedeutung haben
(``#``, ``$``, ``§``, ``{``, ``&`` und sogar literale Backslashes wie in
``Obere\\_Extremität``). Deshalb werden Tags hier ausschließlich als Rohstrings
weitergegeben und erst in ``query.py`` über ``SearchNode`` escaped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PLAN_CONTAINER = "$Lernpläne"
PRIORITY_PREFIXES = ("!", "§")
FACET_PREFIX = "#"

# Versteht "01", "01_Anatomie_Grundlagen", "Tag 01", "1 - Grundlagen".
_NUMBER_RE = re.compile(r"^(?:Tag[ _-]*)?(\d{1,3})(?=$|[\s_.\-])", re.IGNORECASE)
# Sortier- und Escape-Artefakte in AnkiPhil-Tagnamen.
_LABEL_NOISE_RE = re.compile(r"[{}\\]")


def prettify(component: str) -> str:
    """Macht aus einer Tag-Komponente einen lesbaren Text.

    ``{Muskeln`` -> ``Muskeln``, ``Obere\\_Extremität`` -> ``Obere Extremität``,
    ``01_Anatomie_Grundlagen`` behält seine Ziffern (die entfernt
    ``group_label`` separat).
    """
    text = _LABEL_NOISE_RE.sub("", component)
    text = text.replace("_", " ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_number(component: str) -> int | None:
    match = _NUMBER_RE.match(component)
    return int(match.group(1)) if match else None


def _strip_leading_number(component: str) -> str:
    match = _NUMBER_RE.match(component)
    return component[match.end() :].lstrip(" _.-") if match else component


@dataclass(frozen=True)
class Group:
    """Ein Lerntag bzw. eine Lerneinheit eines Plans."""

    tag: str
    """Vollständiger Tag, z. B. ``#Ankiphil…::$Lernpläne::50-Tage::17``."""
    key: str
    """Erste Komponente unterhalb der Plan-Wurzel, z. B. ``17``."""
    number: int | None
    """Führende Zahl, falls vorhanden — bestimmt die Reihenfolge."""
    label: str
    """Lesbarer Rest ohne führende Zahl; bei reinen Zifferntags leer."""

    @property
    def sort_key(self) -> tuple[int, int, str]:
        return (0, self.number, "") if self.number is not None else (1, 0, self.key)

    def number_text(self, width: int = 2) -> str:
        if self.number is None:
            return self.key
        return str(self.number).zfill(width)


@dataclass
class Plan:
    """Ein Lernplan, z. B. ``50-Tage``."""

    name: str
    root: str
    groups: list[Group] = field(default_factory=list)

    @property
    def numbered_groups(self) -> list[Group]:
        return [g for g in self.groups if g.number is not None]


@dataclass
class Taxonomy:
    base: str
    plans: dict[str, Plan] = field(default_factory=dict)
    priority_tags: list[str] = field(default_factory=list)
    facet_roots: list[str] = field(default_factory=list)
    unrecognized_group_tags: list[str] = field(default_factory=list)
    """Tags unter einer Plan-Wurzel, deren erste Komponente keine Zahl trägt."""

    @property
    def plan_root(self) -> str:
        return f"{self.base}::{PLAN_CONTAINER}"

    def plan(self, name: str) -> Plan | None:
        return self.plans.get(name)


def _split(tag: str) -> list[str]:
    return tag.split("::")


def discover_bases(all_tags: list[str]) -> list[str]:
    """Findet Tag-Stämme, die einen Lernplan-Container enthalten.

    Fällt auf Stämme zurück, deren Name mit ``#`` beginnt, damit das Addon auch
    vor dem ersten Lernplan-Import etwas anzeigen kann.
    """
    with_plans: set[str] = set()
    hash_roots: set[str] = set()
    for tag in all_tags:
        parts = _split(tag)
        if parts[0].startswith(FACET_PREFIX):
            hash_roots.add(parts[0])
        if PLAN_CONTAINER in parts[1:]:
            with_plans.add("::".join(parts[: parts.index(PLAN_CONTAINER)]))
    if with_plans:
        return sorted(with_plans)
    return sorted(hash_roots)


def build(all_tags: list[str], base: str) -> Taxonomy:
    """Baut die Taxonomie für einen Basis-Tag aus der vollständigen Tagliste."""
    taxonomy = Taxonomy(base=base)
    base_parts = _split(base)
    depth = len(base_parts)
    plan_container_index = depth
    seen_groups: dict[tuple[str, str], Group] = {}

    for tag in all_tags:
        parts = _split(tag)
        if parts[:depth] != base_parts or len(parts) <= depth:
            continue
        second = parts[depth]

        if second.startswith(PRIORITY_PREFIXES):
            marker = "::".join(parts[: depth + 1])
            if marker not in taxonomy.priority_tags:
                taxonomy.priority_tags.append(marker)
            continue

        if second.startswith(FACET_PREFIX):
            facet = "::".join(parts[: depth + 1])
            if facet not in taxonomy.facet_roots:
                taxonomy.facet_roots.append(facet)
            continue

        if second != PLAN_CONTAINER or len(parts) <= plan_container_index + 1:
            continue

        plan_name = parts[plan_container_index + 1]
        plan = taxonomy.plans.get(plan_name)
        if plan is None:
            plan = Plan(
                name=plan_name,
                root="::".join(parts[: plan_container_index + 2]),
            )
            taxonomy.plans[plan_name] = plan

        if len(parts) <= plan_container_index + 2:
            continue

        key = parts[plan_container_index + 2]
        group_tag = "::".join(parts[: plan_container_index + 3])
        number = _parse_number(key)
        if number is None:
            if group_tag not in taxonomy.unrecognized_group_tags:
                taxonomy.unrecognized_group_tags.append(group_tag)
        identity = (plan_name, key)
        if identity not in seen_groups:
            group = Group(
                tag=group_tag,
                key=key,
                number=number,
                label=prettify(_strip_leading_number(key)),
            )
            seen_groups[identity] = group
            plan.groups.append(group)

    for plan in taxonomy.plans.values():
        plan.groups.sort(key=lambda g: g.sort_key)
    taxonomy.priority_tags.sort()
    taxonomy.facet_roots.sort()
    taxonomy.unrecognized_group_tags.sort()
    return taxonomy


def from_collection(col, base: str | None = None) -> Taxonomy:
    """Liest die Taxonomie direkt aus einer geöffneten Sammlung.

    Muss in einem Hintergrund-Thread laufen (``QueryOp``): ``col.tags.all()``
    kann bei großen Sammlungen spürbar dauern.
    """
    all_tags = col.tags.all()
    if base is None:
        bases = discover_bases(all_tags)
        if not bases:
            return Taxonomy(base="")
        base = bases[0]
    return build(all_tags, base)
