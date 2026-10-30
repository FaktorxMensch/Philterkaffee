<img src="philterkaffee/assets/logo-128.png" width="96" align="right" alt="">

# Philterkaffee

**Auswahlstapel für AnkiPhil, frisch aufgebrüht.** Oben kippst du den Lernplan
rein, unten kommt dein Lerntag raus — das Koffein musst du selbst dazugeben.

Ein Anki-Addon fürs Physikum: es baut aus den Lernplan-Tags deines
AnkiPhil-Stapels benannte, priorisierte Auswahlstapel pro Lerntag — mit
Vorschau, Nachkontrolle und einer einzigen Rückgängig-Stufe.

Statt für 43 Lerntage einzeln einen Auswahlstapel anzulegen, Suchen abzutippen
und sich zu fragen, warum nur 95 statt 361 Karten drin sind, macht das Addon
den ganzen Plan in einem Durchgang — und sagt vorher, was passieren wird.

Benötigt **Anki 23.10 oder neuer** (entwickelt gegen 26.09.3) und einen
installierten AnkiPhil-Stapel mit Lernplan-Tags.

---

## Installieren

**Fertiges Paket** (zum Weitergeben): `dist/philterkaffee-1.0.0.ankiaddon`
verschicken. In Anki: `Extras → Add-ons → Aus Datei installieren …`, danach
Anki neu starten.

Neu bauen mit:

```bash
python3 tools/build_ankiaddon.py
```

**Zum Entwickeln** den Addon-Ordner direkt verlinken:

```bash
ln -sfn "$PWD/philterkaffee" "$HOME/Library/Application Support/Anki2/addons21/philterkaffee"
```

## Bedienen

Unter **Extras → Philterkaffee**, und als Knopf **„Philterkaffee"** unten im
Stapelbrowser neben „Datei importieren".

| Menüeintrag | Was es tut |
|---|---|
| Auswahlstapel erstellen … | Das Hauptfenster: Plan, Lerntiefe, Benennung, Vorschau, Aufbau |
| Auswahlstapel verwalten … | Statustabelle, neu aufbauen, entleeren, löschen, Limit/Sortierung ändern |
| Alle neu aufbauen | Sofort, ohne Fenster, in Lerntagsreihenfolge |
| Einzelnen Stapel neu aufbauen ▸ | Untermenü mit den Lerntagen, füllt sich beim Öffnen |
| Alle entleeren | Alle Karten zurück in die Heimatstapel |
| Karten ein-/ausschließen … | Suspendieren und Reaktivieren nach Tag, im ganzen AnkiPhil-Stapel |

Die ausführliche Beschreibung steht in
[philterkaffee/README.md](philterkaffee/README.md).

## Was es kann

- **Nichts ist fest verdrahtet.** Basis-Tag, Lernpläne und Lerntage werden aus
  der Sammlung gelesen — ein Stapel-Update auf v6.1 braucht keine Codeänderung.
- **Titel aus den Fach-Tags.** Die Lerntags-Tags tragen keinen Namen
  (`…::50-Tage::17`). Der Titel entsteht aus den häufigsten `#Fächer`-Tags der
  enthaltenen Karten (`17 → Herz/Kreislauf & Atmung`) und ist überschreibbar.
- **Lerntiefe über alle fünf Prioritäts-Achsen** — Physikum, High-Yield, Top30,
  Formeln, Klinik-Relevanz, mit ODER/UND und Notizzahlen.
- **Ehrliche Vorschau.** Sie zählt, was Anki nach dem Umbau wirklich holt:
  suspendierte, zurückgestellte und in fremden Auswahlstapeln liegende Karten
  werden getrennt ausgewiesen, und zu löschende Stapel geben ihre Karten
  vorher frei. „Gesperrte Karten zeigen" öffnet den Browser mit genau diesen
  Karten.
- **Namensmuster** mit Platzhaltern, Oberstapel, freiem Präfix.
- **Überschneidungen** nachvollziehbar: frühester Lerntag gewinnt (im Filter
  festgeschrieben) oder Anki entscheiden lassen.
