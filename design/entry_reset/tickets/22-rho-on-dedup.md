# 22: Rho ruler on the live-deduped cell

**What to build:** ticket 01's copula ruler, restricted to names that
survive prefix keep-first at ticket 20 widths (HG 2θ, NKD 1θ, SI 1θ).
Publish AUC at the rung and dollars at AUC 0.60 on the reduced cell
next to the unreduced ruler. Rho=0 is the null.

**Blocked by:** tickets 18 and 20.

**Status:** landed

- [x] `--selftest` runs on a planted reduced cell
- [x] Real run writes
      `artifacts/entry_v2/tabular_recovery/diagnostics/rho_on_dedup_20260822.json`
      schema `QRE2RHODEDUP1` sha256
      `3b5e69c8d249344b1d92b14e2d8e521e81fae83b0a2e0bb81751b51117779c92`

**What it printed (TRAIN). Cannot promote.**

HG n=15 ceiling $2781, AUC at rung 0.87, AUC 0.60 buys $542 (unreduced
was $508 at n=64). NKD n=15 ceiling $1860, AUC at rung 0.90, AUC 0.60
buys $271. SI n=15 ceiling $2409, AUC at rung 0.81, AUC 0.60 buys $446.
Dedup does not lower the ranking bar. The remaining names are distinct
paths. The goal still needs an oracle-grade score among those paths.

**Verify:**

1. [selftest] → `python3 tools/probe_rho_on_dedup.py --selftest`
2. [real] → `OMP_NUM_THREADS=1 python3 tools/probe_rho_on_dedup.py --matrix-dir artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix --out artifacts/entry_v2/tabular_recovery/diagnostics/rho_on_dedup_20260822.json`
