#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

mkdir -p logs

session="${SESSION:-nostalgia_export_webp}"
if tmux has-session -t "$session" 2>/dev/null; then
  echo "WebP export already running in tmux session: $session"
  echo "Log: $(cat logs/full_export_webp.latest 2>/dev/null || true)"
  exit 0
fi

workers="${WORKERS:-4}"
quality="${WEBP_QUALITY:-82}"
stamp="$(date +%Y%m%d_%H%M%S)"
log_file="logs/full_export_webp_${stamp}.log"
exit_file="logs/full_export_webp.exit"
rm -f "$exit_file"

force_arg=""
if [[ "${FORCE:-0}" == "1" ]]; then
  force_arg=" --force"
fi

echo "$log_file" > "logs/full_export_webp.latest"
echo "$session" > "logs/full_export_webp.session"

tmux new-session -d -s "$session" \
  "cd '$ROOT_DIR' && '$ROOT_DIR/.venv/bin/python' -u '$ROOT_DIR/batch_export.py' --all --workers '$workers' --checkpoint-every 10 --pretty --format webp --webp-quality '$quality'$force_arg > '$log_file' 2>&1; echo \$? > '$exit_file'"

echo "Started full WebP export"
echo "tmux session: $session"
echo "Workers: $workers"
echo "WebP quality: $quality"
echo "Log: $log_file"
echo "Index: public/chart_index.json"
