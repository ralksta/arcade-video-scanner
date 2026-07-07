# 🚀 Arcade Video Scanner: Performance & UI Roadmap

Moin moin! Hier ist die gesammelte Übersicht über unsere letzte "Werft-Aktion" und die Pläne für den nächsten Stapellauf.

---

## 🏎️ Performance Audit: Was wir gefixt haben

Wir haben den Motor einmal komplett auseinandergenommen und auf Hochleistung getrimmt.

### 1. Backend & Datenbank (The Engine)
*   **SQLite Tuning**: 
    *   `Cache-Size` auf 64MB erhöht.
    *   `Memory Temp Store` & `256MB MMAP` aktiviert.
    *   **Resultat**: Abfragen sind jetzt blitzschnell, auch bei riesigen Mediatheken.
*   **Streaming Scanner**: 
    *   Kein langes Warten mehr beim "Walking directories...". 
    *   Die Analyse startet sofort beim ersten gefundenen File.
*   **Batch Writes**: 
    *   Implementierung von `bulk_upsert`. 
    *   Schreibvorgänge werden gesammelt (100er Pakete), was den Disk-I/O massiv entlastet.
*   **Thumbnail-Lookup**: 
    *   O(1) statt O(N). Die Suche nach dem Quellvideo für Thumbs nutzt jetzt einen dedizierten Index.

### 2. Frontend (The Cockpit)
*   **Smart Hydration**: Metadaten werden einmalig beim Laden berechnet (Filename, Folder, Codec-Lower).
*   **Single-Pass Filter**: Die Filter-Engine berechnet alle Statistiken (Größe, Count, Bitrate) in einem einzigen Durchlauf.
*   **Smooth UX**: Aktionen wie "Keep Optimized" entfernen Cards nun mit einer Animation, statt die ganze Seite neu zu laden.

---

## 🎨 UI/UX Roadmap: Die nächsten Upgrades

Um den "Arcade"-Vibe auf das nächste Level zu heben, schlage ich folgende Module vor:

### A. Das "Command Center" HUD
*   **Visual Scanline**: Ein dezenter, pulsierender Neon-Strich, der während eines Scans durch den Header läuft.
*   **Status Indicators**: Live-Anzeige der Scanner-Aktivität in der Sidebar mit Glas-Effekt (`backdrop-filter`).

### B. Immersive Media Cards
*   **Micro-Previews**: Automatischer kleiner Loop beim Hovern über eine Card.
*   **Dynamic Glow**: Cards von `HIGH` Bitrate Videos bekommen einen subtilen Cyan-Glow am Rand.
*   **Parallax Tilt**: Die Card neigt sich leicht unter dem Cursor für mehr Tiefe.

### C. Library Health Dashboard
*   **Tacho-Design**: Eine Übersicht über gesparten Speicherplatz und die Verteilung der Codecs (H264, HEVC, AV1).
*   **Redundancy Check**: Direkte Anzeige der größten Speicherfresser und Dubletten-Gruppen.

### D. Batch Action Dock
*   **HUD Interface**: Ein am unteren Bildschirmrand fixiertes Menü, das nur auftaucht, wenn mehrere Items markiert sind.
*   **Multi-Tasking**: Schnelles Tagging, Verschieben oder Löschen von hunderten Files in einem Rutsch.

---

## ⚓️ Nächste Schritte

1.  **UI-Prototyping**: Erstellen der CSS-Klassen für den "Glassmorphism" Style in `styles.css`.
2.  **Batch Actions**: Implementierung der Logik für das Batch-Dock in `batch_operations.js`.
3.  **Stats Visualisierung**: Einbau der ersten Charts (SVG-basiert) für das Health-Dashboard.

**Der Kurs steht! Viel Spaß beim Scannen!** 🚢💨
