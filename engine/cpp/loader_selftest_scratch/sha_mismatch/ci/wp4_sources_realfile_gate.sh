#!/usr/bin/env bash
# ci/wp4_sources_realfile_gate.sh — the WP4 real-file artifact run.
#
# WP4 brief, REAL-FILE CHECK (payload read authorized for this work package on
# EXACTLY these files, and no others):
#   1. /workspace/data/tokens/stock_quotes/IWM/2022/2022-07-05.parquet   (s125)
#   2. /workspace/data/tokens/stock_trades/IWM/2022/2022-07-05.parquet   (s125)
#   3. /workspace/data/tokens/options_prints/IWM/2022/2022-07-05.parquet (s125)
#   4. /workspace/data/tokens/option_quotes/IWM/2025/2025-01-02/exp2025-01-02.parquet
#      — the SAME shard WP3 opened, SCHEMA LEVEL ONLY (no page is decoded).
#
# WHAT THIS GATE PROVES, beyond the committed digests:
#   * THE REGISTRY ORACLE (FINAL_PLAN section 6, correctness oracle 2): the C++
#     stock-quote reader reproduces session 125's `raw_rth_row_count` AND its
#     `complete_group_count` exactly — two numbers signed into the frozen
#     registry by a decoder that shares no code with this one;
#   * two full runs produce the same output digest (two-run byte identity);
#   * the WP4 budget: the full 3-stream session read clears 25M values/s
#     single-threaded.
#
# The two small streams are ALSO asserted on every ctest run (RealSources.*).
# The 15.4M-row quote session is here rather than in ctest for the reason WP3
# established for its 704MB shard.
#
# usage: wp4_sources_realfile_gate.sh [build_dir]   (default: the release tree)
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/release}"
PROBE="${BUILD_DIR}/bin/qr_sources_probe"
CACHE="/workspace/artifacts/cache/cpp"
COMMITTED="${CPP_ROOT}/tests/fixtures/real_file_digests.tsv"

QUOTES_ROOT="/workspace/data/tokens/stock_quotes/IWM"
TRADES_ROOT="/workspace/data/tokens/stock_trades/IWM"
PRINTS_ROOT="/workspace/data/tokens/options_prints/IWM"
SHARD="/workspace/data/tokens/option_quotes/IWM/2025/2025-01-02/exp2025-01-02.parquet"

QUOTES_LABEL="IWM_sources_stock_quotes_2022-07-05"
TRADES_LABEL="IWM_sources_stock_trades_2022-07-05"
PRINTS_LABEL="IWM_sources_options_prints_2022-07-05"
SHARD_LABEL="IWM_sources_option_quotes_2025-01-02_exp2025-01-02"

# The value-rate floor from the WP4 brief.
FLOOR=25000000

if [[ ! -x "${PROBE}" ]]; then
  echo "FAIL: no qr_sources_probe at ${PROBE} (build the release preset first)" >&2
  exit 1
fi

status=0
total_values=0
total_seconds=0

