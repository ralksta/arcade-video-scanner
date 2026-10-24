# iOS-Client: Zustand und was zur Reparatur fehlt

**Stand: 2026-08-17. Der iOS-Client funktioniert gegen den aktuellen Server nicht.**

Gefunden im Nachtlauf beim Abgleich der Clients gegen die Server-Routen.

## Was kaputt ist

### 1. Die aufgerufenen Endpunkte gibt es nicht mehr

`APIService.fetchLibrary()` ruft auf:

- `GET /api/deovr/library.json`
- `GET /api/deovr/collection/<id>.json`

Beide wurden mit Commit `8c6008a` („complete removal of VR Gallery and DeoVR
integration") entfernt, zusammen mit `arcade_scanner/core/deovr_generator.py`.
Im Arbeitsverzeichnis liegt davon nur noch `._deovr_generator.py` — ein
macOS-Ressourcenzweig, kein Python.

Jede Bibliotheksabfrage des Clients bekommt seither einen 404. Die Entfernung
war serverseitig vollständig; der Client wurde schlicht nicht mitgezogen.

### 2. Es wird keine Sitzung mitgeschickt

`fetchLibrary()` und `fetchSmartCollections()` verwenden
`URLSession.shared.data(from: url)` ohne jede Authentifizierung. `/api/settings`
und `/api/videos` sind aber sitzungspflichtig. Selbst wenn die DeoVR-Routen
noch existierten, käme für `/api/settings` heute ein 401 zurück.

Der Client hat also nie einen Login-Fluss gehabt — er stammt aus der Zeit vor
der Mehrbenutzer-Umstellung (`ca3b9c4`, v7.0.0).

## Was eine Reparatur braucht

Der TV-Client zeigt den gangbaren Weg (`tv_client/src/views/MainPanel.js`):
Login gegen `/api/login`, danach `Authorization: Bearer <token>` an jedem
Request.

Konkret sind das vier Schritte:

1. **Login-Ansicht und Token-Haltung.** Server-URL, Nutzername, Passwort;
   `POST /api/login`; Token sicher ablegen (Keychain).
2. **`APIService` auf die echten Endpunkte umstellen.**
   `fetchLibrary()` → `GET /api/videos` (liefert bereits nach Scan-Zielen des
   Nutzers gefiltert), Smart Collections weiterhin aus `GET /api/settings`.
3. **`Video.swift` neu abbilden.** Die DeoVR-Struktur (`scenes[]` mit `title`,
   `videoUrl`, `thumbnailUrl`, `duration`, `is3d`, `screenType`, `stereoMode`)
   passt nicht auf die Felder von `/api/videos` (`FilePath`, `Size_MB`,
   `Duration_Sec`, `codec`, `Width`, `Height`, `thumb`, `favorite`, `hidden`,
   `tags`, …). Wiedergabe läuft über `GET /stream?path=<FilePath>`,
   Vorschaubilder über `GET /thumbnails/<thumb>`.
4. **Nutzerdaten hydrieren.** Favoriten, Vault und Tags kommen aus
   `GET /api/user/data`, nicht aus `/api/videos` — wie im Browser-Client.

## Warum das hier steht statt erledigt zu sein

Die Umstellung ist überschaubar, aber sie lässt sich in dieser Umgebung nicht
prüfen: keine Swift-Toolchain, kein Simulator. Ungetesteten Client-Code zu
schreiben hätte den Anschein von Fortschritt erzeugt, ohne belegen zu können,
dass er läuft — und der nächste Mensch hätte nicht unterscheiden können, was
geprüft ist und was nicht.

`tests/test_client_endpoint_contract.py` hält den Bruch als `xfail` fest und
meldet künftig jeden neuen Endpunkt, den ein Client aufruft und der Server
nicht kennt.

## Alternative: den Client zurückziehen

Falls der iOS-Client ohnehin nicht mehr benutzt wird, ist das Entfernen aus dem
Repository die ehrlichere Lösung als ein Verzeichnis, das seit `8c6008a` nicht
mehr funktioniert. Das ist eine Produktentscheidung und wurde deshalb nicht
eigenmächtig getroffen.
