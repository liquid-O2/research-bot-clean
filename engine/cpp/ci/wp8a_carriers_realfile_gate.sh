#!/usr/bin/env bash
# ci/wp8a_carriers_realfile_gate.sh — the WP8a real-file artifact run.
#
# WP8a brief, REAL-FILE CHECK (payload read authorized for this work package on
# EXACTLY these three s125 streams, and no others):
#   /workspace/data/tokens/stock_quotes/IWM/2022/2022-07-05.parquet
#   /workspace/data/tokens/stock_trades/IWM/2022/2022-07-05.parquet
#   /workspace/data/tokens/options_prints/IWM/2022/2022-07-05.parquet
#
# WHAT THIS GATE PROVES:
#   * the three modality channel constructors, DIRECT_RAW, the 1s grid, the 16
#     location values and the 24-field candidate-set rows all run over a whole
#     real session and refuse nothing;
#   * THE REGISTRY ORACLE still holds through the carrier layer: the NBBO
#     carrier reproduces session 125's complete_group_count (2,810,589) and
#     raw_rth_row_count (14,761,979) exactly;
#   * DIRECT_RAW is EXACTLY 60 columns per modality (the card's own words);
#   * two full runs produce byte-identical receipts, including the feature
#     fingerprint over every DIRECT/location/candidate-set cell;
#   * the WP8a budget: the full single-thread s125 construction clears 6s and
#     peak RSS clears 4GB.
#
# The per-modality channel presence censuses, the typed quality ledger, the
# attachment-state histograms and the condition-code histograms are printed IN
# FULL by the probe and land in the receipt.
#
# usage: wp8a_carriers_realfile_gate.sh [build_dir]   (default: the release tree)
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/release}"
PROBE="${BUILD_DIR}/bin/qr_carriers_probe"
SEAL="${BUILD_DIR}/bin/qr_candidates_seal"
OUT="/workspace/artifacts/cache/cpp/wp8a"

QUOTES_ROOT="/workspace/data/tokens/stock_quotes/IWM"
TRADES_ROOT="/workspace/data/tokens/stock_trades/IWM"
OPTIONS_ROOT="/workspace/data/tokens/options_prints/IWM"
ROSTER="${OUT}/roster_s125/roster.tsv"

# The registry's own two numbers for session 125.
EXPECT_ROWS=14761979
EXPECT_GROUPS=2810589
# The brief's budget.
BUDGET_SECONDS=6.0
BUDGET_RSS_KIB=4194304

if [[ ! -x "${PROBE}" ]]; then
  echo "FAIL: no qr_carriers_probe at ${PROBE} (build the release preset first)" >&2
  exit 1
fi
for root in "${QUOTES_ROOT}" "${TRADES_ROOT}" "${OPTIONS_ROOT}"; do
  if [[ ! -d "${root}" ]]; then
    echo "FAIL: ${root} is missing" >&2
    exit 1
  fi
done

status=0
mkdir -p "${OUT}"

# --- the roster comes from WP6, never from this work package ----------------
if [[ ! -f "${ROSTER}" ]]; then
  echo "== session-125 roster (qr_candidates_seal, WP6's authority)"
  if [[ ! -x "${SEAL}" ]]; then
    echo "FAIL: no qr_candidates_seal at ${SEAL} and no cached roster at ${ROSTER}" >&2
    exit 1
  fi
  if ! "${SEAL}" --out "${OUT}/roster_s125" --stop 125 --resolve 125 --skip-parquet-digest \
       > "${OUT}/seal.log" 2>&1; then
    echo "FAIL: the candidate seal refused; see ${OUT}/seal.log" >&2
    exit 1
  fi
fi

run_probe() {
  local tsv="$1" log="$2"
  if ! "${PROBE}" --quotes "${QUOTES_ROOT}" --trades "${TRADES_ROOT}" \
       --options "${OPTIONS_ROOT}" --roster "${ROSTER}" --tsv "${tsv}" > "${log}" 2>&1; then
    echo "FAIL: the carriers probe refused; see ${log}" >&2
    tail -n 20 "${log}" >&2
    return 1
  fi
  return 0
}

echo "== ${QUOTES_ROOT##*/} session 125: two full WP8a construction runs"
run_probe "${OUT}/run1.tsv" "${OUT}/run1.log" || status=1
run_probe "${OUT}/run2.tsv" "${OUT}/run2.log" || status=1

# --- two-run byte identity ---------------------------------------------------
if [[ ${status} -eq 0 ]]; then
  if ! diff "${OUT}/run1.tsv" "${OUT}/run2.tsv" > /dev/null; then
    echo "FAIL: the two construction runs are not byte identical" >&2
    diff "${OUT}/run1.tsv" "${OUT}/run2.tsv" | head -n 20 >&2
    status=1
  else
    echo "-- two-run byte identity: OK"
    echo "   feature fingerprint = $(awk -F'\t' '$2 == "feature_fnv1a64" { print $3 }' "${OUT}/run1.tsv")"
  fi
fi

