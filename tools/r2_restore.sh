#!/usr/bin/env bash
# Pull r2:runp onto /workspace. GitHub is the code. This is the volume.
#
# Bring keys first. They are not in git.
# Walls: never write nkd-hg, rty, or russel.
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
    echo "keys are not in git. copy the conf onto this box first." >&2
    exit 1
  fi
fi

SRC="${R2_SRC:-r2:runp}"
case "${SRC}" in
  r2:nkd-hg|r2:rty|r2:russel|r2:nkd-hg/*|r2:rty/*|r2:russel/*)
    echo "refusing to use wall bucket ${SRC} as restore source for the workspace tree" >&2
    exit 1
    ;;
esac

exec rclone copy "${SRC}" "${ROOT}" \
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
  --log-level INFO \
  "$@"
