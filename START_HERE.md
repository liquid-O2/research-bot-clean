# START HERE — the one file for a new session

You are working on Entry V2: a tabular (CatBoost) delayed-confirmation entry policy for SI/HG/NKD futures that must clear >$2,000/asset-day, 80% of the exact candidate ceiling, $600/trade, MDD<$1,000, on chronological replay dollars — never proxies. Neural is dead, candidates are frozen, 2025H2 is sealed until the goal is met pre-H2.

## Read, in this order (15 minutes)
1. `~/.optmem/memo wake` — auto-injected at session start; settle any nap it asks.
2. `STATE.md` — the cursor: what is running/stopped right now and the NEXT_ACTION.
3. `CURRENT.md` — currency authority: live vs inherited docs, closed questions WITH scope. **Old material has burned sessions repeatedly; trust nothing dated before 2026-08-18 without checking here.**
4. `AGENTS.md` — the binding execution rules (no serial fix loops; engineering ≠ experimental progress; the launch gate) + the situation→skill routing table.
5. `HARDWARE.md` — the box lies to naive probes: 13.6 effective cores, 263 GiB, pinned cu128.
6. `artifacts/entry_v2/tabular_recovery/rehearsal/FABLE5_SPEED_RESULT.md` — the chain's speed diagnosis + the ORDERED SPEED PLAN addendum (S1–S6). **Speed is the first workstream: everything depends on a verdict loop that fits the budget.**

## How you work here
- Skills auto-trigger by situation (routing table in CLAUDE.md/AGENTS.md — the user never names them; a per-turn hook reminds you). All skills are house-built at `.claude/skills/`; there is no third-party process plugin.
- One consolidated review + ONE fix pass per failure class. Never patch→launch→discover-next.
- No number without its pre-registered controls (preregistering-results). No gate without its goal trace (encoding-goals-in-gates). Every long run: thread budget + tripwire (operating-long-runs).
- Record lasting facts with `memo note`; update STATE.md when the stage moves; journal at milestones.

## Current mission (as of 2026-08-21)
0. **Budget law (user, binding): the full chain verdict in ≤8–9h, target 5–6h. Pod changes are permanently refused — solve it on this box.** The plan is ADDENDUM v2 in the speed file: R1 GPU refits — CONDITIONALLY approved, gated on a 3-fit byte-identity determinism receipt (deletes the 11h fit block if it passes), R2 one-walk-carrying-21-threshold-states, R3 compiled/C++ walk twin (Python's 0.45ms/row state machine is the wall; house pattern = C++ engine differential-accepted vs the Python oracle), R4 overlap all E2R prep inside E1R, R6 APPROVED: C++ port of the dense feature builder (identity re-key first, byte-identical twin — spec in the speed file).
1. **Speed first** — start the R6 C++ feature-builder port (approved; identity re-key is step 1) and land R2/R3 in parallel; R1 is conditionally approved: run the 3-fit byte-identity determinism receipt first — pass = bitwise-deterministic GPU fits; fail = GPU anyway under the approved artifact-pin standard (model hash = identity, strict reload, 5-seed variance receipt). CPU fits are struck. Every twin is adopted only on bit-identical differential proof.
2. **Shepherd the running rehearsal to its four-column verdict** (E1R checkpoint first — do not let E2R block reading it).
3. **Act on the verdict via the pre-registered branches** — calibration-only rerun, action-head refit, or the escalation ladder. No improvisation past the branch table.

Reference (not authority): `design/0x alpha one.md` is another model's synthesis for evaluation — cross-check anything you take from it. The pain-point archaeology and skill rationale live in `.claude/skills_draft/DIAGNOSIS_AND_PROPOSALS.md`.
