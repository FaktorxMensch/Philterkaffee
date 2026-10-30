# Philterkaffee

**Auswahlstapel für AnkiPhil, frisch aufgebrüht.** Oben kippst du den Lernplan
rein, unten kommt dein Lerntag raus — das Koffein musst du selbst dazugeben.

Anki-Addon: baut aus den Lernplan-Tags eines AnkiPhil-Stapels benannte,
priorisierte Auswahlstapel pro Lerntag — mit Vorschau, Nachkontrolle und einer
einzigen Rückgängig-Stufe.

Benötigt Anki 23.10 oder neuer. Entwickelt und getestet gegen Anki 26.09.3.

## Installieren

Das Addon liegt als Ordner im Projekt und ist in Anki verlinkt:

```bash
ln -sfn "$PWD/philterkaffee" "$HOME/Library/Application Support/Anki2/addons21/philterkaffee"
```

Anki danach neu starten. Der Einstieg sitzt unter **Extras → Philterkaffee**
und als Knopf **„Philterkaffee“** unten im Stapelbrowser.

## Die drei Fenster

### Auswahlstapel erstellen

Links die Einstellungen, rechts die Vorschau. Solange die Vorschau nicht zum
aktuellen Stand gehört, ist „Erstellen“ gesperrt — es wird nie etwas
geschrieben, was nicht vorher gezählt und geprüft wurde.

Sobald eine Einstellung geändert wird, färbt sich „Vorschau berechnen“ ein und
trägt ein ⟳. Tabelle und Filteranzeige bleiben dabei stehen — sie gehören zum
vorigen Stand. Wer sie dann benutzt („Karten im Browser zeigen“, „Gesperrte
Karten zeigen“), wird gefragt, ob neu gerechnet werden soll; bei Nein geschieht
nichts. Nach einem erfolgreichen Aufbau schließt sich das Fenster.

1. **Lernplan** — Basis-Tag und Plan werden aus der Sammlung gelesen, nicht
   geraten. Lerntage lassen sich einzeln oder als Bereich wählen. Im
   *Kalendermodus* wird nur ein rollierendes Fenster ab einem Startdatum
   gebaut.
2. **Lerntiefe** — Physikum, High-Yield, Top30, Formeln, Klinik-Relevanz, mit
   ODER/UND verknüpft. Ohne Haken kommen alle Plan-Karten in die Stapel. Der
   Haken *„auch auf alle Karten anwenden“* suspendiert zusätzlich alles andere
   im AnkiPhil-Stapel.
3. **Welche Karten** — Voreinstellung: nur neue Karten. Optional fällige
   Wiederholungen, Begrenzung auf einen Quellstapel, freie Zusatzsuchen.
4. **Benennung** — Oberstapel, Präfix und ein Namensmuster mit Platzhaltern
   (`{nr2}`, `{titel}`, `{plan}`, `{prio}`, `{datum}`, …). Die Titel der
   Lerntage werden aus den `#Fächer`-Tags der enthaltenen Karten abgeleitet und
   sind in einer Tabelle überschreibbar.
5. **Sortierung und Limit** — Voreinstellung *Order added* (Erstelldatum,
   älteste zuerst). Retrievability-Sortierungen erscheinen nur mit aktivem FSRS.
6. **Verhalten** — Normal planen (empfohlen), leere Stapel anlegen,
   Überschneidungsstrategie.
7. **Aufräumen** — Voreinstellung: nur Auswahlstapel unter dem gewählten
   Oberstapel. Fremde Auswahlstapel werden nicht angefasst.

### Verwalten

Statustabelle aller Auswahlstapel mit Karten, neu/fällig, Limit und Sortierung.
Neu aufbauen, entleeren (= Lerntag erledigt), löschen, im Browser zeigen, und
nachträglich Limit, Sortierung oder Planung ändern, ohne das Hauptfenster neu
durchzuklicken.

### Karten ein-/ausschließen

Tagbaum des AnkiPhil-Stapels mit Karten- und Ausschlusszahlen. Drei Aktionen:
einschließen (reaktivieren), ausschließen (suspendieren) oder einen Zustand
hart setzen. Der Umfang ist immer der AnkiPhil-Tagbaum — Stapel außerhalb
werden nie angefasst.

## Was man über Auswahlstapel wissen muss

* **Eine Karte kann nur in einem Auswahlstapel liegen.** Suspendierte und
  zurückgestellte Karten werden gar nicht geholt. Die Vorschau zählt das mit
  und zeigt es in der Spalte „gesperrt“; „Gesperrte Karten zeigen“ öffnet den
  Browser mit genau diesen Karten.
* **Tageslimits der Stapel-Voreinstellungen gelten nicht.** Nur das Limit des
  Auswahlstapels zählt.
* **Die Sortierung entscheidet mit, welche Karten drin sind.** Bei erreichtem
  Limit wird am Ende der Sortierung abgeschnitten.
* **Entleeren und Löschen verlieren nichts.** Die Karten kehren mit ihrem
  Lernstand in die Heimatstapel zurück.
* **Auswahlstapel haben keine Unterstapel.** Sie dürfen unter einem normalen
  Oberstapel liegen, aber nichts unter sich haben.
* **Lernschritte kommen vom Heimatdeck.** Mit „Normal planen“ wirken Antworten
  normal auf SRS/FSRS.

## Sicherheit

* Jeder Umbau läuft in **einer** Rückgängig-Stufe — ein Strg+Z (⌘Z) nimmt
  Löschungen, Suspendierungen und alle angelegten Stapel zusammen zurück.
* Vor dem ersten Schreibvorgang wird jede Suche ausgeführt und geprüft. Erst
  wenn alles stimmt, wird geschrieben.
* Nach dem Anlegen wird jeder Stapel gegen die echten Notiz-Tags geprüft.
  Stimmt etwas nicht, bricht der Lauf mit einer Meldung ab, die auf das
  Rückgängigmachen hinweist.
* Lesen läuft in `QueryOp`, Schreiben in `CollectionOp` — Anki friert nicht ein.
* Es gibt bewusst **kein automatisches Neuaufbauen** beim Tageswechsel: ein
  Rebuild vor dem Synchronisieren kann Wiederholungen von anderen Geräten
  verwerfen.

## Einstellungen

Alles wird mit `col.set_config()` in der Sammlung gespeichert (Schlüssel
`philterkaffee`) und synchronisiert mit. Pro Profil eigene Einstellungen,
keine zweite Wahrheit in einer Datei.

## Aufbau

```
__init__.py          Menü, Dialog-Registrierung, Versionsprüfung
core/taxonomy.py     Tag-Baum entdecken: Basis, Pläne, Lerntage, Prio-Achsen
core/titles.py       Titel aus #Fächer-Tags ableiten
core/naming.py       Namensmuster und Entschärfen von Stapelnamen
core/query.py        Suchen über SearchNode (nie Stringbasteln)
core/config.py       Einstellungen
core/planner.py      Vorschau berechnen — schreibt nichts
core/builder.py      der einzige Ort, an dem geschrieben wird
ui/                  Hauptfenster, Verwalten, Lerntiefe, Titeltabelle
```

AnkiPhil-Tags enthalten `#`, `$`, `§`, `&`, `{` und literale Backslashes
(`Obere\_Extremität`). Suchen werden deshalb ausschließlich über `SearchNode`
und `col.build_search_string()` gebaut.
