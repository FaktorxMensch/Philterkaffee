# AnkiPhil Lernplan-Auswahlstapel — Analyse & Entwicklungsplan

Stand: 2026-10-30 · Anki 26.09.3 (venv) · Stapel `AMBOSS_feat_Ankiphil__Vorklinik_v60.apkg`

---

## 1. Was tatsächlich im Stapel steckt (gemessen, nicht geraten)

7.541 Notizen / 11.891 Karten. Ein einziger Tag-Stamm: `#Ankiphil_Vorklinik_v6.0`,
darunter 3.065 verschiedene Tags in 10 Ästen:

| Ast | Notizen | Struktur |
|---|---|---|
| `!Physikum` | 5.139 | flach (Blatt-Tag) |
| `!High-Yield` | 1.761 | flach |
| `!Top30` | 1.929 | flach |
| `#Fächer` | 11.828 Tag-Treffer / 385 Tags | 3–5 Ebenen tief, 8 Fächer |
| `#Organsysteme` | 6.675 | 2 Ebenen, 17 Systeme |
| `#Universitäten` | 65.634 | 5 Unis × `N_Semester` |
| `$Lernpläne` | 21.159 | **3 Pläne** |
| `$Image_Occlusion` | 213 | nur `::Anatomie` |
| `§Formeln` | 178 | flach |
| `§Klinik_Relevanz` | 737 | flach |

### Die drei Lernpläne

| Plan | Gruppen-Tags | Summe | Union | Mehrfachzuordnung |
|---|---|---|---|---|
| `$Lernpläne::30-Tage` | `01`–`30` | 6.336 | 6.327 | **9 Notizen** |
| `$Lernpläne::50-Tage` | `01`–**`43`** | 6.336 | 6.327 | **9 Notizen** |
| `$Lernpläne::M1-Fachfokus` | `01_…`–`44_…` | 8.487 | 6.327 | **2.160 Notizen** |

**Drei Befunde, die direkt in das Addon-Design gehören:**

1. **Alle drei Pläne decken exakt dieselben 6.327 Notizen ab.** Es sind reine
   Umsortierungen derselben Auswahl, keine unterschiedlichen Inhaltsmengen.
   (Verifiziert: Mengengleichheit der Notiz-IDs.)
2. **Der „50-Tage"-Plan hat nur 43 Tages-Tags**, nicht 50. Tage 44–50 sind im
   AMBOSS-Plan Wiederholung/Generalprobe und haben folgerichtig keine neuen
   Karten. Ein Addon muss die Tage **aus der Sammlung lesen** und darf keine
   Tagesanzahl annehmen.
3. **Überlappung ist plan-abhängig.** 50-/30-Tage: praktisch keine (9 Notizen).
   M1-Fachfokus: **2.160 Notizen in 2–3 Gruppen** — hier ist die
   Überlappungsstrategie entscheidend, nicht kosmetisch.

### Die Tages-Tags haben keine Namen

`…::50-Tage::17` — das ist alles. Es gibt keinen Titel im Tag. Namen müssen
also von außen kommen. Gute Nachricht: sie lassen sich **aus den `#Fächer`-/
`#Organsysteme`-Tags der Karten ableiten**. Beispiel (gemessen):

```
17: Herz/Kreislauf_&_Atmung(286), Grundlagen_Kreislauf(31)
22: Niere_&_Elektrolythaushalt(142), Niere_&_Harnwege(89)
39: Methodische_Grundlagen(137), Patientenversorgung(57)
```

Das deckt sich mit den im Skript hartcodierten AMBOSS-Titeln — die Zuordnung
Tag `01`–`43` ↔ AMBOSS-Lerntag 1–43 ist also korrekt. Aber sie ist nicht
garantiert und bricht bei jedem Stapel-Update (v6.1 …). Deshalb: **ableiten +
editierbar**, nicht hartcodieren.

### Prioritäts-Tags sind fast, aber nicht ganz verschachtelt

