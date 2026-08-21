---
name: operating-long-runs
description: Use when launching, monitoring, or resuming any background run, driver, lane, or rehearsal longer than a few minutes — and when a run looks stalled or dead.
---

# Operating Long Runs

Born of paid incidents: a night lost to a liveness FALSE alarm, another to a REAL cross-driver deadlock reported healthy, ~6h of overnight refusal cascade, and 158-thread × 16-worker CPU oversubscription on a 13.6-core pod. Wall-hours are billed whether or not the hardware works (D-100) — a stalled run costs the same as a productive one.

## Before launch
1. **Thread budget arithmetic**: workers × threads-per-worker ≤ HARDWARE.md cores. Check every library's default (CatBoost `predict(thread_count=-1)` spawns ~n_cpu threads PER WORKER — pin it). Oversubscription looks like progress at 1/10 speed.
2. **Resume safety proven at slice scale**: kill-and-resume the 1-day slice before the long run; the resume path is where three consecutive rehearsals died (running-evals slice-verdict law).
3. **Watcher armed at launch** (D-074): a completion/failure watcher plus a **stage-aware tripwire** — "no new <artifact-kind> in <N min> ⇒ escalate," with N set per stage (a heartbeat-per-era stage needs a longer N than a per-file stage; per-policy heartbeats prevent false alarms).
4. **Logs**: `setsid nohup ... >> <run-root>/logs/<stage>.log`; the log path recorded in the launch note; no orphan processes without a recorded pid.

## While running
- Check LIVENESS before declaring death: nlwp/%cpu of the pid tree, newest artifact mtime, the stage's own heartbeat. 100%-CPU with no output can be real work (verify against the stage's expected cadence) or a deadlock — distinguish by strace/py-spy sample, never by vibes.
- A stall verdict has exactly two lawful exits: escalate to the owner, or freeze-and-audit the whole remaining chain (AGENTS.md rule 1) — never patch-and-relaunch.

## On failure
- The failure is a defect-class instance: sweep the class (generalizing-fixes) across the REMAINING chain in one closure pass before any relaunch.
- Resume must strict-reload published artifacts by receipt, never recompute silently; a resume that recomputes is a defect.

## Red flags
- "It's probably still working" / "it's probably dead" without a liveness check · relaunching with a point fix · two drivers waiting on each other's rc · workers=2 on a 13.6-core box, or 256 threads on it.
