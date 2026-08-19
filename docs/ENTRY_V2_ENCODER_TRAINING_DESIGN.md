# Entry V2 — Encoder-Training Fix Design (rulings 21+, draft for review)

**Status:** DESIGN DRAFT (2026-08-19). No code changes until the running driver
exits (A-016: the source manifest re-hashes engine sources at finalize — mid-run
edits poison the chain). Implementation is ONE fix pass at the driver boundary.

## 1. The measured problem (deep passes v17/v18, instrument VALIDATED)

Gate-5 balanced memorization (32+32/asset, head-only clone, ≤400 steps) — the
question "do this arm's inputs separate winning from losing candidates at all":

| arm | joint | raw route (bypass-off) | occl_drop | recon MAE | base wall |
|---|---|---|---|---|---|
| C0 | 0.73–0.77 | = joint | +0.21..0.28 | 0.40–0.48 (ill-posed) | 64–160s |
| C1 | 0.68–0.76 | = joint | +0.16..0.26 | 0.36–0.44 (ill-posed) | 43–116s |
| L0 | 0.51–0.62 | = joint | +0.01..0.12 | 0.39–0.41 | 35–48s |
| L1 | **0.98–1.00** | 0.45–0.63 | −0.02..+0.16 | 0.33–0.38 | 34–39s |
| M1 | 0.95–0.999 | 0.46–0.64 | −0.045..+0.02 | 0.40 | 350–549s |

Facts the design must answer to:
- **The instrument is valid**: L1/M1 joint ≈ 1.0 — the clone protocol memorizes
  instantly when inputs separate. Every sub-1.0 number is an input fact.
- **No raw route separates candidates** (0.45–0.64, unstable seed-to-seed).
  Static per-candidate geometry separates PERFECTLY — and the geometry-null
  already measured static geometry as ~$0/day. The program's bet lives or dies
  on the raw tape becoming informative at the memory plane.
- **Deep memories are ignored or worse**: M1 occlusion ≈ 0/negative — the
  trained head does better without its own memory. The memory is noise.
- **Preservation plateaus far from target**: reconstruction MAE ~0.4 (z-units)
  vs the 1e-3 law, after ruling-18 put the loss into the shared optimizer
  (progress from ~0.8 unconditional, then flat).
- **The governor stops training almost immediately**: L-arms plateau in ~2–3
  epochs (35–50s); the stopping trace is the TOTAL loss, which the big oracle
  stack dominates — preservation and separation never get to govern.
- 26-row reconstruction validation (held days) — thin; widen (see §4.5).

Root cause, one sentence: **nothing in the base-stage objective demands that a
candidate's memory identify its own slice of tape** — the oracle losses are
mostly session-level, the total-loss governor stops at the oracle plateau, and
the reconstruction share is too small to carry preservation to target.

## 2. The fix (class-level, one pass)

### F1 — Candidate-identity objective (InfoNCE within session)
For per-candidate arms (L0/L1/M1): pooled memory z_i = g(mem_i) (small
projection head, CANARY-registered, discarded after the stage); for each
session batch, InfoNCE over the session's candidates: z_i must match its own
target t_i = sg(h(candidate's own raw window summary — the encoder's LAST-ROW
token input features)) against the other candidates in the same session as
negatives. Temperature τ=0.1 initial, measured (§4).
- Broadcast arms (C0/C1): objective is ill-posed by construction → typed
  IDENTITY_UNAVAILABLE_BROADCAST, not trained, receipted (they remain controls).
- **Leakage law**: identity is a function of the INPUT tape only (which events
  belong to which candidate window) — no outcome, teacher, or forward data.
  A-004 untouched (no outcome veto), shuffled-twin law untouched. It optimizes
  exactly what gate-5 measures, using only decision-time-available bytes.

### F2 — Per-component governor (supersedes the total-loss plateau)
The base stage continues while ANY of {oracle-validation, reconstruction-
validation, identity-validation} improves ≥0.1% within patience 3 (per-trace
staleness). Ceiling stays ruling-10's 40 epochs; wall-clock stays receipted
(D-098 arm budget: soft target ≤12 min/arm — 5 arms ≈ 60 min inside the 3h
law; if measurement shows M1 needs more, the constant comes from the
micro-harness, not from vibes).

