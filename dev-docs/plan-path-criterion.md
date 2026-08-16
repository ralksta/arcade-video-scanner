# Plan: Ordner-Navigation & Path-Kriterium

Zwei Teile, unabhängig voneinander umsetzbar:

- **Teil 1** — Path-Kriterium für Smart Collections (mit Autocomplete) — *offen*
- **Teil 2** — Hierarchischer Folder-Browser auf Mobile (Root-Ebene-Bugfix) —
  **umgesetzt** (siehe CHANGELOG, Abschnitt Unreleased)

Teil 2 ist der kleinere Eingriff und löst das eigentliche Alltagsproblem
(„durchklicken statt filtern"). Teil 1 ist die dauerhafte, kombinierbare Variante.

---

# Teil 1: Path-Kriterium für Smart Collections

## Motivation

Ordner-Navigation nach einem bestimmten Unterbaum (Beispiel: `/media_ralf/OD`, 510 von
8776 Dateien) ist heute umständlich:

- **Ordner-Sidebar** (`setFolderFilter`) filtert **exakt** auf ein Verzeichnis, nicht
  rekursiv — `filter_engine.js:232` vergleicht `folder !== currentFolder`. Unterordner
  fallen raus.
- **Folder-Browser** (`view=folderbrowser`) kann Hierarchie, ist auf dem Handy aber nicht
  erreichbar: die View-Toggle-Leiste ist `hidden md:flex` (`components.py:2133`).
  Nur per Deep-Link `/lobby?view=folderbrowser&folderPath=%2Fmedia_ralf%2FOD`.
- **Smart Collections** kennen kein Pfad-Kriterium. Workaround ist heute
  `criteria.search = "/Media_Ralf/OD"` (Collection `RalfoOD`), was aktuell exakt die
  richtigen 510 Dateien trifft.

Grenzen des Search-Workarounds:

1. **Keine Ordnergrenze** — Substring-Match. Ein künftiges `/media_ralf/ODX/` oder ein
   Dateiname mit diesem String würde mitgezählt.
2. **Search-Feld ist belegt** — „alles unter OD, aber nur Dateien mit `web` im Namen"
   ist in einer Collection nicht ausdrückbar.
3. **Nur ein Pfad, kein Ausschluss** — „OD, aber ohne `archiv`" geht nicht.

## Ziel

`criteria.include.path[]` / `criteria.exclude.path[]` als vollwertiges Kriterium,
mit Präfix-Match auf Ordnergrenze und Autocomplete über die bekannten Ordner.

## Umfang

Rein clientseitig plus Template-Markup. **Kein Server-Change nötig**, keine
Schema-Migration: Collections werden als JSON in `users.db` (`user_data`)
gespeichert, neue Felder sind additiv.

### 1. Schema (`collections.js`)

`getDefaultCollectionCriteria()` um `path: []` in `include` und `exclude` erweitern.
Alte Collections ohne das Feld laufen unverändert weiter (überall `?.length > 0`-Guards).

### 2. Matching (`collections.js`, `evaluateCollectionMatch`)

Neuer Helper, Ordnergrenzen-sicher und case-insensitiv (Rest der Funktion ist es auch):

```js
const underPath = (filePath, prefix) => {
    const f = filePath.replace(/\\/g, '/').toLowerCase();
    const p = prefix.replace(/\\/g, '/').toLowerCase().replace(/\/+$/, '');
    return f === p || f.startsWith(p + '/');
};
```

- Exclude zuerst (konsistent zum bestehenden Aufbau): trifft ein `exclude.path`-Eintrag,
  raus.
- Include: `inc.path.length > 0 && !inc.path.some(p => underPath(video.FilePath, p))`
  → raus. Mehrere Include-Pfade sind ODER-verknüpft, wie bei den anderen Include-Listen.

Einzubauen bei den übrigen Exclusions/Inclusions, vor dem Search-Block.

### 3. Autocomplete-Datenquelle (neu, `collections.js`)

`window.FOLDERS_DATA` (aus `dashboard_template.py:38-47`) enthält nur **Blatt**-Verzeichnisse
(solche, die direkt Dateien haben) mit `count`/`size_mb`. Für die Vorschlagsliste brauchen
wir auch die Elternpfade:

```js
function getAllKnownFolders() {
    // leaf paths -> alle Präfixe ableiten, counts/size aufsummieren
    // Rückgabe: [{path, count, size_mb}], sortiert nach count desc
}
```

Ergebnis für die aktuelle Library: ~600 Pfade inkl. `/media_ralf/OD`, `/media_ralf/OD/ProSessions` usw.
Einmal berechnen und cachen (Modul-Level-Variable), Invalidierung beim Rescan.

### 4. UI (`components.py` + `collections.js`)

Im Collection-Modal, neuer Block im `metadata`-Panel direkt über „Search Term"
(`components.py:1203-1209`):

- `#collectionPathInput` — Text-Input mit `list="collectionPathOptions"`
- `#collectionPathOptions` — `<datalist>`, gefüllt aus `getAllKnownFolders()`
  (Label mit Count, z.B. `/media_ralf/OD (510)`)
- `#collectionPathChips` — Container für die gesetzten Pfade als Chips, Klick auf
  Chip togglet include ↔ exclude, X entfernt
- Handler als `window.*` exportieren: `addCollectionPath()`, `removeCollectionPath(path)`,
  `toggleCollectionPathMode(path)`

Datalist ist die billigste Variante und funktioniert auf Mobile (iOS Safari zeigt sie
als Vorschlagsleiste). Falls das zu schwach ist: eigene gefilterte Dropdown-Liste,
gleiche Datenquelle.

### 5. Persistenz & Sync

- `saveCollection()` (`collections.js:346ff`) kopiert `collectionCriteriaNew` komplett —
  Pfade kommen automatisch mit, sobald sie im State stehen.
- `syncSmartCollectionUI()` um das Rendern der Path-Chips erweitern.
- `updateFilterSectionBadge('metadata')` um die Pfad-Anzahl erweitern
  (`collections.js:194-208`).
- `updateCollectionPreviewCount()` braucht nichts Zusätzliches, solange die Pfade im
  State stehen (es kopiert `collectionCriteriaNew`) — nur prüfen, dass ein noch nicht
  bestätigter Text im Input nicht verloren geht.

### 6. Tests

- `test_dom_contract.py`: neue IDs (`collectionPathInput`, `collectionPathOptions`,
  `collectionPathChips`) müssen im Python-Template auftauchen, `onclick` muss `window.*`
  sein. Dynamisch erzeugte Chip-IDs ggf. in `DYNAMIC_IDS`.
- `test_js_syntax.py` läuft automatisch mit (`node --check`).
- Neuer Test für `underPath`-Semantik wäre sinnvoll, sofern die JS-Contract-Tests so
  etwas hergeben — sonst mindestens manuell: `/media_ralf/OD` darf `/media_ralf/ODX/x.mp4`
  **nicht** matchen.

### 7. Andere Clients

`ios_client/SmartCollection.swift` und `tv_client/src/views/MainPanel.js` werten
Collection-Kriterien eigenständig aus. Sie ignorieren unbekannte Felder, d.h. eine
Collection mit Path-Kriterium zeigt dort **zu viele** Treffer. Nachziehen als
Folgeschritt, nicht Teil dieses Plans.

## Offene Punkte

- Migration der bestehenden `RalfoOD`-Collection (`search: "/Media_Ralf/OD"`) auf
  `include.path` — automatisch oder manuell? Automatisch wäre heuristisch (Search-Term
  sieht aus wie Pfad), manuell ist ein Klick. Tendenz: manuell.
- Soll der Folder-Browser einen „als Collection speichern"-Button bekommen, der den
  aktuellen `folderPath` direkt in eine neue Collection schreibt?

---

# Teil 2: Hierarchischer Folder-Browser auf Mobile

**Status: umgesetzt.** Was unten als Vorschlag steht, ist so gebaut worden —
Abweichungen sind am Ende unter „Abweichungen bei der Umsetzung" vermerkt.

## Befund

Der Folder-Browser kann Hierarchie bereits vollständig:

- Drill-down: `setFolderBrowserPath()` (`folder_browser.js:295`)
- Breadcrumbs: `getFolderBreadcrumbs()` (`folder_browser.js:348`)
- Zurück: `folderBrowserBack()` (`folder_browser.js:304`)
- Zwischenebenen: der `else`-Zweig von `getSubfoldersAt(path)` leitet die nächste Ebene
  korrekt aus den Pfadsegmenten ab — auch für Ordner, die selbst keine Dateien enthalten.

**Der Bug sitzt allein in der Root-Ebene.** `getSubfoldersAt(null)`
(`folder_browser.js:135-145`) definiert einen Root-Ordner als „Pfad, der kein Präfix
eines *anderen Ordners mit Dateien* hat". Da Mount-Verzeichnisse wie `/media_ralf`
selbst keine Dateien direkt enthalten, ist jeder tiefe Blattordner sein eigener Root.

Messung an der aktuellen Library (8776 Dateien, 213 Blatt-Verzeichnisse):

| | |
|---|---|
| Root-Einträge nach aktueller Logik | **153** (flach, tiefe Pfade) |
| Erwartete Root-Einträge | **3** (`/media`, `/media_nas`, `/media_ralf`) |
| Ebene 2 unter `/media_ralf` | `OD` (510), `Reface` (73), `korea` (38) |

Daher wirkt die View wie „Liste der größten Ordner" statt wie ein Datei-Browser.

Zweites Hindernis: Die View ist auf dem Handy gar nicht erreichbar — die
View-Toggle-Leiste ist `hidden md:flex` (`components.py:2133`).

## Änderung 1 — Root-Ebene aus dem echten Pfad-Baum

`getSubfoldersAt(null)` umbauen: statt „ist Präfix eines anderen Blattpfads" die Root-Menge
aus den Pfadsegmenten ableiten, analog zum bereits korrekten `else`-Zweig — nur mit
`normalizedPath = ''` als Startpunkt. Das ergibt automatisch die Mount-Ebene, und die
bestehende Aggregation (`count`, `size_mb`, `hasSubfolders`, Thumbnails über
`getVideosUnderPath()`) greift unverändert.

Damit werden Root- und Kind-Fall zum selben Code — der Sonderzweig kann ganz entfallen.

Optional, danach zu bewerten: **Single-Child-Kompression**. Hat eine Ebene genau einen
Unterordner und keine eigenen Dateien, direkt eine Ebene tiefer springen (Breadcrumb zeigt
`media_ralf / OD`). Spart bei tiefen Bäumen Taps. Erst nach dem Basisfix entscheiden — evtl.
verwirrender als nützlich.

Achtung bei `folderBrowserBack()` (`folder_browser.js:325-333`): die Funktion ruft
`getSubfoldersAt(null)` auf, um zu prüfen, ob der Parent ein Root ist. Mit der neuen
Root-Definition stimmt das weiterhin, aber der Pfad-Vergleich muss den Mount-Fall
(`/media_ralf` → Root, `lastSlash === 0`) sauber treffen. Gleiches gilt für
`getFolderBreadcrumbs()`.

## Änderung 2 — Erreichbarkeit auf Mobile

**Harte Anforderung: Die Ordner-Navigation muss auf dem Handy voll nutzbar sein, nicht nur
technisch erreichbar.**

### 2a. Einstiegspunkt in der Mobile-Bottom-Nav

Es gibt bereits eine Mobile-Navigation: `ui_components.py:189`, `md:hidden fixed bottom-0`.
**Vault wurde dort bereits entfernt** (erledigt), aktuell vier Buttons: Lobby, Favs, Review,
Search — à `w-12`.

Damit ist ein Slot frei: dort kommt der Button **Ordner** (`folder`-Icon) rein, der
`setLayout('folderbrowser')` aufruft. Fünf `w-12`-Buttons passen auch auf 375px-Viewports.

Anmerkung zu Vault: der Workspace ist nur aus der Mobile-Nav verschwunden, nicht entfernt —
`/vault` als Deep-Link und der Desktop-Zugang funktionieren weiter. Ob Vault mobil ganz
wegfällt, ist noch offen.

Das ist der eigentliche Fix. Der Desktop-Toggle (`#viewToggleFolder`, `components.py:2150`)
steckt in einem `hidden md:flex`-Container zusammen mit dem Grid-Scale-Slider; den mobil
einzublenden wäre die schlechtere Lösung (Slider ist auf dem Handy nutzlos, vier
Icon-Buttons quetschen die Toolbar).

### 2b. Ordnerliste mobiltauglich rendern

`createFolderCard()` (`folder_browser.js:390`) baut große Karten mit 2x2-Thumbnail-Mosaik,
`aspect-video` und Hover-Overlay. Auf dem Handy heißt das: **ein Ordner pro Bildschirm**,
und die Hover-Effekte (`group-hover:*`) sind auf Touch tote Fläche.

Vorschlag: unterhalb `md` eine kompakte Listendarstellung statt der Karten — Zeile mit
kleinem Thumbnail (~56px), Ordnername, `count` + Größe als Subline, Chevron rechts.
Tap-Ziel mindestens 44px hoch. Damit sind 8-10 Ordner gleichzeitig sichtbar und
Durchklicken fühlt sich wie ein Dateimanager an.

### 2c. Breadcrumbs und Zurück

- Breadcrumb-Leiste (`getFolderBreadcrumbs()`) muss auf schmalen Viewports horizontal
  scrollen (`overflow-x-auto`, `whitespace-nowrap`) statt umzubrechen oder zu überlaufen.
  Bei tiefen Pfaden ggf. mittlere Segmente zu `…` kürzen, erstes und letztes behalten.
- Der Zurück-Button muss auf Mobile sichtbar sein (nicht nur `folderBrowserBack()` per
  Toolbar) — idealerweise als Pfeil links in der Breadcrumb-Zeile.
- **Achtung, bestehender Konflikt:** Es gibt zwei konkurrierende Popstate-Handler —
  `window.addEventListener('popstate', ...)` (`engine.js:579`) *und*
  `window.onpopstate = ...` (`engine.js:902`). Beide feuern; der erste stellt den State
  wieder her, der zweite ruft danach `loadFromURL()`. Das ist beim Hardware-/Browser-Back
  auf dem Handy zu prüfen, sonst springt die Navigation. Sollte im Zuge dieser Änderung
  auf einen Handler zusammengeführt werden.

## Tests

- `test_dom_contract.py`: neuer Nav-Button braucht `onclick="window.setLayout(...)"`-Form
  bzw. muss dem bestehenden Muster der Nachbarbuttons folgen.
- Root-Ebene manuell gegenprüfen: 3 Einträge statt 153, `/media_ralf` → `OD`/`korea`/`Reface`.
- Zurück-Navigation von tief unten bis Root ohne Sackgasse — einmal per UI-Button, einmal
  per Browser-Back.
- Am echten Handy (nicht nur DevTools-Emulation) gegenprüfen: Tap-Ziele, Breadcrumb-Scroll,
  Bottom-Nav-Überlappung mit der Ordnerliste (`pb-safe-bottom` beachten).

## Abweichungen bei der Umsetzung

- **Single-Child-Kompression nicht gebaut** — erst nach Praxistest entscheiden.
- **Popstate-Konflikt gleich mitbehoben**, weil er den Handy-Zurück-Button direkt
  betrifft: `window.onpopstate` in `engine.js` entfernt (der
  `addEventListener('popstate')` weiter oben bleibt der einzige Handler), und
  `loadFromURL()` setzt `folderBrowserState.currentPath` jetzt auf `null`, wenn die URL
  keinen `folderPath` trägt.
- **Breadcrumbs komplett neu** statt nur angepasst: sie hingen ebenfalls an der alten
  Root-Erkennung (`getSubfoldersAt(null)`) und werden jetzt direkt aus den
  Pfadsegmenten gebaut. Jede Ebene ist ein Präfix des Originalpfads, dadurch bleiben
  Backslash-Pfade unverändert erhalten.
- **Verifikation**: Die Ebenen-Logik wurde per Node-Harness gegen alle 8776 echten
  Pfade geprüft — Root liefert 3 Mounts (vorher 153 Einträge), Summe der Root-Counts
  entspricht der Gesamtzahl, Zurück-Navigation läuft von `…/ProSessions/Lena` ohne
  Sackgasse bis `null`, Windows-Backslash-Pfade werden korrekt rekonstruiert.
  Nicht abgedeckt: das tatsächliche Aussehen am Gerät.

## Offen aus Teil 2

- Optische Prüfung am echten Handy (Tap-Ziele, Breadcrumb-Scroll, Überlappung mit der
  Bottom-Nav).
- Entscheidung, ob Vault mobil ganz entfällt.
- Single-Child-Kompression.

## Beziehung zu Teil 1

Unabhängig, aber sie ergänzen sich: Teil 2 ist zum Stöbern, Teil 1 zum Festhalten. Der
naheliegende Verbindungspunkt ist ein „als Collection speichern"-Button im Folder-Browser,
der den aktuellen `folderPath` als `include.path` in eine neue Collection schreibt (siehe
offene Punkte Teil 1).

---

# Nebenbei aufgefallen (separat entscheiden)

- Ordner-Sidebar rekursiv machen: `getVideosUnderPath()` existiert bereits in
  `folder_browser.js`, wird vom Sidebar-Filter (`setFolderFilter` → exakter Vergleich in
  `filter_engine.js:232`) nur nicht genutzt.
