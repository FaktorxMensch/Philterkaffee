# -*- coding: utf-8 -*-
"""Anki Desktop: Ankiphil M1-Intensiv/50-Tage -> geprüfte Tages-Auswahlstapel.

Anki -> Extras/Werkzeuge -> Debug-Konsole (Mac: Cmd+Shift+;):
    exec(compile(open('/PFAD/anki_m1_intensiv_auswahlstapel.py', encoding='utf-8').read(),
                 'anki_m1_intensiv_auswahlstapel.py', 'exec'))

1. Mit PREVIEW_ONLY=True starten. Vorschau in der Debug-Konsole kontrollieren.
2. Vor echten Änderungen Anki-Sammlung sichern.
3. PREVIEW_ONLY=False setzen und erneut starten, Sicherheitsabfrage bestätigen.

Auswahlstapel werden aus NEUEN Karten befüllt (is:new). Mit config.reschedule=True
werden Antworten normal geplant; die Karten kehren nach dem Lernen ins Heimatdeck
zurück. Faellige Wiederholungen im Heimatdeck lernen. Bereits begonnene
Lernkarten koennen vorübergehend im Tages-Auswahlstapel bleiben.

Bei Fehlern waehrend des Umbaus NICHT blind erneut ausfuehren: Sicherung pruefen.
"""

from __future__ import annotations

import re
from collections import Counter

from aqt import mw
from aqt.utils import askUser, showInfo, showWarning
from anki.collection import SearchNode
from anki.decks import FilteredDeckConfig

# ------------------------------- KONFIG -----------------------------------
PREVIEW_ONLY = False

BASE_TAG = '#Ankiphil_Vorklinik_v6.0'
PLAN_ROOT = BASE_TAG + '::$Lernpläne::50-Tage'
PHYSIKUM_TAG = BASE_TAG + '::!Physikum'
HIGH_YIELD_TAG = BASE_TAG + '::!High-Yield'

TARGET_PARENT = 'M1 Intensiv (50 Tage)'

# ACHTUNG: True löscht ALLE existierenden Auswahlstapel (auch fremde Projekte)!
REMOVE_ALL_FILTERED_DECKS = True
# Nur wirksam, wenn REMOVE_ALL_FILTERED_DECKS=False.
FILTERED_DECK_PREFIXES = ('OLP', 'M1-Fachfokus', 'M1 Fachfokus', TARGET_PARENT)

# Für Lerntage ohne Ankiphil-Tags leere, klar markierte Auswahlstapel erzeugen.
CREATE_EMPTY_DAYS = True

# Geteilte Karten gehören dem frühesten Lerntag: spätere Tage schließen die
# Tags vorheriger Lerntage aus. Dadurch keine Mehrfachzuordnung beim Rebuild.
ASSIGN_SHARED_CARDS_TO_EARLIEST_DAY = True

MAX_CARDS_PER_DAY = 10000
# -------------------------------------------------------------------------

# Namen aus dem vom Benutzer angegebenen AMBOSS M1 Intensiv-Lernplan.
# Sie dienen NUR zur Stapelbenennung; der Such-Tag wird aus Anki gelesen.
DAY_TITLES = {
    1: 'Kreuztipps & Grundlagen der Zellbiologie und Physiologie',
    2: 'Grundlagen der Physiologie und Chemie',
    3: 'Grundlagen der Chemie und Physik',
    4: 'Grundlagen der Chemie und Biochemie',
    5: 'Grundlagen der Zellbiologie',
    6: 'Grundlagen der Zell- und Mikrobiologie',
    7: 'Grundlagen der Anatomie und Histologie',
    8: 'Grundlagen der Anatomie und Histologie',
    9: 'Verdauungssystem',
    10: 'Verdauungssystem',
    11: 'Verdauungssystem',
    12: 'Ernährung und Stoffwechsel',
    13: 'Ernährung und Stoffwechsel',
    14: 'Ernährung und Stoffwechsel',
    15: 'Ernährung und Stoffwechsel',
    16: 'Grundlagen der Physik',
    17: 'Herz-Kreislauf',
    18: 'Herz-Kreislauf und Atmung',
    19: 'Blut',
    20: 'Immunsystem',
    21: 'Immun- und lymphatisches System',
    22: 'Niere',
    23: 'Ableitende Harnwege und Elektrolythaushalt',
    24: 'Hormonsystem und Endokrine Organe',
    25: 'Hormonsystem und Endokrine Organe',
    26: 'Geschlechtsorgane und Sexualität',
    27: 'Entstehung neuen Lebens',
    28: 'Obere Extremität',
    29: 'Untere Extremität',
    30: 'Rumpf',
    31: 'Kopf und Hals',
    32: 'Schädel und Hirnnerven',
    33: 'Nervensystem',
    34: 'Nervensystem',
    35: 'Nervensystem',
    36: 'Nervensystem und Sinnesorgane',
    37: 'Sinnesorgane',
    38: 'Sinnesorgane',
    39: 'Psychologie und Soziologie',
    40: 'Psychologie und Soziologie',
    41: 'Psychologie und Soziologie',
    42: 'Psychologie und Soziologie',
    43: 'Psychologie, Soziologie & Tipps zum Ersten Staatsexamen',
    44: 'Psychologie und Soziologie',
    45: 'Wiederholung',
    46: 'Wiederholung',
    47: 'Generalprobe',
    48: 'Generalprobe',
    49: 'Generalprobe',
    50: 'Generalprobe',
}

