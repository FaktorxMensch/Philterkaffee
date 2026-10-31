# Änderungen

Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [SemVer](https://semver.org/lang/de/).

## [1.0.2] — 2026-10-31

### Behoben

- Die Auswahlliste „Titel ableiten aus“ zeigte nur die nackten Tagnamen. Wer
  dort ``#Universitäten`` wählte, bekam Stapel wie „01 – 4 Semester /
  3 Semester“: zwei Ebenen unter dieser Wurzel steht das Semester und kein
  Thema. Jede Zeile nennt jetzt ein Beispiel für das Ergebnis, und Äste mit
  kaum unterscheidbaren Titeln werden als solche gekennzeichnet.
- Die Voreinstellung hängt nicht mehr fest am Namen ``#Fächer``: Äste, deren
  Titel sich kaum unterscheiden, fallen heraus, und unter den brauchbaren hat
  ``#Fächer`` den Vorzug, falls vorhanden.
- Neue Warnung in der Vorschau, wenn mehrere Lerntage denselben Stapelnamen
  bekämen und mit „(2)“, „(3)“ unterschieden werden müssten.

## [1.0.1] — 2026-10-30

### Behoben

- Der Basis-Tag ließ sich nicht umstellen: die Auswahl sprang sofort auf den
  zuletzt gespeicherten Tag zurück. Beim Wechsel wurden die Einstellungen
  erneut aus der Sammlung gelesen und haben die gerade getroffene Auswahl
  überschrieben. Mit dem Basis-Tag wechseln nun auch Plan, Lerntage,
  Prioritäts-Tags und der Facetten-Ast für die Titelableitung — sie tragen
  den alten Basis-Tag im Namen und wären sonst wertlos.
- Das Schließen des Hauptfensters scheitert nicht mehr, wenn der Dialog nicht
  bei Ankis Fensterverwaltung registriert ist.

## [1.0.0] — 2026-10-30

Erste Fassung von **Philterkaffee**.

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
