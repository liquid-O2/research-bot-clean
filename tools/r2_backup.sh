#!/usr/bin/env bash
# Copy /workspace to Cloudflare R2 bucket runp. GitHub is the code backup.
# This is the volume backup (artifacts, data, .git, secrets).
#
# Walls: never write nkd-hg, rty, or russel.
# Prefer copy over sync so a bad run cannot delete the dest.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="${RCLONE_CONFIG:-}"
if [[ -z "${CONF}" ]]; then
  if [[ -f "${ROOT}/.secrets/rclone-r2.conf" ]]; then
    CONF="${ROOT}/.secrets/rclone-r2.conf"
  elif [[ -f /tmp/rclone-r2.conf ]]; then
    CONF=/tmp/rclone-r2.conf
  else
    echo "missing rclone config: ${ROOT}/.secrets/rclone-r2.conf or /tmp/rclone-r2.conf" >&2
    exit 1
  fi
fi

DEST="${R2_DEST:-r2:runp}"
case "${DEST}" in
  r2:nkd-hg|r2:rty|r2:russel|r2:nkd-hg/*|r2:rty/*|r2:russel/*)
    echo "refusing to write wall bucket ${DEST}" >&2
    exit 1
    ;;
esac

# Flags from MEMORY #260 / #269. rclone 1.75 on Cloudflare R2.
# Tristate flags need =true/=false; a bare --s3-use-unsigned-payload eats the next arg.
exec rclone copy "${ROOT}" "${DEST}" \
  --config "${CONF}" \
  --transfers "${RCLONE_TRANSFERS:-64}" \
  --checkers 32 \
  --fast-list \
  --no-check-dest \
  --s3-no-check-bucket \
  --s3-use-x-id=false \
  --s3-no-head \
  --s3-use-unsigned-payload=true \
  --s3-disable-checksum \
  --s3-sign-accept-encoding=false \
  --exclude 'node_modules/**' \
  --exclude '.venv/**' \
  --exclude '**/.venv/**' \
  --exclude '**/__pycache__/**' \
  --exclude '**/*.pyc' \
  --exclude '.cache/**' \
  --exclude '**/.cache/**' \
  --exclude '**/.git/objects/pack/*.tmp' \
  --log-level INFO \
  "$@"