# Versteht z. B. "01", "01_Grundlagen", "Tag 01", "01 - Grundlagen".
DAY_PART = re.compile(r'^(?:Tag[ _-]*)?(\d{1,2})(?=$|[\s_.-])', re.IGNORECASE)


def has_tag_or_child(actual_tags, root):
    """Anki tag:parent umfasst parent UND parent::subtag (kein String-Prefix-Match)."""
    root = root.casefold()
    return any(t.casefold() == root or t.casefold().startswith(root + '::')
               for t in actual_tags)


def tag_search(tag):
    """Die Anki-API escaped Sonderzeichen in Tags korrekt."""
    return mw.col.build_search_string(SearchNode(tag=tag))


def title_for_day(day, has_tag):
    name = f'{day:02d} – {DAY_TITLES[day]}'
    return name if has_tag else name + ' [kein Tag vorhanden]'


def detect_day_tags():
    """Liest reale Tag-Wurzeln unter ::50-Tage; erfindet keine Tages-Tags."""
    roots = {}
    unrecognized = []
    prefix = PLAN_ROOT + '::'
    for full in mw.col.tags.all():
        if not full.casefold().startswith(prefix.casefold()):
            continue
        rel = full[len(prefix):]
        if not rel:
            continue
        first = rel.split('::', 1)[0]
        m = DAY_PART.match(first)
        if not m or not (1 <= int(m.group(1)) <= 50):
            unrecognized.append(full)
            continue
        day = int(m.group(1))
        # Dieselbe erste Ebene über Untertags mehrfach zu finden ist normal.
        roots.setdefault(day, {})[first.casefold()] = prefix + first

    # Mehrere verschiedene Top-Level-Gruppen für Tag X sind zweideutig.
    ambiguous = {d: list(items.values()) for d, items in roots.items()
                 if len(items) > 1}
    if ambiguous:
        lines = [f'Tag {d:02d}: ' + ' | '.join(tags)
                 for d, tags in sorted(ambiguous.items())]
        raise RuntimeError('ABBRUCH: Mehrere verschiedene Tages-Tag-Wurzeln!\n'
                           + '\n'.join(lines)
                           + '\nBitte manuell klären; keine Änderungen.')

    return {d: next(iter(items.values())) for d, items in roots.items()}, unrecognized


def make_query(day_tag, earlier_tags, priority_node):
    """Gültigen ANKI-Suchtext bauen, nicht das Python-Objekt in Text wandeln."""
    nodes = [SearchNode(tag=day_tag), priority_node,
             'is:new', '-is:suspended', '-is:buried']
    if ASSIGN_SHARED_CARDS_TO_EARLIEST_DAY and earlier_tags:
        prev_or = mw.col.group_searches(
            *(SearchNode(tag=t) for t in earlier_tags), joiner='OR'
        )
        nodes.append(SearchNode(negated=prev_or))
    result = mw.col.build_search_string(*nodes, joiner='AND')
    # Schütze vor dem ursprünglichen Fehler: protobuf-Stringrepräsentation.
    if 'group {' in result or 'nodes {' in result or 'joiner:' in result:
        raise RuntimeError('ABBRUCH: Ungültiger Suchstring von Anki: ' + result)
    return result


