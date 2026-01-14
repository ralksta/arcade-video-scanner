# 💡 Ideen & Vorschläge für Arcade Media Scanner

Basierend auf der aktuellen Roadmap und der Code-Struktur habe ich ein paar Konzepte entwickelt, die das Projekt auf die nächste Stufe heben könnten.

## 1. Content Intelligence (Die "Smarte" Ebene)
*Aktuell scannen wir nur technische Metadaten. Lass uns den **Inhalt** verstehen.*

### 🧠 Semantic Search & Transcription ("Finde den Moment")
Integration von **OpenAI Whisper** (lokal, läuft super auf Mac/GPU) oder einfachen Vektoren.
- **Idee**: Transkribiere gesprochenen Text in Videos automatisch.
- **Use Case**: Du suchst nach "Bossfight" oder einem Moment, wo jemand "Game Over" ruft? Die Suche findet die exakte Sekunde im Video.
- **Machbarkeit**: Mittel (Whisper.cpp ist sehr effizient).


---

## 2. Der "Automated Curator" (Workflow Automation)
*Weg von manueller Pflege hin zu regelbasierten Aktionen.*

### ⚡ Smart Rules Engine
Ein "Wenn-Dann"-System für deine Bibliothek.
- **Idee**: Definiere Regeln wie:
  - *"Wenn Video > 1GB UND Codec != HEVC → Füge zur 'Optimize'-Queue hinzu"*
  - *"Wenn Video im Ordner 'Inbox' landet → Verschiebe nach 7 Tagen ins 'Archive'"*
- **UI**: Ein einfacher "Rule Builder" in den Settings (ähnlich wie intelligente Wiedergabelisten in iTunes).

### 🎞️ Instant Clip & Share
Ein "Social Media" Toolkit direkt im Browser.
- **Idee**: Du schaust ein Video im Review-Tab. Setze "Start" und "Ende" Marker und klicke "Export GIF" oder "Export MP4".
- **Feature**: Automatisches Zuschneiden (Crop) auf 9:16 für TikTok/Shorts optional.


---

## 4. Visualisierung & "Data Porn"
*Daten schöner sichtbar machen.*

### 📊 Bitrate vs. Quality Scatter Plot
- **Idee**: Ein X/Y Diagramm aller Videos. X=Bitrate, Y=Dateigröße.
- **Ziel**: Identifiziere sofort die "schlechten" Dateien (riesig groß, aber niedrige Bitrate/Qualität), die gelöscht oder optimiert werden müssen.

---

## 🗺️ Roadmap Erweiterung (Technisch)

Zusätzlich zu `ROADMAP.md`:

2.  **Hardware Health Check**: Warnung, wenn die Platte, auf der das Archiv liegt, zu voll läuft (Disk Space Monitoring im Dashboard header).
3.  **Docker/Unraid Template**: Wenn du das veröffentlichst, wäre ein Docker-Container der #1 Request.
