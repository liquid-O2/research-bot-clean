# 20: Formation-VWAP width grid for 94% live retention

**What to build:** one probe. Same live coalescer as ticket 18
(formation VWAP-aligned, causal-first). Widths 1.00, 1.25, 1.50,
1.75, 2.00 × TRAIN θ, plus merge-adjacent at 1θ. Per-asset TRAIN
letter: among keys with median names ≤ 16 and shrink ≥ rung, the
highest retained_fraction. Target ret ≥ 0.94. FORWARD of the TRAIN
pick is reported, never a knob. 2021 cannot promote.

**Blocked by:** ticket 18.

**Status:** landed

- [x] `--selftest` 2× width keeps planted winner; NaN y refused
- [x] Real run writes
      `artifacts/entry_v2/tabular_recovery/diagnostics/path_dedup_width_20260822.json`
      schema `QRE2PATHWID1` sha256
      `6348a09da39ca5436449c7066646829f17ed4e213185198475eff776623af646`

**What it printed (TRAIN). Cannot promote. 94% on all three is not in this grid.**

HG 1.75θ ret 0.970 ncell 16 shrink $2846 (FORWARD ret 0.927). HG 2θ
ret 0.948 ncell 15 FORWARD 0.936. NKD best ≤16 is 1θ ret 0.917 ncell
15. SI best ≤16 is 1θ ret 0.934 ncell 15. Merge-adjacent at 1θ kills
(NKD ret 0.66 ncell 3). The leftover 2-8% vs hindsight unique-path
is the representative (first vs later twin), not the width.

**Verify:**

1. [selftest] → `python3 tools/probe_path_dedup_width.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_path_dedup_width.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/path_dedup_width_20260822.json`
