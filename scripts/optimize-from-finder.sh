#!/bin/bash
# ──────────────────────────────────────────────────────────────────
# Arcade Video Optimizer — Finder Quick Action Wrapper
#
# Die Encoder-Engine liegt seit dem Split im eigenen Repo videocrunch. Dieses
# Skript ruft dessen videocrunch.py auf (frueher scripts/video_optimizer.py),
# aufgeloest ueber ARCADE_OPTIMIZER_PATH / VIDEOCRUNCH_PATH / ../videocrunch.
#
# Usage in Quick Action (~/Library/Services/):
#
#   for f in "$@"
#   do
#       osascript -e "tell application \"Terminal\" to do script \
#           \"/pfad/zu/arcade-video-scanner/scripts/optimize-from-finder.sh '$f'\""
#   done
# ──────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INPUT_FILE="$1"

# ── Farben ──────────────────────────────────────────────────────
G='\033[0;32m'
BG='\033[1;32m'
Y='\033[0;33m'
R='\033[0;31m'
B='\033[0;34m'
NC='\033[0m'

# ── Eingabedatei prüfen ──────────────────────────────────────────
if [[ -z "$INPUT_FILE" ]]; then
    echo -e "${Y}Bitte eine Videodatei als Argument übergeben.${NC}"
    exit 1
fi

if [[ ! -f "$INPUT_FILE" ]]; then
    echo -e "${R}Datei nicht gefunden: $INPUT_FILE${NC}"
    exit 1
fi

# ── videocrunch-Checkout auflösen ─────────────────────────────────
# Gleiche Auflösung wie der Server (arcade_scanner/config.py optimizer_path)
# und wie scan-folder-from-finder.sh:
# ARCADE_OPTIMIZER_PATH (legacy) > VIDEOCRUNCH_PATH > Geschwister-Checkout.
if [[ -n "${ARCADE_OPTIMIZER_PATH:-}" ]]; then
    VC_ENGINE="$ARCADE_OPTIMIZER_PATH"
elif [[ -n "${VIDEOCRUNCH_PATH:-}" ]]; then
    VC_ENGINE="$VIDEOCRUNCH_PATH"
else
    VC_ENGINE="$(dirname "$PROJECT_DIR")/videocrunch/videocrunch.py"
fi
VC_DIR="$(dirname "$VC_ENGINE")"

if [[ ! -f "$VC_ENGINE" ]]; then
    echo -e "${R}videocrunch nicht gefunden unter: $VC_ENGINE${NC}"
    echo -e "${Y}Clone es als Geschwister-Checkout (../videocrunch) oder setze VIDEOCRUNCH_PATH.${NC}"
    exit 1
fi

# ── Python aus dem videocrunch-venv ──────────────────────────────
PYTHON="$VC_DIR/.venv/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
    PYTHON="python3"
fi

echo -e "${BG}═══════════════════════════════════════════${NC}"
echo -e "${BG}  🎬 Arcade Video Optimizer${NC}"
echo -e "${BG}═══════════════════════════════════════════${NC}"
echo -e "${G}Datei:${NC} $(basename "$INPUT_FILE")"
echo ""

# ── Audio-Modus wählen ───────────────────────────────────────────
echo -e "${Y}Audio-Lautstärke:${NC}"
echo -e "  ${G}[1]${NC}  Wie Original  – keine Änderung"
echo -e "  ${G}[2]${NC}  Etwas lauter  – sanfte Anpassung ${G}(Standard)${NC}"
echo -e "  ${G}[3]${NC}  Streaming-Laut – für YouTube/Twitch"
echo -ne "  Auswahl [2]: "
read -r AUDIO_INPUT
case "$AUDIO_INPUT" in
    1) AUDIO_MODE="standard" ;;
    3) AUDIO_MODE="enhanced" ;;
    *) AUDIO_MODE="moderate" ;;
esac

echo ""

# ── Auflösung ermitteln ──────────────────────────────────────────
# Anzeige-Dimensionen: bei ±90° Rotation (Handy-Videos) sind width/height
# im Stream vertauscht — ffmpeg dreht beim Encoden automatisch, also
# rechnen wir hier ebenfalls mit den gedrehten Werten.
IFS=, read -r SRC_W SRC_H <<< "$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height -of csv=p=0 "$INPUT_FILE" 2>/dev/null | head -1)"
ROTATION=$(ffprobe -v error -select_streams v:0 \
    -show_entries stream_side_data=rotation -of default=nw=1:nk=1 "$INPUT_FILE" 2>/dev/null | head -1)
