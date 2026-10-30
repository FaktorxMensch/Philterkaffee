# -*- coding: utf-8 -*-
"""Namensmuster für Auswahlstapel.

Platzhalter werden in Werte ersetzt, die Werte werden einzeln entschärft. Das
``::`` im Muster bleibt dagegen erhalten — nur so kann man gewollt verschachteln
(``{plan}::{nr2}``), ohne dass ein Tagname versehentlich eine Stapelebene
erzeugt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .taxonomy import Group

PLACEHOLDER_HELP: list[tuple[str, str]] = [
    ("{praefix}", "Freier Text aus dem Feld „Präfix“"),
    ("{plan}", "Name des Lernplans, z. B. 50-Tage"),
    ("{nr}", "Nummer des Lerntags ohne Auffüllen, z. B. 7"),
    ("{nr2}", "Nummer zweistellig, z. B. 07"),
    ("{nr3}", "Nummer dreistellig, z. B. 007"),
    ("{titel}", "Titel des Lerntags (abgeleitet oder selbst gesetzt)"),
    ("{label}", "Text im Tag selbst, z. B. „Anatomie Grundlagen“"),
    ("{tag}", "Vollständiger Tag des Lerntags"),
    ("{tagblatt}", "Letzte Komponente des Tags, z. B. 17"),
    ("{prio}", "Gewählte Lerntiefe, z. B. „Physikum + High-Yield“"),
    ("{datum}", "Zugeordnetes Datum (nur im Kalendermodus)"),
]

DEFAULT_PATTERN = "{praefix}{nr2} – {titel}"
MAX_COMPONENT_LENGTH = 80

_PLACEHOLDER_RE = re.compile(r"\{([a-zäöüß0-9_]+)\}")
# Anki trennt Stapelebenen mit "::" und verträgt keine Anführungszeichen;
# "{" und "\" sind Sortier- bzw. Escape-Artefakte der AnkiPhil-Tags.
_VALUE_NOISE_RE = re.compile(r"[{}\\\"]")


def sanitize_value(text: str) -> str:
    """Entschärft einen Platzhalterwert für die Verwendung in einem Stapelnamen."""
    cleaned = _VALUE_NOISE_RE.sub("", text).replace("::", " – ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > MAX_COMPONENT_LENGTH:
        cleaned = cleaned[: MAX_COMPONENT_LENGTH - 1].rstrip() + "…"
    return cleaned


def sanitize_deck_name(name: str) -> str:
    """Macht aus einem gerenderten Muster einen gültigen Stapelnamen.

    Leere Ebenen (``A::::B``) würde Anki stillschweigend anders auflösen, also
    werden sie hier entfernt.
    """
    parts = [part.strip(" .") for part in name.split("::")]
    parts = [part for part in parts if part]
    return "::".join(parts) or "Unbenannt"


@dataclass
class NameContext:
    plan: str
    group: Group | None
    title: str
    prefix: str = ""
    priority_label: str = ""
    date: str = ""

    def values(self) -> dict[str, str]:
        group = self.group
        return {
            "praefix": self.prefix,
            "plan": self.plan,
            "nr": group.number_text(1) if group else "",
            "nr2": group.number_text(2) if group else "",
            "nr3": group.number_text(3) if group else "",
            "titel": self.title,
            "label": group.label if group else "",
            "tag": group.tag if group else "",
            "tagblatt": group.key if group else "",
            "prio": self.priority_label,
            "datum": self.date,
        }


def unknown_placeholders(pattern: str) -> list[str]:
    known = {name.strip("{}") for name, _ in PLACEHOLDER_HELP}
    return sorted({m for m in _PLACEHOLDER_RE.findall(pattern) if m not in known})


def render(pattern: str, context: NameContext, parent: str = "") -> str:
    """Setzt das Muster ein und hängt es unter den Oberstapel."""
    values = context.values()

    def replace(match: re.Match[str]) -> str:
        return sanitize_value(values.get(match.group(1), match.group(0)))

    rendered = _PLACEHOLDER_RE.sub(replace, pattern)
    if parent.strip():
        rendered = f"{sanitize_deck_name(parent)}::{rendered}"
    return sanitize_deck_name(rendered)


def deduplicate(names: list[str]) -> list[str]:
    """Hängt an doppelte Namen eine Nummer an.

    Zwei Lerntage mit demselben abgeleiteten Titel sind bei AnkiPhil normal
    (z. B. drei Tage „Verdauungssystem“). Ohne Entdopplung würde Anki den
    zweiten Stapel als denselben behandeln.
    """
    used: dict[str, int] = {}
    result: list[str] = []
    for name in names:
        folded = name.casefold()
        if folded not in used:
            used[folded] = 1
            result.append(name)
            continue
        used[folded] += 1
        result.append(f"{name} ({used[folded]})")
    return result
