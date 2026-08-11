#!/usr/bin/env bash
# ci/wp3_parquet_realfile_gate.sh — the WP3 real-file artifact run.
#
# WP3 brief, REAL-FILE CHECK (payload read authorized for this work package on
# EXACTLY these two files, and no others):
#   1. /workspace/data/tokens/stock_trades/IWM/2022/2022-07-05.parquet  (session 125)
#   2. /workspace/data/tokens/option_quotes/IWM/2025/2025-01-02/exp2025-01-02.parquet
#      (one shard-era option_quotes shard)
# "decode all projected-type columns, print row count + per-column (count,
#  i64-sum or bitwise-xor for doubles) — these numbers become committed fixtures
#  for WP9's differential."
#
# WHAT THIS GATE PROVES, beyond the numbers:
#   * the decode agrees with the WRITER's own per-chunk min/max/null_count
#     (stats_mismatched must be 0) — an independent oracle, since Polars wrote
#     those statistics with its own encoder;
#   * two full runs produce the same output digest (two-run byte identity);
#   * single-thread throughput clears the WP3 budget of 25M values/s.
#
# The small trades file's numbers are ALSO asserted on every ctest run
# (RealFileDigests.*). The 704MB shard is an artifact run, exactly as WP0's
# whole-corpus census is: a 1.1-billion-value decode does not belong in a
# per-commit suite, twice, under ASan.
#
# usage: wp3_parquet_realfile_gate.sh [build_dir]   (default: the release tree)
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/release}"
PROBE="${BUILD_DIR}/bin/qr_parquet_probe"
CACHE="/workspace/artifacts/cache/cpp"
COMMITTED="${CPP_ROOT}/tests/fixtures/real_file_digests.tsv"

TRADES="/workspace/data/tokens/stock_trades/IWM/2022/2022-07-05.parquet"
TRADES_LABEL="IWM_stock_trades_2022-07-05"
SHARD="/workspace/data/tokens/option_quotes/IWM/2025/2025-01-02/exp2025-01-02.parquet"
SHARD_LABEL="IWM_option_quotes_2025-01-02_exp2025-01-02"

# The value-rate floor from the WP3 brief.
FLOOR=25000000

if [[ ! -x "${PROBE}" ]]; then
  echo "FAIL: no qr_parquet_probe at ${PROBE} (build the release preset first)" >&2
  exit 1
fi

status=0

run_one() {
  local path="$1" label="$2" iterations="$3"
  local run1="${CACHE}/wp3_${label}_run1.tsv"
  local run2="${CACHE}/wp3_${label}_run2.tsv"
  local log="${CACHE}/wp3_${label}.log"

  echo "== ${label}"
  if [[ ! -f "${path}" ]]; then
    echo "FAIL: ${path} is missing" >&2
    status=1
    return
  fi

  if ! "${PROBE}" "${path}" --label "${label}" --iterations "${iterations}" --tsv "${run1}" \
      > "${log}" 2>&1; then
    echo "FAIL: probe refused or found a statistics mismatch; see ${log}" >&2
    tail -n 20 "${log}" >&2
    status=1
    return
  fi
  if ! "${PROBE}" "${path}" --label "${label}" --iterations 1 --tsv "${run2}" \
      >> "${log}" 2>&1; then
    echo "FAIL: second probe run failed; see ${log}" >&2
    status=1
    return
  fi

  # --- two-run byte identity of the decoded output ------------------------
  # Everything except the wall-clock-dependent rows must be identical.
  if ! diff <(grep -v $'\tbest_seconds\t\|\tvalues_per_second\t' "${run1}") \
            <(grep -v $'\tbest_seconds\t\|\tvalues_per_second\t' "${run2}") > /dev/null; then
    echo "FAIL: ${label} two runs are not byte identical" >&2
    diff "${run1}" "${run2}" >&2
    status=1
  else
    echo "-- two-run byte identity: OK"
  fi

  # --- the writer's own statistics agreed ----------------------------------
  local compared mismatched
  compared="$(awk -F'\t' '$4 == "stats_compared" { print $5 }' "${run1}")"
  mismatched="$(awk -F'\t' '$4 == "stats_mismatched" { print $5 }' "${run1}")"
  if [[ "${mismatched}" != "0" || -z "${compared}" || "${compared}" == "0" ]]; then
    echo "FAIL: ${label} writer-statistics cross-check: ${compared} compared, ${mismatched} mismatched" >&2
    status=1
  else
    echo "-- writer statistics: ${compared} column chunks compared, 0 mismatched"
  fi

  # --- throughput budget ---------------------------------------------------
  local rate
  rate="$(awk '/^values_per_second/ { print $2 }' "${log}" | head -n 1)"
  if [[ -z "${rate}" ]]; then
    echo "FAIL: ${label} produced no throughput number" >&2
    status=1
  elif (( rate < FLOOR )); then
    echo "FAIL: ${label} decode ${rate} values/s is below the ${FLOOR} values/s budget" >&2
    status=1
  else
    echo "-- throughput: ${rate} values/s (budget ${FLOOR})"
  fi

  # --- the committed fixture still matches ---------------------------------
  if ! diff <(grep -F "${label}"$'\t' "${COMMITTED}") \
            <(grep -F "${label}"$'\t' "${run1}") > /dev/null; then
    echo "FAIL: ${label} no longer matches the committed rows in ${COMMITTED}" >&2
    diff <(grep -F "${label}"$'\t' "${COMMITTED}") <(grep -F "${label}"$'\t' "${run1}") >&2
    status=1
  else
    echo "-- committed fixture rows: OK"
  fi
}

run_one "${TRADES}" "${TRADES_LABEL}" 5
run_one "${SHARD}" "${SHARD_LABEL}" 1

if [[ ${status} -eq 0 ]]; then
  echo "OK: WP3 real-file gate green on both authorized files"
fi
exit ${status}
