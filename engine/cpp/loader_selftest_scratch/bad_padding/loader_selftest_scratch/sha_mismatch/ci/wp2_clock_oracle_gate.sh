#!/usr/bin/env bash
# ci/wp2_clock_oracle_gate.sh — the WP2 acceptance gate.
#
#   1. two-run byte identity of the clock oracle print  (the WP acceptance law:
#      "two-run byte identity inside EVERY WP acceptance")
#   2. the print really covers all 1,003 registered sessions
#   3. the WP2 wall: the full 1,003-session cross-check in under 10 seconds
#   4. the differential itself: diff against the frozen Rust SessionClock's own
#      print of the same five fields; the diff must be EMPTY
#
# Step 4 needs the throwaway Rust cross-check binary, which is built once (it
# is not a per-commit artifact — Rust is the frozen differential oracle, D-004):
#
#   cd /workspace/artifacts/cache/cpp/oracle_clock_rs && \
#     CARGO_TARGET_DIR=/workspace/artifacts/cache/ctpool-a cargo build --release --offline
#
# When that binary is absent the differential reports SKIPPED and the rest of
# the gate still runs. The oracle's source bytes are pinned in
# ci/wp2_oracle_receipt.tsv and re-checked here, so a silently edited
# cross-check cannot certify anything. (Its authorities/REGISTRY.tsv row lands
# at WP9, when the differential becomes a merge gate.)
# Nothing here writes outside /workspace/artifacts/cache.
set -uo pipefail

BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/dev}"
OUT_DIR="/workspace/artifacts/cache/cpp/wp2_oracle"
RUST_ORACLE="/workspace/artifacts/cache/ctpool-a/release/oracle_clock_rs"
BUDGET_SECONDS="10"
EXPECTED_LINES=1004  # header + 1,003 sessions

TOOL="${BUILD_DIR}/bin/qr_clock_oracle"
if [[ ! -x "${TOOL}" ]]; then
  echo "FAIL: ${TOOL} is not built" >&2
  exit 1
fi
mkdir -p "${OUT_DIR}"
status=0

started="$(date +%s.%N)"
if ! "${TOOL}" > "${OUT_DIR}/cpp_run1.tsv" 2> "${OUT_DIR}/cpp_run1.err"; then
  echo "FAIL: the clock oracle refused; see ${OUT_DIR}/cpp_run1.err" >&2
  exit 1
fi
if ! "${TOOL}" > "${OUT_DIR}/cpp_run2.tsv" 2> "${OUT_DIR}/cpp_run2.err"; then
  echo "FAIL: the clock oracle refused on its second run" >&2
  exit 1
fi
finished="$(date +%s.%N)"
elapsed="$(awk -v a="${started}" -v b="${finished}" 'BEGIN { printf "%.4f", b - a }')"

if ! cmp -s "${OUT_DIR}/cpp_run1.tsv" "${OUT_DIR}/cpp_run2.tsv"; then
  echo "FAIL: two runs of the clock oracle are not byte-identical" >&2
  status=1
fi

lines="$(wc -l < "${OUT_DIR}/cpp_run1.tsv")"
if [[ "${lines}" -ne "${EXPECTED_LINES}" ]]; then
  echo "FAIL: clock oracle printed ${lines} lines, expected ${EXPECTED_LINES}" >&2
  status=1
fi

if [[ "$(awk -v e="${elapsed}" -v b="${BUDGET_SECONDS}" 'BEGIN { print (e < b) ? 1 : 0 }')" -ne 1 ]]; then
  echo "FAIL: WP2 cross-check budget blown: ${elapsed}s >= ${BUDGET_SECONDS}s" >&2
  status=1
fi

# --- the cross-check's own source bytes ------------------------------------
RECEIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/wp2_oracle_receipt.tsv"
if [[ -f "${RECEIPT}" ]]; then
  while IFS=$'\t' read -r path sha _built; do
    [[ "${path}" == "path" || -z "${path}" ]] && continue
    if [[ ! -f "${path}" ]]; then
      echo "oracle source ${path}: ABSENT (differential will report SKIPPED)"
      continue
    fi
    actual="$(sha256sum "${path}" | cut -d' ' -f1)"
    if [[ "${actual}" != "${sha}" ]]; then
      echo "FAIL: ${path} does not match its receipt sha (${actual} != ${sha})" >&2
      status=1
    fi
  done < "${RECEIPT}"
else
  echo "FAIL: missing ${RECEIPT}" >&2
  status=1
fi

if [[ -x "${RUST_ORACLE}" ]]; then
  if ! "${RUST_ORACLE}" > "${OUT_DIR}/rust.tsv" 2> "${OUT_DIR}/rust.err"; then
    echo "FAIL: the Rust clock oracle refused; see ${OUT_DIR}/rust.err" >&2
    status=1
  elif ! diff -u "${OUT_DIR}/rust.tsv" "${OUT_DIR}/cpp_run1.tsv" > "${OUT_DIR}/diff.txt"; then
    echo "FAIL: C++/Rust clock differential is NOT empty; see ${OUT_DIR}/diff.txt" >&2
    head -20 "${OUT_DIR}/diff.txt" >&2
    status=1
  else
    echo "differential vs frozen Rust SessionClock: EMPTY over 1,003 sessions"
  fi
else
  echo "differential vs frozen Rust SessionClock: SKIPPED (${RUST_ORACLE} not built)"
fi

echo "[budget] clock oracle, two full 1,003-session runs: ${elapsed}s (wall ${BUDGET_SECONDS}s)"
exit ${status}
