#!/usr/bin/env bash
# ci/wp8b_native_carriers_realfile_gate.sh — the WP8b real-file artifact run.
#
# WP8b brief, REAL-FILE CHECK (payload read authorized for this work package on
# EXACTLY the three s125 streams WP8a already opened, and no others):
#   /workspace/data/tokens/stock_quotes/IWM/2022/2022-07-05.parquet
#   /workspace/data/tokens/stock_trades/IWM/2022/2022-07-05.parquet
#   /workspace/data/tokens/options_prints/IWM/2022/2022-07-05.parquet
#
#   "build micro+bin carriers for the D0 watch roster; report: group-table sizes
#    per modality, mean/max valid recent-128 lengths, bin occupancy stats,
#    truncation-count censuses (full print); two-run byte identity; wall/RSS
#    (budget: <=6s incremental over WP8a's 5.65s, RSS <=6GB)."
#
# WHAT THIS GATE PROVES:
#   * the SIDE-NEUTRAL reduced group table is built once per modality over a
#     whole real session at the ruling's widths (74/67/101 = the card's 69/65/89
#     plus the min block the reflected side's max needs);
#   * the loader's orientation law is byte-compared against the per-side
#     reduction on real sampled rows of every modality, both sides;
#   * the 128-group micro carrier and the 120-bin full carrier are built for
#     every D0 action of the sealed s125 roster and refuse nothing;
#   * every bin of every decision is accounted for: 120 x decisions, split into
#     pre-open pads, empty and occupied bins;
#   * two full runs are byte-identical, INCLUDING the reduced group-vector cells
#     and every carrier index (the receipt's feature fingerprint covers them);
#   * the WP8b budget: total wall <= WP8a's 5.65s + 6s, peak RSS <= 6GB.
#
# usage: wp8b_native_carriers_realfile_gate.sh [build_dir]  (default: release)
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/release}"
PROBE="${BUILD_DIR}/bin/qr_carriers_probe"
SEAL="${BUILD_DIR}/bin/qr_candidates_seal"
OUT="/workspace/artifacts/cache/cpp/wp8b"

QUOTES_ROOT="/workspace/data/tokens/stock_quotes/IWM"
TRADES_ROOT="/workspace/data/tokens/stock_trades/IWM"
OPTIONS_ROOT="/workspace/data/tokens/options_prints/IWM"
# The roster is WP6's, exactly as the WP8a gate reads it.
ROSTER="/workspace/artifacts/cache/cpp/wp8a/roster_s125/roster.tsv"

# WP8a measured 5.654s; the brief allows 6s of increment on top of it.
BUDGET_SECONDS=11.65
BUDGET_RSS_KIB=6291456

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

if [[ ! -f "${ROSTER}" ]]; then
  echo "== session-125 roster (qr_candidates_seal, WP6's authority)"
  if [[ ! -x "${SEAL}" ]]; then
    echo "FAIL: no roster at ${ROSTER} and no qr_candidates_seal at ${SEAL}" >&2
    exit 1
  fi
  if ! "${SEAL}" --out "$(dirname "${ROSTER}")" --stop 125 --resolve 125 --skip-parquet-digest \
       > "${OUT}/seal.log" 2>&1; then
    echo "FAIL: the candidate seal refused; see ${OUT}/seal.log" >&2
    exit 1
  fi
fi

run_probe() {
  local tsv="$1" log="$2"
  if ! "${PROBE}" --quotes "${QUOTES_ROOT}" --trades "${TRADES_ROOT}" \
       --options "${OPTIONS_ROOT}" --roster "${ROSTER}" --native --tsv "${tsv}" \
       > "${log}" 2>&1; then
    echo "FAIL: the carriers probe refused; see ${log}" >&2
    tail -n 20 "${log}" >&2
    return 1
  fi
  return 0
}

echo "== session 125: two full WP8b construction runs (DIRECT + NATIVE_ORDER)"
run_probe "${OUT}/run1.tsv" "${OUT}/run1.log" || status=1
run_probe "${OUT}/run2.tsv" "${OUT}/run2.log" || status=1

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

# --- the group tables: one row per group, at the card's own widths ------------
echo "== side-neutral group tables (69/65/89 + the min block = 74/67/101)"
declare -A EXPECT_DIM=([stock_print]=74 [stock_nbbo]=67 [option_print]=101)
declare -A EXPECT_ORIENTED=([stock_print]=69 [stock_nbbo]=65 [option_print]=89)
for mod in stock_print stock_nbbo option_print; do
  rows="$(value "native.${mod}" group_table_rows)"
  dim="$(value "native.${mod}" group_table_dim)"
  oriented="$(value "native.${mod}" oriented_dim)"
  groups="$(value "${mod}" carrier_group_count)"
  cells="$(value "native.${mod}" group_table_cells)"
  printf "   %-13s rows=%-9s neutral_dim=%-4s oriented_dim=%-3s cells=%s\n" \
         "${mod}" "${rows}" "${dim}" "${oriented}" "${cells}"
  if [[ "${dim}" != "${EXPECT_DIM[${mod}]}" || "${oriented}" != "${EXPECT_ORIENTED[${mod}]}" ]]; then
    echo "FAIL: ${mod} widths are ${dim}/${oriented}, not ${EXPECT_DIM[${mod}]}/${EXPECT_ORIENTED[${mod}]}" >&2
    status=1
  fi
  if [[ "${rows}" != "${groups}" ]]; then
    echo "FAIL: ${mod} has ${rows} reduced vectors for ${groups} carrier groups" >&2
    status=1
  fi
  if [[ "${cells}" != "$((rows * dim))" ]]; then
    echo "FAIL: ${mod} table is ${cells} cells, not rows*dim" >&2
    status=1
  fi
  # The ruling's arithmetic, re-derived on the real table: one neutral table must
  # be smaller than the two per-side tables it replaces.
  if (( cells >= 2 * rows * oriented )); then
    echo "FAIL: ${mod} neutral table is not smaller than the per-side pair it replaces" >&2
    status=1
  fi
