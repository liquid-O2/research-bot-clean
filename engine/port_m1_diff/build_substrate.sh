#!/usr/bin/env bash
# build_substrate.sh — TRACK A substrate build (PORT_M1_SPEC §1.1/§1.2).
#
#   payload .dbn.zst --qr_futsess_decode--> m1/cpp_days/{ASSET}/{YYYYMMDD}.qrday
#                    --qr_futsess_assemble--> m1/cpp_sessions/{ASSET}/{date}.{bin,json}
#
# Assets run one at a time so the lane's worker cap (6) is never exceeded.
# Launch:  lab/run.sh port-m1-cpp-substrate -- engine/port_m1_diff/build_substrate.sh
set -uo pipefail

BIN=/workspace/artifacts/cache/cpp/release/bin
DATA=/workspace/artifacts/reference/futures_mbp1
M0=/workspace/artifacts/cache/port/m0
M1=/workspace/artifacts/cache/port/m1
WORKERS="${QR_M1_WORKERS:-6}"
ASSETS="${*:-SI HG NKD}"

for tool in qr_futsess_decode qr_futsess_assemble; do
  if [[ ! -x "${BIN}/${tool}" ]]; then
    echo "missing ${BIN}/${tool}; build with: cmake --build --preset release" >&2
    exit 2
  fi
done

status=0
for asset in ${ASSETS}; do
  days="${M1}/cpp_days/${asset}"
  sess="${M1}/cpp_sessions/${asset}"
  mkdir -p "${days}" "${sess}"
  echo "=== ${asset}: decode -> ${days}" >&2
  if ! "${BIN}/qr_futsess_decode" "${asset}" "${DATA}" "${days}" "${WORKERS}"; then
    echo "FAIL: decode ${asset}" >&2
    status=1
    continue
  fi
  echo "=== ${asset}: assemble -> ${sess}" >&2
  if ! "${BIN}/qr_futsess_assemble" "${asset}" "${days}" "${sess}" \
        "${M0}/phases_${asset}.json" "${M0}/repro_si2024.receipt.json"; then
    echo "FAIL: assemble ${asset}" >&2
    status=1
  fi
done
echo "=== substrate build finished, status ${status}" >&2
exit ${status}
