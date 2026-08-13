# PORT_M0_VERDICT — targeting decision on the four censuses (orchestrator, 2026-08-13)

Evidence: `artifacts/cache/port/m0/M0_REPORT.md` (generated; spec sha16 4bdf772927b5f316) + census TSVs beside it.
Gates were pre-registered in `design/PORT_M0_CENSUS_SPEC.md` §1 BEFORE any number was seen. Substrate acceptance:
SI-2024 fingerprint MATCH (8/8 committed numbers exact), byte-identity A 167/167 + B 13/13 clean, integrity flags
all explained (foreign-day drops), Yahoo spot-check deltas ≤~1% = session-envelope-vs-RTH-bar + roll basis
(units/multipliers confirmed sane; containment direction holds).

## DECISION: SI + NKD two-asset portfolio CONFIRMED. HG DEFERRED. (§14 provisional ruling now evidence-backed.)

Pre-registered pass rule (plan P-M0e): cost GREEN/CAUTION ∧ walled-phase-close-DP median ≥$2,500/day ∧ recall ≥95%.

| gate | SI | NKD | HG |
|---|---|---|---|
| cost (RT $, share of $1k bar) | **GREEN** $30 / 3.0% | **GREEN** $55 / 5.5% | **GREEN** $30 / 3.0% |
| seatable $/day (walled, phase-close DP, cost-netted; median era-ALL) | **$3,341 PASS** | **$2,672 PASS** | $2,385 **FAIL** |
| recall of oracle top-2 legs @$1,000 (ANCHORED) | **0.996 PASS** | **0.986 PASS** | 0.994 PASS |
| offer floor (median full-session range, companion) | $2,850 PASS | $2,325 fail / 2024-25 $2,963-2,994 PASS | $2,025 FAIL |
| decorrelation (daily return corr vs SI) | — | **0.18** | 0.50 |

SI passes everything in every era (worst year 2021: seats $2,579). NKD passes the registered rule; its weak years
(2021-23) seat $2,135-2,372 — above the $1,500 thin-era floor (D-043), below the $2,000 D-048 bar — while 2024-25
seat $3,385-3,410 with $1,331-1,373 mean per seated trade (co-holds D-021). HG fails the occupancy gate on era-ALL
(and 2023 collapses to $1,929) with the worst per-trade mean ($893, BIND) and the highest correlation to SI — it
diversifies least and pays least. Deferred, not deleted (lockstep code carries it, D-051).

## What the censuses killed or established
1. **The SI cost fear (the 576c analog) is dead**: SI quotes ONE tick wide ($25) at median across all phases and
   eras; $30 RT = 3% of the per-trade bar (IWM lived with 5.8%).
2. **The 5× contamination was real but SI-specific** (parent symbology spreads). NKD/HG unfiltered numbers were
   only mildly inflated (roll days); the re-census moved NKD 2024 mean from $3,404 → $3,207.
3. **The IWM bind (throughput) does not reproduce**: $1k-class candidates run 38-81/day (IWM: ~8.5), G1 generation
   alone already recalls ~99% of the top-2 daily legs, and one position seats 3 trades/day at $1,050-2,174 mean.
   The ceiling CLEARS the D-048 goal with headroom on both chosen assets — on IWM the ceiling itself was the bind.
4. **The wall binds at the $900 cap** (pooled p99 winner MAE $1,955-3,300; p95 ≥$1,187): a meaningful share of
   G1-candidate winners draw >$900 before paying. The seatable numbers already charge those stop-outs. Consequence
   for M1: entry timing/selection inside the leg is the port's risk frontier — D-021's per-trade MAE discipline
   ($300-500) must come from better entries, not from a wider wall (MDD law caps it).
5. **Measure identity documented**: `best_leg = max(max drawup, max drawdown) ≡ range` for any path (one of the
   two always spans min→max). The offer measure IS the session range; the DP seatable number is the real
   feasibility statistic. (CC-M0-2.7 note.)
6. **Honest framing**: all M0 dollars are oracle-selected, wall-truncated, cost-netted CERTIFICATE ceilings —
   feasibility, not forecast. Converting seatable→realized at the D-048 bar is exactly the M1-M3 program
   (generation → labels → features → walk-forward study/blind → frozen taker), now justified to fund.

## Named caveats carried forward
- NKD's D-048 headroom is regime-recent (2024-25); its 2021-23 seats sit $2.1-2.4k. The regime-keyed activation
  law (D-031/D-032) and the walk-forward protocol handle exactly this; the sealed-2026 exam is the arbiter.
- NKD roll weeks: ex-roll splits move medians ≤$56 — no material distortion, dying-book weeks stay flagged.
- 2025 numbers everywhere are GATE-era observations (excluded from wall fit); no fitting has touched them.
- Recall misses (0.4-1.4%) are tagged in `census_d_missed_legs.tsv` → direct input to G2/G3 design (M1).

## Next (M1, per charter §8 + D-049/D-050/D-051)
C++ substrate (DBN decode differential-tested vs Python); G1 confirmation-decay study per asset; G2 level-ledger
generation (D-050 level set incl. virgin levels + volume-profile objects); G3 burst events; label tensor engine
port; atlas screen with learnability ⊥ economic-alignment scoring; all three assets lockstep.
