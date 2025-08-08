#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"
python -m http.server 8001 >/dev/null 2>&1 &
sleep 1
python - <<'PY'
import webbrowser; webbrowser.open("http://127.0.0.1:8001/gardeners_console.html"); print("Opened Console")
PY
