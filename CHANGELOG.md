# Änderungen

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [SemVer](https://semver.org/lang/de/).

## [1.0.0] — 2026-10-30

Erste Fassung.

### Neu

- **Auswahlstapel erstellen** — Lernplan, Lerntage, Lerntiefe über alle fünf
  Prioritäts-Achsen, Kartenzustand, Namensmuster mit Platzhaltern, Oberstapel,
  Sortierung, Limit, Überschneidungsstrategie und Aufräumen. Mit Vorschau, die
  zählt, was Anki nach dem Umbau tatsächlich holt.
- **Titel der Lerntage** werden aus den `#Fächer`-Tags der enthaltenen Karten
  abgeleitet und sind in einer Tabelle überschreibbar.
- **Kalendermodus** — rollierendes Fenster ab einem Startdatum.
- **Auswahlstapel verwalten** — Statustabelle, einzeln oder alle neu aufbauen,
  entleeren, löschen, Limit/Sortierung/Planung nachträglich ändern.
- **Karten ein-/ausschließen** — Suspendieren und Reaktivieren nach Tag, streng
  begrenzt auf den AnkiPhil-Tagbaum.
- **Schnellzugriffe** — Menü mit „Alle neu aufbauen", Untermenü je Lerntag,
  „Alle entleeren"; Knopf „Lernplan" unten im Stapelbrowser.
- Einstellungen liegen in der Sammlung (`col.set_config`) und synchronisieren
  mit.

### Sicherheit

- Jeder Umbau liegt in **einer** Rückgängig-Stufe.
- Erst prüfen, dann schreiben; danach Nachkontrolle gegen die echten Notiz-Tags.
- Aufräumen ab Werk auf „nur unter dem Oberstapel" begrenzt.
- Lesen in `QueryOp`, Schreiben in `CollectionOp` — die Oberfläche friert nicht
  ein.

### Ersetzt

- Das Debug-Konsolen-Skript `anki_m1_intensiv_auswahlstapel.py`, das zum
  Nachschlagen beiliegt.