def selected_old_filtered_decks(all_decks):
    filtered = [d for d in all_decks if d.get('dyn')]
    if REMOVE_ALL_FILTERED_DECKS:
        chosen = filtered
    else:
        chosen = [d for d in filtered if any(
            d['name'].casefold() == p.casefold() or
            d['name'].casefold().startswith(p.casefold() + '::')
            for p in FILTERED_DECK_PREFIXES)]

    # Niemals einen Filter löschen, unter dem reguläre Unterstapel liegen.
    for filt in chosen:
        prefix = filt['name'].casefold() + '::'
        normals = [d['name'] for d in all_decks if not d.get('dyn')
                   and d['name'].casefold().startswith(prefix)]
        if normals:
            raise RuntimeError('ABBRUCH: Regulärer Stapel unter Auswahlstapel '
                               + filt['name'] + ': ' + ', '.join(normals))
    return sorted(chosen, key=lambda d: (-d['name'].count('::'), d['name'].casefold()))


def validate_deck_names(all_decks, deletions, target_names):
    removing = {d['id'] for d in deletions}
    desired = {n.casefold() for n in target_names}
    for d in all_decks:
        folded = d['name'].casefold()
        if folded in desired and d['id'] not in removing:
            raise RuntimeError('ABBRUCH: Geplanter Stapelname schon belegt: ' + d['name'])
        if folded == TARGET_PARENT.casefold() and d.get('dyn') and d['id'] not in removing:
            raise RuntimeError('ABBRUCH: Ziel-Oberstapel ist ein nicht zu löschender Auswahlstapel')


def make_filtered_deck(deck_name, query):
    deck = mw.col.sched.get_or_create_filtered_deck(0)
    deck.name = deck_name
    deck.allow_empty = True
    deck.config.reschedule = True  # Normale Anki-SRS/FSRS-Planung beibehalten.
    del deck.config.search_terms[:]
    deck.config.search_terms.add(
        search=query,
        limit=MAX_CARDS_PER_DAY,
        order=FilteredDeckConfig.SearchTerm.Order.RANDOM,
    )
    return mw.col.sched.add_or_update_filtered_deck(deck).id


def check_matching_notes(card_ids, expected_tag, previous_tags):
    """Kontrolliert jede gefundene Karte gegen ihre tatsächlichen Notiz-Tags."""
    cached_tags = {}
    for cid in card_ids:
        card = mw.col.get_card(cid)
        if card.nid not in cached_tags:
            cached_tags[card.nid] = mw.col.get_note(card.nid).tags
        tags = cached_tags[card.nid]
        if not has_tag_or_child(tags, expected_tag):
            raise RuntimeError(f'ABBRUCH: Karte {cid} OHNE Tages-Tag {expected_tag}: {tags}')
        if not (has_tag_or_child(tags, PHYSIKUM_TAG) or
                has_tag_or_child(tags, HIGH_YIELD_TAG)):
            raise RuntimeError(f'ABBRUCH: Karte {cid} OHNE Prioritäts-Tag: {tags}')
        if ASSIGN_SHARED_CARDS_TO_EARLIEST_DAY:
            for prev in previous_tags:
                if has_tag_or_child(tags, prev):
                    raise RuntimeError(f'ABBRUCH: Karte {cid} ebenfalls im früheren Tag {prev}')


