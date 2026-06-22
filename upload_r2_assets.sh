#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

: "${R2_REMOTE:?set R2_REMOTE to your rclone remote name, for example nostalgia-r2}"
: "${R2_BUCKET:?set R2_BUCKET to your R2 bucket name}"

transfers="${R2_TRANSFERS:-8}"
checkers="${R2_CHECKERS:-16}"

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone is required. Install it and configure a Cloudflare R2 remote first." >&2
  exit 1
fi

rclone sync public/charts_chartonly_webp "${R2_REMOTE}:${R2_BUCKET}/charts_chartonly_webp" \
  --progress \
  --transfers "$transfers" \
  --checkers "$checkers"

rclone sync public/covers "${R2_REMOTE}:${R2_BUCKET}/covers" \
  --progress \
  --transfers "$transfers" \
  --checkers "$checkers"
