---
name: grilling
description: >
  Grill the plan until every branch is resolved. Use when the user says
  draft a plan, write a plan, grill, or a decision is still foggy. Grill
  yourself; take recommended options; ask the user only about the actual
  goal.
when-to-use: >
  draft a plan, write a plan, grill, ambiguous, decision tree
---

> **House port.** Tracker is `design/` markdown (no GitHub/Linear). Tests:
> `python3 -m unittest <module>` (pytest is not installed). One review pass,
> one fix pass (D-001). Read this file in full; do not skip to coding.
> After a `draft a plan` message, planning skills run first; implement
> skills run when YOU write production code (any folder, not only engine/tools).

Map the work as a **design tree**: every decision branches into the decisions that hang off it. Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled.

## House law: grill yourself

The user is not a quant expert and will not steer implementation. **Do the grilling yourself.**

On every frontier branch, pick one:

1. **Fact.** You look it up (repo, box, docs, a sub-agent). Never ask.
2. **Engineering / process / domain.** You take your recommended option, write it into the spec, and proceed. Do not wait. Trading methods, folders, libraries, test shape, loss functions, playbook choice — all of this is you.
3. **Goal.** Only these go to the user: what success is, what is in or out of the program, an irreversible preference they have said they want to own (time, risk, money).

If the remaining frontier has no goal branch, it is empty for the user. Record every taken option in `design/`. Proceed. Do not interview. Do not wait for confirmation of engineering choices.

When a goal branch is open, ask the whole goal-frontier in one round. Number each question. Give your recommended answer. Wait for those answers only.

Format a goal round like so:

```
**Q1 — <question title>.** <question body, including choices>

Recommended: <your recommended answer>
```

Each user answer reshapes the tree. Recompute the frontier. Non-goal branches that just unblocked are taken by you in the same turn. A question whose answer depends on another question still open in this round belongs to a later round.

Finding facts is your job. When a frontier question needs a fact from the environment, dispatch a sub-agent; don't ask the user. Don't block the rest of the frontier on it.

The session is done when every branch is visited — by a looked-up fact, a recommended option you took, or a goal answer the user gave. Nothing left silently assumed.
