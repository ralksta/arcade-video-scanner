# RAW-Fotos unter Linux: Messung und Weg

**Stand: 2026-10-02.** Anlass: CHANGELOG und ROADMAP versprechen seit v6.4.1
„12 RAW formats“, gescannt wurde aber nie eine RAW-Datei. Die Endungen stehen
nur im `ImageInspector`, nicht im Datei-Walker (`scanner/file_system.py`). Unter
`/media` liegen 810 CR2, 683 RAF und 577 DNG.

## Gemessen

Je eine Kopie aus `/media` lief durch `ImageInspector.inspect()` und
`create_thumbnail()`. Auf diesem Server fehlt `sips` (das gibt es nur auf
macOS).

| Datei | Metadaten | Vorschau (ffmpeg) |
|---|---|---|
| CR2, Canon EOS 7D, 22 MB | ✔ 5184×3456 (Pillow liest den TIFF-Kopf) | ✘ ffmpeg dekodiert die RAW-Daten nicht |
| RAF, Fuji X-T3, 56 MB | ✘ Pillow erkennt die Datei nicht → **kein Eintrag** | ✘ |
| DNG, iPhone 16 Pro (ProRAW) | ✔ 3024×4032 | ✘ verlustfreies JPEG (Kompression 52546) kennt ffmpeg nicht |
| „CR2“/„RAF“, die eigentlich JPEGs sind (Exporte aus Apple Fotos) | ✔ | ✔ |

Würde man die Endungen nur im Walker freischalten, entstünden CR2- und
DNG-Einträge ohne Vorschau, und RAF-Dateien fielen still heraus.

## Was funktioniert: die eingebettete Vorschau

Jede RAW-Datei trägt eine JPEG-Vorschau. Nur mit Pillow, also ohne neue
Abhängigkeit, ließ sie sich bei allen drei Formaten herausholen, und die Bilder
waren korrekt:

| Weg | CR2 | RAF | DNG |
|---|---|---|---|
| `Image.open()` direkt (IFD0) | ✔ | ✘ | ✔ richtig ausgerichtet |
| RAF-Kopf: Offset/Länge bei Byte 84–91 (Big-Endian) | — | ✔ | — |
| größtes eingebettetes JPEG (SOI…EOI suchen) | ✔ | ✔ | ✔, aber **gedreht**: braucht `ImageOps.exif_transpose` |

## Vorschlag für die Umsetzung

1. Die RAW-Endungen in `FileSystemScanner.IMAGE_EXTENSIONS` aufnehmen.
2. `ImageInspector`: Kann Pillow die Datei nicht öffnen (RAF), die Maße aus
   der eingebetteten Vorschau nehmen.
3. `create_thumbnail()`: Für RAW-Endungen einen Pillow-Zweig statt ffmpeg —
   der Reihe nach `Image.open()`, RAF-Kopf, eingebettetes JPEG; danach
   `exif_transpose`. Dieselbe Zwischendatei mit `os.replace` wie bei den
   übrigen Vorschaubildern.
4. Tests mit kleinen, synthetischen RAW-artigen Dateien (TIFF mit JPEG-IFD,
   RAF-Kopf mit eingebettetem JPEG) — keine echten Fotos ins Repo.

Danach müssten die ~2.070 Dateien beim nächsten Scan mit Vorschau erscheinen
(sofern „Include Photos“ aktiv ist). NEF/ARW/ORF/RW2 sind TIFF-basiert wie CR2
und dürften über `Image.open()` laufen. Gemessen ist das nicht, denn solche
Dateien gibt es hier nicht.
