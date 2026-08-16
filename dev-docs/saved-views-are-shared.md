# Gespeicherte Ansichten sind für alle Nutzer sichtbar

**Stand: 2026-08-17**, gefunden im Nachtlauf bei der Durchsicht der
Datentrennung. **Nicht behoben — das ist eine Produktentscheidung, keine
eindeutige Fehlfunktion.**

## Der Befund

Das Projekt trennt Nutzerdaten sorgfältig. `/api/settings` mischt über die
globalen Einstellungen alles, was pro Nutzer gehört:

```python
settings_dump["smart_collections"]     = u.data.smart_collections
settings_dump["scan_targets"]          = u.data.scan_targets
settings_dump["exclude_paths"]         = u.data.exclude_paths
settings_dump["available_tags"]        = u.data.available_tags
settings_dump["sensitive_dirs"]        = u.data.sensitive_dirs
settings_dump["sensitive_tags"]        = u.data.sensitive_tags
settings_dump["sensitive_collections"] = u.data.sensitive_collections
```

**`saved_views` fehlt in dieser Liste.** Das Feld existiert nur in
`AppSettings` (`config.py`), also in der globalen `settings.json`, und hat
keine Entsprechung in `UserData`. Jeder angemeldete Nutzer sieht damit die
Ansichten aller anderen — und kann sie überschreiben oder löschen.

## Warum das mehr als kosmetisch ist

Eine gespeicherte Ansicht enthält (`settings.js`, `saveCurrentView()`):

```javascript
{
    id, name,
    search: window.searchTerm,      // frei eingegebener Suchbegriff
    filter, codec, sort,
    mode: window.workspaceMode,
    folder: window.currentFolder    // Ordnerpfad
}
```

Suchbegriff und Ordnerpfad verraten, wonach jemand gesucht hat und wo. In einer
Installation mit mehreren Personen ist das dieselbe Art von Preisgabe wie das
`FOLDERS_DATA`-Leck, das in derselben Nacht behoben wurde — nur dass es hier
eine Anmeldung voraussetzt.

Anonym erreichbar ist nichts davon: sowohl der HTML-Dump als auch
`/api/settings` verlangen eine Sitzung.

## Warum es nicht einfach behoben wurde

Weil unklar ist, was gewollt ist:

- In einer **Familien-Installation** können gemeinsame Ansichten praktisch sein
  („Urlaub 2019" für alle sichtbar).
- In einer Installation mit **getrennten Konten** ist es eine Preisgabe.

Die Umstellung wäre außerdem kein Einzeiler: `saved_views` müsste nach
`UserData` wandern, bestehende Ansichten aus `settings.json` müssten migriert
werden (an wen? an den Admin, wie es `user_store.py:326` bereits für
`smart_collections` tut), und die Schreibpfade in `settings.js` müssten folgen.

Eine solche Änderung an der Datenhoheit gehört nicht in einen unbeaufsichtigten
Nachtlauf.

## Entscheidungsvorlage

**Wenn Ansichten privat sein sollen** (Empfehlung bei getrennten Konten):
`saved_views` nach `UserData` verschieben, in `handle_get_settings()` wie die
anderen Felder überschreiben, und beim ersten Start die vorhandenen Ansichten
dem Admin zuordnen — analog zur bestehenden Migration für `smart_collections`.

**Wenn Ansichten geteilt bleiben sollen:** in `CLAUDE.md` bei der
Mehrbenutzer-Trennung ausdrücklich vermerken, damit die Abweichung als Absicht
erkennbar ist und nicht als vergessenes Feld.

`tests/test_saved_views_sharing.py` hält den heutigen Zustand fest, damit eine
Änderung bewusst geschieht und nicht unbemerkt.
