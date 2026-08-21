---
name: debugging-with-a-loop
description: Use when a hard bug, refusal, stall, or performance regression resists the first look — before proposing hypotheses or fixes.
---

# Debugging With a Loop

Adapted from Pocock `diagnosing-bugs` + the systematic-debugging discipline (house-owned; no plugin dependency).

## Phase 0 — read before touching
Read the ACTUAL error text and the failing input completely; reproduce once as-is before changing anything. State what you observed vs what you expected in one sentence. Never fix a bug you have not reproduced.
**Classify before retrying** (pstack `babysit` step 7): **a failure in code the change never
touched means a stale base, not a flake** — it reproduces every time and no number of reruns
fixes it. One fresh run for a suspected flake; an identical second failure means it was never
flake, so read the logs instead of retrying blind.

## Phase 1 — build the feedback loop. This IS the skill.
A **tight pass/fail signal that goes red on THIS bug**, one command, seconds not hours. Bisection, hypotheses, and instrumentation merely consume it; without it, staring at code is theater. For this repo: a 1-day slice through the real path beats any synthetic fixture (the three rehearsal deaths were all reproducible at slice scale for pennies).

**Ways to build one, in rough order:** a failing test at the seam that reaches the bug · a CLI/driver run on a fixture input diffed against a known-good snapshot · replay a captured artifact (a saved day-store, a real payload) through the path in isolation · a throwaway harness that calls the one function with mocked neighbours · a property/fuzz loop when the symptom is "sometimes wrong" · a bisection harness when the bug appeared between two known states (commit, dataset, config) · **a differential loop: same input through old-vs-new or two configs, diff the outputs** — this is the one that catches resume-width and sign/side classes.
**Phase 1 is done when you can name ONE command you have already run at least once, and paste its output:** red-capable (asserts the exact observed symptom, not "didn't crash"), deterministic (same verdict every run; for flaky bugs, a pinned high reproduction rate — a 50% flake is debuggable, 1% is not), fast (seconds), and runnable unattended. **If you catch yourself reading code to build a theory before this command exists, stop.** If you genuinely cannot build a loop, say so explicitly and list what you tried — do not proceed to hypotheses without one.
**Perf branch:** for a performance regression, logs are usually the wrong instrument. Establish a baseline measurement first (timing harness, profiler, thread/CPU sample), then bisect against it. Measure first, fix second.
The eight strategy families are **hypothesis generators, not a checklist** (pstack `perf-issue`
step 2): elimination · divide-and-conquer · caching · indirection · batching · redundancy/hedging
· lazy evaluation · scheduling. **A family earns an attempt only when the trace shows the signal
it names**, and a focused fix for the dominant cost beats applying all eight. Elimination is the
exception that needs the read-the-code pass, not the profiler: **the trace shows what is slow,
never that it is deletable.** Each family has a *claim-validity check* (what the trace must show
first, what must be named before the win is claimed) — with the trace in hand, read
`references/perf-families.md` beside this skill before picking one.

## Phase 2 — tighten and minimize
Strip the loop until every element is load-bearing (deletion test): fewer sessions, fewer columns, smaller window — while the red stays red. A loop that stops reproducing when simplified just told you where the bug lives.

## Phase 3 — hypotheses, plural
Write **3-5 ranked falsifiable hypotheses** before touching code (a single hypothesis anchors; this repo's "selector-disagreement" and "wall" hypotheses were both refuted by their own first diagnostic — cheap because the loop existed). Each hypothesis names the one-number test that would kill it. Run the cheapest killer first.

## Phase 4 — instrument, don't guess
Tag temporary instrumentation `[DBG-<slug>]` so it greps out cleanly afterward. Log the deciding values immediately before the irreversible step. Redact secrets in anything shown. Change ONE variable per experiment — two changed variables explain nothing; and prefer the sharpest instrument available (Pocock: debugger > targeted logs > never log-everything-and-grep).
**Prove the mechanism before believing it** (pstack `runtime-forensics` step 3): inject the
instrumentation or flip the value live and watch the symptom move. A plausible-but-unconfirmed
cause can be wrong while the real one sits one layer over.

## Exit — root cause, not symptom
The fix lands at the ORIGIN of the bad value (trace backward; fixing where it hurt leaves the class alive one layer up). Red→green through the loop, THEN generalizing-fixes (sibling sweep + depth pass + registry check). A fix without the loop's green is a hope; a green without the root cause named is a symptom patch. The commit message states the winning hypothesis — the next reader of this file gets the mechanism, not just the diff.
**A frame with no source mapping is not a diagnosis** (pstack `trace-forensics` step 4):
resolve the symbol to file and line, or say plainly the artifact does not carry it. **Without a
paired before/after capture, the finding is the strongest hypothesis the artifact supports, not
a confirmed cause** (step 5).

**Restart and resume bugs: suspect state before code.** Code does not change between runs; state does. If clearing or rebuilding a state file, cache, lock, or published artifact restores the behaviour, the fix is state validation at the load boundary, not a code patch.
**Belt-and-suspenders that "might help" is a hypothesis, not a fix, and does not ship. When evidence refutes a hypothesis, revert what it motivated** — only the smallest change the evidence justifies survives the turn.

## Red flags
- "I'll rerun the full 2h chain to check" (build the slice loop first) · one hypothesis pursued to exhaustion · fixing at the symptom layer because the origin is far away · declaring a stall dead without a heartbeat check (this repo lost a night to a liveness false alarm — and another to a real deadlock reported healthy).
