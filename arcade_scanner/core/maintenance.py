import os

from arcade_scanner.config import config
from arcade_scanner.security import path_is_within


def is_safe_to_delete(path: str, expected_parent: str, prefix: str, ext: str) -> bool:
    """Strict check to ensure the file is where we expect and named correctly."""
    abs_path = os.path.abspath(path)
    abs_parent = os.path.abspath(expected_parent)

    # Auf einer Verzeichnisgrenze prüfen, nicht per Präfix: `startswith` allein
    # liesse ein Nachbarverzeichnis durch, dessen Name mit dem erwarteten
    # beginnt (`…/thumbnails_alt`). Über den Aufrufweg hier ist das nicht
    # erreichbar — die Schleifen listen immer das erwartete Verzeichnis —, aber
    # diese Funktion heisst „is_safe_to_delete" und wird gelesen wie eine
    # Zusage. Dieselbe Rechnung wie in security.path_is_within().
    if not path_is_within(abs_path, abs_parent):
        return False

    filename = os.path.basename(path)
    # Check naming pattern
    if not (filename.startswith(prefix) and filename.lower().endswith(ext)):
        return False

    return True


def data_dir_looks_sane() -> bool:
    """Sicherheitsnetz vor jedem Löschlauf: Zeigt das Datenverzeichnis irgendwohin?

    Hier stand::

        if "arcade_data" not in config.hidden_data_dir:

    Das trifft die lokale Installation, aber nicht den Docker-Betrieb: Dort
    setzt `CONFIG_DIR` das Verzeichnis auf ``/config``, der Name „arcade_data"
    kommt nicht vor — und **jede** Wartung brach still ab. `--rebuild` und
    `--cleanup` taten dort nichts, ohne dass es so aussah.

    Geprüft wird jetzt, was der Name prüfen sollte: dass wir nicht das
    Wurzelverzeichnis oder das Home-Verzeichnis ausfegen. Die eigentliche
    Begrenzung leistet ohnehin `is_safe_to_delete()` — entfernt wird nur, was
    im erwarteten Ordner liegt *und* dem Namensmuster entspricht.
    """
    thumb = os.path.abspath(config.thumb_dir)
    forbidden = {
        os.path.abspath(os.sep),
        os.path.abspath(os.path.expanduser("~")),
        os.path.abspath(os.path.expanduser("~/Desktop")),
        os.path.abspath(os.path.expanduser("~/Documents")),
    }
    if thumb in forbidden:
        print(f"❌ [Safety] Thumbnail directory looks suspicious: {thumb}. Aborting.")
        return False
    if os.path.dirname(thumb) == thumb:
        print(f"❌ [Safety] Thumbnail directory is a filesystem root: {thumb}. Aborting.")
        return False
    return True

def purge_media():
    """Löscht alle Vorschaubilder, mit Sicherheitsprüfungen.

    Der frühere Docstring nannte „thumbnail and preview directories". Ein
    Vorschau-Verzeichnis kennt der Code nicht.
    """
    print(f"🧹 Purging media in {config.hidden_data_dir}...")

    if not data_dir_looks_sane():
        return

    # Hier standen zwei identische Einträge. Der Docstring spricht von
    # „thumbnail and preview directories" — ein Vorschau-Verzeichnis gibt es im
    # Code aber nirgends; `arcade_data/previews` ist ein leerer Überrest einer
    # früheren Fassung. Der doppelte Eintrag liess dieselbe Schleife zweimal
    # laufen und die Beschreibung falsch aussehen.
    targets = [
        (config.thumb_dir, "thumb_", ".jpg"),
    ]

    for folder, prefix, ext in targets:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if is_safe_to_delete(file_path, folder, prefix, ext):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"  [Error] Failed to delete {file_path}: {e}")
                else:
                    print(f"  ⚠️ [Safety] Skipping unexpected file: {filename}")
    print("✅ Media purge complete.")

def purge_thumbnails():
    """Deletes all thumbnail files only."""
    print("🧹 Purging thumbnails...")

    if not data_dir_looks_sane():
        return

    if os.path.exists(config.thumb_dir):
        count = 0
        for filename in os.listdir(config.thumb_dir):
            file_path = os.path.join(config.thumb_dir, filename)
            if is_safe_to_delete(file_path, config.thumb_dir, "thumb_", ".jpg"):
                try:
                    os.remove(file_path)
                    count += 1
                except Exception as e:
                    print(f"  [Error] Failed to delete {file_path}: {e}")
        print(f"✅ Thumbnails purge complete. Removed {count} files.")



def purge_broken_media():
    """Removes media files that are 0 bytes or corrupted."""
    if not data_dir_looks_sane():
        return

    removed_count = 0
    # Ebenfalls doppelt aufgeführt gewesen — siehe purge_media().
    targets = [
        (config.thumb_dir, "thumb_", ".jpg"),
    ]
    for folder, prefix, ext in targets:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if is_safe_to_delete(file_path, folder, prefix, ext):
                    if os.path.getsize(file_path) == 0:
                        try:
                            os.remove(file_path)
                            removed_count += 1
                        except Exception:
                            pass
    if removed_count > 0:
        print(f"🧹 Cleaned up {removed_count} failed media generation(s)")

