#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

SESSION_FILE="logs/chartonly_export.session"
LOG_FILE=""
if [[ -f "logs/chartonly_export.latest" ]]; then
  LOG_FILE="$(cat logs/chartonly_export.latest)"
fi

if [[ -f "$SESSION_FILE" ]]; then
  session="$(cat "$SESSION_FILE" || true)"
  if [[ -n "$session" ]] && tmux has-session -t "$session" 2>/dev/null; then
    echo "Status: running (tmux session $session)"
  else
    echo "Status: not running (last tmux session ${session:-unknown})"
  fi
else
  echo "Status: not started"
fi

if [[ -f logs/chartonly_export.exit ]]; then
  echo "Last exit code: $(cat logs/chartonly_export.exit)"
fi

if [[ -n "$LOG_FILE" && -f "$LOG_FILE" ]]; then
  echo "Log: $LOG_FILE"
  echo "--- Last 20 log lines ---"
  tail -n 20 "$LOG_FILE"
fi

if [[ -f public/chart_index_chartonly.json ]]; then
  echo "--- Index summary ---"
  .venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("public/chart_index_chartonly.json")
data = json.loads(p.read_text(encoding="utf-8"))
print(f"requested={data.get('requested_count')}")
print(f"completed={data.get('completed_count')}")
print(f"exported={data.get('exported_count')}")
print(f"rendered={data.get('rendered_count')}")
print(f"skipped={data.get('skipped_count')}")
print(f"failed={data.get('failure_count')}")
print(f"format={data.get('image_format')}")
PY
fi

echo "--- Output size ---"
find public/charts_chartonly -type f 2>/dev/null | wc -l || true
du -sh public/charts_chartonly 2>/dev/null || true