value() { awk -F'\t' -v s="$1" -v m="$2" '$1 == s && $2 == m { print $3 }' "${OUT}/run1.tsv"; }

# --- CC-008: the pinned condition census is re-derived, not trusted ----------
echo "== CC-008 condition census (session 125, re-derived and diffed vs the pin)"
PIN="${CPP_ROOT}/tests/fixtures/carriers_conditions_session125.tsv"
if ! "${PROBE}" --conditions-only --trades "${TRADES_ROOT}" --ordinal 125 \
     --tsv "${OUT}/conditions_run.tsv" > "${OUT}/conditions_run.log" 2>&1; then
  echo "FAIL: the condition census refused; see ${OUT}/conditions_run.log" >&2
  status=1
elif ! diff "${PIN}" "${OUT}/conditions_run.tsv" > /dev/null; then
  echo "FAIL: the session-125 condition census no longer matches ${PIN}" >&2
  diff "${PIN}" "${OUT}/conditions_run.tsv" | head -n 20 >&2
  status=1
else
  echo "-- pinned census reproduced byte for byte"
  awk -F'\t' '$1 == "quality.stock_print" { printf "   %-20s %10s\n", $2, $3 }' "${PIN}"
fi

# --- THE REGISTRY ORACLE, through the carrier layer --------------------------
echo "== registry oracle (session 125, reproduced by the NBBO carrier)"
rows="$(value stock_nbbo reader_rth_rows)"
groups="$(value stock_nbbo carrier_group_count)"
echo "   carrier_group_count = ${groups} (registry ${EXPECT_GROUPS})"
echo "   reader_rth_rows     = ${rows} (registry ${EXPECT_ROWS})"
if [[ "${rows}" != "${EXPECT_ROWS}" || "${groups}" != "${EXPECT_GROUPS}" ]]; then
  echo "FAIL: the carrier's counts are not the registry's pinned numbers" >&2
  status=1
fi

# --- DIRECT_RAW is exactly 60 columns ----------------------------------------
echo "== DIRECT_RAW shape"
columns="$(value direct_raw columns_per_row)"
echo "   columns_per_row = ${columns} (the card: \"Exactly 60 columns/modality\")"
if [[ "${columns}" != "60" ]]; then
  echo "FAIL: DIRECT_RAW is ${columns} columns, not 60" >&2
  status=1
fi
direct_rows="$(value direct_raw rows)"
actions="$(value roster d0_actions)"
if [[ -n "${actions}" && $((actions * 3)) -ne ${direct_rows} ]]; then
  echo "FAIL: ${direct_rows} DIRECT rows for ${actions} actions x 3 modalities" >&2
  status=1
else
  echo "   ${direct_rows} rows = ${actions} D0 actions x 3 modalities"
fi

# --- the censuses, printed in full -------------------------------------------
echo "== per-modality channel presence censuses (in full)"
awk -F'\t' '$1 ~ /^census\./ { printf "   %-20s %-32s %12s\n", $1, $2, $3 }' "${OUT}/run1.tsv"
echo "== stock-print quality ledger + attachment/condition histograms (in full)"
awk -F'\t' '$1 ~ /^(quality|attach|codes)\./ { printf "   %-28s %-24s %12s\n", $1, $2, $3 }' \
  "${OUT}/run1.tsv"
echo "== 1s midpoint grid"
awk -F'\t' '$1 == "grid_1s" { printf "   %-24s %12s\n", $2, $3 }' "${OUT}/run1.tsv"
echo "== roster / location / candidate set"
awk -F'\t' '$1 ~ /^(roster|location|candidate_set)$/ { printf "   %-16s %-28s %12s\n", $1, $2, $3 }' \
  "${OUT}/run1.tsv"

# --- the budget ---------------------------------------------------------------
echo "== budget"
total="$(awk '/^total_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
rss="$(awk '/^peak_rss_kib/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
nbbo="$(awk '/^nbbo_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
trades="$(awk '/^trades_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
options="$(awk '/^options_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
features="$(awk '/^feature_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
if [[ -z "${total}" ]]; then
  echo "FAIL: the probe printed no timing" >&2
  status=1
else
  echo "-- full construction: ${total}s (nbbo ${nbbo}s + trades ${trades}s + options ${options}s"
  echo "   + per-decision features ${features}s), budget ${BUDGET_SECONDS}s"
  echo "-- peak RSS: ${rss} KiB, budget ${BUDGET_RSS_KIB} KiB"
  if ! awk -v v="${total}" -v b="${BUDGET_SECONDS}" 'BEGIN { exit !(v <= b) }'; then
    echo "FAIL: the construction is over the WP8a budget of ${BUDGET_SECONDS}s" >&2
    status=1
  fi
  if [[ -n "${rss}" ]] && (( rss > BUDGET_RSS_KIB )); then
    echo "FAIL: peak RSS ${rss} KiB is over the WP8a budget" >&2
    status=1
  fi
fi

if [[ ${status} -eq 0 ]]; then
  echo "OK: WP8a carriers real-file gate green on the three authorized s125 streams"
fi
exit ${status}
