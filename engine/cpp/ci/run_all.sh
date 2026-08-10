#!/usr/bin/env bash
# ci/run_all.sh — the whole gate chain for the C++ substrate, in order:
#
#   1. banned-construct grep gates      (range-limiting guards, unordered containers)
#   2. compile-fail gate                (the frame type wall really is a wall)
#   3. asan/ubsan configure + build     (-fno-sanitize-recover=all)
#   4. asan/ubsan test suite
#   5. dev configure + build            (the tree the red ledger enumerates)
#   6. dev test suite
#   7. red-ledger check                 (every test proven able to fail)
#   8. benchmark gates                  (WP1: registry parse+gate <= 5s, enforced
#                                        inside the suite; WP0 census budget is
#                                        the artifact run, see NOTES below)
#   9. WP2 clock oracle gate             (two-run byte identity, 1,003-session
#                                        coverage, <10s wall, and the empty
#                                        differential vs the frozen Rust clock)
#  10. WP3 parquet real-file gate       (release build; both authorized real
#                                        files: two-run identity, the writer's
#                                        own statistics, 25M values/s, and the
#                                        committed digest rows)
#  11. WP4 sources real-file gate       (release build; the four authorized
#                                        files: THE REGISTRY ORACLE for session
#                                        125 — raw_rth_row_count AND
#                                        complete_group_count reproduced —
#                                        two-run identity, the committed digest
#                                        rows, and the 25M values/s 3-stream
#                                        budget)
#  11b. WP5 nbbo real-file gate       (release build; the one authorized file:
#                                        THE REGISTRY ORACLE reproduced by the
#                                        equal-ms group STATE MACHINE, the
#                                        published census, two-run identity and
#                                        the <=3s pass budget)
#  12. WP6 candidate seal gate         (release build; the sealed event-signal
#                                        publication: the frozen witness numbers
#                                        reproduced, the full 0..749 prefix
#                                        sealed, two-run leaf identity, the
#                                        kernel-level non-prefetch proof, and
#                                        the <=10min / <=100MB budgets)
#
# Nothing here writes outside /workspace/artifacts/cache/cpp. Nothing downloads.
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="/workspace/artifacts/cache/cpp"
status=0
declare -a FAILED_STEPS=()

step() {
  local name="$1"
  shift
  echo
  echo "=============================================================="
  echo "== ${name}"
  echo "=============================================================="
  if "$@"; then
    echo "-- ${name}: OK"
  else
    echo "-- ${name}: FAILED" >&2
    FAILED_STEPS+=("${name}")
    status=1
  fi
}

step "1. banned constructs" "${CPP_ROOT}/ci/check_banned_constructs.sh"
step "2. compile-fail wall" "${CPP_ROOT}/ci/check_compile_fail.sh"
step "3. asan build" bash -c "cd '${CPP_ROOT}' && cmake --preset asan > '${CACHE}/asan_configure.log' 2>&1 && cmake --build --preset asan -j 12 > '${CACHE}/asan_build.log' 2>&1"
step "4. asan tests" bash -c "cd '${CACHE}/asan' && ctest --output-on-failure"
step "5. dev build" bash -c "cd '${CPP_ROOT}' && cmake --preset dev > '${CACHE}/dev_configure.log' 2>&1 && cmake --build --preset dev -j 12 > '${CACHE}/dev_build.log' 2>&1"
step "6. dev tests" bash -c "cd '${CACHE}/dev' && ctest --output-on-failure"
step "7. red ledger" "${CPP_ROOT}/scripts/check_red_ledger.sh" "${CACHE}/dev"
step "7b. red ledger (python)" "${CPP_ROOT}/scripts/check_red_ledger_python.sh"

