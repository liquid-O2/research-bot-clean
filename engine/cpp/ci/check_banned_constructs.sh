#!/usr/bin/env bash
# ci/check_banned_constructs.sh — the grep gates named in FINAL_PLAN section 6.
#
#   1. RANGE-LIMITING GUARDS ARE BANNED in qr_core and qr_clock. Overflow and
#      out-of-domain values are refusals; a guard may never substitute a
#      boundary value for the true one. Banned pattern: std::clamp | saturat.
#   3. TEST-ONLY ESCAPE HATCHES may not appear in production code (the clock's
#      without_construction_gate, which skips boundary condition 2).
#   2. UNORDERED CONTAINERS ARE BANNED outside an explicit whitelist
#      (ci/unordered_whitelist.txt) — "no unordered containers on output paths
#      (CI grep gate + whitelist)". Iteration order of an unordered container
#      is a nondeterminism source and two-run byte identity is a law.
#
# Exit 0 = clean, 1 = a banned construct is present.
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHITELIST="${CPP_ROOT}/ci/unordered_whitelist.txt"
status=0

# Scanned tree: the modules we own. Vendored third_party, the CI scripts
# themselves (which must be able to name the banned tokens), the mutant patches
# and the committed red logs are not compiled and are not scanned.
mapfile -t SOURCES < <(
  find "${CPP_ROOT}" \
    -path "${CPP_ROOT}/third_party" -prune -o \
    -path "${CPP_ROOT}/ci" -prune -o \
    -path "${CPP_ROOT}/scripts" -prune -o \
    -path "${CPP_ROOT}/tests/mutants" -prune -o \
    -path "${CPP_ROOT}/tests/red_logs" -prune -o \
    -type f \( -name '*.cpp' -o -name '*.hpp' -o -name '*.h' -o -name '*.cc' \) -print | sort
)

if [[ ${#SOURCES[@]} -eq 0 ]]; then
  echo "FAIL: banned-construct gate found no sources to scan under ${CPP_ROOT}" >&2
  exit 1
fi

# --- gate 1: range-limiting guards in qr_core / qr_clock --------------------
guard_hits=""
for file in "${SOURCES[@]}"; do
  case "${file}" in
    "${CPP_ROOT}"/qr_core/*|"${CPP_ROOT}"/qr_clock/*) ;;
    *) continue ;;
  esac
  hits="$(grep -nE 'std::clamp|saturat' "${file}" || true)"
  if [[ -n "${hits}" ]]; then
    guard_hits+="${file}:"$'\n'"${hits}"$'\n'
  fi
done
if [[ -n "${guard_hits}" ]]; then
  echo "FAIL: range-limiting guard in a refusal module (qr_core/qr_clock):" >&2
  echo "${guard_hits}" >&2
  status=1
fi

# --- gate 2: unordered containers outside the whitelist ---------------------
if [[ ! -f "${WHITELIST}" ]]; then
  echo "FAIL: missing whitelist file ${WHITELIST}" >&2
  exit 1
fi
unordered_hits=""
for file in "${SOURCES[@]}"; do
  rel="${file#"${CPP_ROOT}"/}"
  if grep -qxF "${rel}" "${WHITELIST}"; then
    continue
  fi
  hits="$(grep -nE 'unordered_map|unordered_set' "${file}" || true)"
  if [[ -n "${hits}" ]]; then
    unordered_hits+="${rel}:"$'\n'"${hits}"$'\n'
  fi
done
if [[ -n "${unordered_hits}" ]]; then
  echo "FAIL: unordered container outside ${WHITELIST}:" >&2
  echo "${unordered_hits}" >&2
  status=1
fi

# --- gate 3: test-only escape hatches never reach production code -----------
# SessionClock::without_construction_gate builds a clock WITHOUT boundary
# condition 2, so that conditions 4 and 5 — unreachable from any valid registry
# row under exact arithmetic — can be fired by a counterfixture. It may appear
# only in its own declaration, its own definition, and test files.
hatch_hits=""
for file in "${SOURCES[@]}"; do
  rel="${file#"${CPP_ROOT}"/}"
  case "${rel}" in
    qr_clock/include/qr_clock/session_clock.hpp|qr_clock/src/session_clock.cpp|*/tests/*) continue ;;
  esac
  hits="$(grep -n 'without_construction_gate' "${file}" || true)"
  if [[ -n "${hits}" ]]; then
    hatch_hits+="${rel}:"$'\n'"${hits}"$'\n'
  fi
done
if [[ -n "${hatch_hits}" ]]; then
  echo "FAIL: test-only clock escape hatch used outside its module and tests:" >&2
  echo "${hatch_hits}" >&2
  status=1
fi

if [[ ${status} -eq 0 ]]; then
  echo "OK: banned-construct gates clean over ${#SOURCES[@]} source files"
fi
exit ${status}
