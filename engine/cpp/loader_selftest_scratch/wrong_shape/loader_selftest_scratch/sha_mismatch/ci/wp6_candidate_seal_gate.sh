#!/usr/bin/env bash
# ci/wp6_candidate_seal_gate.sh — the WP6 real-data artifact gate.
#
# What it proves, on the sealed publications themselves (no fixture):
#   1. the ordinal-0..125 prefix reproduces the frozen feasibility witness
#      NUMBER FOR NUMBER — 3,316,682 data rows, physical stop at byte
#      3,316,834,639, 126 session roots, and safe-leaf sha256
#      549a9225000de0ba27b982434b379da5433eb712807d21756d52c6193c192eed
#      (the digest the task card pins);
#   2. the full ordinal-0..749 prefix seals — 10,684,134 rows, 750 roots — and
#      stops at its own exact boundary byte;
#   3. two independent extractions produce a byte-identical safe leaf;
#   4. the kernel was never asked for more bytes than the ledger requested
#      (/proc/self/io rchar), which is the physical non-prefetch proof;
#   5. session 125's roster resolves through the PUBLICATION dialect profile
#      (ruling CC-003) with every pinned digest verified in process:
#      25,934/25,934 primitive candidates side-resolved (12,987 LONG /
#      12,947 SHORT), 25,759 UNION rows census-only, and 25,934 candidate
#      physical keys authenticated against their member sets;
#   6. the budgets hold: prefix seal <= 10 minutes, peak RSS <= 100MB.
#
# It is a binary run rather than a ctest case because it walks 10.7GB of sealed
# publication text — exactly the rule ci/run_all.sh already applies to the WP0
# whole-corpus census and the WP3 option-quote shard.
#
# usage: wp6_candidate_seal_gate.sh [build_dir]   (default: the release tree)
set -uo pipefail

BUILD_DIR="${1:-/workspace/artifacts/cache/cpp/release}"
SEAL="${BUILD_DIR}/bin/qr_candidates_seal"
OUT_ROOT="/workspace/artifacts/cache/cpp/wp6_gate"

# The frozen witness numbers (task card V4 section 2 + probe_s125_v3/receipt.json).
WITNESS_LEAF_SHA="549a9225000de0ba27b982434b379da5433eb712807d21756d52c6193c192eed"
WITNESS_S125_ROWS=3316682
WITNESS_S125_STOP=3316834639
WITNESS_S125_ROOTS=126
FULL_ROWS=10684134
FULL_ROOTS=750
# The frozen s125 roster numbers (feasibility receipt candidate_fd + the V4
# physical-key check the card requires the production probe to add).
S125_RESOLVED=25934
S125_LONG=12987
S125_SHORT=12947
S125_UNION=25759
# Budgets (FINAL_PLAN section 6: "prefix seal <=10min"; brief: RSS <=100MB).
MAX_PREFIX_SECONDS=600
MAX_RSS_KIB=102400

if [[ ! -x "${SEAL}" ]]; then
  echo "FAIL: no qr_candidates_seal at ${SEAL} (build the release preset first)" >&2
  exit 1
fi

status=0
fail() { echo "FAIL: $*" >&2; status=1; }

field() {  # field <receipt> <name>
  grep -oE "\"$2\": [^,]*" "$1" | head -n 1 | sed -e 's/^[^:]*: //' -e 's/"//g'
}

rm -rf "${OUT_ROOT}"
mkdir -p "${OUT_ROOT}"

echo "== WP6 gate 1/3: the ordinal-0..125 prefix, twice"
for run in 1 2; do
  if ! "${SEAL}" --out "${OUT_ROOT}/s125_run${run}" --stop 125 --resolve 125 --no-roster \
       --skip-parquet-digest > "${OUT_ROOT}/s125_run${run}.log" 2>&1; then
    fail "the s125 seal (run ${run}) refused; see ${OUT_ROOT}/s125_run${run}.log"
    exit 1
  fi
done

R1="${OUT_ROOT}/s125_run1/receipt.json"
[[ "$(field "${R1}" decoded_data_rows)" == "${WITNESS_S125_ROWS}" ]] || \
  fail "s125 decoded rows $(field "${R1}" decoded_data_rows) != ${WITNESS_S125_ROWS}"
[[ "$(field "${R1}" event_end_offset_exclusive)" == "${WITNESS_S125_STOP}" ]] || \
  fail "s125 physical stop $(field "${R1}" event_end_offset_exclusive) != ${WITNESS_S125_STOP}"
[[ "$(field "${R1}" roots_verified)" == "${WITNESS_S125_ROOTS}" ]] || \
  fail "s125 roots $(field "${R1}" roots_verified) != ${WITNESS_S125_ROOTS}"
[[ "$(field "${R1}" safe_leaf_sha256)" == "${WITNESS_LEAF_SHA}" ]] || \
  fail "safe leaf sha $(field "${R1}" safe_leaf_sha256) != the card-pinned ${WITNESS_LEAF_SHA}"

echo "== WP6 gate 2/3: two-run leaf identity"
if ! cmp -s "${OUT_ROOT}/s125_run1/s0125_event_signal_auth.tsv" \
            "${OUT_ROOT}/s125_run2/s0125_event_signal_auth.tsv"; then
  fail "two independent extractions produced different safe leaves"
