#!/bin/bash
# FileMaker Service Monitor Starter

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
MONITOR_SCRIPT="$SCRIPT_DIR/monitor.py"

# Prüfe ob venv existiert
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment nicht gefunden!"
    echo "Erstelle venv mit: python -m venv $VENV_DIR"
    exit 1
fi

# Aktiviere venv und starte Monitor
source "$VENV_DIR/bin/activate"
python "$MONITOR_SCRIPT" "$@"
