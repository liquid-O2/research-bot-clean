#!/usr/bin/env bash
# ci/wp9_differential_gate.sh — THE WP9 MERGE GATE.
#
# SPEC (FINAL_PLAN.md section 6, correctness oracle 2, verbatim): the full-scope
#   registry oracle "+ per-column colsum/checksum differential vs Rust across
#   all 625 (minutes) — **WP9 merge gate**".
# SPEC (WP9 brief, verbatim): "(f) wire as ci/wp9_differential_gate.sh (merge
#   gate; the full-625 runs archive their verdicts under artifacts/cache/cpp/
#   wp9/ and the gate re-checks the archived verdict shas + reruns the 3 probe
#   sessions live)".
#
# WHY THE GATE IS SPLIT THIS WAY. The full-scope differential decodes 7.46
# billion rows twice, once per language; that is an artifact run, not a
# per-commit gate. What a per-commit gate CAN do, and what this one does, is:
#
#   1. RE-CHECK THE ARCHIVE, by sha. A verdict file is evidence only if it is
#      the same bytes the full-scope run wrote. A truncated archive is the exact
#      attack that turns "no FAIL rows" into a lie, because the FAIL rows are
#      simply not in the file any more — so the sha is re-computed and the file
#      is re-parsed, and any waiver id outside the closed set is a refusal.
#   2. RE-CHECK THE ORACLE BINARY, by source sha. The Rust side of the
#      differential is a separately-built diagnostic (it counts wrong-civil-day
#      attachments where the production build aborts). It is rebuilt here from
#      its own source and made to print its embedded source sha256, which must
#      equal the pinned one — so the archive names the binary that produced it.
#   3. RERUN THREE SESSIONS LIVE, end to end: both dumps, the byte differential,
#      the WCD reconciliation and the comparator, on ordinals 125 / 437 / 749 —
#      first, exact midpoint, last. Ordinal arithmetic, never hash selection.
#
# Nothing here writes outside /workspace/artifacts/cache. Nothing downloads:
# the Rust build is `--offline` against the already-resolved registry.
#
# usage: wp9_differential_gate.sh [build_dir]   (default: the release tree)
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/release}"
DUMP="${BUILD_DIR}/bin/qr_census_dump"
COMPARE="${BUILD_DIR}/bin/qr_census_compare"
WP9="/workspace/artifacts/cache/cpp/wp9"
ORACLE_SRC="/workspace/artifacts/cache/cpp/oracle_diff_rs"
ORACLE_BIN="/workspace/artifacts/cache/ctpool-a/release/oracle_diff_rs"
PINS="${CPP_ROOT}/tests/fixtures/wp9_archive_pins.tsv"
TOKENS="/workspace/data/tokens"

status=0
mkdir -p "${WP9}"

pin() {
  awk -F'\t' -v key="$1" 'NR > 1 && $1 == key { print $2 }' "${PINS}"
}

if [[ ! -x "${DUMP}" || ! -x "${COMPARE}" ]]; then
  echo "FAIL: build the release preset first (${DUMP} / ${COMPARE} missing)" >&2
  exit 1
fi
if [[ ! -f "${PINS}" ]]; then
  echo "FAIL: missing ${PINS}" >&2
  exit 1
fi

# --- 1. the archived verdicts, re-checked by sha ----------------------------
echo "== 1. archived verdicts"
for archive in full625 ladder; do
  path="${WP9}/${archive}_verdict.tsv"
  expected="$(pin "${archive}_verdict_sha256")"
  if [[ -z "${expected}" ]]; then
    echo "FAIL: ${PINS} carries no ${archive}_verdict_sha256 row" >&2
    status=1
    continue
  fi
  if [[ ! -f "${path}" ]]; then
    echo "FAIL: the ${archive} verdict archive ${path} is missing — rerun the full-scope pass" >&2
    status=1
    continue
  fi
  if ! "${COMPARE}" --verify "${path}" --sha "${expected}"; then
    echo "FAIL: the ${archive} verdict archive does not re-check" >&2
    status=1
  else
    echo "-- ${archive}: archive sha and parse OK"
  fi
done

