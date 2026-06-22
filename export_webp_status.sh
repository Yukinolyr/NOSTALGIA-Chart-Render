#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

SESSION_FILE="logs/full_export_webp.session"
LOG_FILE=""
if [[ -f "logs/full_export_webp.latest" ]]; then
  LOG_FILE="$(cat logs/full_export_webp.latest)"
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

if [[ -f logs/full_export_webp.exit ]]; then
  echo "Last exit code: $(cat logs/full_export_webp.exit)"
fi

if [[ -n "$LOG_FILE" && -f "$LOG_FILE" ]]; then
  echo "Log: $LOG_FILE"
  echo "--- Last 20 log lines ---"
  tail -n 20 "$LOG_FILE"
fi

echo "--- WebP output size ---"
find public/charts -type f -name '*.webp' | wc -l
du -ch public/charts/*/*.webp 2>/dev/null | tail -n 1 || true