| Kombination (Physikum, High-Yield, Top30) | Notizen |
|---|---|
| Physikum only | 2.357 |
| Physikum + High-Yield | 1.026 |
| Physikum + Top30 | 1.022 |
| alle drei | 734 |
| Top30 only | 173 |
| High-Yield only | 1 |
| keiner | 2.228 |

→ High-Yield ⊂ Physikum (bis auf 1 Notiz). **Top30 ist eine eigene Achse**
(173 Notizen außerhalb Physikum) und für viele Lerntage **leer**: bei 20 der 43
Tage gibt es null Top30-Karten. Das muss die UI anzeigen, sonst baut man
stillschweigend leere Stapel.

**Konsequenz des Skript-Filters `(Physikum OR High-Yield)`:** er verwirft
1.187 der 6.327 Plan-Notizen (≈19 %). Das ist eine legitime Entscheidung, aber
sie muss wählbar sein — genau die „Tiefe", die du willst.

### Karten pro Lerntag (50-Tage, als Karten nicht Notizen)

Spannweite 87–365 Karten/Tag (alle), 87–355 mit `Physikum|High-Yield`.
Notizen haben 1–12 Karten (4.851 mit 1, 2.065 mit 2, Rest mehr) — Image
Occlusion zieht den Schwanz. Geschwisterkarten sind also real und relevant.

---

## 2. Wie Auswahlstapel wirklich funktionieren (die Regeln, die wehtun)

Recherchiert in Anki-Manual, Anki-Forums und dem lokalen Anki-26.09.3-Quellcode
(`aqt/filtered_deck.py`, `anki/scheduler/base.py`).

### Harte Grenzen

1. **Eine Karte kann in genau einem Auswahlstapel liegen.** Nicht gesammelt
   werden: suspendierte Karten, zurückgestellte (buried) Karten, Karten in
   einem *anderen* Auswahlstapel. → Baut man 43 Tagesstapel, „gewinnt" bei
   Überlappung der zuerst gebaute. Im 50-Tage-Plan betrifft das 9 Notizen, im
   Fachfokus 2.160.
2. **Auswahlstapel haben keine Unterstapel.** Sie können *unter* einem normalen
   Oberstapel liegen (`Oberstapel::Tag 01`), aber selbst keine Kinder haben.
3. **Deck-Presets/Tageslimits gelten nicht.** Nur das eigene `limit` des
   Auswahlstapels zählt. Das ist hier ein Vorteil (keine Limit-Kämpfe) und ein
   Risiko (unbegrenzt neue Karten an einem Tag).
4. **Reihenfolge = Auswahl.** Das `order` bestimmt nicht nur die Lernreihenfolge,
   sondern *welche* Karten bei Limit-Überschreitung drin sind. Abgeschnitten
   wird am Ende der Sortierung.
5. **Löschen ≠ Datenverlust.** „Entleeren" und „Löschen" schicken Karten in ihr
   Heimatdeck zurück; der Lernstand bleibt.
6. **Lernschritte kommen vom Heimatdeck.** Karten verlassen den Auswahlstapel,
   sobald (Re-)Lernen abgeschlossen ist.

### Sortier-Optionen (`FilteredDeckConfig.SearchTerm.Order`, aus dem Quellcode)

```
0 OLDEST_REVIEWED_FIRST   5 ADDED                  ← „Erstelldatum, älteste zuerst"
1 RANDOM                  6 DUE
2 INTERVALS_ASCENDING     7 REVERSE_ADDED
3 INTERVALS_DESCENDING    8 RETRIEVABILITY_ASC   ← nur mit FSRS
4 LAPSES                  9 RETRIEVABILITY_DESC  ← nur mit FSRS
                         10 RELATIVE_OVERDUENESS
```

Dein Wunsch-Default „Erstelldatum, älteste zuerst" ist **`ADDED` (5)**.
Die beiden Retrievability-Optionen dürfen nur angeboten werden, wenn FSRS aktiv
ist — Anki blendet sie selbst aus (`FSRS_ONLY_ORDERS`), ein Addon muss das
nachbauen.

### Der zweite Filter