# --- 2. the diagnostic Rust oracle, rebuilt and pinned ----------------------
echo "== 2. the count-and-skip Rust oracle"
if [[ ! -d "${ORACLE_SRC}" ]]; then
  echo "FAIL: the oracle source tree ${ORACLE_SRC} is missing (authorities/REGISTRY.tsv row wp9_oracle_diff_rs)" >&2
  status=1
else
  if ! ( cd "${ORACLE_SRC}" && CARGO_TARGET_DIR=/workspace/artifacts/cache/ctpool-a \
         cargo build --offline --release > "${WP9}/oracle_build.log" 2>&1 ); then
    echo "FAIL: the diagnostic oracle does not build; see ${WP9}/oracle_build.log" >&2
    tail -n 20 "${WP9}/oracle_build.log" >&2
    status=1
  else
    echo "-- oracle build: OK"
  fi
fi

# --- 3. the three probe sessions, live end to end ---------------------------
echo "== 3. live probe (ordinals 125 / 437 / 749)"
probe_cpp="${WP9}/gate_probe_cpp.tsv"
probe_rust="${WP9}/gate_probe_rust.tsv"
probe_receipt="${WP9}/gate_probe_receipt.tsv"
probe_verdict="${WP9}/gate_probe_verdict.tsv"

if ! "${DUMP}" --root "${TOKENS}" --out "${probe_cpp}" --ordinals probe --bytes --workers 3 \
     > "${WP9}/gate_probe_cpp.log" 2>&1; then
  echo "FAIL: the C++ probe dump refused; see ${WP9}/gate_probe_cpp.log" >&2
  tail -n 10 "${WP9}/gate_probe_cpp.log" >&2
  status=1
fi
if [[ -x "${ORACLE_BIN}" ]]; then
  if ! "${ORACLE_BIN}" --root "${TOKENS}" --out "${probe_rust}" --receipt "${probe_receipt}" \
       --ordinals probe --bytes --wcd-mode count --workers 3 \
       > "${WP9}/gate_probe_rust.log" 2>&1; then
    echo "FAIL: the Rust probe dump refused; see ${WP9}/gate_probe_rust.log" >&2
    tail -n 10 "${WP9}/gate_probe_rust.log" >&2
    status=1
  fi
  # The oracle binary prints the sha256 of its OWN embedded source, so the pin
  # binds the archive to the source that produced it.
  measured_source="$(awk -F'\t' '$1 == "source_sha256" { print $2 }' "${probe_receipt}" 2>/dev/null)"
  expected_source="$(pin "oracle_diff_rs_source_sha256")"
  if [[ -z "${expected_source}" ]]; then
    echo "FAIL: ${PINS} carries no oracle_diff_rs_source_sha256 row" >&2
    status=1
  elif [[ "${measured_source}" != "${expected_source}" ]]; then
    echo "FAIL: the diagnostic oracle's source sha is ${measured_source}, pinned ${expected_source}" >&2
    status=1
  else
    echo "-- oracle source sha: OK"
  fi
else
  echo "FAIL: no oracle binary at ${ORACLE_BIN}" >&2
  status=1
fi

if [[ -s "${probe_cpp}" && -s "${probe_rust}" ]]; then
  if ! "${COMPARE}" --cpp "${probe_cpp}" --rust "${probe_rust}" --out "${probe_verdict}"; then
    echo "FAIL: the live probe differential is not clean; see ${probe_verdict}" >&2
    status=1
  else
    echo "-- live probe differential: OK"
  fi
  # The probe must actually have compared the byte images, not just counters:
  bytes_rows="$(awk -F'\t' '$1 ~ /row_sha256$/ && $4 == "PASS"' "${probe_verdict}" | wc -l)"
  if (( bytes_rows < 9 )); then
    echo "FAIL: the live probe produced ${bytes_rows} passing byte digests, expected 9 (3 sessions x 3 streams)" >&2
    status=1
  else
    echo "-- live probe byte identity: ${bytes_rows} digests"
  fi
fi

echo
if [[ ${status} -eq 0 ]]; then
  echo "OK: WP9 differential gate green"
else
  echo "WP9 DIFFERENTIAL GATE FAILED" >&2
fi
exit ${status}
