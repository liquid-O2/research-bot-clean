#!/usr/bin/env bash
# ci/wp7_labels_realfile_gate.sh — the WP7 real-file artifact run.
#
# WP7 brief, REAL-FILE CHECK (payload read authorized for this work package on
# EXACTLY the already-opened session-125 streams):
#   /workspace/data/tokens/stock_quotes/IWM/2022/2022-07-05.parquet
#   + the WP6 authority's own sealed candidate roster for that session.
#
# WHAT THIS GATE PROVES:
#   * the watch build covers ALL 25,934 side-resolved primitive candidates —
#     three watches each (77,802 ledger rows), converging onto 31,977 unique
#     (session, decision_ordinal, side) action rows;
#   * the authority decision-ordinal roster really is the sorted union: 23,400
#     registered whole seconds plus the distinct off-second visibilities;
#   * every action row carries a full menu + certificate label, with the
#     per-state census, the per-horizon stop_hit counts and the certificate vs
#     menu_net_15m summary published in full;
#   * the execution envelope binds to the WP5 projection group for group
#     (`verify_against`), so WP7's extrema and WP5's eligible groups cannot
#     drift apart;
#   * two full runs produce byte-identical artifacts;
#   * the WP7 budget: the label pass clears 30s single-threaded (target 10s)
#     and peak RSS stays under 8GB.
#
# usage: wp7_labels_realfile_gate.sh [build_dir]   (default: the release tree)
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/release}"
PROBE="${BUILD_DIR}/bin/qr_labels_probe"
SEAL="${BUILD_DIR}/bin/qr_candidates_seal"
CACHE="/workspace/artifacts/cache/cpp"
OUT_ROOT="${CACHE}/wp7_gate"
COMMITTED="${CPP_ROOT}/tests/fixtures/labels_session125_census.tsv"

QUOTES_ROOT="/workspace/data/tokens/stock_quotes/IWM"
LABEL="IWM_labels_2022-07-05"
# The frozen session-125 numbers this gate pins.
EXPECT_SIDE_RESOLVED=25934
EXPECT_WATCH_ROWS=77802
EXPECT_ACTIONS=31977
EXPECT_SECONDS=23400
# Budgets (WP7 brief): label pass <= 30s (target 10s), RSS <= 8GB.
BUDGET_SECONDS=30.0
TARGET_SECONDS=10.0
MAX_RSS_KIB=8388608

if [[ ! -x "${PROBE}" ]]; then
  echo "FAIL: no qr_labels_probe at ${PROBE} (build the release preset first)" >&2
  exit 1
fi
if [[ ! -x "${SEAL}" ]]; then
  echo "FAIL: no qr_candidates_seal at ${SEAL} (build the release preset first)" >&2
  exit 1
fi
if [[ ! -d "${QUOTES_ROOT}" ]]; then
  echo "FAIL: ${QUOTES_ROOT} is missing" >&2
  exit 1
fi

status=0
fail() { echo "FAIL: $*" >&2; status=1; }

rm -rf "${OUT_ROOT}"
mkdir -p "${OUT_ROOT}"

# --- the roster comes from the WP6 AUTHORITY, sealed here in process ---------
echo "== WP7 gate 1/5: the WP6-sealed session-125 candidate roster"
if ! "${SEAL}" --out "${OUT_ROOT}/roster" --stop 125 --resolve 125 \
     > "${OUT_ROOT}/roster.log" 2>&1; then
  echo "FAIL: the candidate seal refused; see ${OUT_ROOT}/roster.log" >&2
  exit 1
fi
ROSTER="${OUT_ROOT}/roster/roster.tsv"
roster_rows="$(($(wc -l < "${ROSTER}") - 1))"
echo "-- roster rows: ${roster_rows}"
[[ "${roster_rows}" == "${EXPECT_SIDE_RESOLVED}" ]] || \
  fail "the sealed roster carries ${roster_rows} candidates, not ${EXPECT_SIDE_RESOLVED}"

# --- two full runs -----------------------------------------------------------
echo "== WP7 gate 2/5: two full watch+label runs"
for run in 1 2; do
  if ! "${PROBE}" --root "${QUOTES_ROOT}" --roster "${ROSTER}" --label "${LABEL}" \
       --out "${OUT_ROOT}/run${run}" > "${OUT_ROOT}/run${run}.log" 2>&1; then
    echo "FAIL: the label probe refused; see ${OUT_ROOT}/run${run}.log" >&2
    tail -n 20 "${OUT_ROOT}/run${run}.log" >&2
    exit 1
  fi
done

echo "== WP7 gate 3/5: two-run byte identity"
for artifact in summary.tsv labels.tsv watch_ledger.tsv tape_census.tsv watch_census.tsv \
                label_census.tsv; do
  if ! cmp -s "${OUT_ROOT}/run1/${artifact}" "${OUT_ROOT}/run2/${artifact}"; then
    fail "the two runs disagree on ${artifact}"
  fi
done
[[ ${status} -eq 0 ]] && echo "-- six artifacts, byte identical"

# --- the pinned numbers ------------------------------------------------------
echo "== WP7 gate 4/5: the session-125 numbers"
value() { awk -F'\t' -v m="$1" '$2 == m { print $3 }' "${OUT_ROOT}/run1/summary.tsv"; }