def main():
    if not mw.col:
        raise RuntimeError('Anki-Sammlung ist nicht geöffnet.')
    if set(DAY_TITLES) != set(range(1, 51)):
        raise RuntimeError('Interner Fehler: Tagesnamen 01–50 nicht vollständig.')

    actual_roots, unrecognized = detect_day_tags()
    if not actual_roots:
        raise RuntimeError('ABBRUCH: Keine nummerierten Tages-Tags unter ' + PLAN_ROOT)

    missing = [i for i in range(1, 51) if i not in actual_roots]
    day_numbers = list(range(1, 51)) if CREATE_EMPTY_DAYS else sorted(actual_roots)

    # WICHTIG: group_searches() gibt einen SearchNode zurück, keinen String.
    priority_node = mw.col.group_searches(
        SearchNode(tag=PHYSIKUM_TAG), SearchNode(tag=HIGH_YIELD_TAG), joiner='OR'
    )

    all_decks = mw.col.decks.all()
    old_filters = selected_old_filtered_decks(all_decks)
    deck_names = [f'{TARGET_PARENT}::{title_for_day(i, i in actual_roots)}'
                  for i in day_numbers]
    validate_deck_names(all_decks, old_filters, deck_names)

    proposals = []
    seen_ids = set()
    aggregate = Counter()
    past_roots = []

    # Weder Karten noch Stapel ändern, bevor ALLE Queries validiert wurden.
    for day in day_numbers:
        tag = actual_roots.get(day)
        if tag is None:
            proposals.append(dict(day=day, tag=None, query=None, ids=set(),
                                  deck_name=f'{TARGET_PARENT}::{title_for_day(day, False)}',
                                  overlaps=0))
            continue

        q = make_query(tag, past_roots, priority_node)
        ids = set(mw.col.find_cards(q))  # Anki prüft die Suchsyntax!
        if len(ids) > MAX_CARDS_PER_DAY:
            raise RuntimeError(f'ABBRUCH: Tag {day:02d} hat {len(ids)} neue Karten, '
                               f'Limit ist nur {MAX_CARDS_PER_DAY}. '
                               'Limit erhöhen, um Abschneiden zu verhindern.')
        check_matching_notes(ids, tag, past_roots)
        repeats = ids & seen_ids
        if repeats:
            raise RuntimeError(f'ABBRUCH: {len(repeats)} Karten für mehrere Tage ({day}).')
        seen_ids.update(ids)

        # Für die Vorschau zählen wir Karten, die in zwei (oder mehr) Tagen
        # vorkommen würden, wenn wir nicht die vorherigen Tage ausschlössen.
        broad_q = make_query(tag, [], priority_node)
        broad_ids = set(mw.col.find_cards(broad_q))
        overlap_count = len(broad_ids) - len(ids)
        aggregate['overlap_exclusions'] += overlap_count

        # Diese Karten bleiben in ihren Heimatdecks und kommen nicht in die
        # Auswahlstapel. Sie dürfen trotzdem für andere Lerntage getaggt sein.
        proposals.append(dict(day=day, tag=tag, query=q, ids=ids,
                              deck_name=f'{TARGET_PARENT}::{title_for_day(day, True)}',
                              overlaps=overlap_count))
        past_roots.append(tag)

    if not seen_ids:
        raise RuntimeError('ABBRUCH: 0 passende neue Karten; Tagstruktur prüfen.')

    print('\n' + '=' * 100)
    print('ANKIPHIL M1 INTENSIV | ' + ('VORSCHAU (OHNE ÄNDERUNGEN)' if PREVIEW_ONLY else 'UMBAU'))
    print('TAG-WURZEL:', PLAN_ROOT)
    print('NEUE Auswahlstapel:', len(proposals))
    print('Einzigartige neue Karten:', len(seen_ids))
    print('Tagübergreifende Übereinstimmungen, dem früheren Tag zugeordnet:',
          aggregate['overlap_exclusions'])
    print('Alte Auswahlstapel zum Löschen:', len(old_filters))
    print('Schutz: is:new, -is:suspended, -is:buried; Physikum ODER High-Yield')
    print('SRS/FSRS: Wiederholungen finden im regulären Heimatstapel statt.')
    if missing:
        print('\nACHTUNG: Keine Ankiphil-Tags für Tage:', ', '.join(f'{x:02d}' for x in missing))
    if unrecognized:
        print('\nUntertags ohne erkennbaren Tag 01–50:')
        for bad in sorted(set(unrecognized)):
            print('  ', bad)
    print('\nLERNSTAPEL / TAG / NEUE KARTEN / SCHON FRÜHER ZUGEORDNET:')
    for p in proposals:
        print(f'  {p["deck_name"]} | neu: {len(p["ids"])} | Überschneidungen: {p["overlaps"]}')
        print('     Tag:', p['tag'] if p['tag'] else '(FEHLT: leerer Stapel ohne Such-Tag)')
        if p['query']:
            print('     Query:', p['query'])
    print('\nWERDEN ENTFERNT:')
    for old in old_filters:
        print('  -', old['name'])
    print('=' * 100 + '\n')

    if PREVIEW_ONLY:
        showInfo(f'Vorschau abgeschlossen (nichts geändert).\n\n'
                 f'{len(proposals)} Tagesstapel, {len(seen_ids)} verschiedene neue Karten.\n'
                 f'{len(old_filters)} alte Auswahlstapel zur Entfernung.\n'
                 f'{len(missing)} Tage ohne Ankiphil-Tags.\n\n'
                 'Alle echten Queries und Tag-Zuordnungen stehen in der Debug-Konsole.\n'
                 'Nach Kontrolle PREVIEW_ONLY=False setzen.')
        return

    if not askUser(
        f'ACHTUNG: {len(old_filters)} Auswahlstapel löschen und '
        f'{len(proposals)} neue Tagesstapel mit zusammen {len(seen_ids)} '
        'verschiedenen neuen Karten erstellen?\n\n'
        f'Tage ohne vorhandene Ankiphil-Tags: {len(missing)}.\n'
        f'Überschneidungen früheren Tagen zugeordnet: {aggregate["overlap_exclusions"]}.\n\n'
        'Die Karten behalten ihren Lernstand und kehren beim Entfernen alter '
        'Auswahlstapel in ihre Heimatstapel zurück.\n\n'
        'Nur fortfahren, wenn eine Anki-Sicherung erstellt wurde.',
        defaultno=True,
    ):
        print('ABGEBROCHEN (keine Änderungen).')
        return

    try:
        # Erst Karten aus alten Filterdecks zurückschicken, dann neu verteilen.
        if any(d['id'] == mw.col.decks.get_current_id() for d in old_filters):
            normal = next((d for d in all_decks if not d.get('dyn') and not any(
                d['name'].casefold().startswith(f['name'].casefold() + '::')
                for f in old_filters)), None)
            if normal is None:
                raise RuntimeError('Kein regulärer Stapel zum Auswählen vorhanden.')
            mw.col.decks.select(normal['id'])

        deleted = 0
        for old in old_filters:
            did = mw.col.decks.id_for_name(old['name'])
            if did is None:
                continue
            if not mw.col.decks.is_filtered(did):
                raise RuntimeError('Stapeltyp vor Löschung geändert: ' + old['name'])
            mw.col.decks.remove([did])
            deleted += 1

        if mw.col.decks.id_for_name(TARGET_PARENT) is None:
            mw.col.decks.id(TARGET_PARENT)  # Regulärer Oberstapel.

        created = 0
        for p in proposals:
            if p['tag'] is None:
                # Anki braucht einen gültigen, aber garantiert nicht passenden
                # Filterausdruck; kein erfundener Tages-Tag wird verwendet.
                query = 'is:new is:review'  # logisch unmöglich
            else:
                query = p['query']
            new_did = make_filtered_deck(p['deck_name'], query)
            created += 1
            # Nachher jede tatsächlich eingezogene Karte gegen reale Notiz-Tags prüfen.
            if p['tag'] is not None:
                in_deck_query = mw.col.build_search_string(SearchNode(deck=p['deck_name']))
                obtained = set(mw.col.find_cards(in_deck_query))
                if not obtained.issubset(p['ids']):
                    raise RuntimeError(
                        f'Abbruch: {p["deck_name"]}: Karten außerhalb der geprüften Auswahl! '
                        + repr(list(obtained - p['ids'])[:10])
                    )
                past = [actual_roots[x] for x in range(1, p['day']) if x in actual_roots]
                check_matching_notes(obtained, p['tag'], past)
                print(f'OK Tag {p["day"]:02d}: {len(obtained)} Karten korrekt eingeordnet '
                      f'(vorgeschlagen: {len(p["ids"])}).')
            else:
                empty_query = mw.col.build_search_string(SearchNode(deck=p['deck_name']))
                if mw.col.find_cards(empty_query):
                    raise RuntimeError(f'Abbruch: Tag {p["day"]:02d} ohne Tag ist NICHT leer!')
                print(f'OK Tag {p["day"]:02d}: leer (kein Tages-Tag).')
        mw.reset()
        showInfo(f'Fertig: {deleted} alte Auswahlstapel entfernt, '
                 f'{created} M1-Intensiv-Tagesstapel angelegt.\n\n'
                 'Jede tatsächlich eingeordnete Karte wurde anhand ihrer '
                 'echten Tages- und Prioritäts-Tags geprüft.\n'
                 'Fällige Wiederholungen weiterhin im ursprünglichen Stapel lernen.')
    except Exception as exc:
        mw.reset()
        showWarning('FEHLER: Umbau ist möglicherweise nur teilweise erfolgt!\n'
                    'Nicht einfach erneut starten; Sicherung kontrollieren.\n\n' + str(exc))
        raise


main()
