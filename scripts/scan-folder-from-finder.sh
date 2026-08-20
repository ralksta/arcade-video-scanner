#!/bin/bash
# ──────────────────────────────────────────────────────────────────
# Arcade Folder Scanner — Finder Quick Action Wrapper
#
# Zeigt für einen Ordner an, welche Videos sich zu optimieren lohnen,
# und encodiert auf Wunsch die markierten.
#
# Einrichtung als Finder-Schnellaktion:
#   Automator -> Neues Dokument -> Schnellaktion
#   "Arbeitsablauf empfaengt aktuell": Ordner   in: Finder.app
#   Aktion "Shell-Skript ausfuehren", Shell /bin/bash
#   "Uebergabe der Eingabe": ALS ARGUMENTE  <- sonst ist "$@" leer und es
#                                              oeffnet sich nur ein leeres Terminal
#   Skript:
#
#   SCRIPT="/pfad/zu/arcade-video-scanner/scripts/scan-folder-from-finder.sh"
#
#   if [ "$#" -eq 0 ]; then
#       osascript -e 'display alert "Keine Eingabe angekommen" message "Uebergabe der Eingabe muss auf \"als Argumente\" stehen."'
#       exit 1
#   fi
#
#   for d in "$@"
#   do
#       /usr/bin/osascript \
#           -e 'on run {p}' \
#           -e 'tell application "Terminal" to do script "'"$SCRIPT"' " & quoted form of p' \
#           -e 'end run' "$d"
#   done
#
#   osascript -e 'tell application "Terminal" to activate'
#
# Der Pfad geht als Argument an AppleScript (quoted form), nicht per
# String-Verkettung — sonst zerlegt ein Apostroph im Ordnernamen das Quoting.
# ──────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INPUT_DIR="$1"

# ── Farben ──────────────────────────────────────────────────────
G='\033[0;32m'
BG='\033[1;32m'
Y='\033[0;33m'
R='\033[0;31m'
NC='\033[0m'

# ── Eingabe prüfen ───────────────────────────────────────────────
if [[ -z "$INPUT_DIR" ]]; then
    echo -e "${Y}Bitte einen Ordner als Argument übergeben.${NC}"
    exit 1
fi

# Wird eine Datei übergeben (Finder gibt bei Rechtsklick auf eine Datei
# deren Pfad), nehmen wir den umgebenden Ordner — das ist fast immer gemeint.
if [[ -f "$INPUT_DIR" ]]; then
    INPUT_DIR="$(dirname "$INPUT_DIR")"
fi

if [[ ! -d "$INPUT_DIR" ]]; then
    echo -e "${R}Ordner nicht gefunden: $INPUT_DIR${NC}"
    exit 1
fi

# ── videocrunch-Checkout auflösen ─────────────────────────────────
# Gleiche Auflösung wie der Server (arcade_scanner/config.py optimizer_path):
# ARCADE_OPTIMIZER_PATH (legacy) > VIDEOCRUNCH_PATH > Geschwister-Checkout.
if [[ -n "${ARCADE_OPTIMIZER_PATH:-}" ]]; then
    VC_ENGINE="$ARCADE_OPTIMIZER_PATH"
elif [[ -n "${VIDEOCRUNCH_PATH:-}" ]]; then
    VC_ENGINE="$VIDEOCRUNCH_PATH"
else
    VC_ENGINE="$(dirname "$PROJECT_DIR")/videocrunch/videocrunch.py"
fi
VC_DIR="$(dirname "$VC_ENGINE")"

if [[ ! -f "$VC_DIR/scan.py" ]]; then
    echo -e "${R}videocrunch nicht gefunden unter: $VC_DIR${NC}"
    echo -e "${Y}Clone es als Geschwister-Checkout (../videocrunch) oder setze VIDEOCRUNCH_PATH.${NC}"
    exit 1
fi

# ── Python aus dem videocrunch-venv ──────────────────────────────
PYTHON="$VC_DIR/.venv/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON="python3"
fi

# ── Audio-Modus wählen ───────────────────────────────────────────
# Nur relevant, falls anschließend encodiert wird.
echo -e "${Y}Audio-Lautstärke (falls encodiert wird):${NC}"
echo -e "  ${G}[1]${NC}  Wie Original  – keine Änderung ${G}(Standard)${NC}"
echo -e "  ${G}[2]${NC}  Streaming-Laut – für YouTube/Twitch"
echo -ne "  Auswahl [1]: "
read -r AUDIO_INPUT
case "$AUDIO_INPUT" in
    2) AUDIO_MODE="enhanced" ;;
    *) AUDIO_MODE="standard" ;;
esac
echo ""

"$PYTHON" "$VC_DIR/scan.py" "$INPUT_DIR" --audio-mode "$AUDIO_MODE"
STATUS=$?

echo ""
echo -e "${G}(Dieses Fenster kann geschlossen werden)${NC}"
exit $STATUS