ROTATION=${ROTATION%%.*}
ROTATION=${ROTATION#-}
if [[ "$ROTATION" == "90" || "$ROTATION" == "270" ]]; then
    TMP=$SRC_W; SRC_W=$SRC_H; SRC_H=$TMP
fi

# ── Hilfsfunktionen für die Skalierung ───────────────────────────
gcd() {
    local a=$1 b=$2 t
    while (( b != 0 )); do t=$b; b=$(( a % b )); a=$t; done
    echo "$a"
}

# Gerade Zahl, kaufmännisch gerundet (Encoder brauchen gerade Dimensionen)
even_round() {
    local num=$1 den=$2 v
    v=$(( (num + den / 2) / den ))
    echo $(( (v + 1) / 2 * 2 ))
}

SCALE_HEIGHT=""    # leer = Originalauflösung behalten

choose_scale() {
    SCALE_HEIGHT=""
    if [[ -z "$SRC_W" || -z "$SRC_H" ]] || (( SRC_W <= 0 || SRC_H <= 0 )); then
        echo -e "${Y}Auflösung konnte nicht ermittelt werden – bleibe bei Original.${NC}"
        return
    fi

    local d ar_w ar_h short is_portrait
    d=$(gcd "$SRC_W" "$SRC_H")
    ar_w=$(( SRC_W / d )); ar_h=$(( SRC_H / d ))

    if (( SRC_W <= SRC_H )); then
        short=$SRC_W; is_portrait=1
    else
        short=$SRC_H; is_portrait=0
    fi

    echo -e "${Y}Auflösung:${NC} ${SRC_W}x${SRC_H}  (Seitenverhältnis ${ar_w}:${ar_h})"
    echo -e "${Y}Kleiner skalieren? Das Seitenverhältnis bleibt erhalten.${NC}"
    echo -e "  ${G}[0]${NC}  Originalauflösung behalten ${G}(Standard)${NC}"

    # Kandidaten: Standard-Stufen unterhalb der kurzen Seite
    local -a OPT_H=() OPT_LABEL=()
    local n=0 s tw th px_pct
    for s in 2160 1440 1080 720 480; do
        (( s < short )) || continue
        if (( is_portrait == 1 )); then
            tw=$s
            th=$(even_round $(( SRC_H * s )) "$SRC_W")
        else
            th=$s
            tw=$(even_round $(( SRC_W * s )) "$SRC_H")
        fi
        (( tw > 0 && th > 0 )) || continue
        n=$(( n + 1 ))
        OPT_H[$n]=$th
        # Pixelreduktion als grober Indikator für die Dateigröße
        px_pct=$(( 100 - (tw * th * 100) / (SRC_W * SRC_H) ))
        OPT_LABEL[$n]="${tw}x${th}  (${s}p, ~${px_pct}% weniger Pixel)"
        echo -e "  ${G}[$n]${NC}  ${OPT_LABEL[$n]}"
    done

    if (( n == 0 )); then
        echo -e "  ${Y}(keine sinnvolle kleinere Stufe – Quelle ist bereits klein)${NC}"
        echo ""
        return
    fi

    echo -e "  ${G}[h]${NC}  Eigene Höhe eingeben"
    echo -ne "  Auswahl [0]: "
    local SCALE_CHOICE CUSTOM_H
    read -r SCALE_CHOICE

    case "$SCALE_CHOICE" in
        h|H)
            echo -ne "  Zielhöhe in Pixeln = "
            read -r CUSTOM_H
            if [[ "$CUSTOM_H" =~ ^[0-9]+$ ]] && (( CUSTOM_H > 0 && CUSTOM_H < SRC_H )); then
                SCALE_HEIGHT=$(( (CUSTOM_H + 1) / 2 * 2 ))
                echo -e "  ${G}→ Ziel: ${SCALE_HEIGHT}px Höhe${NC}"
            else
                echo -e "${R}Ungültige Höhe – behalte Originalauflösung.${NC}"
            fi
            ;;
        ''|0)
            echo -e "  ${G}→ Originalauflösung${NC}"
            ;;
        *)
            if [[ "$SCALE_CHOICE" =~ ^[0-9]+$ ]] && (( SCALE_CHOICE >= 1 && SCALE_CHOICE <= n )); then
                SCALE_HEIGHT=${OPT_H[$SCALE_CHOICE]}
                echo -e "  ${G}→ Ziel: ${OPT_LABEL[$SCALE_CHOICE]}${NC}"
            else
                echo -e "${R}Ungültige Auswahl – behalte Originalauflösung.${NC}"
            fi
            ;;
    esac
    echo ""
}

