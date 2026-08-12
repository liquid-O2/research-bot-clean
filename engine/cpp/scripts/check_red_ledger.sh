#!/usr/bin/env bash
# scripts/check_red_ledger.sh — the RED-LEDGER LAW gate (FINAL_PLAN section 6).
#
#   "red-ledger law: tests/red_ledger.tsv maps every test -> committed failing-
#    mutant log; CI fails any test without proof it ever failed."
#
# What this enforces, per test enumerated from the built binaries:
#   1. tests/red_ledger.tsv carries a row for the test id;
#   2. the row's mutation_id has a committed patch under tests/mutants/;
#   3. that patch STILL APPLIES to the working tree;
#   4. the row's red_log_path exists AND actually contains a gtest FAILED line
#      naming THAT test — not merely some failure somewhere.
# A green test with no proof that it can go red is not evidence of anything.
#
# WHY (3) IS HERE (repo-health finding, 2026-08-12). A committed patch whose
# anchors have drifted out from under it is a proof that can no longer be
# reproduced: the log still names the test, so checks (2) and (4) pass, and the
# evidence has silently rotted. Ten mutations had rotted this way before the
# check existed. A rotted proof is a FAILED gate, exactly like a missing one.
#
# Usage: check_red_ledger.sh [build_dir]   (default: the dev build tree)
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/dev}"
LEDGER="${CPP_ROOT}/tests/red_ledger.tsv"
MUTANT_DIR="${CPP_ROOT}/tests/mutants"

if [[ ! -f "${LEDGER}" ]]; then
  echo "FAIL: missing red ledger ${LEDGER}" >&2
  exit 1
fi
if [[ ! -d "${BUILD_DIR}/bin" ]]; then
  echo "FAIL: no test binaries under ${BUILD_DIR}/bin (build first)" >&2
  exit 1
fi

mapfile -t BINARIES < <(find "${BUILD_DIR}/bin" -maxdepth 1 -type f -name 'qr_*_tests' | sort)
if [[ ${#BINARIES[@]} -eq 0 ]]; then
  echo "FAIL: found no qr_*_tests binaries under ${BUILD_DIR}/bin" >&2
  exit 1
fi

# --- enumerate every test id in the built suite ----------------------------
tests=()
for binary in "${BINARIES[@]}"; do
  while IFS= read -r id; do
    tests+=("${id}")
  done < <("${binary}" --gtest_list_tests 2>/dev/null | awk '
    /^[^[:space:]]/ { suite = $1; next }
    /^[[:space:]]+/ { name = $1; if (suite != "" && name != "") print suite name }
  ')
done

if [[ ${#tests[@]} -eq 0 ]]; then
  echo "FAIL: enumerated zero tests; the ledger cannot be checked" >&2
  exit 1
fi

# --- header check ----------------------------------------------------------
expected_header=$'test_id\tmutation_id\tred_log_path'
actual_header="$(head -n 1 "${LEDGER}")"
if [[ "${actual_header}" != "${expected_header}" ]]; then
  echo "FAIL: ${LEDGER} header is '${actual_header}', expected 'test_id<TAB>mutation_id<TAB>red_log_path'" >&2
  exit 1
fi

status=0
checked=0
declare -A applies
for id in "${tests[@]}"; do
  row="$(awk -F'\t' -v id="${id}" 'NR > 1 && $1 == id { print; exit }' "${LEDGER}")"
  if [[ -z "${row}" ]]; then
    echo "FAIL: ${id} has no row in tests/red_ledger.tsv (never proven able to fail)" >&2
    status=1
    continue
  fi
  mutation_id="$(cut -f2 <<<"${row}")"
  red_log_rel="$(cut -f3 <<<"${row}")"
  red_log="${CPP_ROOT}/${red_log_rel}"
  patch_file="${MUTANT_DIR}/${mutation_id}.patch"

  if [[ ! -f "${patch_file}" ]]; then
    echo "FAIL: ${id} cites mutation ${mutation_id} but ${patch_file} is missing" >&2
    status=1
    continue
  fi
  # Each patch is dry-run applied ONCE per gate run, not once per citing test:
  # M000 alone is cited by 35 rows.
  if [[ -z "${applies[${mutation_id}]+set}" ]]; then
    # --batch: never prompt. --fuzz=0: every CONTEXT line must match exactly.
    # Line-number OFFSETS are still tolerated, so a patch does not rot merely
    # because the file above it grew — only because the code it names changed.
    # Without --fuzz=0 `patch` silently absorbs a drifted context and the check
    # is vacuous (measured: a deliberately corrupted anchor still "applied").
    if (cd "${CPP_ROOT}" && patch -p1 --dry-run --silent --batch --fuzz=0 < "${patch_file}") >/dev/null 2>&1; then
      applies["${mutation_id}"]=1
    else
      applies["${mutation_id}"]=0
    fi
  fi
  if [[ "${applies[${mutation_id}]}" != "1" ]]; then
    echo "FAIL: ${id} cites mutation ${mutation_id} whose patch no longer applies — the proof has rotted and cannot be reproduced" >&2
    status=1
    continue
  fi
  if [[ ! -f "${red_log}" ]]; then
    echo "FAIL: ${id} cites red log ${red_log_rel} which does not exist" >&2
    status=1
    continue
  fi
  if ! grep -qF "[  FAILED  ] ${id}" "${red_log}"; then
    echo "FAIL: ${red_log_rel} contains no '[  FAILED  ] ${id}' line — the log does not prove this test ever failed" >&2
    status=1
    continue
  fi
  checked=$((checked + 1))
done

# --- ledger hygiene: every row must name a test that still exists -----------
while IFS=$'\t' read -r id mutation_id red_log_rel; do
  [[ "${id}" == "test_id" ]] && continue
  [[ -z "${id}" ]] && continue
  found=0
  for existing in "${tests[@]}"; do
    if [[ "${existing}" == "${id}" ]]; then found=1; break; fi
  done
  if [[ ${found} -eq 0 ]]; then
    echo "FAIL: ledger row ${id} (${mutation_id}, ${red_log_rel}) names a test that no longer exists" >&2
    status=1
  fi
done < "${LEDGER}"

if [[ ${status} -eq 0 ]]; then
  echo "OK: red ledger proves all ${checked} tests have failed at least once (every cited patch still applies)"
fi
exit ${status}