done

echo "== side-neutral equivalence on real rows (orient(neutral) vs the per-side reduction)"
for mod in stock_print stock_nbbo option_print; do
  spot="$(value "native.${mod}" orientation_spot_groups)"
  compared="$(value "native.${mod}" orientation_spot_cells_compared)"
  mismatches="$(value "native.${mod}" orientation_spot_mismatches)"
  printf "   %-13s sampled_groups=%-7s cells_compared=%-10s mismatches=%s\n" \
         "${mod}" "${spot}" "${compared}" "${mismatches}"
  if [[ -z "${spot}" || "${spot}" == "0" ]]; then
    echo "FAIL: ${mod} sampled no groups for the orientation check" >&2
    status=1
  fi
  if [[ "${mismatches}" != "0" ]]; then
    echo "FAIL: ${mod} orientation law disagrees with the per-side reduction in ${mismatches} cells" >&2
    status=1
  fi
done

# --- the carriers, per decision ----------------------------------------------
echo "== micro carrier (128 groups) and bin carrier (120 x 1s), per D0 action"
actions="$(value roster d0_actions)"
for mod in stock_print stock_nbbo option_print; do
  decisions="$(value "native.${mod}" decisions)"
  len_sum="$(value "native.${mod}" micro_length_sum)"
  len_max="$(value "native.${mod}" micro_length_max)"
  len_min="$(value "native.${mod}" micro_length_min)"
  pads="$(value "native.${mod}" micro_left_pad_decisions)"
  trunc_sum="$(value "native.${mod}" micro_truncated_sum)"
  trunc_max="$(value "native.${mod}" micro_truncated_max)"
  bins_total="$(value "native.${mod}" bins_total)"
  bins_pad="$(value "native.${mod}" bins_pre_open_pad)"
  bins_nonempty="$(value "native.${mod}" bins_nonempty)"
  bin_members="$(value "native.${mod}" bin_member_groups)"
  bin_max="$(value "native.${mod}" bin_length_max)"
  mean_len="$(awk -v s="${len_sum}" -v n="${decisions}" 'BEGIN { if (n > 0) printf "%.3f", s / n; else print "0" }')"
  echo "   ${mod}:"
  echo "     recent128 length  mean=${mean_len} max=${len_max} min=${len_min} (left-padded decisions: ${pads})"
  echo "     truncated groups  sum=${trunc_sum} max=${trunc_max}"
  echo "     bins              total=${bins_total} pre_open_pad=${bins_pad} nonempty=${bins_nonempty} max_len=${bin_max} member_groups=${bin_members}"
  if [[ "${decisions}" != "${actions}" ]]; then
    echo "FAIL: ${mod} built ${decisions} carriers for ${actions} D0 actions" >&2
    status=1
  fi
  if [[ "${bins_total}" != "$((decisions * 120))" ]]; then
    echo "FAIL: ${mod} produced ${bins_total} bins, not 120 per decision" >&2
    status=1
  fi
  if (( len_max > 128 )); then
    echo "FAIL: ${mod} retained ${len_max} groups in a 128-group carrier" >&2
    status=1
  fi
done

# --- the censuses, printed IN FULL -------------------------------------------
echo "== truncation-count census (log2 buckets, in full)"
awk -F'\t' '$1 ~ /^native\..*\.truncated$/ { printf "   %-32s %-10s %12s\n", $1, $2, $3 }' \
  "${OUT}/run1.tsv"
echo "== micro-slot phase census (in full)"
awk -F'\t' '$1 ~ /^native\..*\.phase_slots$/ { printf "   %-34s %-22s %12s\n", $1, $2, $3 }' \
  "${OUT}/run1.tsv"
echo "== bin-occupancy census (log2 buckets, in full)"
awk -F'\t' '$1 ~ /^native\..*\.bin_occupancy$/ { printf "   %-36s %-10s %12s\n", $1, $2, $3 }' \
  "${OUT}/run1.tsv"

# --- the budget ---------------------------------------------------------------
echo "== budget"
total="$(awk '/^total_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
rss="$(awk '/^peak_rss_kib/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
features="$(awk '/^feature_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
nbbo="$(awk '/^nbbo_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
trades="$(awk '/^trades_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
options="$(awk '/^options_seconds/ { print $2 }' "${OUT}/run1.log" | head -n 1)"
if [[ -z "${total}" ]]; then
  echo "FAIL: the probe printed no timing" >&2
  status=1
else
  echo "-- full construction: ${total}s (nbbo ${nbbo}s + trades ${trades}s + options ${options}s"
  echo "   + per-decision features ${features}s), budget ${BUDGET_SECONDS}s"
  echo "-- peak RSS: ${rss} KiB, budget ${BUDGET_RSS_KIB} KiB"
  if ! awk -v v="${total}" -v b="${BUDGET_SECONDS}" 'BEGIN { exit !(v <= b) }'; then
    echo "FAIL: the construction is over the WP8b budget of ${BUDGET_SECONDS}s" >&2
    status=1
  fi
  if [[ -n "${rss}" ]] && (( rss > BUDGET_RSS_KIB )); then
    echo "FAIL: peak RSS ${rss} KiB is over the WP8b budget" >&2
    status=1
  fi
fi

if [[ ${status} -eq 0 ]]; then
  echo "OK: WP8b native-carrier real-file gate green on the three authorized s125 streams"
fi
exit ${status}