fi
if [[ "$(field "${OUT_ROOT}/s125_run1/receipt.json" consumed_prefix_sha256)" != \
      "$(field "${OUT_ROOT}/s125_run2/receipt.json" consumed_prefix_sha256)" ]]; then
  fail "two runs consumed different prefix bytes"
fi

echo "== WP6 gate 3/3: the full ordinal-0..749 seal + the s125 roster"
# No --skip-parquet-digest and no --no-roster: this run verifies every pinned
# digest in process and resolves the real roster through the PUBLICATION
# dialect profile.
if ! "${SEAL}" --out "${OUT_ROOT}/full" --stop 749 --resolve 125 \
     > "${OUT_ROOT}/full.log" 2>&1; then
  fail "the full 0..749 seal refused; see ${OUT_ROOT}/full.log"
  exit 1
fi
RF="${OUT_ROOT}/full/receipt.json"
[[ "$(field "${RF}" decoded_data_rows)" == "${FULL_ROWS}" ]] || \
  fail "full seal decoded $(field "${RF}" decoded_data_rows) rows, not ${FULL_ROWS}"
[[ "$(field "${RF}" roots_verified)" == "${FULL_ROOTS}" ]] || \
  fail "full seal verified $(field "${RF}" roots_verified) roots, not ${FULL_ROOTS}"
[[ "$(field "${RF}" safe_leaf_sha256)" == "${WITNESS_LEAF_SHA}" ]] || \
  fail "the full seal's s125 leaf drifted from the card-pinned digest"

[[ "$(field "${RF}" resolved_rows)" == "${S125_RESOLVED}" ]] || \
  fail "s125 resolved $(field "${RF}" resolved_rows) candidates, not ${S125_RESOLVED}"
[[ "$(field "${RF}" admitted_rows)" == "${S125_RESOLVED}" ]] || \
  fail "s125 admitted $(field "${RF}" admitted_rows) candidates, not ${S125_RESOLVED}"
[[ "$(field "${RF}" resolved_long)" == "${S125_LONG}" ]] || \
  fail "s125 LONG $(field "${RF}" resolved_long) != ${S125_LONG}"
[[ "$(field "${RF}" resolved_short)" == "${S125_SHORT}" ]] || \
  fail "s125 SHORT $(field "${RF}" resolved_short) != ${S125_SHORT}"
[[ "$(field "${RF}" nonprimitive_union_census_only_rows)" == "${S125_UNION}" ]] || \
  fail "s125 UNION census-only $(field "${RF}" nonprimitive_union_census_only_rows) != ${S125_UNION}"
[[ "$(field "${RF}" physical_key_authenticated_candidates)" == "${S125_RESOLVED}" ]] || \
  fail "s125 authenticated physical keys $(field "${RF}" physical_key_authenticated_candidates) != ${S125_RESOLVED}"
[[ "$(field "${RF}" side_unavailable_candidates)" == "0" ]] || \
  fail "s125 has $(field "${RF}" side_unavailable_candidates) side-unavailable candidates; the card requires 100% resolution"

# The physical non-prefetch proof: the kernel may not have been asked for more
# bytes than the ledger recorded (1MiB of slack for /proc/self/io itself).
requested="$(field "${RF}" event_requested_bytes)"
rchar="$(field "${RF}" proc_self_io_rchar_delta)"
if (( rchar > requested + 1048576 )); then
  fail "the kernel read ${rchar} bytes for ${requested} requested: a prefetch is present"
fi

# Budgets.
prefix_seconds="$(field "${RF}" prefix_seconds)"
if (( $(printf '%.0f' "${prefix_seconds}") > MAX_PREFIX_SECONDS )); then
  fail "prefix seal took ${prefix_seconds}s, over the ${MAX_PREFIX_SECONDS}s budget"
fi
rss="$(field "${RF}" vm_hwm_kib)"
if (( rss > MAX_RSS_KIB )); then
  fail "peak RSS ${rss}KiB is over the ${MAX_RSS_KIB}KiB budget"
fi

echo
echo "s125:  rows=$(field "${R1}" decoded_data_rows) stop=$(field "${R1}" event_end_offset_exclusive) roots=$(field "${R1}" roots_verified) leaf=$(field "${R1}" safe_leaf_sha256)"
echo "full:  rows=$(field "${RF}" decoded_data_rows) stop=$(field "${RF}" event_end_offset_exclusive) roots=$(field "${RF}" roots_verified)"
echo "s125:  resolved=$(field "${RF}" resolved_rows)/$(field "${RF}" admitted_rows) LONG=$(field "${RF}" resolved_long) SHORT=$(field "${RF}" resolved_short) union_census_only=$(field "${RF}" nonprimitive_union_census_only_rows) physical_keys=$(field "${RF}" physical_key_authenticated_candidates)"
echo "budget: prefix ${prefix_seconds}s (<= ${MAX_PREFIX_SECONDS}s), RSS ${rss}KiB (<= ${MAX_RSS_KIB}KiB)"
if [[ ${status} -eq 0 ]]; then
  echo "OK: WP6 seal gate green"
fi
exit ${status}