Ein Auswahlstapel kann **zwei** Suchterme haben, jeder mit eigenem `limit` und
`order`. Genau das Werkzeug für „neue Karten des Lerntags + fällige
Wiederholungen der Vortage in einem Stapel".

### Wichtig: `-deck:filtered` in der Vorschau

Anki selbst zeigt im Dialog über den „Hinweis"-Button, welche Karten *passen,
aber nicht geholt werden können* — und nutzt dafür genau
`is:suspended OR is:buried OR (deck:filtered -deck:<dieser>)`. Eine Vorschau
ohne `-deck:filtered` zählt zu hoch.

### Was es an Addons schon gibt — und was fehlt

| Addon | Kann | Kann nicht |
|---|---|---|
| Multi Filtered Deck Creator From Tags | 1 Stapel pro Tag aus einer Tag-Liste | kein Plan-Begriff, keine Prio-Stufen, kein Namensmuster, keine Überlappungsstrategie |
| Filtered Deck By Tag | Rechtsklick auf Tag → Stapel, Zusatz-Query | baut nicht neu, kein Multi-Tag |
| Filtered Deck Builder | Tags per Klick mit AND/OR/NOT | keine Massenerzeugung über einen Plan |
| Rebuild All / Rebuild Filtered Decks | „Alle neu aufbauen"-Button | kein Bezug zu Plan/Prio, kein Umbau |

Wiederkehrende Beschwerden in den Foren: Tag-Auswahl im eingebauten Dialog ist
„tag:1, speichern, zurück, tag:2, …" für jeden Tag einzeln; leere
Auswahlstapel waren lange nicht erzeugbar (heute: `allow_empty`); überlappende
Tag-Stapel bleiben stillschweigend unvollständig; Auto-Rebuild wird von
Addon-Autoren **absichtlich abgelehnt**, weil ein Rebuild vor dem Sync
Wiederholungen von anderen Geräten verlieren kann.

→ **Die Lücke, die dieses Addon füllt, ist real:** „Lernplan → N benannte,
priorisierte, überlappungsfreie Tagesstapel unter einem Oberstapel, verwaltbar
und wiederholbar." Das gibt es nicht.

---

## 3. Bewertung des bestehenden Skripts

`anki_m1_intensiv_auswahlstapel.py`, 440 Zeilen, läuft über die Debug-Konsole.

### Was gut ist und übernommen wird

- **`build_search_string(SearchNode(...))` statt String-Bastelei.** Tags mit
  `#`, `$`, `§`, Umlauten und Leerzeichen werden korrekt escaped. Der
  Selbstschutz gegen protobuf-`repr` (`if 'group {' in result`) ist ein kluger
  Fingerabdruck eines echten, einmal erlebten Bugs.
- **„Erst alles validieren, dann schreiben."** Alle Queries werden ausgeführt
  und geprüft, bevor ein einziger Stapel angelegt wird. Genau richtig.
- **`has_tag_or_child()`** respektiert, dass Anki `tag:X` als „X oder X::*"
  interpretiert — kein naives String-Prefix-Matching.
- **Nachkontrolle:** jede *tatsächlich* eingezogene Karte wird gegen die echten
  Notiz-Tags geprüft. Paranoid im guten Sinn.
- **Schutz gegen Namenskollisionen** und gegen das Löschen von Auswahlstapeln,
  unter denen normale Stapel hängen.
- **`allow_empty = True`** und `reschedule = True` sind richtig gesetzt.
- **PREVIEW_ONLY-Modus** mit Sicherheitsabfrage.

### Was nicht sinnvoll ist

