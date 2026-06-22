#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

mkdir -p logs
mkdir -p public/charts_chartonly

session="${SESSION:-nostalgia_chartonly_export}"
if tmux has-session -t "$session" 2>/dev/null; then
  echo "Chart-only export already running in tmux session: $session"
  echo "Log: $(cat logs/chartonly_export.latest 2>/dev/null || true)"
  exit 0
fi

workers="${WORKERS:-4}"
stamp="$(date +%Y%m%d_%H%M%S)"
log_file="logs/chartonly_export_${stamp}.log"
exit_file="logs/chartonly_export.exit"
rm -f "$exit_file"

format="${FORMAT:-png}"
quality="${WEBP_QUALITY:-82}"
force_args=()
if [[ "${FORCE:-0}" == "1" ]]; then
  force_args=(--force)
fi

echo "$log_file" > "logs/chartonly_export.latest"
echo "$session" > "logs/chartonly_export.session"

tmux new-session -d -s "$session" \
  "cd '$ROOT_DIR' && '$ROOT_DIR/.venv/bin/python' -u '$ROOT_DIR/batch_export.py' --all --workers '$workers' --checkpoint-every 10 --pretty ${force_args[*]} --format '$format' --webp-quality '$quality' --output-dir '$ROOT_DIR/public/charts_chartonly' --index-output '$ROOT_DIR/public/chart_index_chartonly.json' --url-prefix /charts_chartonly > '$log_file' 2>&1; echo \$? > '$exit_file'"

echo "Started chart-only export"
echo "tmux session: $session"
echo "Workers: $workers"
echo "Format: $format"
echo "Force: ${FORCE:-0}"
echo "Log: $log_file"
echo "Index: public/chart_index_chartonly.json"
echo "Output: public/charts_chartonly"