for pair in "roster_side_resolved:${EXPECT_SIDE_RESOLVED}" \
            "watch_rows:${EXPECT_WATCH_ROWS}" \
            "action_rows:${EXPECT_ACTIONS}" \
            "decision_roster_registered_seconds:${EXPECT_SECONDS}"; do
  metric="${pair%%:*}"
  expected="${pair##*:}"
  actual="$(value "${metric}")"
  echo "   ${metric} = ${actual} (expected ${expected})"
  [[ "${actual}" == "${expected}" ]] || fail "${metric} is ${actual}, not ${expected}"
done

# The union law, checked arithmetically rather than pinned: the roster is the
# registered seconds plus the DISTINCT off-second visibilities, so its size is
# at least the second count and never more than seconds + visibilities.
roster_size="$(value decision_roster_size)"
off_second="$(value decision_roster_visibilities_off_second)"
if (( roster_size < EXPECT_SECONDS || roster_size > EXPECT_SECONDS + off_second )); then
  fail "the authority roster size ${roster_size} is not the sorted union of ${EXPECT_SECONDS} seconds and ${off_second} off-second visibilities"
fi
echo "   decision_roster_size = ${roster_size} (${EXPECT_SECONDS} seconds + distinct of ${off_second} off-second visibilities)"

# Every watch is either built or typed CLOCK_UNAVAILABLE; every built watch
# lands on an action row; no candidate multiplicity duplicates a fit row.
built="$(value watches_built)"
unavailable="$(value watches_clock_unavailable)"
converged="$(value converged_watches)"
actions="$(value action_rows)"
(( built + unavailable == EXPECT_WATCH_ROWS )) || \
  fail "watches ${built} + ${unavailable} != ${EXPECT_WATCH_ROWS}"
(( converged + actions == built )) || \
  fail "converged ${converged} + actions ${actions} != built ${built}"

# The WP5 binding check ran and matched every lawful mark.
marks="$(value tape_lawful_marks)"
verified="$(value wp5_verified_eligible_groups)"
[[ "${marks}" == "${verified}" ]] || \
  fail "the WP5 binding check verified ${verified} groups against ${marks} lawful marks"
echo "   lawful marks = ${marks}, bound to the WP5 projection group for group"

# Every action row is labelled and retained.
rows="$(value label_rows)"
[[ "${rows}" == "${actions}" ]] || fail "labelled ${rows} of ${actions} action rows"
ok="$(value label_state_OK)"
entry_unavailable="$(value label_state_ENTRY_UNAVAILABLE)"
exit_unavailable="$(value label_state_EXIT_UNAVAILABLE)"
(( ok + entry_unavailable + exit_unavailable == rows )) || \
  fail "the three label states do not partition the ${rows} rows"
echo "   label states: OK=${ok} ENTRY_UNAVAILABLE=${entry_unavailable} EXIT_UNAVAILABLE=${exit_unavailable}"
echo "   stop_hit: 2m=$(value stop_hit_2m) 5m=$(value stop_hit_5m) 15m=$(value stop_hit_15m) 30m=$(value stop_hit_30m) 60m=$(value stop_hit_60m) 120m=$(value stop_hit_120m) close=$(value stop_hit_close)"
echo "   certificate net: mean=$(value certificate_net_mean_cent_trunc)c p50=$(value certificate_net_p50_cent)c max=$(value certificate_net_max_cent)c"
echo "   menu net 15m:    mean=$(value menu_net_15m_mean_cent_trunc)c p50=$(value menu_net_15m_p50_cent)c max=$(value menu_net_15m_max_cent)c"

# --- the published census ----------------------------------------------------
if [[ ! -f "${COMMITTED}" ]]; then
  fail "missing ${COMMITTED}"
elif ! diff <(grep -v '^#' "${COMMITTED}") "${OUT_ROOT}/run1/summary.tsv" > /dev/null; then
  fail "the published session-125 label census no longer matches ${COMMITTED}"
  diff <(grep -v '^#' "${COMMITTED}") "${OUT_ROOT}/run1/summary.tsv" | head -n 20 >&2
else
  echo "-- published census: OK"
fi

# --- the budget --------------------------------------------------------------
echo "== WP7 gate 5/5: budget"
full="$(awk '/^full_seconds/ { print $2 }' "${OUT_ROOT}/run1.log" | head -n 1)"
tape="$(awk '/^tape_seconds/ { print $2 }' "${OUT_ROOT}/run1.log" | head -n 1)"
labels="$(awk '/^label_seconds/ { print $2 }' "${OUT_ROOT}/run1.log" | head -n 1)"
rss="$(awk '/^peak_rss_kib/ { print $2 }' "${OUT_ROOT}/run1.log" | head -n 1)"
if [[ -z "${full}" || -z "${rss}" ]]; then
  fail "the probe printed no timing or RSS"
else
  echo "-- full label pass: ${full}s (envelope ${tape}s + kernel ${labels}s), budget ${BUDGET_SECONDS}s / target ${TARGET_SECONDS}s"
  echo "-- peak RSS: ${rss}KiB, budget ${MAX_RSS_KIB}KiB"
  awk -v v="${full}" -v b="${BUDGET_SECONDS}" 'BEGIN { exit !(v <= b) }' || \
    fail "the label pass is over the WP7 budget of ${BUDGET_SECONDS}s"
  awk -v v="${full}" -v t="${TARGET_SECONDS}" 'BEGIN { exit !(v <= t) }' || \
    echo "   NOTE: over the ${TARGET_SECONDS}s target but inside the hard budget"
  (( rss <= MAX_RSS_KIB )) || fail "peak RSS ${rss}KiB is over the ${MAX_RSS_KIB}KiB budget"
fi

if [[ ${status} -eq 0 ]]; then
  echo "OK: WP7 labels real-file gate green on session 125"
fi
exit ${status}