| # | Problem | Folge |
|---|---|---|
| 1 | `REMOVE_ALL_FILTERED_DECKS = True` als **Default** | Löscht *jeden* Auswahlstapel im Profil, auch völlig fremde. Der Kommentar warnt davor und setzt es trotzdem auf `True`. |
| 2 | `DAY_TITLES` hartcodiert für Tage 1–50 | Der Plan hat 43 Tags → 7 Stapel mit der absichtlich unmöglichen Query `is:new is:review`. Permanente Leerstapel als Platzhalter. Bricht bei v6.1. |
| 3 | Vorschau ohne `-deck:filtered` | Zählt Karten mit, die in anderen Auswahlstapeln liegen und nie geholt werden. Vorschau ≠ Ergebnis. |
| 4 | `Order.RANDOM` fest verdrahtet | Widerspricht deinem Wunsch (`ADDED`). Bei Limit-Überschreitung außerdem willkürliche Auswahl. |
| 5 | `check_matching_notes()` macht `get_card()`+`get_note()` **pro Karte** | 43 Tage × bis 365 Karten, zweimal (vorher/nachher). Minutenlang, im UI-Thread. |
| 6 | Alles läuft synchron im Hauptthread | Anki friert ein; `mw.reset()` statt der heutigen `CollectionOp`-Mechanik. |
| 7 | Keine zusammengefasste Undo-Stufe | 43 Stapel = 43 Rückgängig-Schritte, dazwischen die Löschungen. Praktisch nicht zurücknehmbar. |
| 8 | `!Top30`, `§Formeln`, `§Klinik_Relevanz` kommen nicht vor | Ein Drittel der Prioritäts-Achsen fehlt. |
| 9 | Prio-Filter `(Physikum OR High-Yield)` fest | Verwirft 19 % des Plans ohne Wahlmöglichkeit. |
| 10 | Negativ-Kette wächst linear | Tag 43 trägt 42 negierte Tags in der Query. Funktioniert, ist aber für 9 betroffene Notizen im 50-Tage-Plan viel Aufwand — im Fachfokus (2.160) dagegen zwingend. |
| 11 | Nur `is:new` | Keine Wiederholungstage, kein zweiter Filter. |
| 12 | Nur 50-Tage-Plan, Prefix-Konstanten | 30-Tage und M1-Fachfokus nicht nutzbar; `v6.0` im Tag fest verdrahtet. |
| 13 | Kein Nachbearbeiten | „Alle neu aufbauen", „Tag erledigt → entleeren", „Prio ändern" fehlen komplett. |

### Fazit

Die **Validierungslogik ist überdurchschnittlich gut** und wird der Kern des
Addons. Die **Konfiguration ist hartcodiert, der Default gefährlich, die
Performance untragbar** für eine UI. Das Skript ist ein brauchbarer Prototyp,
kein Fundament.

---

## 4. Addon-Architektur

Anki 26.09.3, PyQt6. Addon-Ordner (`addons21/ankiphil_lernplan/`):

```
__init__.py          Menü-Registrierung, lazy imports
manifest.json        name, package, min/max point version
config.json/.md      Defaults + Doku (Anki-Konfig-Editor)
core/
  taxonomy.py        Tag-Baum entdecken: Basis-Tag, Pläne, Gruppen, Prio-Achsen
  naming.py          Namensmuster-Engine + Deckname-Sanitizing
  query.py           SearchNode-Komposition (nie String-Konkatenation)
  planner.py         reine Funktion: Config → Liste von Stapel-Vorschlägen
  builder.py         CollectionOp: löschen + anlegen, eine Undo-Stufe
  gating.py          Suspendieren/Entsuspendieren ("Lerntiefe")
  profiles.py        Profile in col.set_config() (synct mit)
ui/
  main_dialog.py     Hauptfenster (Plan, Tiefe, Benennung, Optionen)
  preview_table.py   Vorschau: pro Tag Karten/blockiert/Query
  manage_dialog.py   Bestand verwalten: neu aufbauen, entleeren, umbauen
  gating_dialog.py   Lerntiefe (Suspendierung) mit Vorschau
```

### Nicht verhandelbare technische Regeln

- **Jede Schreiboperation in `CollectionOp`**, jede Leseoperation in `QueryOp`.
  Nie `mw.col.*` im UI-Thread, nie `mw.reset()`.
- **Eine Undo-Stufe** für den ganzen Umbau:
  `col.add_custom_undo_entry("Lernplan-Auswahlstapel")` →
  `col.merge_undo_entries(target)` nach jedem Teilschritt.
