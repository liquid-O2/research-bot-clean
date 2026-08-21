# ENTRY V2 — PATH TO GOAL (0x-alpha master plan)

- **Written:** 2026-08-21 (~10:00Z)
- **Author:** 0x-alpha (opencode), synthesized from full transcript archaeology (Codex Aug 19 14:47Z → Aug 20 09:56Z; Codex Aug 20 09:56Z → 18:34Z; Grok Aug 20 18:30Z → midnight; Grok Aug 21 live session) + repo state + provenance journals
- **Status:** PLAN ONLY. No phase has been started. Grok (pid 2910403) is actively optimizing the build; its rehearsal child (pid 2786655) and Fable speed pass (pid 1249248) are mid-flight and **untouched by this plan's authorship**.
- **Sources of truth:** raw transcripts (authoritative where repo files lag), `STOP_CHECKPOINT_20260820T182424Z.md`, `provenance/sessions/JOURNAL.md`, receipts under `artifacts/entry_v2/tabular_recovery/rehearsal/`, `design/ENTRY_V2_RECOVERY_PLAN{,_AMENDMENTS}.md`, AGENTS.md.

---

## 1. Problem statement and binding laws

Build a deployable, pre-H2, tabular (CatBoost) delayed-confirmation entry policy for SI / HG / NKD that, measured on untouched forward blocks by canonical chronological replay dollars (never proxies), clears:

| # | Law | Value |
|---|-----|-------|
| L1 | Per-asset economics | ≥ $2,000/asset-day independently for SI, HG, NKD |
| L2 | Portfolio economics | ≥ $3,000/active portfolio-day floor; $6,000/day target |
| L3 | Ceiling capture | ≥ 80% of the exact delayed-candidate ceiling per forward block (90% target) |
| L4 | Seed honesty | Weakest real seed > strongest matched shuffle seed |
| L5 | Trade quality | ≥ $600/trade; MDD ≤ $1,000 |
| L6 | Capacity | K=1 per asset with unlimited sequential reentry; ≤ 12 portfolio entries/day |
| L7 | Frozen invariants | Candidate generator frozen; neural RETIRED; 2025H2 sealed until goal reached |

**Process laws (AGENTS.md, non-negotiable):**
1. No serial `patch → launch → discover next defect` loops. After any failure: freeze launches, audit the complete remaining execution chain in one closure pass before relaunch.
2. Unit/synthetic/mocked tests are regression checks only — never launch-readiness evidence.
3. A launch requires a real production-path rehearsal on authoritative pre-H2 data covering the entire chain.
4. Engineering progress and experimental progress are reported separately. Code/tests/audits are never described as learning or economic results.
5. Economic confidence is measured, not inferred. Classification metrics, oracle headroom, or positive-but-small PnL cannot substitute for the gate.

---

## 2. Where we are right now (snapshot 2026-08-21 ~10:00Z)

**Live processes (do not touch):**

| Process | PID | Role |
|---|---|---|
| grok CLI chat | 2910403 | Session `01a02080-fe17…`, idle-awaiting-user but owns all children below |
| run_tabular_recovery.py | 2786655 (parent bash 2786649) | Rehearsal resume #4 "RESUME_SPAWN" since 07:49:39Z; 16 spawn workers 2796383–2796400 |
| claude "Fable 5" | 1249248 | Independent lossless-speed pass, started 08:49Z; writes `FABLE5_SPEED_RESULT.md` |

