#!/usr/bin/env bash
# run_gen.sh — the S2.2 production run (PORT_M1B_SPEC §1 S2 + CC-M1-6.1/7.1).
#
#   lab/run.sh port-m1b-s22 -- engine/port_m1b/run_gen.sh [OUT_SUBDIR]
#
# One process per asset (three, inside the <= 6 worker cap). Each process walks
# its asset's sessions in date order — the level ledger's cross-session memory
# makes that a law — and writes one shard pair per calendar month under
# artifacts/cache/port/m1/gen_cpp/<OUT_SUBDIR>/.
#
# --fomc is the S1.2 NEWS-WINDOW calendar. It is REQUIRED: without it the family
# would silently degrade to the fixed 08:30/10:00 ET slots, which is a quiet
# wrong answer rather than a refusal.
set -uo pipefail

M1=/workspace/artifacts/cache/port/m1
M0=/workspace/artifacts/cache/port/m0
REF=/workspace/artifacts/reference/port_context
BIN=/workspace/artifacts/cache/cpp/release/bin/qr_gen_build
OUT="${1:-roster_v3}"

mkdir -p "${M1}/gen_cpp/${OUT}"
rc=0
pids=()
for asset in SI HG NKD; do
  "${BIN}" --asset "${asset}" \
      --sessions "${M1}/cpp_sessions/${asset}" \
      --out "${M1}/gen_cpp/${OUT}" \
      --sanity "${M1}/skel/sanity/${asset}" \
      --bars "${M0}/bars_${asset}.tsv" \
      --cost "${M0}/census_a_cost_rollup.tsv" \
      --v1 "${M1}/fvol/v1_realized.tsv" \
      --fvol "${M1}/fvol/fvol_forecasts.tsv" \
      --fomc "${REF}/calendar_fomc.csv" &
  pids+=("$!")
done
for pid in "${pids[@]}"; do
  wait "${pid}" || rc=1
done
echo "qr_gen_build: rc=${rc}" >&2
exit "${rc}"
