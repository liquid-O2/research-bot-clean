# Why we are not at the goal — transcript archaeology verdict + proposed changes

2026-08-21. Sources: 38 Opus readers over ALL Grok + Codex transcripts (13MB reduced corpus, 451 evidence-anchored episodes, 292 user signals, 287 goal-blocker statements, 302 process gaps — every claim carries a verbatim quote + file/line anchor; 10/10 sampled anchors verified mechanically), plus my own full read of the 546-entry program journal and the current design docs. Aggregate: `artifacts/cache/continuity/archaeology/FINDINGS.json`, digest beside it.

## Part 1 — The diagnosis (current line, old material separated)

### 1. The deciding measurement has never run. This is pain point #1.
Across every harness and every session: **zero learned economic results exist**. The journal's own words, over and over: "no economics, engineering evidence only." Three rehearsal launches in a row died on typed plumbing refusals (resume-identity defects) — after the audit machinery reported an EMPTY freeze list. Before that: nine plumbing failures; a rehearsal that would have crashed on a dead neural stub after the expensive stage; a 1h46m run whose receipts "cannot attribute the failure." The chain's wall-clock (historically ~18-24h) never fit the iteration budget, so there has never been a repeatable measurement loop. Your words, anchored: *"so we spent 8 hours on nothing"*, *"this is insane, why are we having to restart so many times"*.

### 2. When gates existed, they did not encode the goal.
The PASS gate measured **pooled portfolio dollars — one failing asset could hide**; a **shuffled control could pass it**; a conformal haircut produced literally zero eligible rows across three folds (a gate defect logged as if it were a model finding). So even a completed run could not have certified — or honestly falsified — the $2,000/asset-day contract. (STATE says a fix batch landed for two of these; verification of the current PASS path is proposal B3.)

### 3. The science that HAS run localizes the gap precisely: selection information, posed wrongly.
The prize is real — perfect skip/take at +60s = **+$5,019/day**; oracle headroom exceeds the goal on all three assets; candidate generation is not the bottleneck. The post-formation confirmation window was closed cleanly (direction-blind grammar, AUROC 0.496). Best honest capture ~28-35% vs the 80% gate. And the fleet surfaced a consistent **formulation defect family**: whole-day top-K ranking trained for a live sequential ENTER/DEFER decision; pointwise BCE on 1.5-1.75% positives; 5-minute supervision for hours-long trades; features asking "what does the market look like now," never "what is this side worth now"; PLATT blocks burned by repeated inspection; pseudo-replication (24,798 rows = 827 paths). The learner has repeatedly been optimized against a problem the runtime never poses.

### 4. Where the hours actually went (451 episodes classified):
verification-gap **86** · data-contract-break **80** · leakage/tautology **51** · plumbing **50** · harness/tooling **44** · rework-loop **33** · context-loss/compaction **25** · spec-ambiguity **23** · premise-refuted-late **17**. The top three = 48%: **almost half of all burn is measurement hygiene, not science and not model capability.** Signature current-era case: the corrupted-label night — `str(side).startswith("B")` on integer sides simulated all 8,993 trades short, plus a silent survivorship filter → "$8k/day, first deployable result" → withdrawn wholesale.

### 5. Old-vs-new contamination is real, measured, and yours to hear back verbatim:
*"we get conflated over old stuff and new stuff over and over again"* — confirmed: inherited port-campaign narrative (the $977 champion era) sits undated next to live work; agents mistook old files for current ("Isn't 4/6/7 the older select we discarded?"); the Grok goal-verifier certified the goal "Achieved" for shipping a runner while zero economics ran. Old nulls were also over-generalized the other way: several "closed" verdicts were scope-limited to dead representations yet kept steering work.

### 6. Recurring environment friction: cgroup/nproc lie on RunPod (16 vCPU not 64, no 1TB RAM), workers set to 2 with 16 available, optional installs silently swapping the pinned CUDA Torch — each rediscovered multiple times, each time on paid box-hours.

### The honest bottom line
The goal is blocked by ONE unrun measurement standing behind a chain that has never survived to its verdict — and when it does run, the current best evidence says capture lands far below the 80% gate, at which point the money question becomes formulation (sequential decision contract, longer supervision horizons, day/regime grain) and the user-owned doors (instruments, sizing), not more of the same screening. Every wasted week so far has a named, preventable mechanism.

## Part 2 — Proposed changes (nothing applied yet; your call)

### Pack A — Measurement discipline (attacks the 48%)
- **A1. New skill `preregistering-results`**: no experiment starts and no number is quoted without: pre-registered promotion metric = replay dollars at the deployable operating point; a luck bar; a matched null that CAN fail; 5-seed variance; knob provenance (inner-selected only); and the **perfect-label ceiling test** ("if a model ranked this label perfectly, would it clear the gate?" — asked before training, ever).
- **A2. New skill `encoding-goals-in-gates`**: every gate/law in code traces line-by-line to the goal contract (per-asset vs portfolio; shuffle-must-fail; MAE/DD denominators), each clause proven by a mutant that makes the gate fail; "zero selected" is a typed gate-defect state, never a model finding.
- **A3. Extend `generalizing-fixes` with a **defect-class registry** (named recurring classes: side-encoding, silent-empty, resume-width, denominator, eval-selected knobs, mirror fixtures, stale-doc-read) — checked as a standing lens in every consolidated review.

### Pack B — Verdict-speed + gate truth (attacks pain #1)
- **B1. Slice-verdict law** (extends `running-evals`): the FULL chain — including resume/restart boundaries and the final verdict object — must run end-to-end on a 1-day slice in minutes before any long launch; the three resume-refusal deaths were all catchable at slice scale for pennies.
- **B2. `HARDWARE.md` environment truth file** (measured cores/RAM/GPU stance, cgroup caveat, pinned CUDA stack) injected via the routing table — ends the 2-workers/64-CPU/Torch-swap rediscoveries.
- **B3. One verification task now**: confirm the current PASS path encodes per-asset $2k + shuffle-must-fail (the fix batch claims it; nothing has re-proven it).

### Pack C — Currency hygiene (attacks old-vs-new)
- **C1. `CURRENT.md` manifest**: one file naming the live line, the authoritative files with dates, and the dead lines with their scope-limited verdicts ("closed FOR representation X, not for Y"). Sessions read only through it; SessionStart hook injects the pointer.
- **C2. Stale banners**: inherited/superseded docs get a one-line header (`INHERITED NARRATIVE — pre-reset, do not treat as current`); a one-time sweep marks the known set.
- **C3. Extend `keeping-continuity`**: nulls are recorded WITH their scope (what representation/data/grain they close), so old nulls stop both over-steering and being re-litigated.

Also queued from the upstream mining (present rather than applied, per your instruction): the refuted-lane registry, debugging-with-a-loop skill, Given/When/Then acceptance scenarios inside frozen specs, law-anchored-line deletion guard, scenario IDs binding spec→test→receipt, and the `## Commands` block (pytest is NOT installed here — verified working line: `python3 -m unittest ...`). Full texts in `skills_draft/audit/upstream1-3*.md`.