**Chain position:** round-0 curriculum COMPLETE on disk (5 real + 5 shuffle seeds action models + `curriculum_round.json`, ~03:53Z). Current run is building/consuming the dense REPLAY cache (42 sessions cached; zero new `.npz` observed since ~07:50 — either cache hits or a silent stall; **Grok's own tripwire governs**: no new `.npz` within 10–15 min ⇒ freeze as model-load hang — that decision belongs to Grok/user, not this plan).

**Inventory at last stop (STOP_CHECKPOINT_20260820T182424Z):** component bundles 1 (+round-0 action fits), rollout rounds 0/2 done, calibration/threshold/replay/economics **all absent**. **No learned dollar has ever been published.** The currently running rehearsal is the first configuration carrying every known fix.

---

## 3. Why we have not reached the goal

### 3.1 Program-level failure chronicle (condensed)

- **v3:** universal no-entry. **v4:** tiny HG/NKD signal, SI dead. Representation probes repeatedly showed better AUROC ≠ better economics.
- **r1–r6 rehearsal refusals; v9:** warm corpus 8m38 then raw_fidelity refusal (236/235 session-set difference).
- **Historical null ledger:** every axis closed with numbers; seating lookahead voided the early program; $/session denominator defect; repeated celebration-retraction cycles.
- **Aug 19 forensic audit:** prior CatBoost null was invalid (double-charged costs, 3/9-vs-12 law mismatch, a $118/day model falsely "accepted").
- **Aug 19 max-effort audit WITHDREW the confirmation lane:** side-parse bug graded all 8,993 trades SHORT; M-regression survivorship; honest book ≈ $0/day. All ignition/grammar "discoveries" downstream of corrupted labels were artifacts. Passive execution (+$84–116/trade) banked.
- **Aug 19 Codex session (14:47Z→):** rebuilt everything on candidate-local outcomes; exact delayed-entry ceiling via MILP (2021-08-04 SI $4,285/3 trades; all-asset day $7,267.50/9 trades; 4-day avg ceiling $7,400.31/day, 80% floor $5,920.25); label geometry audit (old `$600+` label ~85% timing mismatch); clock leakage found (`phase_remaining_sec` 86–92% of score); discretionary PDF library mined (31 PDFs/411 pages → schema v8, 1,351 discretionary features); QRF4 forward-vol publisher (+16.2%/18.5% pooled sigma gain); rank probes (30s age-rank THRESHOLD capture 23.95% vs 13.32% control; FIT-forward stable balanced top-4 33.37% vs 21.36% shuffle); fixed-horizon right-censored 120s targets = $2,710/day = 90.7% of roster ceiling; **oracle fixed-horizon stopping recovers 89.47% ($2,674/day, 30 trades / 7 PLATT days = $624/trade — user-approved cadence)**; acceptance-head war ended at ordinal positive-top-3 FIT-only OOF ceiling $2,248/day vs perfect-score $3,426 = **65.6% recovery — below the 80% law**; deployable global cutoff ceiling $2,009/day; two-head book $466/day (7.8% conversion); learned top-4 sparse-gate ceilings $2,074/$2,698 vs oracle top-4 $3,571/$4,774; top-12 broadening worsened to ~$234/day (**occupancy destroys headroom**). Ended with the Goal-Bound Recovery Plan awaiting approval.
- **Aug 20 Codex session (09:56Z→18:34Z):** executed the plan. One-day real rehearsal 2024-01-03: 853 candidates, exact ceiling $7,192.50, seat-count DP replaces MILP (56.1s → 0.154s). E1R/E2R bounded: 266 sessions / 59,819 candidates / 89 teacher days. Defect class fixed in one closure pass after user's 17:11Z "one fix pass, one review": quadratic watch construction, teacher occupancy leak, realized-PnL field leak, bundle/calibration lineage, CatBoost reserialization, native-thread oversubscription (16×3×64 → 1/worker; 0 shards/58min → 5/~90s), sealed-date guard regex FP on SHA dirs, `Too many open files`, unbounded `validate()` over 10.4GB, `<U2>/<U3>` dtype "drift", `<U1` receipt truncation (`np.full(...,str)` → `sha256_row_array <U64`). Matrix published 17:57Z; first fold fitted 17:58Z; OOF refusal root-caused + fixed; review gates passed (21 → 23 regressions). User STOP 18:23Z before second fold.
- **Aug 20 evening (Grok):** MemPalace hooks fixed ("Memplace thing is completely fixed"); multi-agent workflows built; PASS law made real in code (per-asset $2k + per-asset 80%, portfolio $3k/80%, shuffle `floor_pass` cannot PASS, hidden-asset fail); `_run_neural` RETIRED; action-store resume width 1793; blockers B1–B4 closed; first overnight rehearsal launched ~22:15–22:45Z.
- **Aug 21 overnight→morning (Grok):** refusal cascade — #1 `2026 SEALED: refusing d8=20260820` (seed dir misread as date, ~3.9h wasted); resume#1 "resumed component matrix day stores differ"; resume#2 "resumed component predictions differ" (172s); resume#3 completed round-0 curriculum (~03:53Z). User slammed ETA (24h unacceptable → 4–6h max). FREEZE_SPEED diagnosed CatBoost `predict(thread_count=-1)` → ~158 threads × 16 workers on a 16-vCPU pod + EventPack rehashing + uncached dense features + unused round_0 json. RESUME_SPAWN 07:49Z current; oversubscription **not fully fixed** (workers still ~158 threads); Fable delegated as independent thinker.

### 3.2 Root causes (the honest five)

1. **Label geometry was broken for most of the program.** Corrupted sides, survivorship filters, ~85% timing mismatch in the old label. Every conclusion downstream was an artifact. Only the last 48h produced an exact future-only teacher.
2. **The operative half is genuinely hard.** The honest re-derivation (cleanest instrument ever run): premise CONFIRMED — candidates contain ~$5,019/day of goal-grade outcomes [CI +4,386, +5,683]; operative half REFUTED for the ignition/grammar feature family (winners-vs-losers AUROC 0.496; net of forfeit+spread −$70..−$83/trade; winners realize median 0.5% of their move by +60s; trained skip-books collapse OOS, rank corr +0.006).
3. **Acceptance-head conversion is the unproven link.** Best honest deployable attempt recovered 65.6% ($2,248/day vs $3,426 perfect) on a small slice — below the 80% law. The signal that does survive honest controls lives in the full causal set (30s age-rank real and stable; fixed-horizon stopping mechanism recovers 89.47%) — but causal conversion end-to-end has never been demonstrated.
4. **Serial defect-discovery loops ate the calendar.** Each typed refusal cost hours because iteration latency is high (cold caches, thread explosions, full-chain restarts). The overnight cascade burned ~6h on three refusals that were each cheap to prevent.
5. **Evidence discipline was previously violated** ($118/day false accept; AUC/Brier proxies; hindsight schedulers). Now gated by the four-column verdict and shuffle-seed law — must stay gated.

### 3.3 What is NOT the problem (measured, do not re-litigate)

- **Candidate generator** — user ruling: "candidate is perfect as is, nothing says that is the bottleneck." Premise confirmed at $5k+/day.
- **Model family** — CatBoost oracles are strong wherever labels are clean; neural/sequence encoders measured unjustified (ordered-sequence adds nothing: destroyed twin 0.2475 vs 0.2477).
- **The laws** — K=1/≤12 capacity laws match production; oracle ceilings clear them comfortably ($7.2k–$9.9k/day range on measured days).

---

## 4. Scientific evidence line (what is proven vs open)

**Proven (receipted, honest controls):**
- Candidates contain goal-grade outcomes worth ~$5,019/day pooled (perfect +60s skip/take).
- Exact delayed-candidate ceilings: $7,192.50 (2024-01-03), $7,400.31/day 4-day avg, broad E1R/E2R preflight ceilings $5.16k–$6.91k/day.
- 30s age-rank capture signal is real and stable FIT-forward (23.95% vs 13.32%; balanced top-4 OOF 33.37% vs 21.36% shuffle).
- Fixed-horizon (120s, right-censored) formulation: oracle stopping recovers 89.47% ($2,674/day, 30 trades/7 days, $624/trade, zero drawdown, mean entry 109s).
- QRF4 forward-vol publisher beats persistence everywhere tested (+16.2%/18.5% pooled sigma gain).

**Open (the decisive experiment):**
- Whether the **unchanged causal learner** through the full chain (exact teacher → curriculum relabeling → calibration → threshold bank → canonical replay) converts ≥80% of ceiling with ≥$3k/portfolio-day. Everything else is engineering around this question.
- Tension to manage: the honest re-derivation closed the ignition/grammar family specifically; the chain uses the full 1,764-column set. If the chain's economics come back structurally weak, Section 6 Phase 3 is the lawful response — not another round of the same heads.

---

## 5. Durable assets inventory (paid for — never rebuild)

| Asset | Receipt / identity |
|---|---|
| 266 outcome dispositions; 89 exact-teacher days; 235 feature shards (174 E1R) | corpus chain |
| 67 corrected E1R day stores (+4 quarantined stale duplicates) | strict-load verified |
| Feature audit 3,505 → 1,764 retained | `7425ca1c…6868e7` |
| Combined matrix 1,473,724 × 1,764 ≈ 10.4 GB | `7e9e2588…0bb48` |
| Training-join hash (unchanged through fixes) | `120fc6fd…` |
| Component bundle seed 20260820 fold BURN_E2_STACK, 5 heads (current value, continuation value, wall prob, adverse excursion, occupancy) | `dee94ac5…ad88d0` |
| First component OOF table, 1,799 rows | `7857defc…` / file `92f22a71…` |
| Round-0 curriculum: 5 real + 5 shuffle seeds action models + `curriculum_round.json` | on disk ~03:53Z Aug 21 |
| Dense REPLAY cache, 42 sessions | `artifacts/entry_v2/tabular_recovery/rehearsal/cache/fit_only/e1r/rollout/dense_replay_features/` — paid compute, preserve |
| Closure reviews 21 & 23 regressions | `f2ac05dd…`, `30611c1f…` |
| STOP checkpoint + journals + MemPalace mine (111 drawers) | `26478591…38ad3`, `e398909f…c483`, `74b88713…a878` |

---

## 6. The plan

> Governing discipline for every phase: one fix pass + one review per failure class (user law, 17:11Z Aug 20). Every branch below is **pre-registered now**, before the verdict exists, so no serial loop can start.

### Phase 0 — While Grok optimizes (zero collision)

Read-only monitoring + preparation only:

1. Watch Grok's declared tripwire (no new `.npz` in dense_replay_features within 10–15 min ⇒ report to user; **Grok decides** any freeze/restart — this plan never kills PIDs).
2. Draft verdict tooling under `scratchpad/entry_v2_path/` (outside Grok's locked surface) so Phase 1 starts the minute receipts land.
3. No edits to `engine/entry_v2/*`, `tools/run_tabular_recovery.py`, rehearsal artifacts, logs, or process trees. See Section 8.

```bash
# read-only stall check (safe to run anytime)
find artifacts/entry_v2/tabular_recovery/rehearsal/cache/fit_only/e1r/rollout/dense_replay_features \
  -name '*.npz' -newermt '2026-08-21 07:49' | wc -l     # 0 for >15 min => escalate to Grok/user
ps -o pid,etime,nlwp,%cpu -p 2786655,1249248            # liveness only
```

### Phase 1 — Rehearsal completes → verify, then extract the verdict

1. Strict-reload every published artifact; verify receipt lineage chains to matrix `7e9e2588…` and join hash `120fc6fd…`; confirm H2 access count still zero.
2. Extract the four-column verdict per forward block: goal-grade ceiling | exact offer ceiling | prophet-through-funnel | learner (+ shuffled null).
3. Compute the gate ratios (code sketch in Section 7.1). Report engineering vs experimental results separately (AGENTS.md rule 6).

### Phase 2 — Pre-registered verdict branches (decided NOW)

| Verdict class | Response (exactly one fix pass + one review + one rerun) | Expected cost |
|---|---|---|
| **PASS** (all of L1–L6 on every required block) | Freeze bundle; publish; proceed to Phase 4 confirmation | — |
| Threshold/Platt miscalibration only (scores good, cutoffs wrong) | Re-run calibration + threshold-bank + replay phases only; dense cache warm | tens of min – 2h |
| Action-head weak but signal present (capture materially < oracle-top-4 gap) | Refit action stack reusing dense cache + round-1 curriculum relabel; single pre-registered variant: pairwise ranking objective (PairLogitPairwise / YetiRank on within-day candidate pairs) replacing/augmenting ordinal top-3 | 2–4h |
| Structural under-recovery (<80% repeatedly across branches) | Escalation ladder, Phase 3 | days |

### Phase 3 — Escalation ladder (only if conversion structurally fails; in evidence order)

1. **Stop-mechanism exploitation.** The strongest conversion result ever measured is fixed-horizon acceptance: oracle stopping at the 120s mark recovers 89.47%. Shift the learning burden from "when to enter" (open-ended timing — repeatedly failed) to "which candidates to take at the fixed horizon" (right-censored-clean labels). Concretely: acceptance head trains on the existing fixed-horizon target family; policy enters at horizon expiry iff P(goal-grade | features) ≥ chronologically-fit threshold; reentry follows K=1 law.
2. **Sparse-gate quality, never occupancy.** Learned top-4 gate ceilings sit far under oracle top-4 ($2,074/$2,698 vs $3,571/$4,774) while top-12 broadening collapsed to ~$234/day. Widen acceptance *quality* (better head, better calibration), never widen the book.
3. **Feature-family adjudication on the NEW labels.** disc_* (1,351 discretionary) and fvol columns were never judged against the exact future-only teacher. Typed leak-audited ablation/addition pass. **Requires fresh go/no-go from the user before starting (default ruling — days of compute).**
4. **Per-regime calibration + conformal-on-honest-splits.** The side-research conclusion that mapped onto the existing stack; chronologically fit per asset/regime; global-cutoff ceiling ($2,009/day) warns that unconditional single cutoffs are insufficient.

### Phase 4 — Confirmation & launch readiness (AGENTS.md rule 8)

Launch confidence is measured, not inferred:
- Unchanged real fit-only learner passes **exact replay** on every asset in both frozen rehearsal transitions.
- Clears absolute capacity / trade / drawdown / day-coverage laws.
- Recovers ≥80% of the exact candidate ceiling on each threshold and untouched forward block (90% remains the target).
- FORWARD roles opened only after the above; 2025H2 stays sealed regardless of outcome.
- Full documentation + receipts; engineering and experimental results reported separately.

---

## 7. Code sketches

> Sketches live in `scratchpad/entry_v2_path/` when implemented. They read published artifacts only; they never modify engine code or running processes.

### 7.1 Verdict reader + gate checker

```python
# scratchpad/entry_v2_path/verdict.py
"""Strict-reload published replay artifacts and evaluate the PASS law.
Read-only. Receipts are verified before any number is believed."""
from pathlib import Path
import json, hashlib

REHEARSAL = Path("artifacts/entry_v2/tabular_recovery/rehearsal")
ASSETS = ("SI", "HG", "NKD")

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def load_publication():
    pub = REHEARSAL / "launch_rehearsal.json"          # absent until the chain completes
    if not pub.exists():
        raise SystemExit("no publication yet — chain incomplete")
    manifest = json.loads(pub.read_text())
    replay = load_replay_strict(manifest)              # engine strict loader, receipts checked
    ceilings = manifest["exact_ceilings"]              # per-block exact delayed-candidate ceilings
    seeds = manifest["seed_replays"]                   # 5 real + 5 matched shuffles
    return replay, ceilings, seeds

def seed_usd(r) -> float:
    return float(r["usd"].sum())

def gate_verdict(replay, ceilings, seeds) -> dict:
    per_asset = {a: replay[replay.asset == a]["usd"].sum()
                    / replay[replay.asset == a]["active_day"].nunique() for a in ASSETS}
    port = replay["usd"].sum() / replay["active_day"].nunique()
    capture = port / ceilings["portfolio_per_day"]
    weakest_real = min(seed_usd(r) for r in seeds["real"])
    strongest_shuffle = max(seed_usd(s) for s in seeds["shuffle"])
    trades = replay.groupby("active_day").size()
    mdd = max_drawdown(replay)                          # canonical replay drawdown
    checks = {
        "L1_per_asset_2000": min(per_asset.values()) >= 2000,
        "L2_portfolio_3000": port >= 3000,
        "L3_capture_80pct": capture >= 0.80,
        "L4_seed_honesty":  weakest_real > strongest_shuffle,
        "L5_trade_quality": replay["usd"].mean() >= 600 and mdd <= 1000,
        "L6_capacity":      capacity_ok(replay),        # K=1 per asset, <=12 entries/portfolio-day
    }
    return {"checks": checks, "pass": all(checks.values()),
            "numbers": {"per_asset": per_asset, "portfolio_per_day": port,
                        "capture": capture, "weakest_real": weakest_real,
                        "strongest_shuffle": strongest_shuffle, "mdd": mdd}}
```

### 7.2 Branch controller (pre-registered decision tree)

```python
# scratchpad/entry_v2_path/branch.py
"""Map the verdict to exactly one pre-registered branch. No improvisation."""
def next_branch(v: dict) -> str:
    if v["pass"]:
        return "PHASE4_CONFIRMATION"
    n = v["numbers"]
    if not n["checks"]["L3_capture_80pct"] and scores_calibrated_ok(v):
        return "BRANCH_CALIBRATION_ONLY"        # rerun calibration+threshold+replay; warm cache
    if signal_present(v):                        # capture gap concentrated in acceptance head
        return "BRANCH_ACTION_REFIT_RANKING"    # round-1 relabel + PairLogit/YetiRank variant
    return "ESCALATION_LADDER_GO_NO_GO_USER"    # requires explicit user authorization
```

### 7.3 Escalation rung 1 sketch — fixed-horizon acceptance head

```python
# scratchpad/entry_v2_path/fh_acceptance.py
"""Rung 1: accept/rank at the fixed 120s horizon where labels are right-censored-clean.
Uses ONLY existing cached features + existing fixed-horizon target family. No new columns."""
HORIZON_SEC = 120
# label: y = 1 if realized fixed-horizon value >= registered quantile q (chronology-safe:
# q fit on FIT role only), else 0. Policy: enter at t0+120s iff p_model >= tau(role=THRESHOLD).
# Capacity filter applied post-hoc by the canonical replay (K=1, <=12/day) — never learned.
```

### 7.4 Monitoring loop (Phase 0)

```bash
#!/usr/bin/env bash
# scratchpad/entry_v2_path/watch.sh — read-only; reports; never signals processes.
CACHE=artifacts/entry_v2/tabular_recovery/rehearsal/cache/fit_only/e1r/rollout/dense_replay_features
while kill -0 2786655 2>/dev/null; do
  N=$(find "$CACHE" -name '*.npz' -newermt '2026-08-21 07:49' 2>/dev/null | wc -l)
  echo "$(date -u +%FT%TZ) new_npz=$N proc_alive=yes"
  sleep 300
done
echo "$(date -u +%FT%TZ) rehearsal process exited — check logs/rehearsal_live.log tail"
```

---

## 8. Collision-avoidance contract (binding while Grok/Fable run)

**Locked — this plan will not touch:**
1. Process trees: 2786649 / 2786655 / workers 2796383–2796400; Fable 1249248. No kills, no signals, no renice.
2. Fable I/O: `FABLE5_SPEED_PROMPT.md`, `FABLE5_SPEED_RESULT.md`.
3. Engine files (in-flight, likely to be edited again by Grok/Fable): `engine/entry_v2/tabular_campaign.py`, `tabular_models.py`, `tabular_orchestration.py`, `tabular_matrix_store.py`, `tabular_experiment.py`, `common.py`, `native_thread_cap.py`, `test_tabular_recovery.py`, `test_common.py`, `tools/run_tabular_recovery.py`. Hard-forbidden for everyone: `tabular_training.py`.
4. Durable artifacts: combined matrix + 67 day stores (+ quarantined), round-0 fits incl. `curriculum_round.json`, dense_replay_features cache (all 42 sessions), `logs/rehearsal_live.log`.
5. Contract red lines: 2025H2 sealed; no neural revival; no new candidates/instruments/sizing; no matrix rebuild; PASS laws never weakened; nothing that could change a receipt.

**Stall protocol:** if the `.npz` tripwire fires, report to the user immediately with evidence; the freeze/restart decision belongs to Grok (owner of the run) relayed through the user.

---

## 9. Risks and guardrails

| Risk | Guardrail |
|---|---|
| Silent stall in dense-cache build | Phase 0 tripwire; Grok-owned freeze decision |
| Thread oversubscription persists (workers ~158 threads) | Fable's mandate; this plan adds nothing to that lane |
| Verdict arrives sub-gate | Branches pre-registered (Section 6 Phase 2) — one pass, one review, one rerun; no serial loops |
| Proxy temptation (AUC looks good, dollars don't) | Four-column verdict only; AGENTS.md rules 2/5 enforced in every report |
| Small-sample overfit on 89 teacher days | Seed-honesty law + untouched forward blocks + exact-ceiling ratio per block |
| Accidental H2 access | Seal guard already hardened (SHA-dir FP fixed); access count asserted zero in every verification |
| Escalation scope creep into feature work | Rung 3 requires explicit user go/no-go; rungs 1–2 use existing columns/targets only |

---

## 10. Decision log / defaults

1. **Escalation authority (user question left open):** DEFAULT = structural-failure escalation (disc_*/fvol ablation, days of compute) requires a fresh go/no-go from the user. Not pre-authorized.
2. **Plan location:** `design/0x alpha one.md` (this file), per user instruction.
3. **No phases started** at write time, per user instruction. Phase 0 begins only on explicit user command.
4. Where transcripts and repo files disagree, transcripts win (user ruling); where receipts and narratives disagree, receipts win.

---

*End of plan. Nothing in this file authorizes touching Grok's active work.*