- **Kalendermodus** für ein rollierendes Fenster ab Startdatum — der
  verlustfreie Weg bei Plänen mit vielen Überschneidungen.
- **Einstellungen bleiben.** Sie liegen in der Sammlung (`col.set_config`) und
  synchronisieren mit; beim nächsten Öffnen steht alles wie zuletzt.

## Sicherheit

- Jeder Umbau liegt in **einer** Rückgängig-Stufe. Ein Strg+Z (⌘Z) nimmt
  Löschungen, Suspendierungen und alle angelegten Stapel zusammen zurück.
- **Erst prüfen, dann schreiben.** Jede Suche wird ausgeführt und geprüft,
  bevor der erste Stapel entsteht.
- Nach dem Anlegen wird jeder Stapel gegen die **echten Notiz-Tags** geprüft.
- Aufräumen ist ab Werk auf „nur unter dem Oberstapel" gestellt — fremde
  Auswahlstapel werden nicht angefasst.
- Suspendieren bleibt strikt im AnkiPhil-Tagbaum.
- Lesen läuft in `QueryOp`, Schreiben in `CollectionOp` — Anki friert nicht ein.
- **Kein automatisches Neuaufbauen** beim Tageswechsel: ein Rebuild vor dem
  Synchronisieren kann Wiederholungen von anderen Geräten verwerfen.

Es gehen in keinem Fall Karten verloren. Entleeren und Löschen schicken sie mit
ihrem Lernstand in die Heimatstapel zurück.

## Aufbau

```
philterkaffee/
  __init__.py        Menü, Knopf im Stapelbrowser, Dialog-Registrierung
  branding.py        Name, Version, Urheber, Symbol
  core/              Logik ohne Oberfläche — einzeln testbar
    taxonomy.py        Tag-Baum entdecken
    titles.py          Titel aus #Fächer ableiten
    naming.py          Namensmuster
    query.py           Suchen über SearchNode
    config.py          Einstellungen
    planner.py         Vorschau berechnen — schreibt nichts
    builder.py         der einzige Ort, an dem geschrieben wird
  ui/                Hauptfenster, Verwalten, Lerntiefe, Titeltabelle
tools/build_ankiaddon.py   verteilbares Paket bauen
```

AnkiPhil-Tags enthalten `#`, `$`, `§`, `&`, `{` und literale Backslashes
(`Obere\_Extremität`). Suchen werden deshalb ausschließlich über `SearchNode`
und `col.build_search_string()` gebaut, nie durch Zusammensetzen von Text.

## Veröffentlichen

[docs/VEROEFFENTLICHEN.md](docs/VEROEFFENTLICHEN.md) hält fest, was AnkiWeb
verlangt (Lizenz, Paketform, Marken), was beim Hochladen abgefragt wird, und
enthält den fertigen Text für die Beschreibung.

## Hintergrund

[ANALYSE_UND_PLAN.md](ANALYSE_UND_PLAN.md) hält fest, was im AnkiPhil-Stapel
tatsächlich steckt (gemessen, nicht geschätzt), wie Auswahlstapel sich
verhalten, und warum einzelne Entscheidungen so getroffen wurden.

`anki_m1_intensiv_auswahlstapel.py` im Wurzelverzeichnis ist das
Vorgänger-Skript für die Debug-Konsole. Es wird vom Addon vollständig ersetzt
und liegt nur noch zum Nachschlagen dabei.

## Lizenz und Urheber

© 2026 Faktor Mensch MEDIA UG (haftungsbeschränkt), Emanuel Leube.
<https://github.com/FaktorxMensch/Philterkaffee>

Lizenziert unter der **GNU Affero General Public License, Version 3 oder
später** ([LICENSE](LICENSE)) — wie Anki selbst, mit dem das Addon im selben
Prozess läuft.

AnkiPhil und AMBOSS sind Marken ihrer jeweiligen Inhaber. Philterkaffee ist ein
unabhängiges Werkzeug und steht in keiner Verbindung zu ihnen.
