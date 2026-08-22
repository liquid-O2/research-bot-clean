# START HERE — the one file for a new session

You are working on Entry V2: a tabular (CatBoost) delayed-confirmation entry policy for SI/HG/NKD futures that must clear >$2,000/asset-day, 80% of the exact candidate ceiling, $600/trade, MDD<$1,000, on chronological replay dollars — never proxies. Neural is dead, candidates are frozen, 2025H2 is sealed until the goal is met pre-H2.

## Read, in this order (15 minutes)
1. `~/.optmem/memo wake` — auto-injected at session start; settle any nap it asks.
2. `design/ENTRY_HANDOFF_2026-08-22.md` — the cold-start handoff (where we are, everything done with receipts, what remains). Then `STATE.md` — the cursor: what is running/stopped right now and the NEXT_ACTION.
3. `CURRENT.md` — currency authority: live vs inherited docs, closed questions WITH scope. **Old material has burned sessions repeatedly; trust nothing dated before 2026-08-18 without checking here.**
4. `AGENTS.md` — the binding execution rules (no serial fix loops; engineering ≠ experimental progress; the launch gate) + the situation→skill routing table.
5. `HARDWARE.md` — the box lies to naive probes: 13.6 effective cores, 263 GiB, pinned cu128.
6. `artifacts/entry_v2/tabular_recovery/rehearsal/FABLE5_SPEED_RESULT.md` — the chain's speed diagnosis + the ORDERED SPEED PLAN addendum (S1–S6). **Speed is the first workstream: everything depends on a verdict loop that fits the budget.**

## How you work here
- Skills auto-trigger by situation (routing table in CLAUDE.md/AGENTS.md — the user never names them; a per-turn hook reminds you). All skills are house-built at `.claude/skills/`; there is no third-party process plugin.
- One consolidated review + ONE fix pass per failure class. Never patch→launch→discover-next.
- No number without its pre-registered controls (preregistering-results). No gate without its goal trace (encoding-goals-in-gates). Every long run: thread budget + tripwire (operating-long-runs).
- Record lasting facts with `memo note`; update STATE.md when the stage moves; journal at milestones.

## Current mission (as of 2026-08-22 — STOPPED, waiting for the user's go-ahead)
The entry line is in diagnosis-then-design mode after the E1R learner scored $0. Measured 2026-08-22: nothing is decidable at candidate formation; a confirmation signal accrues over the 300 s watch window (unit-weight four-state composite ≈ .60/.56/.62 AUC at 290 s) but no causal decision-time rule inside that window reaches goal grade; a hindsight pick of the phase's most extended candidate would keep 37–60% of the ceiling. Open levers (user decides): 600 s window, the book's unbuilt order-flow ingredients, time-remaining conditioning, a phase-scale sequential object, a fast A1. Laws in force: ≤12 trades per portfolio-day; per-asset rungs $2,000 HG / $1,500 NKD, SI; 80% capture; 5+5 seeds; replay dollars; generator frozen; 2025H2 sealed; entries first (D-107); 6 h per item by speed (D-109). The speed program (R6 native builder landed, not yet adopted; R3 compiled walk not landed) is standing work, not a one-time push.

Reference (not authority): `design/0x alpha one.md` is another model's synthesis for evaluation — cross-check anything you take from it. The pain-point archaeology and skill rationale live in `.claude/skills_draft/DIAGNOSIS_AND_PROPOSALS.md`.
