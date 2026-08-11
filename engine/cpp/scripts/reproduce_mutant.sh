#!/usr/bin/env bash
# scripts/reproduce_mutant.sh — re-run a red-ledger mutation from its patch.
#
# A committed red log is only worth what it can be reproduced with, so every
# mutation_id in tests/red_ledger.tsv has an applicable patch and this driver:
#
#   apply tests/mutants/<id>.patch -> build the `mutant` preset -> run the suite
#   -> print the FAILED ids -> revert the patch, always.
#
# The working tree is restored even when the build or the suite fails.
# usage: reproduce_mutant.sh <mutation_id>
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MUT_ID="${1:-}"
if [[ -z "${MUT_ID}" ]]; then
  echo "usage: $(basename "$0") <mutation_id>   (see tests/mutants/)" >&2
  exit 2
fi
PATCH="${CPP_ROOT}/tests/mutants/${MUT_ID}.patch"
BUILD="/workspace/artifacts/cache/cpp/mutant"
if [[ ! -f "${PATCH}" ]]; then
  echo "no such mutant patch: ${PATCH}" >&2
  exit 2
fi

cd "${CPP_ROOT}" || exit 2
revert() {
  patch -p1 -R --silent < "${PATCH}" || echo "WARNING: could not revert ${MUT_ID}; check git status" >&2
  # A STALE BUILD TREE CORRUPTS THE EVIDENCE CHAIN (lane finding, 2026-08-11).
  # `patch` restores the original bytes, and on a filesystem whose timestamp
  # granularity is coarser than an apply/build/revert cycle the restored file
  # can carry the SAME mtime it had before, so the next `cmake --build` decides
  # the object is up to date and keeps the MUTATED code linked in. The next
  # mutation run then records red tests that have nothing to do with its own
  # patch. Touching every file the patch names makes the rebuild unconditional.
  while IFS= read -r reverted; do
    [[ -f "${reverted}" ]] && touch "${reverted}"
  done < <(sed -n 's|^--- a/||p' "${PATCH}")
}
if ! patch -p1 --silent < "${PATCH}"; then
  echo "FAILED to apply ${MUT_ID}" >&2
  exit 1
fi
trap revert EXIT

echo "== ${MUT_ID}: building the mutant preset"
if ! cmake --preset mutant > /dev/null 2>&1 || ! cmake --build --preset mutant -j 12 > /dev/null 2>&1; then
  echo "== ${MUT_ID}: the mutant does not build (that is itself a red result)"
  exit 0
fi

echo "== ${MUT_ID}: running the suite (expected RED)"
failed=0
for binary in "${BUILD}"/bin/qr_*_tests; do
  output="$("${binary}" 2>&1)"
  while IFS= read -r line; do
    echo "  ${line}"
    failed=$((failed + 1))
  done < <(grep -oE '^\[  FAILED  \] [A-Za-z0-9_]+\.[A-Za-z0-9_]+' <<<"${output}" | sort -u)
done
echo "== ${MUT_ID}: ${failed} distinct tests went red"
[[ ${failed} -gt 0 ]]
