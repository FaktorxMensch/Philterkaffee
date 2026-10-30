# -*- coding: utf-8 -*-
"""Einstellungen des Addons.

Gespeichert wird über ``col.set_config()``: die Einstellungen hängen an Tags
und Stapeln eines Profils, gehören also in die Sammlung und nicht in die
``config.json`` des Addons — und sie synchronisieren damit mit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum

from .naming import DEFAULT_PATTERN
from .query import CardState, PriorityJoin

CONFIG_KEY = "ankiphilLernplan"
CONFIG_VERSION = 1


class OverlapStrategy(Enum):
    """Wie mit Karten umgegangen wird, die zu mehreren Lerntagen gehören.

    Eine Karte kann physisch nur in **einem** Auswahlstapel liegen. Es geht
    also nicht darum, ob verteilt wird, sondern ob die Verteilung
    nachvollziehbar ist.
    """

    EARLIEST_WINS = "earliest_wins"
    ANKI_ORDER = "anki_order"

    @property
    def label(self) -> str:
        return {
            OverlapStrategy.EARLIEST_WINS: (
                "Frühester Lerntag gewinnt (im Filter festgeschrieben)"
            ),
            OverlapStrategy.ANKI_ORDER: (
                "Anki entscheiden lassen (wer zuerst gebaut wird, bekommt sie)"
            ),
        }[self]

    @property
    def explanation(self) -> str:
        return {
            OverlapStrategy.EARLIEST_WINS: (
                "Spätere Lerntage schließen die Tags der früheren aus. Die "
                "Zuordnung steht damit im gespeicherten Filter und bleibt auch "
                "gleich, wenn du später einen einzelnen Stapel neu aufbaust."
            ),
            OverlapStrategy.ANKI_ORDER: (
                "Kürzere Filter. Die Zuordnung hängt aber an der Baureihenfolge: "
                "baust du später einen einzelnen Stapel neu auf, kann er Karten "
                "übernehmen, die vorher zu einem anderen Lerntag gehörten."
            ),
        }[self]


class CleanupScope(Enum):
    """Welche bestehenden Auswahlstapel vor dem Neuaufbau entfernt werden."""

    NONE = "none"
    UNDER_PARENT = "under_parent"
    NAME_PREFIX = "name_prefix"
    ALL = "all"

    @property
    def label(self) -> str:
        return {
            CleanupScope.NONE: "Nichts entfernen",
            CleanupScope.UNDER_PARENT: "Nur Auswahlstapel unter dem Oberstapel",
            CleanupScope.NAME_PREFIX: "Auswahlstapel mit bestimmten Namensanfängen",
            CleanupScope.ALL: "ALLE Auswahlstapel im Profil (auch fremde!)",
        }[self]


class BuildMode(Enum):
    """Alle Lerntage auf einmal oder ein rollierendes Fenster."""

    ALL = "all"
    WINDOW = "window"

    @property
    def label(self) -> str:
        return {
            BuildMode.ALL: "Alle gewählten Lerntage auf einmal",
            BuildMode.WINDOW: "Rollierendes Fenster ab Startdatum",
        }[self]


@dataclass
class Settings:
    """Vollständiger Zustand des Hauptfensters."""

    version: int = CONFIG_VERSION

    # Was
    base: str = ""
    plan: str = ""
    selected_groups: list[str] = field(default_factory=list)
    build_mode: str = BuildMode.ALL.value
    window_start: str = ""
    window_days: int = 3

    # Lerntiefe
    priority_tags: list[str] = field(default_factory=list)
    priority_join: str = PriorityJoin.ANY.value
    apply_priority_to_all_cards: bool = False

    # Umfang
    card_state: str = CardState.NEW.value
    scope_deck: str = ""
    extra_include: str = ""
    extra_exclude: str = ""

    # Benennung
    use_parent: bool = True
    parent_deck: str = "M1 Intensiv"
    prefix: str = ""
    pattern: str = DEFAULT_PATTERN
    titles: dict[str, str] = field(default_factory=dict)
    auto_titles: bool = True
    title_facet_root: str = ""

    # Sortierung
    order: int = 5  # FilteredDeckConfig.SearchTerm.Order.ADDED
    limit: int = 9999

    # Verhalten
    reschedule: bool = True
    allow_empty: bool = True
    overlap: str = OverlapStrategy.EARLIEST_WINS.value
    create_missing_groups: bool = False

    # Aufräumen
    cleanup: str = CleanupScope.UNDER_PARENT.value
    cleanup_prefixes: list[str] = field(default_factory=list)

    # Merker
    backup_reminder_shown: bool = False

    # --- getippte Zugriffe -------------------------------------------------

    @property
    def card_state_enum(self) -> CardState:
        return CardState(self.card_state)

    @property
    def priority_join_enum(self) -> PriorityJoin:
        return PriorityJoin(self.priority_join)

    @property
    def overlap_enum(self) -> OverlapStrategy:
        return OverlapStrategy(self.overlap)

    @property
    def cleanup_enum(self) -> CleanupScope:
        return CleanupScope(self.cleanup)

    @property
    def build_mode_enum(self) -> BuildMode:
        return BuildMode(self.build_mode)

    @property
    def effective_parent(self) -> str:
        return self.parent_deck.strip() if self.use_parent else ""

    # --- Persistenz --------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Settings":
        settings = cls()
        if not isinstance(data, dict):
            return settings
        known = {f for f in asdict(settings)}
        for key, value in data.items():
            if key in known and value is not None:
                setattr(settings, key, value)
        settings.version = CONFIG_VERSION
        return settings


def load(col) -> Settings:
    try:
        raw = col.get_config(CONFIG_KEY, default=None)
    except Exception:
        raw = None
    return Settings.from_dict(raw)


def save(col, settings: Settings) -> None:
    col.set_config(CONFIG_KEY, settings.to_dict())
