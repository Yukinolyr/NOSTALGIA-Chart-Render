#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f .env.r2 ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.r2
  set +a
fi

: "${R2_ACCOUNT_ID:?set R2_ACCOUNT_ID in .env.r2}"
: "${R2_ACCESS_KEY_ID:?set R2_ACCESS_KEY_ID in .env.r2}"
: "${R2_SECRET_ACCESS_KEY:?set R2_SECRET_ACCESS_KEY in .env.r2}"

R2_REMOTE="${R2_REMOTE:-nostalgia-r2}"
RCLONE_BIN="${RCLONE_BIN:-/home/yukino/.local/bin/rclone}"

if [[ ! -x "$RCLONE_BIN" ]]; then
  echo "rclone not found at $RCLONE_BIN" >&2
  exit 1
fi

"$RCLONE_BIN" config create "$R2_REMOTE" s3 \
  provider Cloudflare \
  access_key_id "$R2_ACCESS_KEY_ID" \
  secret_access_key "$R2_SECRET_ACCESS_KEY" \
  endpoint "https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" \
  acl private \
  --non-interactive

echo "Configured rclone remote: $R2_REMOTE"
