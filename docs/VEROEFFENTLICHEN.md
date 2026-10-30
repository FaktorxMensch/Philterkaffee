# Veröffentlichen auf AnkiWeb

Repository: <https://github.com/FaktorxMensch/Philterkaffee>

Stand der Recherche: 2026-10-30. Quellen am Ende.

## Was AnkiWeb verlangt — und wo wir stehen

| Anforderung | Quelle | Stand |
|---|---|---|
| Lizenz AGPL3 oder kompatibel; ohne Angabe wird AGPL3 angenommen | [Terms](https://ankiweb.net/account/terms), Abschnitt „Sharing Add-ons" | ✅ `LICENSE` = AGPL-3.0, im README und in `manifest.json` benannt |
| ZIP mit Endung `.ankiaddon` | [Sharing Add-ons](https://docs.ankiweb.net/addons/sharing) | ✅ `tools/build_ankiaddon.py` |
| Dateien **an der ZIP-Wurzel**, kein umschließender Ordner | ebd. | ✅ geprüft |
| **Kein** `__pycache__` im ZIP — AnkiWeb lehnt sonst ab | ebd. | ✅ ausgeschlossen |
| Kein `meta.json` im ZIP | [Add-on folders](https://docs.ankiweb.net/addons/addon-folders) | ✅ ausgeschlossen |
| Keine Inhalte ohne Nutzungsrecht (Copyright, **Marken**) | [Terms](https://ankiweb.net/account/terms), „Acceptable Content" | ⚠️ siehe „Name und Marken" |
| AnkiWeb-Konto zum Hochladen | [ankiweb.net/shared/addons](https://ankiweb.net/shared/addons) | ⬜ deins |
| Support-Seite / `homepage` in der `manifest.json` | — | ✅ GitHub-URL eingetragen |

`manifest.json` ist laut Doku **nur für die Weitergabe außerhalb von AnkiWeb**
nötig (`package` und `name`). Für AnkiWeb-Uploads schadet sie nicht, und für das
`.ankiaddon`, das du direkt an Kommiliton:innen gibst, ist sie nötig. Sie ist
da und vollständig.

## Was beim Hochladen noch gefragt wird

Die Upload-Seite erwartet zusätzlich:

- **Titel** — steht in der Liste und ist das, wonach gesucht wird.
- **Beschreibung** — HTML mit einer begrenzten Tag-Auswahl; einfache
  Markdown-Formatierung funktioniert. Fertiger Text unten.
- **Unterstützte Anki-Versionen** — hier **23.10** als Minimum. Das ist dieselbe
  Grenze wie `min_point_version: 231000` in der `manifest.json`.
- **Support-Seite** — <https://github.com/FaktorxMensch/Philterkaffee>. Steht
  bereits in `manifest.json` unter `homepage` und im README.

## Name und Marken

Ankis Nutzungsbedingungen verlangen, dass hochgeladene Inhalte keine fremden
**Marken**rechte verletzen. Praktische Folge für die Namenswahl:

- Ein **eigener** Name mit beschreibendem Zusatz („… für AnkiPhil-Stapel") ist
  die unbedenkliche Form: AnkiPhil und AMBOSS tauchen nur als Hinweis auf, wofür
  das Addon gedacht ist.
- Ein Name, der ein fremdes Produkt **selbst zur Marke macht**
  (etwa „AnkiPhil …" als Titel), kann den Eindruck einer Zusammenarbeit
  erwecken. Das ist der riskantere Weg.

Im README steht bereits der Hinweis, dass AnkiPhil und AMBOSS Marken ihrer
Inhaber sind und das Addon unabhängig ist. Das sollte so bleiben.

Das ist eine praktische Einschätzung, keine Rechtsberatung.

## Zwei Fallstricke beim Betrieb

**Doppelte Installation.** Addons von AnkiWeb landen in einem Ordner mit der
numerischen Addon-ID, nicht in `philterkaffee`. Wer den Entwicklungs-Symlink
behält *und* die AnkiWeb-Fassung installiert, hat das Addon zweimal laufen —
mit zwei Menüeinträgen und zwei Knöpfen. Vor dem Testen der veröffentlichten
Fassung den Symlink entfernen:

```bash
rm "$HOME/Library/Application Support/Anki2/addons21/philterkaffee"
```

**Der Code ist ordnerunabhängig.** Es gibt nur relative Importe, kein
`import philterkaffee`. Der Zahlen-Ordner von AnkiWeb macht also keine
Probleme.

## Fertiger Text für die Beschreibung

Titel, Versionsangabe und Support-URL beim Hochladen eintragen; den Rest unten
in das Beschreibungsfeld kopieren und bei Bedarf an die erlaubten HTML-Tags
anpassen.

---

Auswahlstapel für AnkiPhil, frisch aufgebrüht. Oben kippst du den Lernplan rein,
unten kommt dein Lerntag raus — das Koffein musst du selbst dazugeben.

Philterkaffee baut aus den Lernplan-Tags deines AnkiPhil-Stapels benannte,
priorisierte Auswahlstapel pro Lerntag — mit Vorschau, Nachkontrolle und einer
einzigen Rückgängig-Stufe.

Statt für 43 Lerntage einzeln einen Auswahlstapel anzulegen, Suchen abzutippen
und sich zu fragen, warum nur 95 statt 361 Karten drin sind, macht das Addon den
ganzen Plan in einem Durchgang — und sagt vorher, was passieren wird.

**Was es kann**

- Basis-Tag, Lernpläne und Lerntage werden aus deiner Sammlung gelesen. Ein
  Stapel-Update braucht keine neue Addon-Version.
- Die Lerntags-Tags tragen keinen Namen (`…::50-Tage::17`). Der Titel entsteht
  aus den häufigsten Fach-Tags der enthaltenen Karten (`17 → Herz/Kreislauf &
  Atmung`) und ist überschreibbar.
- Lerntiefe über alle Prioritäts-Achsen: Physikum, High-Yield, Top30, Formeln,
  Klinik-Relevanz — mit ODER/UND und Kartenzahlen.
- Namensmuster mit Platzhaltern, Oberstapel, freies Präfix.
- Ehrliche Vorschau: sie zählt, was Anki nach dem Umbau wirklich holt.
  Suspendierte, zurückgestellte und in fremden Auswahlstapeln liegende Karten
  werden getrennt ausgewiesen. „Gesperrte Karten zeigen" öffnet den Browser mit
  genau diesen Karten.
- Überschneidungen nachvollziehbar: frühester Lerntag gewinnt, oder Anki
  entscheiden lassen.
- Kalendermodus für ein rollierendes Fenster ab Startdatum.
- Verwaltungsfenster: neu aufbauen, entleeren, löschen, Limit und Sortierung
  nachträglich ändern.
- Karten nach Tag ein- und ausschließen (suspendieren), streng begrenzt auf den
  AnkiPhil-Tagbaum.

**Sicherheit**

- Jeder Umbau liegt in einer Rückgängig-Stufe. Ein Strg+Z nimmt Löschungen,
  Suspendierungen und alle angelegten Stapel zusammen zurück.
- Erst prüfen, dann schreiben: jede Suche wird ausgeführt und geprüft, bevor der
  erste Stapel entsteht. Danach wird jeder Stapel gegen die echten Notiz-Tags
  kontrolliert.
- Aufräumen ist ab Werk auf „nur unter dem Oberstapel" begrenzt — fremde
  Auswahlstapel werden nicht angefasst.
- Es gehen keine Karten verloren: Entleeren und Löschen schicken sie mit ihrem
  Lernstand in die Heimatstapel zurück.
- Kein automatisches Neuaufbauen beim Tageswechsel — ein Rebuild vor dem
  Synchronisieren kann Wiederholungen von anderen Geräten verwerfen.

**Bedienung**

Extras → Philterkaffee, oder der Knopf „Philterkaffee“ unten im Stapelbrowser
neben „Datei importieren“.

Benötigt Anki 23.10 oder neuer und einen installierten AnkiPhil-Stapel mit
Lernplan-Tags.

Quelltext und Support: https://github.com/FaktorxMensch/Philterkaffee

Lizenz: AGPL-3.0-or-later. AnkiPhil und AMBOSS sind Marken ihrer jeweiligen
Inhaber; Philterkaffee ist unabhängig und steht in keiner Verbindung zu ihnen.

---

## Quellen

- [Sharing Add-ons — Anki Docs](https://docs.ankiweb.net/addons/sharing)
- [Add-on folders — Anki Docs](https://docs.ankiweb.net/addons/addon-folders)
- [AnkiWeb Terms and Conditions](https://ankiweb.net/account/terms) — Abschnitte
  „Sharing Add-ons" und „Acceptable Content"
- [AnkiWeb Add-ons](https://ankiweb.net/shared/addons) — Upload