# --- 8. benchmark gates ----------------------------------------------------
# WP1's budget (registry full parse + digest gate <= 5s) is enforced as a real
# test: RegistryBudget.FullParseAndDigestGateUnderFiveSeconds, run in steps 4
# and 6 above, which fails the suite when the budget is blown.
#
# WP0's budget (dialect census over the whole corpus <= 10min) is a
# whole-corpus artifact run, not a per-commit gate; run it with
#   engine/cpp/tools/qr_dialect_census.py --out-dir /workspace/artifacts/cache/cpp
# and compare against dialect_census.tsv for two-run byte identity.
#
# WP2's budget (1,003 clocks + a full trading day of conversions each, well
# inside the 10s cross-check wall) is enforced as a real test:
# ClockBudget.EveryRegisteredSessionBuildsAndConvertsUnderTheCrossCheckWall.
#
# WP3's budget (single-thread parquet decode >= 25M values/s on the real trades
# file) is enforced as a real test on the small authorized file:
# RealFileBudget.SingleThreadDecodeMeetsTheValueRateFloor, asserted in every
# non-sanitized build; the 704MB option-quote shard's throughput is enforced by
# step 10's artifact run.
#
# WP4's budget (the full session-125 3-stream read >= 25M values/s
# single-thread) is enforced by step 11's artifact run; the fixture-level
# reader laws are enforced inside the suite (qr_sources_tests).
#
# WP11's budget (1,000,000 synthetic actions replayed in <= 2s single-thread,
# through the real quantile gate) is enforced as a real test:
# ReplayBudget.OneMillionActionsReplayInsideTheSingleThreadWall, asserted in
# every non-sanitized build and reported-not-asserted under the sanitizers.
#
# PLACEHOLDER: WP7..WP9 each add their own benchmark gate here as they land
# (FINAL_PLAN section 6 "Efficiency law": slower than budget cannot merge).
step "8. benchmark gates" bash -c "
  echo 'WP1 registry parse+gate budget: enforced inside the test suite (steps 4 and 6)'
  echo 'WP0 census budget: artifact run, see ${CACHE}/dialect_census.tsv'
  echo 'WP2 clock budget: enforced inside the test suite (steps 4 and 6)'
  echo 'WP3 decode budget: enforced inside the test suite (steps 4 and 6) + step 10'
  echo 'WP4 sources budget: 3-stream session-125 read, enforced by step 11'
  echo 'WP5 nbbo budget: session-125 full group-machine pass <= 3s single-thread, enforced by step 11b'
  echo 'WP6 prefix-seal budget (<=10min) + RSS (<=100MB): enforced by step 12'
  echo 'WP10 emit write budget (>=500 MB/s on a 1GB shard to MooseFS): enforced by step 13,'
  echo '                        printed with the raw write(2) baseline so FS_BOUND is visible'
  echo 'WP11 replay budget: 1M actions <= 2s single-thread, enforced inside the test suite (steps 4 and 6)'
  echo 'WP7..WP9: placeholders, added by their own lanes'
"

# --- 9. WP2 clock oracle ---------------------------------------------------
step "9. WP2 clock oracle" "${CPP_ROOT}/ci/wp2_clock_oracle_gate.sh" "${CACHE}/dev"

# --- 10. WP3 parquet real-file gate ----------------------------------------
# Release build + both authorized real files: two-run byte identity, the
# writer-statistics cross-check, the 25M values/s budget, and the committed
# fixture rows. The 704MB shard belongs here rather than in ctest.
step "10. WP3 release build" bash -c "cd '${CPP_ROOT}' && cmake --preset release > '${CACHE}/release_configure.log' 2>&1 && cmake --build --preset release -j 12 > '${CACHE}/release_build.log' 2>&1"
step "10b. WP3 parquet real-file gate" "${CPP_ROOT}/ci/wp3_parquet_realfile_gate.sh" "${CACHE}/release"

# --- 11. WP4 sources real-file gate ----------------------------------------
# Release build + the four authorized files. The registry oracle lives here:
# the C++ stock-quote reader must reproduce session 125's raw_rth_row_count and
# complete_group_count exactly.
step "11. WP4 sources real-file gate" "${CPP_ROOT}/ci/wp4_sources_realfile_gate.sh" "${CACHE}/release"

# --- 11b. WP5 nbbo real-file gate ------------------------------------------
# Release build + the one authorized file. The registry oracle again, this time
# reproduced by the equal-millisecond group STATE MACHINE, plus the published
# census, two-run byte identity, and the <=3s single-thread pass budget.
step "11b. WP5 nbbo real-file gate" "${CPP_ROOT}/ci/wp5_nbbo_realfile_gate.sh" "${CACHE}/release"

# --- 12. WP6 candidate seal gate -------------------------------------------
# Release build + the sealed event-signal publication. Reproduces the frozen
# feasibility witness number for number (3,316,682 rows, physical stop at byte
# 3,316,834,639, 126 roots, the card-pinned safe-leaf digest), seals the full
# ordinal-0..749 prefix (10,684,134 rows, 750 roots), proves two-run leaf
# identity and kernel-level non-prefetch, and enforces the <=10min / <=100MB
# budgets. It walks 10.7GB of text, so it belongs here and not in ctest.
step "12. WP6 candidate seal gate" "${CPP_ROOT}/ci/wp6_candidate_seal_gate.sh" "${CACHE}/release"

# --- WP10 qr_emit artifact gate --------------------------------------------
# Two-run byte identity of a full synthetic shard, the C++ -> numpy round trip
# and the loader's refusal fixtures, the static truth-separation check, the
# feature-builder fd census, and the >= 500 MB/s write budget on 1GB.
step "13. WP10 emit gate" "${CPP_ROOT}/ci/wp10_emit_gate.sh" "${CACHE}/release"

echo
echo "=============================================================="
if [[ ${status} -eq 0 ]]; then
  echo "== ALL GATES GREEN"
else
  echo "== GATES FAILED: ${FAILED_STEPS[*]}" >&2
fi
echo "=============================================================="
exit ${status}
