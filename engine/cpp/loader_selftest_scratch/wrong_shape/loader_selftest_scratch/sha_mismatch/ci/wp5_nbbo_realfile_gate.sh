#!/usr/bin/env bash
# ci/wp5_nbbo_realfile_gate.sh — the WP5 real-file artifact run.
#
# WP5 brief, REAL-FILE CHECK (payload read authorized for this work package on
# EXACTLY this file, and no other):
#   /workspace/data/tokens/stock_quotes/IWM/2022/2022-07-05.parquet   (s125)
#
# WHAT THIS GATE PROVES:
#   * THE REGISTRY ORACLE, stateful-machine half (FINAL_PLAN section 6,
#     correctness oracle 2): the equal-millisecond group STATE MACHINE — not
#     just the reader underneath it — reproduces session 125's
#     complete_group_count (2,810,589) and raw_rth_row_count (14,761,979)
#     exactly, and seals against both;
#   * two full runs produce byte-identical output (the probe TSV and the
#     census TSV);
#   * the published census still matches tests/fixtures/nbbo_session125_census.tsv
#     row for row;
#   * the WP5 budget: the full session-125 group-machine pass clears 3s
#     single-threaded, with the marginal cost of the machine reported apart
#     from the WP4 decode it sits on.
#
# usage: wp5_nbbo_realfile_gate.sh [build_dir]   (default: the release tree)
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/release}"
PROBE="${BUILD_DIR}/bin/qr_nbbo_probe"
CACHE="/workspace/artifacts/cache/cpp"
COMMITTED="${CPP_ROOT}/tests/fixtures/nbbo_session125_census.tsv"

QUOTES_ROOT="/workspace/data/tokens/stock_quotes/IWM"
LABEL="IWM_nbbo_2022-07-05"
# The registry's own two numbers for session 125, restated here so the gate
# fails loudly if the probe ever stops printing them.
EXPECT_GROUPS=2810589
EXPECT_ROWS=14761979
# The WP5 brief's budget for the full single-thread pass.
BUDGET_SECONDS=3.0

if [[ ! -x "${PROBE}" ]]; then
  echo "FAIL: no qr_nbbo_probe at ${PROBE} (build the release preset first)" >&2
  exit 1
fi
if [[ ! -d "${QUOTES_ROOT}" ]]; then
  echo "FAIL: ${QUOTES_ROOT} is missing" >&2
  exit 1
fi

status=0
run1_tsv="${CACHE}/wp5_nbbo_run1.tsv"
run2_tsv="${CACHE}/wp5_nbbo_run2.tsv"
run1_census="${CACHE}/wp5_census_run1.tsv"
run2_census="${CACHE}/wp5_census_run2.tsv"
run1_log="${CACHE}/wp5_probe_run1.log"
run2_log="${CACHE}/wp5_probe_run2.log"

run_probe() {
  local tsv="$1" census="$2" log="$3"
  if ! "${PROBE}" --root "${QUOTES_ROOT}" --label "${LABEL}" --tsv "${tsv}" \
       --census "${census}" > "${log}" 2>&1; then
    echo "FAIL: the group-machine probe refused; see ${log}" >&2
    tail -n 20 "${log}" >&2
    return 1
  fi
  return 0
}

echo "== ${LABEL}: two full-day group-machine runs"
run_probe "${run1_tsv}" "${run1_census}" "${run1_log}" || status=1
run_probe "${run2_tsv}" "${run2_census}" "${run2_log}" || status=1

# --- two-run byte identity --------------------------------------------------
if [[ ${status} -eq 0 ]]; then
  if ! diff "${run1_tsv}" "${run2_tsv}" > /dev/null; then
    echo "FAIL: the two probe runs are not byte identical" >&2
    diff "${run1_tsv}" "${run2_tsv}" >&2
    status=1
  elif ! diff "${run1_census}" "${run2_census}" > /dev/null; then
    echo "FAIL: the two censuses are not byte identical" >&2
    diff "${run1_census}" "${run2_census}" >&2
    status=1
  else
    echo "-- two-run byte identity: OK"
  fi
fi

# --- THE REGISTRY ORACLE ----------------------------------------------------
echo "== registry oracle (session 125, the STATE MACHINE's reproduction)"
for metric in registry_rth_rows_match registry_group_count_match sealed; do
  value="$(awk -F'\t' -v m="${metric}" '$2 == m { print $3 }' "${run1_tsv}")"
  if [[ "${value}" != "1" ]]; then
    echo "FAIL: ${metric} is '${value}', not 1" >&2
    status=1
  else
    echo "-- ${metric}: OK"
  fi
done
groups="$(awk -F'\t' '$2 == "machine_group_count" { print $3 }' "${run1_tsv}")"
rows="$(awk -F'\t' '$2 == "machine_rth_rows" { print $3 }' "${run1_tsv}")"
echo "   machine_group_count = ${groups} (registry ${EXPECT_GROUPS})"
echo "   machine_rth_rows    = ${rows} (registry ${EXPECT_ROWS})"
if [[ "${groups}" != "${EXPECT_GROUPS}" || "${rows}" != "${EXPECT_ROWS}" ]]; then
  echo "FAIL: the machine's counts are not the registry's pinned numbers" >&2
  status=1
fi

# --- the published census ---------------------------------------------------
echo "== published census"
if [[ ! -f "${COMMITTED}" ]]; then
  echo "FAIL: missing ${COMMITTED}" >&2
  status=1
elif ! diff <(grep -v '^#' "${COMMITTED}") "${run1_census}" > /dev/null; then
  echo "FAIL: the census no longer matches ${COMMITTED}" >&2
  diff <(grep -v '^#' "${COMMITTED}") "${run1_census}" >&2
  status=1
else
  echo "-- committed census rows: OK"
  grep -v '^#' "${COMMITTED}" | awk -F'\t' 'NR > 1 { print "   " $2 " = " $3 }'
fi

# --- the budget -------------------------------------------------------------
echo "== budget"
full="$(awk '/^full_seconds/ { print $2 }' "${run1_log}" | head -n 1)"
read_only="$(awk '/^read_seconds/ { print $2 }' "${run1_log}" | head -n 1)"
machine="$(awk '/^machine_seconds/ { print $2 }' "${run1_log}" | head -n 1)"
if [[ -z "${full}" ]]; then
  echo "FAIL: the probe printed no timing" >&2
  status=1
else
  echo "-- full group-machine pass: ${full}s (WP4 decode ${read_only}s + machine ${machine}s), budget ${BUDGET_SECONDS}s"
  if ! awk -v v="${full}" -v b="${BUDGET_SECONDS}" 'BEGIN { exit !(v <= b) }'; then
    echo "FAIL: the full pass is over the WP5 budget of ${BUDGET_SECONDS}s" >&2
    status=1
  fi
fi

if [[ ${status} -eq 0 ]]; then
  echo "OK: WP5 nbbo real-file gate green on the one authorized file"
fi
exit ${status}
