---
name: operating-long-runs
description: Use when launching, monitoring, or resuming any background run, driver, lane, or rehearsal longer than a few minutes — and when a run looks stalled or dead.
---

# Operating Long Runs

Born of paid incidents: a night lost to a liveness FALSE alarm, another to a REAL cross-driver deadlock reported healthy, ~6h of overnight refusal cascade, and 158-thread × 16-worker CPU oversubscription on a 13.6-core pod. Wall-hours are billed whether or not the hardware works (D-100) — a stalled run costs the same as a productive one.

## Before launch
1. **Thread budget arithmetic**: workers × threads-per-worker ≤ HARDWARE.md cores. Check every library's default (CatBoost `predict(thread_count=-1)` spawns ~n_cpu threads PER WORKER — pin it). Oversubscription looks like progress at 1/10 speed.
2. **Resume safety proven at slice scale**: kill-and-resume the 1-day slice before the long run; the resume path is where three consecutive rehearsals died (running-evals slice-verdict law). Design test (pstack `make-operations-idempotent`): what happens if this runs twice in a row, and what happens if the previous run crashed at EVERY possible point? Each answer is either "converges / resumes correctly by receipt" or a named defect.
3. **Watcher armed at launch** (D-074): a completion/failure watcher plus a **stage-aware tripwire** — "no new <artifact-kind> in <N min> ⇒ escalate," with N set per stage (a heartbeat-per-era stage needs a longer N than a per-file stage; per-policy heartbeats prevent false alarms).
4. **Logs**: `setsid nohup ... >> <run-root>/logs/<stage>.log`; the log path recorded in the launch note; no orphan processes without a recorded pid.
5. **Freeze the ruler before the first attempt** (pstack `hillclimb` step 2): prove the
   measurement harness separates a known-good case from a known-bad one, then pin it. Changing
   it mid-run invalidates every earlier number. Sample enough to clear noise — median of N,
   never a single run (DEFECT_CLASSES.md `seed-draw-headline`). **A stop predicate pairs its
   target with a floor on attempts** (`hillclimb` step 1), so a lucky early result cannot end
   the run. **One change, one measurement, keep or revert** — never stack untested changes; a
   reject reverts in full. Keep a decision log from the first attempt (`hillclimb` step 3): one
   row per attempt — hypothesis, change, before, after, delta, verdict kept/reverted — held
   outside the tree so it survives reverts, and read before each attempt so the search
   accumulates instead of circling.
6. **Six-hour arithmetic, written before the launch (D-109).** State the block's predicted wall
   time and the arithmetic behind it: stages × per-stage measured rate × the HARDWARE.md core
   budget from step 1. Under 6h: launch. Over 6h: the answer is faster code, not smaller science
   (D-109-AMENDMENT) — name the next speed-engineering option and take BOTH the arithmetic and
   that option to the user **before** the run, never after it overruns. A slice is a plumbing
   check before a launch (running-evals slice-verdict law); it is never a substitute for the
   verdict, and scoping a quality-bearing block down to fit is struck as an enforcement
   mechanism. If any of these triggers mid-run, abort immediately and report — do not narrate
   and continue: the predicted time is exceeded by half, a stage's measured rate falls below
   the rate the arithmetic assumed, or the run enters a stage the arithmetic did not price.

## While running
- Check LIVENESS before declaring death: nlwp/%cpu of the pid tree, newest artifact mtime, the stage's own heartbeat. 100%-CPU with no output can be real work (verify against the stage's expected cadence) or a deadlock — distinguish by strace/py-spy sample, never by vibes.
- **When a check fails or a run looks dead, suspect the observation method before the system.** A blank artifact, a stale mtime, a heartbeat file nobody writes, `nproc` on this pod (`DEFECT_CLASSES.md:18` env-probe-lie) — verify the instrument, then the subject.
- **A plateau is not a stop, and the predicate is not negotiable.** Pivot the approach or escalate a genuine dead end — never relax the exit predicate to declare victory.
- A stall verdict has exactly two lawful exits: escalate to the owner, or freeze-and-audit the whole remaining chain (AGENTS.md rule 1) — never patch-and-relaunch.
- **Classify before you recommend** (bigpowers `diagnose-stall`). Name the stall as exactly one
  of: `waiting_approval` · `blocked_dependency` (an upstream stage never published) ·
  `agent_exhausted` (retries spent) · `misconfigured_watcher` (the tripwire was never armed, or
  its N is wrong for this stage) · `external_io` (a fetch or a lock with no timeout) · `unknown`
  (escalate with the evidence bundle — pid tree, newest artifact mtime, last `run.jsonl` line).
  Then **recommend exactly one action.** A menu of three is an un-made decision handed to the
  person with less context.
- **Never resume a lane to check on it — a resume restarts an idle agent** (pstack
  `orchestrate`, Liveness). Probe read-only: the published artifact, the receipt, the pid tree,
  the log tail. **Transcript mtime is not liveness.**
- **Retry by failure mode, and cap it at two** (pstack `orchestrate`, Liveness): OOM or
  budget-cap ⇒ respawn with smaller scope; transient I/O ⇒ retry as-is; tool error ⇒ retry on a
  different model; unknown ⇒ retry once. Then abandon the unit and replan around it.
- **A late lane reconciles before it is accepted** (pstack `orchestrate`, Liveness): a report
  arriving hours after the frontier moved is checked against the current STATE.md cursor and
  receipts first. Salvage unique findings through a fresh unit, never a blind merge — the world
  moved while it slept.
- **Bound your own retries the way you bound a lane's** (pstack `orchestrate`, Liveness). After
  a few consecutive tool aborts, stop: write the terminal handoff to STATE.md (what is done,
  where it lives, the exact command to resume) and end the run. Hours of retry loops against a
  dead executor produce nothing a handoff would not.

## On failure
- The failure is a defect-class instance: sweep the class (generalizing-fixes) across the REMAINING chain in one closure pass before any relaunch.
- **After any driver death, sweep for its orphaned pool** (`spawn_main` processes with ppid 1, DEFECT_CLASSES `orphaned-pool`): the crashed parent's workers survive, burn cores against the successor, and write under the pre-crash code. Kill them, then verify every manifest written in the crash window parses — atomic `os.replace` publishes make the kill safe; a torn small-json manifest is the residual risk.
- Resume must strict-reload published artifacts by receipt, never recompute silently; a resume that recomputes is a defect.

## Red flags
- "It's probably still working" / "it's probably dead" without a liveness check · relaunching with a point fix · two drivers waiting on each other's rc · workers=2 on a 13.6-core box, or 256 threads on it.

## Ledger binding (D-111)

A launched run is a work item, so it has an `unlazy` ledger before it launches. Its gates carry the pid, the log path, the receipt path and the verdict marker as CHECK lines, so 'the run finished' is decided by a command rather than by a glance at a log tail. The Stop wall then blocks the turn until the run's own receipt gate is checked with evidence.