run_stream() {
  local stream="$1" root="$2" label="$3" iterations="$4"
  local run1="${CACHE}/wp4_${label}_run1.tsv"
  local run2="${CACHE}/wp4_${label}_run2.tsv"
  local log="${CACHE}/wp4_${label}.log"

  echo "== ${label}"
  if [[ ! -d "${root}" ]]; then
    echo "FAIL: ${root} is missing" >&2
    status=1
    return
  fi
  if ! "${PROBE}" "${stream}" --root "${root}" --label "${label}" --iterations "${iterations}" \
      --tsv "${run1}" > "${log}" 2>&1; then
    echo "FAIL: probe refused; see ${log}" >&2
    tail -n 20 "${log}" >&2
    status=1
    return
  fi
  if ! "${PROBE}" "${stream}" --root "${root}" --label "${label}" --iterations 1 \
      --tsv "${run2}" >> "${log}" 2>&1; then
    echo "FAIL: second probe run failed; see ${log}" >&2
    status=1
    return
  fi

  # --- two-run byte identity of the decoded output ------------------------
  if ! diff "${run1}" "${run2}" > /dev/null; then
    echo "FAIL: ${label} two runs are not byte identical" >&2
    diff "${run1}" "${run2}" >&2
    status=1
  else
    echo "-- two-run byte identity: OK"
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

  # --- the budget's numerator and denominator ------------------------------
  local values seconds
  values="$(awk -F'\t' '$4 == "decoded_values" { print $5 }' "${run1}")"
  seconds="$(awk '/^best_seconds/ { print $2 }' "${log}" | head -n 1)"
  if [[ -n "${values}" && -n "${seconds}" ]]; then
    total_values=$((total_values + values))
    total_seconds="$(awk -v a="${total_seconds}" -v b="${seconds}" 'BEGIN { printf "%.6f", a + b }')"
    echo "-- ${values} values in ${seconds}s"
  else
    echo "FAIL: ${label} produced no throughput numbers" >&2
    status=1
  fi
}

run_stream stock_quotes "${QUOTES_ROOT}" "${QUOTES_LABEL}" 1
run_stream stock_trades "${TRADES_ROOT}" "${TRADES_LABEL}" 3
run_stream options_prints "${PRINTS_ROOT}" "${PRINTS_LABEL}" 3

# --- THE REGISTRY ORACLE ----------------------------------------------------
echo "== registry oracle (session 125 stock quotes)"
quotes_run="${CACHE}/wp4_${QUOTES_LABEL}_run1.tsv"
for metric in registry_rth_rows_match registry_group_count_match; do
  value="$(awk -F'\t' -v m="${metric}" '$4 == m { print $5 }' "${quotes_run}")"
  if [[ "${value}" != "1" ]]; then
    echo "FAIL: ${metric} is '${value}', not 1 — the C++ reader disagrees with the registry" >&2
    status=1
  else
    echo "-- ${metric}: OK"
  fi
done
awk -F'\t' '$4 == "rth_rows" || $4 == "group_count" || $4 == "registry_raw_rth_row_count" ||
            $4 == "registry_complete_group_count" { print "   " $4 " = " $5 }' "${quotes_run}"

# --- the option-quote shard, schema level only ------------------------------
echo "== ${SHARD_LABEL} (schema level only)"
shard_run="${CACHE}/wp4_${SHARD_LABEL}_run1.tsv"
if ! "${PROBE}" option_quotes_schema --file "${SHARD}" --label "${SHARD_LABEL}" \
    --tsv "${shard_run}" > "${CACHE}/wp4_${SHARD_LABEL}.log" 2>&1; then
  echo "FAIL: the authorized option-quote shard no longer matches its pins" >&2
  tail -n 5 "${CACHE}/wp4_${SHARD_LABEL}.log" >&2
  status=1
elif ! diff <(grep -F "${SHARD_LABEL}"$'\t' "${COMMITTED}") \
             <(grep -F "${SHARD_LABEL}"$'\t' "${shard_run}") > /dev/null; then
  echo "FAIL: ${SHARD_LABEL} no longer matches the committed rows" >&2
  status=1
else
  echo "-- committed fixture rows: OK"
fi

# --- the budget -------------------------------------------------------------
echo "== budget"
rate="$(awk -v v="${total_values}" -v s="${total_seconds}" \
        'BEGIN { if (s > 0) printf "%d", v / s; else print 0 }')"
echo "-- full 3-stream session 125 read: ${total_values} values in ${total_seconds}s = ${rate} values/s (floor ${FLOOR})"
if (( rate < FLOOR )); then
  echo "FAIL: the 3-stream read is below the WP4 budget of ${FLOOR} values/s" >&2
  status=1
fi

if [[ ${status} -eq 0 ]]; then
  echo "OK: WP4 real-file gate green on all four authorized files"
fi
exit ${status}