### F3 — Gradient-normalized auxiliary weights (ruling-13 methodology)
Measure encoder-parameter gradient-norm shares of (oracle stack | recon |
identity) on real batches in the micro-harness; set weights so recon and
identity each carry a measured fair share (initial target: each ≈ the action
loss's encoder share). Constants land as MEASURED values with receipts, like
ruling 13 did for the head losses.

### F4 — GRU stability guard (L0/L1)
The 35-second plateau on the L-arms is consistent with immediate optimization
collapse. In the micro-harness, measure per-epoch validation with (a) current
lr, (b) 0.3×lr for encoder GRU parameters only (param-group). Keep whichever
trace actually descends; receipt the choice. No architecture change.

## 3. What this does NOT touch
- No label/objective changes on the atlas (the 44+44 law is frozen).
- No head redesign: the E1r/E2r heads already train under their own law; they
  consume better memories automatically.
- No gate weakening: gate-5 thresholds, reconstruction thresholds, the
  raw-route law (bypass-off ≥.995) all stand. The fix must EARN them.
- Broadcast arms stay as controls (typed identity-unavailable).
- 2025H2/2026 sealed; risk contract untouched.

## 4. Cheap-test protocol (BEFORE any driver pass — the 55-min cycle killer)
Standalone micro-harness (extends scratchpad micro_learn_check.py):
1. factory→prepare once (~10 min, reused across iterations via kept process);
2. base stage for L0 and M1 under F1–F4;
3. print per-epoch traces (oracle/recon/identity validation) + gate-5 +
   reconstruction receipt on the spot;
4. iterate constants (τ, weights, lr-group, patience) INSIDE the live process;
5. acceptance to leave the harness: L0 or M1 raw-route ≥0.995 AND recon
   MAE ≤1e-3 + cat-acc 1.0 on held days, stable across 2 seeds.
6. ALSO measure §4.5: widen reconstruction validation days so rows ≥ 100
   (currently 26) — a law-quality change, receipted.
Only then: one driver deep pass → all five arms + full chain → then the
amendments re-land + dual re-pin → the ONE real run.

## 5. Pre-registered outcome bands (D-075)
- Micro-harness hits acceptance → proceed as above.
- Identity converges but gate-5 raw-route still <0.995 → the memory carries
  identity but the balanced task needs more: escalate to C-route (raw-summary
  arm through the lawful funnel; denser candidate generation) — already queued.
- Identity does NOT converge on L0/M1 → representation capacity fact →
  architecture iteration at the named layer (M1 band widths / pooling), one
  design cycle, no thrash.

## 6. Implementation map (for the Opus lane, post-driver)
- `neural_sufficiency_resources.py::_encode`: F1 head + loss (per-candidate
  arms), F2 per-trace staleness (replace single `stale`), F3 weights (constants
  from harness), F4 param-group lr. Identity head registered via _run_optimizer
  category=CANARY fit_id=f"arm/{arm}/identity" (fit-census safe: CANARY is
  UNREGISTERED — verified by the sweep's census proof).
- Receipts: identity trace + weights + lr-group choice into the arm evidence
  (nonsemantic wall-clock stays stderr-only).
- Tests: red-first law tests for the per-trace governor and the typed
  broadcast-identity refusal; harness smoke for shapes (the session-batch
  InfoNCE gather is exactly the class that bit gate-5 — write the smoke FIRST).

---

# REVISION 2 (2026-08-19, post Fable adversarial review — supersedes conflicting §§ above)

The independent review confirmed F2/F3/harness discipline and found five real
defects. The implemented design is THIS revision.

## R1 — F1 re-targeted (the last-row target is struck)
The drafted target sg(h(last-row features)) is degenerate: InfoNCE over it is
optimally solved by a last-tick snapshot — informationally the neighbor of the
static geometry already measured at ~$0/day. Replacement, in order:
- PRIMARY: **cropped-view positive** — positive pair = (memory of the full
  window, sg-target of the same window truncated by k∈{1..8} trailing events);
  negatives = same-session candidates. Structurally forbids last-row-only
  solutions (the views differ in their last rows — matched content must be
  depth). InfoNCE lives behind the projection head g (z-space invariance,
  never on raw pooled memory — coexists with exact last-row reconstruction).
- FALLBACK: multi-depth fingerprint target t_i = sg(R·φ_i), φ_i = fixed stats
  over the last d events, d∈{1,4,16,64} (L) / {1,16,64,256} (M1), R seeded.
- Both: L2-normalize z,t; dedupe same-cutoff candidates into one identity
  class; exclude/down-weight negatives with tiny cutoff gaps (pre-registered);
  typed refusal for <2 unique windows, (asset,day)-pooled negatives when
  session K<8, receipted. τ measured in harness, tuning trace receipted.
- LEAKAGE LAW (verified against code): identity loss uses the outcome-free
  `base` weights or uniform ONLY (never action/top3/wall weights — those are
  outcome-derived); a graph-walk assertion proves the identity loss's autograd
  graph touches no target/teacher tensor; identity-validation on held days.

## R2 — THE BRIDGE: memory-only oracle probe (the dollars link; new instrument)
Fact-check adopted: the base stage is NOT label-free — _actual_multitask_loss
already trains on teacher-joined oracle targets; the frozen law is
train-once-freeze-memory. Therefore, lawfully and at near-zero cost:
- A small discarded probe p(mem_i) (LastRowReconstructionProbe pattern,
  CANARY-registered `arm/{arm}/memory-value-probe`) predicts a subset of the
  ALREADY-IN-STAGE oracle targets (value_bin, top3, action) from the RAW
  MEMORY ALONE, gradient into the encoder (ruling-18 disclosed-shaping
  precedent). No new information class enters the stage.
- Its held-day validation trace joins the F2 governed traces, and becomes THE
  acceptance instrument (gate-5 is demoted to a sanity floor the moment F1
  optimizes it — Goodhart): **memory-only held-day oracle loss must beat the
  memory-OCCLUDED baseline by a pre-registered margin, and the occlusion drop
  on held-day value metrics must be positive.** That is the untrained-on
  measurement pointed at dollars.

## R3 — F2 completed: the checkpoint law moves with the stopping law
Stopping alone is a null fix (best-checkpoint selection would still reload the
early oracle-plateau weights). Selection law: scale-free composite — each
governed trace normalized by its own epoch-0 value; best checkpoint = min of
the mean of normalized traces. Traces: oracle-val, recon-val, identity-val,
memory-value-val (C-arms: no identity — typed). Per-trace 0.1% / patience 3;
stop when ALL stale; ceiling 40 epochs.
Wall ceilings ASYMMETRIC (measured epoch costs): C0 6 / C1 6 / L0 8 / L1 8 /
M1 30 minutes (~58 total inside the 3h law). Stop reason receipted as
CONVERGED vs WALL_CEILING — the distinction is itself a finding.

## R4 — F4 struck; replaced by the free discriminating diagnostic
L0/L1 have no GRU (nn.LSTM at model.py:326; GRUs are M1's). F4 is replaced in
the harness by: governor OFF, 10 fixed epochs on L0, logging per-group
grad-norms and parameter deltas (encoder.lstm | rest-of-encoder | head) plus
per-component validation traces. Healthy grads + still-descending aux traces →
it was the stopping law (F2 suffices). Vanishing encoder grads → add a
correctly-named lstm param-group at 0.3x lr. Large grads + flat traces → R5.

## R5 — L-arm reconstruction threshold: measured band, arch fix pre-registered
The LiT patch pooling sum-pools 4-event patches with position signal only at
patch level — exact last-row recovery at MAE 1e-3 is a DeepSets-inversion
problem; the measured 0.4 plateau ≈ within-patch dispersion. Law: L-arm recon
threshold becomes a MEASURED BAND from the harness (M1 keeps 1e-3 as target);
the band-3 architecture action is pre-registered as intra-patch position
embeddings before the sum (one line), triggered by R4's third outcome — NOT by
identity non-convergence.

## R6 — Acceptance rewritten (M1 is the deployable scale; "L0 or M1" struck)
Leave the harness / enter the paid run only when, stable across 2 seeds, M1:
1. memory-only held-day oracle trace beats the occluded baseline by the
   pre-registered margin (R2), AND
2. gate-5 raw-route >= 0.995 (sanity floor), AND
3. recon within its measured-feasible band (1e-3 target),
with F3 weights set by the two-point (init + epoch-3) gradient-share
measurement, single-auxiliary share caps, and the conflict-cosine receipted.
