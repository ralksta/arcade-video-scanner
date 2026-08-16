# Das Dashboard lädt Ressourcen von Fremdservern

**Stand: 2026-08-17**, gefunden im Nachtlauf beim Abgleich der
README-Zusagen mit dem Code. **Nicht behoben — siehe „Warum nicht heute Nacht".**

## Der Widerspruch

Das README verspricht an erster Stelle:

> **Privacy-First**: No data ever leaves your computer. The scan, database, and
> web dashboard run 100% locally.

Der erste Halbsatz stimmt für Scan und Datenbank. Für das Dashboard nicht:

| Ressource | Herkunft | Verwendet in |
|---|---|---|
| `cdn.tailwindcss.com` | Cloudflare | `templates/ui_components.py:26` |
| `fonts.googleapis.com/icon?family=Material+Icons` | Google | `ui_components.py`, `settings_redesign.html` |
| `fonts.googleapis.com/css2?family=Inter` | Google | `ui_components.py`, `login.html`, `settings_redesign.html` |
| `fonts.gstatic.com` | Google | Schriftdateien, über obiges CSS |

Ein lokaler Ersatz existiert nicht (`static/` enthält weder Tailwind noch
Schriftdateien).

## Was das praktisch bedeutet

Bei **jedem** Aufruf des Dashboards — auch der Anmeldeseite, also noch vor dem
Login — erfahren Cloudflare und Google:

- die IP-Adresse des Geräts,
- den User-Agent,
- den Zeitpunkt der Nutzung.

Der Inhalt der Bibliothek verlässt den Rechner **nicht**. Es geht um
Metadaten der Nutzung, nicht um Mediendaten. Für ein Werkzeug, das eine private
Mediensammlung verwaltet, ist der Zeitstempel allein aber schon eine Aussage.

Zusätzlich: `cdn.tailwindcss.com` liefert **ausführbares JavaScript** (den
JIT-Compiler, der zur Laufzeit die CSS-Klassen erzeugt). Dieses Skript läuft im
Kontext der angemeldeten Sitzung. Wer diesen CDN kompromittiert, hat Zugriff auf
alles, was die Seite darf. Bei Schriften ist das Risiko kleiner, bei einem
Skript ist es das nicht.

Über Tailscale ändert sich daran nichts: die Anfragen an Cloudflare und Google
gehen am Tunnel vorbei direkt ins Internet.

## Warum nicht heute Nacht behoben

**Schriften** wären einfach zu lokalisieren — die Dateien müssten aber
heruntergeladen und ins Repository gelegt werden. Beides wollte ich in einem
unbeaufsichtigten Lauf nicht tun: Dateien aus dem Netz zu holen und einzuchecken
ist eine Entscheidung mit Lizenz- und Größenfolgen (Inter und Material Icons
sind je nach Umfang mehrere hundert Kilobyte bis Megabyte).

**Tailwind** ist der schwierigere Teil. Eingebunden ist der CDN-JIT-Compiler,
der die Klassen zur Laufzeit im Browser erzeugt. Ihn zu ersetzen heißt entweder

- ein Build-Schritt, der eine CSS-Datei erzeugt — was der ausdrücklichen
  Architekturentscheidung „no bundler, no build step for the web client"
  widerspricht (`CLAUDE.md`), oder
- eine einmal erzeugte, eingecheckte CSS-Datei, die bei jeder Änderung an den
  Klassen im Markup neu gebaut werden muss — mit dem Risiko, dass sie
  unbemerkt veraltet.

Ohne Browser ließe sich außerdem nicht prüfen, ob nach der Umstellung noch
alles richtig aussieht. Eine Oberfläche über Nacht auf eine andere CSS-Quelle
umzustellen und ungeprüft zu hinterlassen, wäre schlechter als der jetzige
Zustand.

## Entscheidungsvorlage

**Wenn die Zusage gelten soll**, in dieser Reihenfolge:

1. **Schriften lokal** — der größte Gewinn bei geringstem Risiko. Inter und
   Material Icons als woff2 nach `static/fonts/`, `@font-face` in `styles.css`.
   Betrifft `ui_components.py`, `login.html`, `settings_redesign.html`.
2. **Tailwind ersetzen** — entweder einmalig erzeugte CSS einchecken (mit einem
   Test, der meldet, wenn im Markup Klassen auftauchen, die die CSS nicht
   kennt), oder die verwendeten Utilities durch eigene Klassen im vorhandenen
   Design-System ablösen. Das Projekt hat mit `theme.py` bereits ein
   Token-System, das den größten Teil abdeckt.

**Wenn der Zustand bleiben soll**, gehört die README-Zusage präzisiert — etwa:
„Ihre Mediendaten verlassen den Rechner nie. Das Dashboard lädt Schriften und
CSS von öffentlichen CDNs." Das ist kein Rückzug, sondern eine zutreffende
Aussage.

`tests/test_external_resources.py` hält den Ist-Zustand fest und zählt die
Fundstellen, damit weder unbemerkt neue dazukommen noch die Behebung unbemerkt
bleibt.
