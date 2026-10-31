# -*- coding: utf-8 -*-
"""Berechnet den geplanten Umbau — ohne eine Zeile zu schreiben.

Grundregel aus dem Vorgänger-Skript, die hier bleibt: **erst alles prüfen, dann
schreiben.**

Die Vorschau muss zählen, was Anki *nach* dem Umbau tatsächlich holt — nicht,
was im aktuellen Zustand holbar wäre. Das sind drei verschiedene Dinge:

* Anki holt keine suspendierten und keine zurückgestellten Karten.
* Anki holt keine Karte, die in einem **anderen** Auswahlstapel liegt — aber
  Stapel, die dieser Lauf löscht, geben ihre Karten vorher frei. Wer das
  übersieht, zählt beim Neuaufbau eines bestehenden Lernplans fast alles als
  „blockiert“ und baut dann trotzdem volle Stapel.
* Wird „auch auf alle Karten anwenden“ genutzt, verschiebt die Suspendierung
  die Grenze noch einmal: reaktivierte Karten kommen hinzu.

Die Reihenfolge hier ist deshalb: Namen → Löschungen → Suspendierung →
Kartenzahlen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from anki.collection import SearchNode

from . import naming, query
from .config import BuildMode, CleanupScope, OverlapStrategy, Settings
from .query import PriorityJoin
from .taxonomy import Group, Taxonomy


@dataclass
class Proposal:
    """Ein geplanter Auswahlstapel."""

    group: Group | None
    deck_name: str
    search: str
    order: int
    limit: int
    card_ids: frozenset[int] = frozenset()
    matching_total: int = 0
    """Karten, die der Filter inhaltlich trifft — vor allen Sperren."""
    suspended: int = 0
    buried: int = 0
    in_other_filtered: int = 0
    overlap_excluded: int = 0
    revived: int = 0
    """Karten, die erst durch die geplante Reaktivierung dazukommen."""
    date: str = ""

    @property
    def count(self) -> int:
        return len(self.card_ids)

    @property
    def blocked(self) -> int:
        return self.suspended + self.buried + self.in_other_filtered

    @property
    def truncated(self) -> bool:
        return self.count > self.limit

    @property
    def expected(self) -> int:
        return min(self.count, self.limit)


@dataclass
class Deletion:
    deck_id: int
    name: str
    card_ids: frozenset[int] = frozenset()

    @property
    def card_count(self) -> int:
        return len(self.card_ids)


@dataclass
class GatingPreview:
    """Vorschau für „auch auf alle Karten anwenden“ (Suspendieren)."""

    keep_search: str = ""
    scope_search: str = ""
    to_suspend: list[int] = field(default_factory=list)
    to_unsuspend: list[int] = field(default_factory=list)
    scope_total: int = 0

    @property
    def active(self) -> bool:
        return bool(self.keep_search)

    @property
    def changes(self) -> int:
        return len(self.to_suspend) + len(self.to_unsuspend)


@dataclass
class PlanResult:
    proposals: list[Proposal] = field(default_factory=list)
    deletions: list[Deletion] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    gating: GatingPreview = field(default_factory=GatingPreview)
    priority_label: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def total_cards(self) -> int:
        return sum(p.expected for p in self.proposals)

    @property
    def unique_cards(self) -> int:
        seen: set[int] = set()
        for proposal in self.proposals:
            seen |= proposal.card_ids
        return len(seen)


# --- Hilfsfunktionen -----------------------------------------------------


def priority_label(taxonomy: Taxonomy, settings: Settings) -> str:
    """Kurzer Text für den Platzhalter ``{prio}`` und die Oberfläche."""
    if not settings.priority_tags:
        return "alle Plan-Karten"
    base_prefix = taxonomy.base + "::"
    names = [
        tag[len(base_prefix) :].lstrip("!§#$") if tag.startswith(base_prefix) else tag
        for tag in settings.priority_tags
    ]
    separator = " + " if settings.priority_join_enum is PriorityJoin.ALL else " / "
    return separator.join(names)


def selected_groups(taxonomy: Taxonomy, settings: Settings) -> list[Group]:
    plan = taxonomy.plan(settings.plan)
    if plan is None:
        return []
    if not settings.selected_groups:
        return list(plan.groups)
    wanted = set(settings.selected_groups)
    return [group for group in plan.groups if group.key in wanted]


def _window_groups(groups: list[Group], settings: Settings) -> tuple[list[Group], str]:
    """Im Kalendermodus nur die Lerntage des aktuellen Fensters."""
    if settings.build_mode_enum is not BuildMode.WINDOW:
        return groups, ""
    import datetime

    try:
        start = datetime.date.fromisoformat(settings.window_start)
    except (ValueError, TypeError):
        return groups, (
            "Kalendermodus ohne gültiges Startdatum — es werden alle gewählten "
            "Lerntage gebaut."
        )
    offset = (datetime.date.today() - start).days
    span = max(1, settings.window_days)
    if offset < 0:
        chosen = groups[:span]
        note = (
            f"Startdatum liegt {abs(offset)} Tage in der Zukunft — es werden die "
            f"ersten {len(chosen)} Lerntage gebaut."
        )
    else:
        chosen = groups[offset : offset + span]
        note = (
            f"Kalendermodus: Lerntag {offset + 1} bis {offset + len(chosen)} "
            f"(Start {start.isoformat()})."
        )
    if not chosen:
        chosen = groups[-span:]
        note = (
            "Das Zeitfenster liegt hinter dem letzten Lerntag — es werden die "
            "letzten Lerntage gebaut."
        )
    return chosen, note


def _assign_dates(groups: list[Group], settings: Settings) -> dict[str, str]:
    if settings.build_mode_enum is not BuildMode.WINDOW or not settings.window_start:
        return {}
    import datetime

    try:
        start = datetime.date.fromisoformat(settings.window_start)
    except (ValueError, TypeError):
        return {}
    return {
        group.key: (start + datetime.timedelta(days=index)).isoformat()
        for index, group in enumerate(groups)
    }


def _is_under(name: str, parent: str) -> bool:
    folded, parent_folded = name.casefold(), parent.casefold()
    return folded == parent_folded or folded.startswith(parent_folded + "::")


def _deck_cards(col, name: str) -> frozenset[int]:
    return frozenset(col.find_cards(query.build(col, SearchNode(deck=name))))


def plan_deletions(
    col, settings: Settings, planned_names: set[str]
) -> tuple[list[Deletion], list[str]]:
    """Welche Auswahlstapel entfernt werden — und warum das sicher ist.

    Ein Auswahlstapel, unter dem ein *normaler* Stapel hängt, wird nie
    gelöscht: Anki würde den normalen Unterstapel mitnehmen, und darin stecken
    echte Karten. (Anki lässt diesen Zustand heute nicht mehr entstehen, aber
    importierte oder umbenannte Altbestände können ihn mitbringen.)

    Die Namensprüfung am Ende läuft **immer**, auch wenn nichts aufgeräumt
    wird — ein belegter Zielname ist unabhängig vom Aufräumen ein Abbruchgrund.
    """
    scope = settings.cleanup_enum
    errors: list[str] = []
    all_decks = col.decks.all()
    filtered = [deck for deck in all_decks if deck.get("dyn")]

    chosen: list[dict] = []
    if scope is CleanupScope.ALL:
        chosen = filtered
    elif scope is CleanupScope.UNDER_PARENT:
        parent = settings.effective_parent
        if not parent:
            errors.append(
                "Aufräumen „unter dem Oberstapel“ braucht einen Oberstapel. "
                "Entweder Oberstapel aktivieren oder Aufräumen umstellen."
            )
        else:
            chosen = [deck for deck in filtered if _is_under(deck["name"], parent)]
    elif scope is CleanupScope.NAME_PREFIX:
        prefixes = [p.strip() for p in settings.cleanup_prefixes if p.strip()]
        if not prefixes:
            errors.append(
                "Aufräumen nach Namensanfang, aber kein Namensanfang angegeben."
            )
        else:
            chosen = [
                deck
                for deck in filtered
                if any(_is_under(deck["name"], prefix) for prefix in prefixes)
            ]

    safe: list[dict] = []
    for deck in chosen:
        prefix = deck["name"].casefold() + "::"
        blockers = [
            other["name"]
            for other in all_decks
            if not other.get("dyn") and other["name"].casefold().startswith(prefix)
        ]
        if blockers:
            errors.append(
                f"Unter dem Auswahlstapel „{deck['name']}“ liegen normale Stapel "
                f"({', '.join(blockers)}). Bitte erst verschieben."
            )
        else:
            safe.append(deck)

    deletions = [
        Deletion(
            deck_id=deck["id"],
            name=deck["name"],
            card_ids=_deck_cards(col, deck["name"]),
        )
        for deck in safe
    ]
    # Tiefste Stapel zuerst, damit kein Elternteil ein Kind mitnimmt.
    deletions.sort(key=lambda d: (-d.name.count("::"), d.name.casefold()))

    removing = {deletion.deck_id for deletion in deletions}
    desired = {name.casefold() for name in planned_names}
    for deck in all_decks:
        if deck["name"].casefold() in desired and deck["id"] not in removing:
            kind = "Auswahlstapel" if deck.get("dyn") else "normaler Stapel"
            errors.append(
                f"Der geplante Name „{deck['name']}“ ist schon belegt "
                f"({kind}, wird nicht entfernt)."
            )
    parent = settings.effective_parent
    if parent:
        for deck in all_decks:
            if (
                deck["name"].casefold() == parent.casefold()
                and deck.get("dyn")
                and deck["id"] not in removing
            ):
                errors.append(
                    f"Der Oberstapel „{parent}“ ist selbst ein Auswahlstapel. "
                    "Auswahlstapel können keine Unterstapel haben."
                )
    return deletions, errors


def gating_preview(
    col, taxonomy: Taxonomy, settings: Settings, groups: list[Group], priority
) -> GatingPreview:
    """Welche Karten im AnkiPhil-Stapel suspendiert bzw. reaktiviert würden.

    „Behalten“ heißt: in einem der gewählten Lerntage **und** passend zur
    Lerntiefe. Der Kartenzustand spielt hier bewusst keine Rolle — eine
    Wiederholungskarte soll nicht suspendiert werden, nur weil der
    Auswahlstapel gerade nur neue Karten sammelt.

    Der Umfang ist immer der AnkiPhil-Tagbaum. Alles außerhalb wird nie
    angefasst.
    """
    group_node = query.any_tag(col, [group.tag for group in groups])
    if group_node is None:
        return GatingPreview()

    keep_search = query.build(col, group_node, priority)
    scope = query.scope_search(col, taxonomy.base, settings.scope_deck or None)
    keep_negated = SearchNode(negated=SearchNode(parsable_text=keep_search))
    suspended = SearchNode(card_state=SearchNode.CARD_STATE_SUSPENDED)

    to_suspend = col.find_cards(
        query.build(col, scope, keep_negated, SearchNode(negated=suspended))
    )
    to_unsuspend = col.find_cards(query.build(col, scope, keep_search, suspended))
    return GatingPreview(
        keep_search=keep_search,
        scope_search=scope,
        to_suspend=list(to_suspend),
        to_unsuspend=list(to_unsuspend),
        scope_total=len(col.find_cards(scope)),
    )


# --- Hauptberechnung -----------------------------------------------------


def build_plan(col, taxonomy: Taxonomy, settings: Settings, progress=None) -> PlanResult:
    """Erzeugt die vollständige Vorschau. Gehört in einen ``QueryOp``.

    ``progress`` wird, wenn gesetzt, mit ``(erledigt, gesamt, text)`` gerufen.
    """
    result = PlanResult()
    result.priority_label = priority_label(taxonomy, settings)

    plan = taxonomy.plan(settings.plan)
    if plan is None:
        result.errors.append(
            f"Lernplan „{settings.plan}“ ist in dieser Sammlung nicht vorhanden."
        )
        return result

    groups = selected_groups(taxonomy, settings)
    if not groups:
        result.errors.append("Es ist kein Lerntag ausgewählt.")
        return result

    all_plan_groups = list(plan.groups)
    dates = _assign_dates(all_plan_groups, settings)
    groups, window_note = _window_groups(groups, settings)
    if window_note:
        result.warnings.append(window_note)
    if not groups:
        result.errors.append("Das gewählte Zeitfenster enthält keinen Lerntag.")
        return result

    priority = query.priority_node(
        col, list(settings.priority_tags), settings.priority_join_enum
    )
    state = settings.card_state_enum
    overlap = settings.overlap_enum

    # 1. Namen — plan_deletions muss wissen, welche Namen belegt werden.
    names, name_collisions = _render_names(
        settings, plan.name, groups, result.priority_label, dates
    )

    # 2. Löschungen. Ihre Karten sind beim Bauen frei, zählen also nicht als
    #    blockiert.
    deletions, delete_errors = plan_deletions(col, settings, set(names))
    result.deletions = deletions
    result.errors.extend(delete_errors)
    freed_ids: set[int] = set()
    for deletion in deletions:
        freed_ids |= deletion.card_ids

    # 3. Suspendierung — reaktivierte Karten werden holbar.
    if settings.apply_priority_to_all_cards:
        result.gating = gating_preview(col, taxonomy, settings, groups, priority)
    revived_ids = set(result.gating.to_unsuspend)

    # 4. Kartenzahlen.
    plan_order = {group.key: index for index, group in enumerate(all_plan_groups)}
    claimed: set[int] = set()
    total = len(groups)

    for index, (group, deck_name) in enumerate(zip(groups, names)):
        if progress is not None:
            progress(index, total, deck_name)

        excluded: list[str] = []
        if overlap is OverlapStrategy.EARLIEST_WINS:
            own_index = plan_order.get(group.key, 0)
            excluded = [
                other.tag
                for other in all_plan_groups
                if plan_order.get(other.key, 0) < own_index
            ]

        def make(
            include_guards: bool,
            with_exclusions: bool = True,
            _group=group,
            _excluded=excluded,
        ) -> str:
            return query.group_search(
                col,
                group_tag=_group.tag,
                priority=priority,
                state=state,
                excluded_group_tags=_excluded if with_exclusions else None,
                scope_deck=settings.scope_deck or None,
                extra_include=settings.extra_include,
                extra_exclude=settings.extra_exclude,
                with_state_guards=include_guards,
            )

        search = make(True)
        unguarded = make(False)
        try:
            matching = set(col.find_cards(unguarded))
        except Exception as exc:
            result.errors.append(f"Ungültige Suche für „{deck_name}“: {exc}")
            continue

        suspended = matching & set(
            col.find_cards(
                query.and_search(
                    col,
                    unguarded,
                    SearchNode(card_state=SearchNode.CARD_STATE_SUSPENDED),
                )
            )
        )
        buried = matching & set(
            col.find_cards(
                query.and_search(
                    col,
                    unguarded,
                    SearchNode(card_state=SearchNode.CARD_STATE_BURIED),
                )
            )
        )
        in_filtered = (
            set(
                col.find_cards(
                    query.and_search(
                        col, search, query.other_filtered_decks_node(col, deck_name)
                    )
                )
            )
            - freed_ids
        )

        still_suspended = suspended - revived_ids
        available = matching - still_suspended - buried - in_filtered

        if overlap is OverlapStrategy.ANKI_ORDER:
            before = len(available)
            available = available - claimed
            overlap_excluded = before - len(available)
        elif excluded:
            broad = set(col.find_cards(make(True, with_exclusions=False)))
            overlap_excluded = max(0, len(broad) - len(set(col.find_cards(search))))
        else:
            overlap_excluded = 0
        claimed |= available

        result.proposals.append(
            Proposal(
                group=group,
                deck_name=deck_name,
                search=search,
                order=settings.order,
                limit=max(1, settings.limit),
                card_ids=frozenset(available),
                matching_total=len(matching),
                suspended=len(still_suspended),
                buried=len(buried),
                in_other_filtered=len(in_filtered),
                overlap_excluded=overlap_excluded,
                revived=len(suspended & revived_ids),
                date=dates.get(group.key, ""),
            )
        )

    if progress is not None:
        progress(total, total, "")
    _add_warnings(result, settings, taxonomy, plan.name, name_collisions)
    return result


def _render_names(
    settings: Settings,
    plan_name: str,
    groups: list[Group],
    priority_text: str,
    dates: dict[str, str],
) -> tuple[list[str], int]:
    names = [
        naming.render(
            settings.pattern,
            naming.NameContext(
                plan=plan_name,
                group=group,
                title=settings.titles.get(group.key) or group.label or group.key,
                prefix=settings.prefix,
                priority_label=priority_text,
                date=dates.get(group.key, ""),
            ),
            settings.effective_parent,
        )
        for group in groups
    ]
    # Kollisionen zählen, bevor deduplicate() sie mit „(2)“ unsichtbar macht:
    # viele gleiche Namen heißt fast immer, dass die Titelquelle nichts
    # Unterscheidendes hergibt.
    collisions = len(names) - len({name.casefold() for name in names})
    return naming.deduplicate(names), collisions


def _add_warnings(
    result: PlanResult,
    settings: Settings,
    taxonomy: Taxonomy,
    plan_name: str,
    name_collisions: int = 0,
) -> None:
    if not result.proposals:
        result.errors.append("Es konnte kein Stapel geplant werden.")
        return

    if name_collisions:
        result.warnings.append(
            f"{name_collisions} Lerntage hätten denselben Stapelnamen bekommen und "
            "wurden mit „(2)“, „(3)“ unterschieden. Das deutet darauf hin, dass "
            "die gewählte Titelquelle nichts Unterscheidendes hergibt — unter "
            "„Titel ableiten aus“ einen anderen Facetten-Ast wählen oder die Titel "
            "von Hand setzen."
        )

    empty = [p.deck_name for p in result.proposals if p.count == 0]
    if empty and not settings.allow_empty:
        result.errors.append(
            f"{len(empty)} Lerntage haben keine passende Karte, und „leere Stapel "
            "anlegen“ ist aus. Anki bricht den Aufbau dann ab. Beispiele: "
            + ", ".join(empty[:3])
        )
    elif empty:
        result.warnings.append(
            f"{len(empty)} Lerntage bleiben leer (werden als leere Stapel angelegt): "
            + ", ".join(empty[:5])
            + ("…" if len(empty) > 5 else "")
        )

    truncated = [p for p in result.proposals if p.truncated]
    if truncated:
        worst = max(truncated, key=lambda p: p.count)
        result.warnings.append(
            f"{len(truncated)} Stapel überschreiten das Limit von {settings.limit} "
            f"Karten (größter: „{worst.deck_name}“ mit {worst.count}). Anki "
            "schneidet am Ende der gewählten Sortierung ab — welche Karten "
            "wegfallen, hängt also an der Sortierung."
        )

    blocked = sum(p.in_other_filtered for p in result.proposals)
    if blocked:
        result.warnings.append(
            f"{blocked} passende Karten liegen in Auswahlstapeln, die bleiben, und "
            "können nicht geholt werden. Eine Karte kann nur in einem "
            "Auswahlstapel liegen — diese Stapel vorher entleeren oder mit "
            "aufräumen."
        )

    suspended = sum(p.suspended for p in result.proposals)
    if suspended:
        result.warnings.append(
            f"{suspended} passende Karten sind suspendiert und werden nicht geholt. "
            "Über „Karten ein-/ausschließen“ lässt sich das ändern."
        )

    revived = sum(p.revived for p in result.proposals)
    if revived:
        result.warnings.append(
            f"{revived} suspendierte Karten werden durch die geplante "
            "Reaktivierung wieder holbar und sind in den Zahlen enthalten."
        )

    overlap = sum(p.overlap_excluded for p in result.proposals)
    if overlap:
        result.warnings.append(
            f"{overlap} Karten gehören zu mehreren Lerntagen und wurden dem "
            "früheren zugeordnet."
        )

    if taxonomy.unrecognized_group_tags:
        relevant = [
            tag for tag in taxonomy.unrecognized_group_tags if f"::{plan_name}::" in tag
        ]
        if relevant:
            result.warnings.append(
                f"{len(relevant)} Tags unter diesem Plan tragen keine Nummer und "
                "werden hinten einsortiert: " + ", ".join(relevant[:3])
            )

    if settings.cleanup_enum is CleanupScope.ALL:
        result.warnings.append(
            "Aufräumen ist auf ALLE Auswahlstapel gestellt. Das löscht auch "
            "Auswahlstapel, die nichts mit diesem Lernplan zu tun haben."
        )

    unknown = naming.unknown_placeholders(settings.pattern)
    if unknown:
        result.warnings.append(
            "Unbekannte Platzhalter im Namensmuster (bleiben als Text stehen): "
            + ", ".join("{" + name + "}" for name in unknown)
        )
