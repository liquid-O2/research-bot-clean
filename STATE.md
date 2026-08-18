# STATE — current fast cursor

**Last updated:** 2026-08-18T11:14:00Z

**Canonical entry point:** [`index.md`](index.md)

**Detailed ledger:** [`docs/ENTRY_V2_CURRENT_STATUS.md`](docs/ENTRY_V2_CURRENT_STATUS.md)

## Operational state

**STOPPED BY EXPLICIT USER ORDER.**

- No Entry V2 production/training process or GPU compute process is running.
- Long-lived unrelated Claude/tmux sessions and an idle historical port-m2
  supervisor exist on the host. They are outside this Entry V2 cursor and were
  not touched by the documentation pass.
- Do not resume code changes, audits, rehearsals, or runs unless the user gives
  a new explicit instruction.
- The only active work at this boundary is documentation.
- 2025H2 remains sealed.

## Experimental state

There is no successful new Entry V2 learner result.

- `pre_h2_v3`: E3-E5 primary learned arms all used threshold `1.000001`, made
  no entries, and produced no learned economics.
- `pre_h2_v4`: E3 full-prefix arm found one HG trade at $91.75/asset-day and
  five NKD trades at $302.50/asset-day; SI had no feasible threshold. Both
  static GBT arms had no feasible threshold on every asset. Gate failed at
  `POLICY_NO_FEASIBLE_THRESHOLD:SI`.
- v4 representation probe: static and late fusion improved calibrated AUROC
  over the 512-wide embedding, but the standard arms made zero test trades;
  the only nonzero tail-aware test arm lost money.
- Replacement C0/C1/L0/L1/M1 arms: never reached authoritative training.
- 44 real/shuffled objective screen: never ran.
- Replacement E1, E2, E3: never ran.
- Winner adoption and E4-E8 replacement campaign: absent.

## Latest retained attempt

`pre_h2_v9`:

- warm corpus passed in 518.133 seconds against a 600-second ceiling;
- 574 verified-session durable hits;
- 236 diagnostic-plane durable hits;
- zero physical full-pack opens;
- zero model-array physical fills;
- `one_load` completed and published exact E1r/E2r candidate preflight;
- `raw_fidelity` failed before arm C0 with
  `expanded transform diagnostic binding lacks corpus session`.

Exact root cause: DiagnosticCorpus correctly had 236 candidate-bearing
sessions, while EntryCorpus correctly had 235 sessions with at least one
`CLEAR + READY` learner row. The sole diagnostic-only session was SI
2021-07-12 with a `NO_SANE_SUFFIX` teacher. The old transform metadata builder
incorrectly required the two domains to be equal.

## Current source status

The working tree now implements the intended diagnostic/learner intersection
law and has been locally checked against the real 236/235 roster. It has not
been production-verified. Most Entry V2 source is untracked; multiple later
lanes were frozen after static review without one consolidated compile or real
run, so a clean cross-layer baseline does not exist.

Treat the source as:

`DIRTY + PARTIALLY VERIFIED + NOT LAUNCH READY`

## What is genuinely reusable

- causal QRE2 substrate and retained manifests;
- candidate/teacher/replay receipts;
- exact v3/v4 fold artifacts;
- v4 representation diagnostic;
- durable verified-session, session-array, and diagnostic-plane products;
- v9 warm timing and one-load receipts;
- frozen recovery/clock/diagnostic authority documents;
- failure and rehearsal logs under `provenance/entry_v2/`.

Reusable does not mean learned or deployable.

## Binding execution rule

[`AGENTS.md`](AGENTS.md) is mandatory. In short:

- no serial `point fix -> paid launch -> next defect` loop;
- unit/synthetic/mock tests are regression checks, never launch evidence;
- no launch before one complete real authoritative pre-H2 production-path
  rehearsal executes every boundary, publication, strict reload, and restart;
- before held E1-E3, the unchanged fit-only learner must pass every asset and
  recover at least 80% of each exact candidate ceiling on both rehearsal
  transitions; 90% is the target;
- 2025H2 stays sealed.

## Resume recipe

Only after a new explicit user instruction:

1. Read [`index.md`](index.md).
2. Read [`docs/ENTRY_V2_CURRENT_STATUS.md`](docs/ENTRY_V2_CURRENT_STATUS.md).
3. Read [`AGENTS.md`](AGENTS.md).
4. Read the frozen plan, amendments, neural diagnostic, and clock law.
5. Inspect the current dirty worktree without discarding unrelated changes.
6. Verify the exact retained v9 and durable-store identities.
7. Do not launch until every prerequisite in the detailed ledger's resume
   section is measured on the real production path.

The older port-m2/port-m3 cursor formerly stored here is historical. Its
evidence remains in [`index.md`](index.md),
[`provenance/sessions/JOURNAL.md`](provenance/sessions/JOURNAL.md), and the
port-m2/port-m3 receipt tables. It is not the current Entry V2 stage.