choose_scale

# ── Quality-Level abfragen ───────────────────────────────────────
echo -e "${Y}Quality-Level eingeben (Enter = automatische Suche):${NC}"
echo -e "  VideoToolbox: 45–75 (höher = besser), z.B. ${G}65${NC}"
echo -e "  NVENC/libx265: 20–44 (niedriger = besser), z.B. ${G}28${NC}"
echo -ne "  Q = "
read -r Q_INPUT

if [[ -n "$Q_INPUT" ]] && ! [[ "$Q_INPUT" =~ ^[0-9]+$ ]]; then
    echo -e "${R}Ungültiger Wert – starte automatische Suche.${NC}"
    Q_INPUT=""
fi

# ── Nach Encode weiteres Q ausprobieren? ────────────────────────
echo ""
echo -e "${Y}Automatisch verschiedene Qualitätsstufen testen?${NC}"
echo -ne "  [j/N]: "
read -r INTER_INPUT
if [[ "$INTER_INPUT" =~ ^[jJyY]$ ]]; then
    INTERACTIVE_MODE=1
else
    INTERACTIVE_MODE=0
fi

echo ""

# ── Hilfsfunktion: Dateigröße formatiert ────────────────────────
format_size() {
    local bytes=${1:-0} scaled
    if (( bytes >= 1073741824 )); then
        # Ganzzahl-Mathematik statt bc/printf %f — locale-unabhängig (de_DE nutzt Komma)
        scaled=$(( (bytes * 100 + 536870912) / 1073741824 ))   # Hundertstel GB, gerundet
        printf "%d.%02d GB" "$(( scaled / 100 ))" "$(( scaled % 100 ))"
    elif (( bytes >= 1048576 )); then
        scaled=$(( (bytes * 10 + 524288) / 1048576 ))          # Zehntel MB, gerundet
        printf "%d.%d MB" "$(( scaled / 10 ))" "$(( scaled % 10 ))"
    else
        printf "%d KB" "$(( bytes / 1024 ))"
    fi
}

# ── Encode-Schleife ──────────────────────────────────────────────
CURRENT_Q="$Q_INPUT"
BEST_OPT_FILE=""
ROUND=1

