# 18: Path-dedup live keys (formation, not +180 VWAP)

**What to build:** a read-only probe. Dedup stays the reduction.
The live key MUST be prefix-only. Measure formation-time buckets
and a prefix NMS (same side, close in time, close in aligned
dollars) against the ticket 16 +180 VWAP diagnostic.

Bars unchanged: TRAIN retained_fraction ≥ 0.70, median names ≤ 16,
shrink ≥ rung. FORWARD of a TRAIN survivor is reported, never a
knob. 2021 cannot promote.

Catalog, each causal-first inside the cluster, y unused:

- `snap180_vwap_1x` baseline echo of ticket 16
- `form0_vwap_1x` / `form0_vwap_2x` using VWAP-aligned at age ≈ 0
- `form_side_time_60` / `form_side_time_120` (nested-rung collapse)
- `form_nms_60_1x` prefix NMS: same side, |Δt| ≤ 60 s, |Δaligned| ≤ θ
- `after_form_earliest_16` / `after_form_earliest_12` cap on the
  formation-VWAP causal-first set

**Blocked by:** ticket 16 path-dedup receipt.

**Status:** landed

- [x] `--selftest` splits a planted pair at +180 that stays one
      path at formation; NMS drops the later twin; NaN y refused
- [x] Real run writes
      `artifacts/entry_v2/tabular_recovery/diagnostics/path_dedup_live_20260822.json`
      schema `QRE2PATHLIVE1` sha256
      `4beb0045a2ab01126bb8abe810c0f3a2198886d2ea001c027bf663cb2db268c8`
      form0 coverage 1.0

**Verify:**

1. [selftest] → `python3 tools/probe_path_dedup_live.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_path_dedup_live.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/path_dedup_live_20260822.json`

**What it printed (TRAIN, 2021). Cannot promote.**

Live key that cuts HG to ≤16: `form0_vwap_2x` (VWAP-aligned at
age≈0, width 2θ). HG $2781 ret 0.95 ncell 15; NKD $1775 ret 0.88
ncell 9; SI $2348 ret 0.91 ncell 9. FORWARD HG $2628 / NKD $1681 /
SI $2020. Time-bin and prefix-NMS at 60 s are fat nets (48-65
names). Duplicates share a price, not a 60 s clock. +180 VWAP 1θ
echoes ticket 16 and is not the live key.
