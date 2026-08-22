# RAIL-0 — Ladder gate (FROZEN spec, 2026-08-22)

User rulings encoded (DIRECTIVES_INBOX.md, 2026-08-22): (1) the per-asset goal is a LADDER —
$2,000/asset-day where the block's exact ceiling supports it, $1,500 where it does not;
(2) $600/trade is a PREFERENCE (higher-EV trades first), never a gate refusal.
Companion: design/ENTRY_PHASE_B_PLAN.md RAIL-0 card; design/ENTRY_SELECTION_MAP.md decisions.

## Problem
`evaluate_economic_gate` (engine/entry_v2/tabular_calibration.py:445-515) enforces a FLAT
$2,000/asset-day floor (`C.TARGET_ASSET_DAY_USD`, clause at :488) and refuses on
usd_per_trade < $600 (:482-483, pinned at tabular_recovery_contracts.py:242). Both clauses
now misstate the user's goal. Everything else in the gate stays law.

## The law changes (complete list — nothing else changes)

### L1 · Ladder rung per asset (replaces the flat ASSET_DAY_FLOOR clause)
For each asset in C.ASSETS:
```
ceiling_per_day_usd = exact_ceiling_usd_by_asset[asset] / n_eligible_days(asset)
    # n_eligible_days(asset) = count of (asset, day) in evidence.eligible_asset_days —
    # the SAME per-asset denominator the gate already uses at :473-474. Never the
    # portfolio day count (denominator-poison class, DEFECT_CLASSES.md).
rung_usd = 2000.0 if ceiling_per_day_usd * config.minimum_ceiling_capture >= 2000.0
           else 1500.0
    # minimum_ceiling_capture = 0.80 — single source of truth, no new capture constant.
if asset_evaluation.usd_per_asset_day < rung_usd:
    reasons.append(f"ASSET_DAY_LADDER:{asset}")
```
- New constant `LADDER_FALLBACK_ASSET_DAY_USD = 1500.0` beside `TARGET_ASSET_DAY_USD`
  (common.py:63); the rung rule reads both constants, no literal 2000/1500 in the gate.
- Receipt core gains `"ladder": {asset: {"ceiling_usd_per_day": float, "rung_usd": float,
  "rung_supported": bool}}` where rung_supported = (ceiling_per_day_usd *
  minimum_ceiling_capture >= rung_usd). A block whose ceiling cannot support even $1,500 at
  80% capture keeps rung $1,500 (the ladder has exactly two rungs — no goal lowering) and
  reports rung_supported=false, so the failure reads as a ceiling fact, not a model fact.

### L2 · USD_PER_TRADE demoted to reported preference
- Delete the refusal clause at :482-483 (`reasons.append(f"USD_PER_TRADE:{asset}")`).
- Receipt core gains `"usd_per_trade_by_asset": {asset: float}` so the preference is
  REPORTED per asset in every gate receipt.
- `minimum_usd_per_trade` field and its 600.0 pin (contracts:216, :242) STAY — the value is
  the preference reference; only the gate refusal goes. Rename nothing.

### L3 · Schema bump + migration honesty
- Receipt schema string: `QRE2TABECONOMICGATE1` → `QRE2TABECONOMICGATE2`.
- Consequence, owned not discovered: `load_policy_block_result`
  (tabular_evaluation.py:387-399) recomputes the gate on load, so strict reload of
  pre-ladder block artifacts (fit_only/e1r/evaluation/*) now refuses with the existing
  typed "strict block replay gate differs". That refusal is CORRECT (the artifacts are
  superseded law) and must be covered by a test, not silenced.
- New tool `tools/regate_policy_block.py`: loads a published block artifact JSON, rebuilds
  `BlockReplayEvidence` exactly as `load_policy_block_result` does, applies the CURRENT
  gate, writes `<artifact>.regate.json` receipt {old_reasons, new_reasons, ladder,
  gate_receipt_sha256}. Carries `--selftest` (house single-file-tool law) with a red
  fixture. This is how old blocks are read under the new law.

## Acceptance scenarios (SC ids bind spec→test→receipt)
- **SC-RAIL0-1** Given synthetic evidence, per-asset ceiling $2,870/day and replay
  $1,900/asset-day on every asset → Then reasons contain ASSET_DAY_LADDER for each asset
  (rung $2,000 applied) and ladder receipt shows rung_usd=2000.
- **SC-RAIL0-2** Given the SAME replay dollars with ceiling $1,900/day → Then the ladder
  clause passes (rung $1,500; $1,600–1,900/day ≥ rung — use $1,600/day replay per the plan
  card) and the receipt names rung_usd=1500, rung_supported=true.
- **SC-RAIL0-3** Given evidence whose ONLY old-gate failure is usd_per_trade $450 < $600 →
  Then laws_pass=True and usd_per_trade_by_asset reports the $450. (The mutant that proves
  the demotion; before the change this exact fixture must FAIL — run it red first.)
- **SC-RAIL0-4** Given ceiling $1,200/day and replay $1,300/day → Then reasons contain
  ASSET_DAY_LADDER (rung $1,500 held) and rung_supported=false.
- **SC-RAIL0-5** Regression: re-gating the two frozen E1R blocks (E1R_frozen_FORWARD and
  E1R_raw_THRESHOLD artifacts) via tools/regate_policy_block.py still yields laws_pass=False
  with non-empty reasons ($0 trades cannot pass the ladder). Receipt files land beside the
  artifacts.
- **SC-RAIL0-6** Strict reload of a pre-ladder artifact refuses with "strict block replay
  gate differs" (typed, loud).
- **SC-RAIL0-7** Mutant on the rung boundary: ceiling_per_day exactly $2,500 → rung $2,000
  (0.8×2500=2000 ≥ 2000); ceiling $2,499 → rung $1,500. Both asserted.
- Every other existing gate clause keeps its current tests green (portfolio cap, MDD,
  CLOSED_K1, coverage, MINIMUM_TRADES, ceiling capture, portfolio floors — all unchanged).

## Verify
- Static: `python3 -m unittest engine.entry_v2.test_tabular_ladder_gate` (new module, seen
  RED first per driving-tests-first) and the existing gate tests.
- Real-path: `python3 tools/regate_policy_block.py --selftest` then the SC-RAIL0-5 run on
  the real E1R artifacts, receipts committed.

## Out of scope
Threshold selection preference-ordering (design-round output), any decide()/policy change
(A1 lane owns), portfolio floor values, 2025H2, generator.