while true; do
    echo -e "${BG}─── Durchgang $ROUND ───────────────────────────────────${NC}"

    # Output-Datei bestimmen (videocrunch.py erzeugt _opt.mp4)
    INPUT_STEM="${INPUT_FILE%.*}"
    OPT_FILE="${INPUT_STEM}_opt.mp4"

    # Vorherige _opt.mp4 entfernen damit der Optimizer nicht skippt
    if [[ -f "$OPT_FILE" ]]; then
        echo -e "${Y}⚠️  Vorherige _opt.mp4 wird entfernt um neu zu encodieren...${NC}"
        rm -f "$OPT_FILE"
    fi

    # videocrunch starten
    Q_ARGS=""
    if [[ -n "$CURRENT_Q" ]]; then
        Q_ARGS="--q $CURRENT_Q"
        echo -e "${G}Starte Encode mit Q=${CURRENT_Q}...${NC}"
    else
        echo -e "${G}Starte Encode mit automatischer Q-Suche...${NC}"
    fi
    SCALE_ARGS=""
    if [[ -n "$SCALE_HEIGHT" ]]; then
        SCALE_ARGS="--scale-height $SCALE_HEIGHT"
        echo -e "${G}Skalierung: Höhe ${SCALE_HEIGHT}px (Seitenverhältnis bleibt)${NC}"
    fi
    echo ""

    "$PYTHON" "$VC_ENGINE" $Q_ARGS $SCALE_ARGS --audio-mode "$AUDIO_MODE" "$INPUT_FILE"
    EXIT_CODE=$?

    echo ""

    # ── Ergebnis auswerten ───────────────────────────────────────
    if [[ $EXIT_CODE -ne 0 ]]; then
        echo -e "${R}❌ videocrunch-Fehler (Exit $EXIT_CODE).${NC}"
        break
    fi

    if [[ ! -f "$OPT_FILE" ]]; then
        echo -e "${R}❌ Keine Ausgabedatei gefunden: $OPT_FILE${NC}"
        break
    fi

    # Größen berechnen
    SIZE_ORIG=$(stat -f%z "$INPUT_FILE" 2>/dev/null || stat -c%s "$INPUT_FILE")
    SIZE_OPT=$(stat -f%z "$OPT_FILE" 2>/dev/null || stat -c%s "$OPT_FILE")
    SAVED=$(( SIZE_ORIG - SIZE_OPT ))
    if (( SIZE_ORIG > 0 )); then
        SAVED_PCT=$(echo "scale=1; $SAVED * 100 / $SIZE_ORIG" | bc)
    else
        SAVED_PCT="0"
    fi

    echo -e "${BG}═══════════════════════════════════════════${NC}"
    echo -e "${BG}  📊 Ergebnis Durchgang $ROUND${NC}"
    echo -e "${BG}═══════════════════════════════════════════${NC}"
    echo -e "  Original:   ${Y}$(format_size $SIZE_ORIG)${NC}"
    echo -e "  Optimiert:  ${G}$(format_size $SIZE_OPT)${NC}"
    echo -e "  Einsparung: ${BG}${SAVED_PCT}%  ($(format_size $SAVED) gespart)${NC}"
    [[ -n "$CURRENT_Q" ]] && echo -e "  Q-Level:    ${G}${CURRENT_Q}${NC}" || echo -e "  Q-Level:    ${G}auto${NC}"
    if [[ -n "$SCALE_HEIGHT" ]]; then
        IFS=, read -r OUT_W OUT_H <<< "$(ffprobe -v error -select_streams v:0 \
            -show_entries stream=width,height -of csv=p=0 "$OPT_FILE" 2>/dev/null | head -1)"
        echo -e "  Auflösung:  ${G}${SRC_W}x${SRC_H} → ${OUT_W:-?}x${OUT_H:-?}${NC}"
    else
        echo -e "  Auflösung:  ${G}${SRC_W}x${SRC_H} (unverändert)${NC}"
    fi
    echo ""

    BEST_OPT_FILE="$OPT_FILE"

    # ── Nicht-interaktiv: fertig ─────────────────────────────────
    if [[ "$INTERACTIVE_MODE" != "1" ]]; then
        echo -e "${BG}✅ Fertig!${NC}"
        break
    fi

    # ── Interaktiv: fragen was als nächstes ─────────────────────
    echo -e "${Y}Was möchtest du tun?${NC}"
    echo -e "  ${G}[Enter]${NC}  Dieses Ergebnis behalten und fertig"
    echo -e "  ${G}[q]${NC}      Neues Q-Level eingeben und nochmal versuchen"
    echo -e "  ${G}[a]${NC}      Automatische Suche starten"
    echo -e "  ${G}[s]${NC}      Auflösung ändern und nochmal versuchen"
    echo -ne "  Auswahl: "
    read -r CHOICE

    case "$CHOICE" in
        s|S)
            echo ""
            choose_scale
            ROUND=$(( ROUND + 1 ))
            continue
            ;;
        q|Q)
            echo -ne "  Neues Q-Level = "
            read -r NEW_Q
            if [[ -n "$NEW_Q" ]] && [[ "$NEW_Q" =~ ^[0-9]+$ ]]; then
                CURRENT_Q="$NEW_Q"
                ROUND=$(( ROUND + 1 ))
                continue
            else
                echo -e "${R}Ungültige Eingabe – behalte aktuelles Ergebnis.${NC}"
                break
            fi
            ;;
        a|A)
            CURRENT_Q=""
            ROUND=$(( ROUND + 1 ))
            continue
            ;;
        *)
            # Enter oder alles andere → aktuelles Ergebnis behalten
            echo -e "${BG}✅ Ergebnis übernommen!${NC}"
            break
            ;;
    esac
done

# ── Abschluss ────────────────────────────────────────────────────
if [[ -f "$BEST_OPT_FILE" ]]; then
    echo ""
    echo -e "${G}📁 Ausgabedatei:${NC} $(basename "$BEST_OPT_FILE")"
    echo -e "${G}📂 Ordner:${NC} $(dirname "$BEST_OPT_FILE")"
fi

echo ""
echo -e "${B}(Dieses Fenster kann geschlossen werden)${NC}"
