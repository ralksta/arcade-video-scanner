# Design-Spezifikation: D-Pad TV-Interface für Arcade Video Scanner

Dieses Dokument beschreibt das Design und die technische Umsetzung einer D-pad-optimierten Benutzeroberfläche (10-Foot-UI) für den Betrieb auf einem LG Smart TV (webOS Homebrew) via unverschlüsseltes HTTP.

---

## 1. Übersicht & Zielsetzung

*   **Was gebaut wird:** Eine dedizierte TV-Benutzeroberfläche (`tv.html`), gehostet im statischen Verzeichnis des Servers, sowie ein schlanker webOS Web-Wrapper (`.ipk`), der dorthin weiterleitet.
*   **Warum es existiert:** Ersetzt das mausfokussierte Desktop-Interface auf dem Fernseher durch ein Plex-artiges, flüssiges D-Pad-Interface, das sich blind mit der Fernbedienung steuern lässt.
*   **Wichtigste Features:**
    *   Links: Einklappbare Seitenleiste für Kategorien (Alle Videos, Favoriten, Zuletzt importiert).
    *   Rechts: Großes Kachelgitter (Grid) für Videos.
    *   Vollbild-Player: Startet per Klick im Vollbild, einfache Steuerung per Fernbedienung (Play/Pause, Vor-/Zurückspulen, Schließen).

---

## 2. Architektur & Komponenten

```text
/static/tv.html  (Gehostet auf dem Server)
   │
   ├── HTML Shell (Sidebar, Grid, Video Overlay)
   ├── CSS Styling (Dunkelviolettes Theme, pulsierender Neon-Cyan-Fokusring)
   └── Vanilla JS Focus Manager (Spatial Navigation Logik)
```

---

## 3. Technische Umsetzung der TV-UI (`tv.html`)

### 3.1 D-Pad Focus Manager Logik (JavaScript)

Das Script lauscht auf `keydown`-Events und steuert den aktiven Fokus visuell.

```javascript
// D-Pad Steuerungscodes
const KEYS = {
    UP: 'ArrowUp',
    DOWN: 'ArrowDown',
    LEFT: 'ArrowLeft',
    RIGHT: 'ArrowRight',
    ENTER: 'Enter',
    BACK: 'Escape', // webOS Back-Taste mappt oft auf Escape/Backspace im Browser
    BACKSPACE: 'Backspace'
};

let currentSection = 'sidebar'; // 'sidebar' oder 'grid' oder 'player'
let sidebarIndex = 0;
let gridIndex = 0;
const gridCols = 4; // 4 Spalten im Grid

function handleKeyDown(event) {
    if (currentSection === 'player') {
        handlePlayerKeys(event);
        return;
    }
    
    switch (event.key) {
        case KEYS.UP:
            navigateVertical(-1);
            break;
        case KEYS.DOWN:
            navigateVertical(1);
            break;
        case KEYS.LEFT:
            navigateHorizontal(-1);
            break;
        case KEYS.RIGHT:
            navigateHorizontal(1);
            break;
        case KEYS.ENTER:
            activateCurrentItem();
            break;
    }
}
```

### 3.2 Navigation & Grid-Mathematik

*   **Wechsel Sidebar -> Grid:** Wenn in der Sidebar `ArrowRight` gedrückt wird, wechselt `currentSection` auf `'grid'` und das erste Element der aktuellen Zeile wird fokussiert.
*   **Wechsel Grid -> Sidebar:** Wenn im Grid an Spalte 0 `ArrowLeft` gedrückt wird, springt der Fokus zurück auf das aktive Element in der Sidebar.
*   **Grid-Navigation:**
    *   Horizontal: `gridIndex = Math.max(0, Math.min(totalGridItems - 1, gridIndex + direction))`
    *   Vertikal: `gridIndex = Math.max(0, Math.min(totalGridItems - 1, gridIndex + (direction * gridCols)))`
*   **Smooth Scrolling:** Bei jedem Fokuswechsel sorgt `element.scrollIntoView({ block: 'nearest', behavior: 'smooth' })` dafür, dass das fokussierte Element zentriert bleibt.

---

## 4. Entscheidungs-Logbuch (Decision Log)

| Datum | Entscheidung | Alternativen | Begründung |
| :--- | :--- | :--- | :--- |
| 05.07.2026 | **D-Pad TV-UI gehostet auf Server** | Integrierte UI im IPK-Paket | UI-Updates erfordern kein erneutes Bauen und Installieren des `.ipk` auf dem Fernseher. |
| 05.07.2026 | **Vanilla JS Focus Manager** | Externe Bibliotheken (Enact, CAPH) | Minimale Payload, maximale Performance auf älterer TV-Hardware, kein Overhead (YAGNI). |
| 05.07.2026 | **Full-Screen Video Player Overlay** | Split-Screen-Vorschau | Simpler zu implementieren, performanter auf dem Fernseher, klassischer Kinomodus. |

---

## 5. Risiken & Edge Cases

*   **Cookie-Ablauf:** Wenn die Session auf dem TV abläuft, muss sich der Nutzer einmalig über den TV-Browser neu einloggen.
*   **Back-Taste Loop:** webOS fängt die Zurück-Taste standardmäßig ab. Wir binden `Escape` und `Backspace` ein, um den Video-Player sauber zu schließen und ins Grid zurückzukehren.
