#!/usr/bin/env bash
# scripts/check_red_ledger_python.sh — the RED-LEDGER LAW for the Python side.
#
# scripts/check_red_ledger.sh enumerates GoogleTest binaries, so it cannot see
# the Python suites. The law is the same law:
#
#   "tests/red_ledger.tsv maps every test -> committed failing-mutant log; CI
#    fails any test without proof it ever failed."
#
# Each Python suite's checks are the names in its @check("...") decorators, and
# each one must have a row in tests/red_ledger_python.tsv whose mutation has a
# committed patch and whose log actually carries that check's FAIL line.
#
# SUITES covered:
#   python/test_decision_tape_loader.py   (WP10 loader)
#   python/campaign/test_campaign.py      (the §5 arms + §7 controls + C7 harness)
#   python/test_m25_reading.py            (M2.5: the pinned bounds, the affine
#                                          encoding, the walls, and the
#                                          reachable/unreachable gate fixtures)
#
# usage: check_red_ledger_python.sh
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEDGER="${CPP_ROOT}/tests/red_ledger_python.tsv"
SUITES=(
  "${CPP_ROOT}/python/test_decision_tape_loader.py"
  "${CPP_ROOT}/python/campaign/test_campaign.py"
  "${CPP_ROOT}/python/test_m25_reading.py"
)
MUTANT_DIR="${CPP_ROOT}/tests/mutants"
status=0

for required in "${LEDGER}" "${SUITES[@]}"; do
  if [[ ! -f "${required}" ]]; then
    echo "FAIL: missing ${required}" >&2
    exit 1
  fi
done

expected_header=$'test_id\tmutation_id\tred_log_path'
if [[ "$(head -n 1 "${LEDGER}")" != "${expected_header}" ]]; then
  echo "FAIL: ${LEDGER} header is not 'test_id<TAB>mutation_id<TAB>red_log_path'" >&2
  exit 1
fi

CHECKS=()
for suite in "${SUITES[@]}"; do
  mapfile -t suite_checks < <(sed -n 's/^@check("\(.*\)")$/\1/p' "${suite}")
  if [[ ${#suite_checks[@]} -eq 0 ]]; then
    echo "FAIL: found no @check(...) names in ${suite}" >&2
    exit 1
  fi
  CHECKS+=("${suite_checks[@]}")
done

# A duplicate name across suites would make one row of the ledger cover two
# different tests, which is exactly the hole this gate exists to close.
duplicates="$(printf '%s\n' "${CHECKS[@]}" | sort | uniq -d)"
if [[ -n "${duplicates}" ]]; then
  echo "FAIL: two suites declare the same check name:" >&2
  echo "${duplicates}" >&2
  exit 1
fi

checked=0
for name in "${CHECKS[@]}"; do
  row="$(awk -F'\t' -v id="${name}" 'NR > 1 && $1 == id { print; exit }' "${LEDGER}")"
  if [[ -z "${row}" ]]; then
    echo "FAIL: check '${name}' has no row in tests/red_ledger_python.tsv" >&2
    status=1
    continue
  fi
  mutation_id="$(cut -f2 <<<"${row}")"
  red_log="${CPP_ROOT}/$(cut -f3 <<<"${row}")"
  if [[ ! -f "${MUTANT_DIR}/${mutation_id}.patch" ]]; then
    echo "FAIL: check '${name}' cites ${mutation_id}, whose patch is missing" >&2
    status=1
    continue
  fi
  if [[ ! -f "${red_log}" ]]; then
    echo "FAIL: check '${name}' cites a red log that does not exist" >&2
    status=1
    continue
  fi
  if ! grep -qF "FAIL: ${name}" "${red_log}"; then
    echo "FAIL: ${red_log} does not prove '${name}' ever failed" >&2
    status=1
    continue
  fi
  checked=$((checked + 1))
done

# Ledger hygiene: no row may name a check that no longer exists.
while IFS=$'\t' read -r id mutation_id red_log_rel; do
  [[ "${id}" == "test_id" || -z "${id}" ]] && continue
  found=0
  for name in "${CHECKS[@]}"; do
    if [[ "${name}" == "${id}" ]]; then found=1; break; fi
  done
  if [[ ${found} -eq 0 ]]; then
    echo "FAIL: ledger row '${id}' (${mutation_id}, ${red_log_rel}) names a check that is gone" >&2
    status=1
  fi
done < "${LEDGER}"

if [[ ${status} -eq 0 ]]; then
  echo "OK: red ledger proves all ${checked} python loader checks have failed at least once"
fi
exit ${status}
