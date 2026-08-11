#!/usr/bin/env bash
# ci/wp10_emit_gate.sh — the WP10 (qr_emit) artifact gate.
#
# The parts of WP10's acceptance that do not belong inside ctest, because they
# either cross the language boundary or move a gigabyte:
#
#   1. TWO-RUN BYTE IDENTITY of a full synthetic shard, manifest included.
#      Two independent runs of qr_emit_make_shard, compared file by file.
#   2. THE C++ -> numpy ROUND TRIP: python/test_decision_tape_loader.py loads
#      the shard run A published and compares every leaf against the formulas
#      recomputed in Python, then exercises the refusal fixtures (sha mismatch,
#      header padding, manifest mismatch, allowlist, runtime truth guard).
#   3. THE STATIC SEPARATION CHECK over every Python file in engine/cpp/python
#      AND every C++ source we own (APPENDIX C4: "static check no truth array is
#      concatenated into any feature tensor"; card section 7(p) / review F4/F5
#      widened the sinks to setitem/put/insert/out= and added the
#      CensusInternalScope scope check, which is a C++ question and therefore
#      needs the C++ files in the argument list). The trainer's own sources join
#      this list at C7.
#   4. THE FEATURE-BUILDER fd CENSUS: a features-only build declaring
#      ProcessRole::FEATURE_BUILDER must finish with an empty truth record and a
#      clean /proc sweep.
#   5. THE WRITE BUDGET: >= 500 MB/s to MooseFS on a 1GB synthetic shard, with
#      the raw write(2) baseline printed beside it so an FS-bound run is
#      reported as FS_BOUND rather than as a pass or a failure of the writer.
#
# usage: wp10_emit_gate.sh [build_dir]   (default: the release build tree)
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/release}"
WORK="/workspace/artifacts/cache/cpp/wp10_gate"
MAKE_SHARD="${BUILD_DIR}/bin/qr_emit_make_shard"
BENCH="${BUILD_DIR}/bin/qr_emit_bench"
status=0

fail() {
  echo "FAIL: $*" >&2
  status=1
}

for binary in "${MAKE_SHARD}" "${BENCH}"; do
  if [[ ! -x "${binary}" ]]; then
    echo "FAIL: missing ${binary} (build the release preset first)" >&2
    exit 1
  fi
done

rm -rf "${WORK}"
mkdir -p "${WORK}"

# --- 1. two-run byte identity ----------------------------------------------
echo "== 1. two-run byte identity of a full synthetic shard"
# The shard path is composed by the tool from the APPENDIX C4 shape, so what
# these two runs are given is a BASE and the published tape lands at
# <base>/s0125/L (orchestrator ruling 2026-08-10).
"${MAKE_SHARD}" --base "${WORK}/run_a" --rows 129 --groups 337 --seconds 391 > \
  "${WORK}/run_a.receipt" || fail "run A did not publish"
"${MAKE_SHARD}" --base "${WORK}/run_b" --rows 129 --groups 337 --seconds 391 > \
  "${WORK}/run_b.receipt" || fail "run B did not publish"

digest_tree() {
  (cd "$1" && find . -type f | LC_ALL=C sort | while IFS= read -r file; do
    printf '%s  %s\n' "$(sha256sum < "${file}" | cut -d' ' -f1)" "${file#./}"
  done)
}
digest_tree "${WORK}/run_a/s0125/L" > "${WORK}/run_a.digests"
digest_tree "${WORK}/run_b/s0125/L" > "${WORK}/run_b.digests"
if ! diff -u "${WORK}/run_a.digests" "${WORK}/run_b.digests" > "${WORK}/identity.diff"; then
  fail "two runs are NOT byte identical (see ${WORK}/identity.diff)"
else
  echo "   OK: $(wc -l < "${WORK}/run_a.digests") files identical across two runs"
  echo "   manifest sha: $(grep 'manifest.tsv' "${WORK}/run_a.digests" | cut -d' ' -f1)"
fi
# The receipts must agree too, on everything except the publish path, which is
# the one thing the two runs were deliberately given differently.
for run in a b; do
  grep -v '^published\b' "${WORK}/run_${run}.receipt" > "${WORK}/run_${run}.receipt.cmp"
done
if ! diff -u "${WORK}/run_a.receipt.cmp" "${WORK}/run_b.receipt.cmp" > "${WORK}/receipt.diff"; then
  fail "the two publish receipts differ (see ${WORK}/receipt.diff)"
fi

# --- 2. the C++ -> numpy round trip and the loader refusals ------------------
echo "== 2. python loader self-test (round trip + refusal fixtures)"
if ! python3 "${CPP_ROOT}/python/test_decision_tape_loader.py" \
      --shard "${WORK}/run_a/s0125/L" --scratch "${WORK}/loader_scratch" \
      > "${WORK}/loader_selftest.log" 2>&1; then
  fail "python loader self-test (see ${WORK}/loader_selftest.log)"
fi
tail -n 1 "${WORK}/loader_selftest.log"

# --- 3. the static truth-separation check ----------------------------------
echo "== 3. static truth-separation check over engine/cpp/python and the C++ tree"
mapfile -t PY_SOURCES < <(find "${CPP_ROOT}/python" -name '*.py' | LC_ALL=C sort)
# Every .cpp/.hpp we own — third_party is vendored and not ours to police.
mapfile -t CPP_SOURCES < <(
  find "${CPP_ROOT}" -path "${CPP_ROOT}/third_party" -prune -o \
       -type f \( -name '*.cpp' -o -name '*.hpp' \) -print | LC_ALL=C sort)
if ! python3 "${CPP_ROOT}/python/check_truth_separation.py" \
      "${PY_SOURCES[@]}" "${CPP_SOURCES[@]}" \
      > "${WORK}/truth_separation.log" 2>&1; then
  fail "static truth-separation check (see ${WORK}/truth_separation.log)"
fi
tail -n 1 "${WORK}/truth_separation.log"

# --- 4. the feature-builder fd census --------------------------------------
echo "== 4. feature-builder fd census on a features-only build"
if ! "${MAKE_SHARD}" --base "${WORK}/builder" --features-only \
      > "${WORK}/builder.receipt" 2>&1; then
  fail "the features-only build did not publish (see ${WORK}/builder.receipt)"
fi
if ! grep -q '^fd_census	CLEAN' "${WORK}/builder.receipt"; then
  fail "the feature builder's fd census is not clean (see ${WORK}/builder.receipt)"
fi
if [[ -e "${WORK}/builder/s0125/L/truth" ]]; then
  fail "a features-only build created a truth/ directory"
fi
grep '^fd_census' "${WORK}/builder.receipt" || true

# --- 5. the write budget ----------------------------------------------------
echo "== 5. write throughput on a 1GB synthetic shard (floor 500 MB/s)"
if ! "${BENCH}" --base "${WORK}/bench" --bytes 1073741824 --floor-mb-s 500 \
      > "${WORK}/bench.tsv" 2>&1; then
  fail "write throughput below the floor (see ${WORK}/bench.tsv)"
fi
cat "${WORK}/bench.tsv"

echo
if [[ ${status} -eq 0 ]]; then
  echo "OK: WP10 emit gate green (artifacts under ${WORK})"
else
  echo "WP10 emit gate FAILED" >&2
fi
exit ${status}