- **Alle Queries über `SearchNode` / `group_searches` / `build_search_string`.**
  Plus der protobuf-`repr`-Selbsttest aus dem Skript.
- **Mengenoperationen statt Karten-Schleifen** für die Validierung
  (`find_cards` / `find_notes` + Set-Differenz), nicht `get_card()` pro Karte.
- **Vorschau zählt mit `-is:suspended -is:buried -deck:filtered`** und zeigt die
  blockierten Karten getrennt aus.
- **Kein Auto-Rebuild beim Tageswechsel** (Sync-Datenverlustrisiko, siehe oben).
  Höchstens eine Erinnerung.

---

## 5. Funktionsumfang

### A — Hauptfenster „Auswahlstapel erstellen"

**Lernplan**
- Basis-Tag automatisch erkannt (`#Ankiphil_*`), überschreibbar
- Plan-Dropdown aus der Sammlung gelesen (30-Tage / 50-Tage / M1-Fachfokus /
  beliebiger anderer Tag-Ast)
- Tages-/Gruppenliste mit Checkboxen; Teilmengen wählbar („nur Tag 12–20")

**Lerntiefe (Prioritätsfilter)**
- Mehrfachauswahl: Physikum, High-Yield, Top30, Formeln, Klinik-Relevanz,
  „alle Plan-Karten"
- Verknüpfung ODER / UND
- **Live-Kartenzahl pro Auswahl** und Warnung bei leeren Tagen (Top30!)

**Eingrenzung (optional)**
- Quell-Stapel begrenzen
- `#Fächer` / `#Organsysteme` ein-/ausschließen
- `#Universitäten::<Uni>::<Semester>` einschließen
- `$Image_Occlusion` ein-/ausschließen

**Kartenzustand**
- nur neue (`is:new`) — Default
- neue + fällige Wiederholungen
- nur fällige
- „noch nie gesehen" vs. „auch angefangene Lernkarten"
- immer implizit: `-is:suspended -is:buried`

**Benennung**
- Oberstapel (Default „M1 Intensiv (50 Tage)"), Auswahlstapel darunter — oder flach
- **Namensmuster mit Platzhaltern**:
  `{praefix}` `{plan}` `{nr}` `{nr2}` `{titel}` `{fach}` `{tag}` `{tagblatt}`
  `{prio}` `{datum}` `{anzahl}`
  Default: `{praefix}{nr2} – {titel}`
- Titel-Quelle: **automatisch aus dominanten `#Fächer`-Tags** / manuelle Tabelle
  / nur Nummer. Tabelle editierbar, als Profil speicherbar.
- Sanitizing: `"` entfernen, `::` in Komponenten neutralisieren, Länge kappen

**Sortierung & Limit**
- Order-Dropdown, Default **`ADDED` (Erstelldatum, älteste zuerst)**
- Retrievability-Optionen nur bei aktivem FSRS
- Limit pro Stapel (Default hoch, z. B. 9999) + Warnung bei Abschneiden

**Verhalten**
- Neu planen (`reschedule`) an/aus; bei „aus" die drei Vorschau-Verzögerungen
- Leere Stapel anlegen (`allow_empty`) an/aus
- **Überlappungsstrategie**: frühester Tag gewinnt (explizite Ausschlüsse) /
  Anki-Reihenfolge entscheiden lassen / Mehrfachzuordnung erlauben
- **Zweiter Filter**: neue Karten des Tages + fällige Karten des Plans

**Aufräumen**
- nichts löschen / nur Auswahlstapel unter *diesem* Oberstapel / nach
  Namensmuster / alle (mit expliziter Extra-Bestätigung)
- **Default: nur unter dem gewählten Oberstapel.** Niemals „alle".
- Schutz: kein Löschen, wenn normale Unterstapel darunter hängen

**Vorschau (immer, vor jedem Schreibvorgang)**
Tabelle: Stapelname · Karten · davon neu/fällig · blockiert (suspendiert /
buried / in anderem Auswahlstapel) · Überlappung · Query. Plus Gesamtsumme,
Liste der Tage ohne Tags und der zu löschenden Stapel.

### B — Verwaltungsfenster „Bestand"

- Statustabelle aller Plan-Auswahlstapel: Name, enthaltene Karten, neu/fällig,
  letzter Aufbau
- **Alle neu aufbauen** / einzelne neu aufbauen (in Plan-Reihenfolge, damit
  „frühester Tag gewinnt" reproduzierbar bleibt)
- **Alle entleeren** / einzelne entleeren („Lerntag erledigt")
- **Alle löschen** (Karten gehen heim)
- **Umbauen**: Prio/Order/Limit/Benennung ändern → auf alle anwenden, ohne neu
  zu konfigurieren
- **Umbenennen** nach geändertem Muster, ohne Neuaufbau
- „Prüfen": Tage ohne Tags, verwaiste Stapel, Tag-Umbenennungen nach
  Stapel-Update (v6.0 → v6.1), Karten, die in fremden Auswahlstapeln festhängen

### C — Lerntiefe-Fenster (Suspendierung)

Was aktuell im AnkiPhil-Stapel **ausgeschlossen** ist, sichtbar und steuerbar:

- Baumansicht mit Ist-Zustand: pro Prio-Achse / Fach / Organsystem / Uni-Semester
  die Zahl aktiver vs. suspendierter Karten
- Regel setzen: „aktiv = Physikum ∪ High-Yield; alles andere suspendieren"
- Vorschau: „wird suspendiert: N · wird reaktiviert: M", dann ausführen
- **Streng auf die AnkiPhil-Stapel begrenzt** — fremde Stapel werden nie berührt
- Eine Undo-Stufe; deutlicher Hinweis, dass dies die Sammlung dauerhaft ändert
  und synct (im Gegensatz zu Auswahlstapeln)
- **Wechselwirkung sichtbar machen:** suspendierte Karten können *nicht* in
  Auswahlstapel geholt werden. Tiefe per Suspendierung und Tiefe per Prio-Filter
  sind zwei Schichten — die UI muss beide gleichzeitig zeigen.

### D — Zusätzlich sinnvoll (Begründung je Punkt)

1. **Profile** — benannte Konfigurationen, in `col.set_config()` (syncen mit),
   Export/Import als JSON. Du wirst „50-Tage Physikum" und „Fachfokus
   High-Yield" nebeneinander brauchen.
2. **Rollierendes Fenster / Kalendermodus** — Startdatum setzen, nur
   heute + nächste N Tage bauen. Löst das Kernproblem elegant: solange nur
   wenige Stapel gefüllt sind, kann keine Karte „falsch belegt" sein, und die
   Zahlen bleiben überschaubar. Für M1-Fachfokus (2.160 Überlappungen) der
   einzige verlustfreie Weg.
3. **Wiederholungstage** — Tage ohne eigene Tags (44–50) als zweiter Filter über
   `is:due` des gesamten Plans statt als Leerstapel.
4. **Titel automatisch aus `#Fächer`** — die Tages-Tags sind namenlos; die
   Ableitung aus den dominanten Fach-Tags ist belastbar (oben verifiziert) und
   überlebt Stapel-Updates.
5. **Trockenlauf-Bericht exportieren** — Vorschau als Text/CSV, damit du
   Änderungen zwischen zwei Durchläufen vergleichen kannst.
6. **Hinweis-Button wie in Anki** — Browser öffnen mit genau den Karten, die
   passen aber blockiert sind. Beantwortet „warum sind hier nur 95 statt 361
   Karten?" (Tag 28: 361 gesamt, 95 mit Physikum|High-Yield) ohne Rätselraten.
7. **Backup-Erinnerung** vor dem ersten Schreibvorgang, einmal pro Sitzung.
8. **Browser-Kontextmenü** — Rechtsklick auf einen Plan-Tag in der Seitenleiste
   → „Auswahlstapel für diesen Lerntag".
9. **Fortschrittsanzeige** — welche Lerntage entleert (= erledigt) sind.

### E — Bewusst nicht gebaut

- **Auto-Rebuild beim Tageswechsel.** Addon-Autoren lehnen das begründet ab:
  ein Rebuild vor dem Sync kann Wiederholungen anderer Geräte verwerfen.
  Stattdessen: Erinnerung, Aufbau bleibt ein Klick.
- **Direkte `col.db`-Schreibzugriffe.** Syncen nicht.
- **Eigener Scheduler.** `reschedule=True` + Heimatdeck-Einstellungen sind
  korrekt und bewährt.

---

## 6. Entscheidungen und Umsetzungsstand

Entschieden am 2026-10-30:

| Frage | Entscheidung |
|---|---|
| Baumodus | **Beides, umschaltbar** — alle Lerntage auf einmal als Voreinstellung, Kalenderfenster als Option |
| Karteninhalt | **Erstmal nur neue Karten**; die anderen Zustände sind implementiert und wählbar, aber nicht Voreinstellung |
| Lerntiefe | **Beides** — Filter wirkt auf die Auswahlstapel, plus Haken „auch auf alle Karten anwenden“, plus eigenes Fenster zum Ein-/Ausschließen nach Tag |
| Benennung | **Automatisch aus `#Fächer` + editierbare Tabelle** |

### Umgesetzt (lauffähig, getestet)

* **Fundament** — `taxonomy`, `titles`, `naming`, `query`, `config`, `planner`,
  `builder`. Nichts ist auf v6.0 festgelegt; Basis-Tag, Pläne und Lerntage
  kommen aus der Sammlung.
* **Hauptfenster** mit allen sieben Abschnitten, Vorschautabelle, Filteranzeige,
  „Gesperrte Karten zeigen“, Staleness-Sperre für „Erstellen“.
* **Verwaltungsfenster** — Statustabelle, neu aufbauen (einzeln/alle),
  entleeren, löschen, nachträglicher Umbau von Limit/Sortierung/Planung.
* **Lerntiefe-Fenster** — Tagbaum mit Karten- und Ausschlusszahlen, drei
  Aktionen, Vorschau, strikt auf den AnkiPhil-Tagbaum begrenzt.
* **Sicherheit** — eine Rückgängig-Stufe pro Umbau, Prüfung vor dem Schreiben,
  Nachkontrolle gegen echte Notiz-Tags, alles im Hintergrund-Thread.
* **Titelableitung** aus den `#Fächer`-Tags, überschreibbar, als Profil in der
  Sammlung gespeichert.

### Während der Entwicklung gefundene und behobene Fehler

Drei davon hätten im Betrieb wehgetan:

1. **Namenskollisionen wurden bei „nichts aufräumen“ nicht geprüft** — der
   frühe Ausstieg in `plan_deletions()` übersprang die Prüfung. Ein belegter
   Zielname ist unabhängig vom Aufräumen ein Abbruchgrund.
2. **Ankis Rückgängig-Warteschlange ist begrenzt.** Nach 44 Löschungen war der
   eigene Sammeleintrag verdrängt (`target undo op not found`). Es muss nach
   *jeder* Einzeloperation zusammengefasst werden, nicht nach einer Schleife.
3. **Die Vorschau rechnete nicht mit, dass die zu löschenden Auswahlstapel ihre
   Karten freigeben.** Beim Neuaufbau eines bestehenden Lernplans zählte sie
   fast alles als „blockiert“ und baute dann trotzdem volle Stapel — genau der
   „Vorschau ≠ Ergebnis“-Fehler, der am Vorgängerskript kritisiert wurde. Die
   Berechnung läuft jetzt in der Reihenfolge Namen → Löschungen →
   Suspendierung → Kartenzahlen.
4. Im Lerntiefe-Fenster gingen die Haken nach jedem Anwenden verloren, weil der
   Baum neu aufgebaut wurde.

Die Nachkontrolle, die Fehler 3 gefunden hat, ist die Idee aus dem
Vorgängerskript — sie hat sich sofort bezahlt.

### Was absichtlich offen bleibt (Stufe 4)

* Benannte Profile mit Export/Import als JSON
* Wiederholungstage über den zweiten Filter (`is:due` des ganzen Plans)
* Rechtsklick auf einen Plan-Tag in der Browser-Seitenleiste
* Vorschaubericht als Text/CSV exportieren
* „Prüfen“-Funktion: verwaiste Stapel, Tag-Umbenennungen nach Stapel-Update
* Fortschrittsanzeige, welche Lerntage erledigt (entleert) sind

### Bewusst nicht gebaut

* **Automatisches Neuaufbauen beim Tageswechsel.** Addon-Autoren lehnen das
  begründet ab: ein Rebuild vor dem Synchronisieren kann Wiederholungen von
  anderen Geräten verwerfen.
* Direkte `col.db`-Schreibzugriffe (synchronisieren nicht).
* Ein eigener Scheduler.

### Zur FSRS-Frage

Ein „Wiederholungen“-Stapel zerstört FSRS **nicht**, solange „Normal planen“
eingeschaltet ist: fällige Karten verhalten sich im Auswahlstapel wie im
Heimatstapel, und das nächste Intervall kommt aus den Einstellungen des
Heimatdecks. Schädlich sind zwei andere Dinge: „Normal planen“ *aus* (dann
zählt gar nichts) und das regelmäßige Vorziehen **nicht fälliger** Karten
(`prop:due>0`) — Anki rechnet das über eine Gleitskala gegen, das Handbuch rät
aber ausdrücklich von wiederholter Nutzung ab. Ein Stapel, der auf `is:due`
begrenzt ist, ist unbedenklich.

## 7. Quellen

- [Filtered Decks & Cramming — Anki Manual](https://docs.ankiweb.net/filtered-decks.html)
- [Add-on folders — Anki Docs](https://docs.ankiweb.net/addons/addon-folders)
- [The anki module — Anki Docs](https://docs.ankiweb.net/addons/the-anki-module)
- [A card to be able to appear in multiple filtered decks — Anki Forums](https://forums.ankiweb.net/t/a-card-to-be-able-to-appear-in-multiple-filtered-decks/53213)
- [Multiple Tag Selecting for Filtered Decks — Anki Forums](https://forums.ankiweb.net/t/multiple-tag-selecting-for-filtered-decks/30041)
- [I want to create filtered decks, even if they don't have cards yet — Anki Forums](https://forums.ankiweb.net/t/i-want-to-create-filtered-decks-even-if-they-dont-have-cards-yet/35902)
- [Rebuild All / Empty All Filtered Decks (enhanced fork) — Anki Forums](https://forums.ankiweb.net/t/rebuild-all-empty-all-filtered-decks-enhanced-fork-official-thread/557)
- [Feature Request: Filtered Decks — automatic rebuild — Anki Forums](https://forums.ankiweb.net/t/feature-request-filtered-decks-automatic-rebuild/9277)
- [How can I ensure that the Filtered Deck adheres to the New Card Limit — Anki Forums](https://forums.ankiweb.net/t/how-can-i-ensure-that-the-filtered-deck-adheres-to-the-new-card-limit-of-each-subdeck/33696)
- [Multi Filtered Deck Creator From Tags — AnkiWeb](https://ankiweb.net/shared/info/1031039445)
- [Filtered Deck From Tag — AnkiWeb](https://ankiweb.net/shared/info/2058067048)
- [Filtered Deck Builder — AnkiWeb](https://ankiweb.net/shared/info/290332704)
- [anki-filtered-deck-by-tag — GitHub](https://github.com/sachingooo/anki-filtered-deck-by-tag)
- [anki-rebuild-all — GitHub](https://github.com/Arthaey/anki-rebuild-all)
- [Anki-Karten zum Lernplan — AMBOSS Support](https://support.amboss.com/hc/de/articles/46050238019985-Anki-Karten-zum-Lernplan)
- Lokaler Quellcode Anki 26.09.3: `aqt/filtered_deck.py`, `aqt/operations/scheduling.py`,
  `anki/scheduler/base.py`, `anki/collection.py`, `_aqt/hooks.py`
