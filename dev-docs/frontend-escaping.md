# Maskierung im Frontend: Stand und offene Punkte

**Stand: 2026-08-17**, erhoben im Nachtlauf.

## Warum das ein Thema ist

Dateinamen dürfen auf jedem gängigen Dateisystem fast jedes Zeichen enthalten,
spitze Klammern eingeschlossen. Das Dashboard baut seine Oberfläche über
`innerHTML` aus Template-Strings. Ein Name wie

```
<img src=x onerror=fetch('/api/…')>.mp4
```

führt damit beim Anzeigen Code aus — in der Sitzung des angemeldeten Nutzers,
mit dessen Rechten auf allen Endpunkten.

Für eine Bibliothek aus heruntergeladenen Dateien ist das kein konstruierter
Fall: der Name kommt von außen, und Anzeigen genügt. Der Nutzer muss nichts
anklicken.

## Was behoben ist

`createVideoCard()` in `engine.js` — der Pfad, über den **jede** Datei der
Bibliothek läuft. Dateiname, Verzeichnisname und vollständiger Pfad gehen jetzt
durch `escapeHtml()`, sowohl im Text als auch in den `title`-Attributen.

`createComparisonCard()` in `engine.js` — die Gegenüberstellung von Original und
optimierter Fassung in der Review-Ansicht, beide Seiten.

Abgesichert durch `tests/test_filename_escaping.py`.

Unkritisch, aber leicht zu verwechseln: `container.setAttribute('data-path',
v.FilePath)` setzt den rohen Pfad — `setAttribute` maskiert selbst. Wird das je
auf String-Interpolation umgestellt, ist es eine Lücke; ein Test hält es fest.

## Behoben in einer zweiten Runde (Loop J)

`tag_manager.js` und `folder_browser.js` — die beiden Dateien, die unten als
vorrangig benannt waren, weil sie die einzigen mit echtem Fremdeinfluss sind
(frei eingegebene Tags, Ordnernamen vom Dateisystem).

Gefunden wurden **fünf interpolierte `onclick`-Handler**:

```javascript
onclick="deleteTag('${t.name}')"
onclick="toggleTagFilter('${tag.name}')"
onclick="toggleBatchTagOption('${tag.name}')"
onclick="editTagShortcut('${t.name}', '${shortcutValue}')"
onclick="setFolderBrowserPath('${crumb.path.replace(/'/g, "\\'")}')"
```

Der letzte war sogar abgesichert — aber nur gegen Apostrophe. Das Attribut wird
von *Anführungszeichen* begrenzt: ein Ordner namens `a"onmouseover=…` bricht
trotzdem aus.

Alle fünf Renderer bauen jetzt DOM-Knoten mit `textContent` und
`addEventListener`. Farben gehen über `style.backgroundColor` statt über
interpolierte `style`-Attribute — ungültige Werte verwirft der Browser dann,
statt Markup zu übernehmen.

Die Zahl der Interpolationen von Namensfeldern ist damit von 87 auf 60
gefallen. Der Rest betrifft Felder ohne Fremdeinfluss (Zahlen, feste Auswahl,
bereits geprüfte Werte) — die Angriffsfläche ist abgedeckt.

## Was offen ist

Eine Erhebung über alle statischen JS-Dateien fand **87 Interpolationen** von
Namens-, Pfad- oder Tag-Feldern ohne sichtbare Maskierung:

| Datei | Fundstellen |
|---|---|
| `engine.js` | 21 |
| `folder_browser.js` | 15 |
| `tag_manager.js` | 15 |
| `collections.js` | 12 |
| `cinema.js` | 7 |
| übrige (autotag, context_menu, batch_operations, optimizer, settings, shortcuts, candidates, export_view, treemap) | 17 |

Ein erheblicher Teil davon sind Fehlalarme der Suche: interpolierte Zahlen,
bereits geprüfte Konstanten, Werte aus fester Auswahl. Welche davon echt sind,
lässt sich nur einzeln beurteilen — Fundstelle für Fundstelle, mit Blick auf die
Herkunft des Wertes.

Bewusst nicht heute Nacht pauschal umgestellt: `escapeHtml()` über alle 87
Stellen zu ziehen, würde dort, wo bereits maskiert oder bewusst Markup
eingesetzt wird, sichtbaren Schaden anrichten (doppelt maskierte Anzeigen,
zerstörte Icon-Spans) — und ohne Browser ließe sich das Ergebnis nicht prüfen.

## Empfohlenes Vorgehen

1. Nach Herkunft sortieren statt nach Datei: Was stammt aus einem Dateinamen
   oder einem frei eingegebenen Tag? Nur das ist Angriffsfläche.
2. `folder_browser.js` und `tag_manager.js` zuerst — Ordnernamen und
   selbstvergebene Tags sind beides frei wählbare Zeichenketten.
3. Beim Umbau die Alternative erwägen: Knoten über `document.createElement` und
   `textContent` bauen statt zu interpolieren. Das kann gar nicht schiefgehen.
   In `settings.js` (View-Chips) wurde in derselben Nacht genau so umgestellt,
   nachdem sich zeigte, dass `escapeHtml` für JS-in-Attribut ohnehin nicht
   ausreicht: der HTML-Parser löst `&#39;` auf, bevor der JS-Parser die Zeile
   sieht.
