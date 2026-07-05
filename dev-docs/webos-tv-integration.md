# Design-Spezifikation: Native Enact TV-App für Arcade Video Scanner

Dieses Dokument beschreibt das Design und die technische Umsetzung einer nativen webOS-App (`.ipk`), die mit dem offiziellen LG Smart TV React-Framework **Enact (Sandstone UI)** gebaut wird.

---

## 1. Übersicht & Zielsetzung

*   **Was gebaut wird:** Eine native webOS-App (`.ipk`), geschrieben in React unter Nutzung des LG Enact Frameworks.
*   **Warum es existiert:** Bietet eine extrem flüssige TV-Bedienung (60 FPS) mit nativer D-Pad-Fokussteuerung und einem voll integrierten TV-Videoplayer.
*   **Architektur:** Die App läuft komplett lokal auf dem TV (keine HTML-Umleitung) und kommuniziert rein über API-Requests mit dem Server.
*   **Verbindungstyp:** Unverschlüsseltes HTTP zur Vermeidung von SSL-Zertifikats-Zicken auf dem TV.

---

## 2. Struktur & Komponenten

Die App wird im Verzeichnis `tv_client/` aufgesetzt und hat folgende Kern-Struktur:

```text
tv_client/
├── package.json
├── appinfo.json      # Metadaten für webOS
├── icon.png          # Retro-Icon für den TV Launcher
└── src/
    ├── App/
    │   ├── App.js        # Hauptkomponente (TabLayout + VideoPlayer)
    │   └── App.module.less
    └── index.js          # App-Bootstrapper
```

### Enact Sandstone UI Elemente

*   **`sandstone/TabLayout`:** Steuert die linke, einklappbare Seitenleiste (Kategorien) und das rechte Inhaltsgitter.
*   **`sandstone/VirtualGridList`:** Das Gitter (Grid) auf der rechten Seite. Rendert performant Hunderte von Filmkacheln per DOM-Virtualisierung.
*   **`sandstone/VideoPlayer`:** Der native TV-Videoplayer. Fängt Fernbedienungstasten (Play/Pause, Spulen, Back-Button) automatisch ab.

---

## 3. Technische Details & Datenfluss

### 3.1 Daten abrufen
Beim App-Start ruft die React-App die Filmdaten vom Server ab:

*   **Endpoint:** `http://192.168.2.183:8000/api/videos`
*   **Credentials:** `credentials: 'include'` wird beim Fetch-Aufruf übergeben, um bestehende Session-Cookies des TV-Webviews zu nutzen.

### 3.2 Video Streaming
Wenn ein Video im Grid gestartet wird, lädt der Enact `VideoPlayer` den Stream:

*   **URL:** `http://192.168.2.183:8000/stream?path=<encoded_path>`

---

## 4. Entscheidungs-Logbuch (Decision Log)

| Datum | Entscheidung | Alternativen | Begründung |
| :--- | :--- | :--- | :--- |
| 05.07.2026 | **Enact (React) App (Ansatz 1)** | Custom JS Focus Manager, Iframe | Maximale Performance auf dem TV, native D-Pad-Steuerung auf Betriebssystemebene, keine Browser-History-Hacks nötig. |
| 05.07.2026 | **Lokale App-Ausführung** | Server-gehostete UI | Startet sofort aus dem lokalen Speicher, keine Lade-Lags oder weiße Bildschirme beim Start. |
| 05.07.2026 | **Hardcoded Server IP** | Dynamischer IP-Einstellungsbildschirm | Hält das Projekt extrem simpel (YAGNI). |

---

## 5. Risiken & Edge Cases

*   **CORS / Mixed Content:** Da die App lokal über `file:///` läuft, müssen wir sicherstellen, dass der Server die CORS-Header für die TV-IP korrekt setzt. Da der Server bereits standardmäßig `Access-Control-Allow-Origin: *` für Ressourcen mitschickt, ist das Risiko gering.
*   **Session Ablauf:** Läuft die Session ab, zeigt die App einen Fehler. Der Nutzer kann sich über die TV-Browser-Session neu authentifizieren.
