# START HERE. The one file for a new session (current as of 2026-08-22, night)

You are working on Entry V2: a tabular CatBoost entry policy for SI, HG and
NKD futures that must bank more than $2,000 per asset-day on HG and more
than $1,500 per asset-day on NKD and SI, from one contract per asset, on
held pre-2025H2 blocks, in exact chronological replay dollars, with at most
12 entries per portfolio-day, one position per asset, and a maximum
drawdown under $1,000. Neural is dead. The candidate generator is frozen.
2025H2 is sealed until the goal is met pre-H2. The goal is the user's and
is non-negotiable (D-110).

**Stop.** Do not launch probes, fits, Fable, or Opus unless the user says
so. The diagnosis below is the live state. This file is meant to be enough
to understand the problem.

## If this is a new session on this workspace

OptMem is the session memory. It outlives every session, compact, model,
and vendor change. Without it you do not know what was decided. A chat
that is not this `/workspace` cannot see OptMem or these receipts.
Compaction summaries are not the memory. Do not start from
`DIRECTIVES.md`, `.mempalace/hook_state/RECALL.md`, or
`compaction/INDEX.md`.

Tool: `~/.optmem/memo`. Store: `/workspace/.optmem/memory` (also at
`~/.optmem/memory`). Backup binary: `/workspace/.optmem/memo`. Never
edit or delete anything under those paths. The tool manages them.

### How to use OptMem

Run these yourself. Some harnesses print wake stdout at session start.
Some ignore that stdout. A printed hook is not the recall. After a
compact, PreToolUse denies every tool until wake has actually run in
this session.

1. First command of the session. `~/.optmem/memo wake`. If the shebang
   fails (`python3: No such file or directory`), run
   `/usr/bin/python3 ~/.optmem/memo wake` (same for `note`, `nap`,
   `recall`, `zoom`). A bare PATH can also fail. Then
   `export PATH=/usr/local/bin:/usr/bin:/bin` and retry. Done when the
   output includes `You are awake.`

2. Follow the output to the end. If it says `Not awake yet. Run:
   ~/.optmem/memo wake 2 T`, run that exact command. If it says
   `Run: ~/.optmem/memo nap ...`, run that exact line before any other
   work. Repeat until it prints `Nothing left to compress` or does not
   ask for another nap. Unsettled compressions pile up and wake
   degrades.

3. Then keep reading this file through the short way. Then
   `STATE.md` (first NEXT_ACTION block) and
   `design/entry_reset/SELECTION_HOLD_EXTREME_20260822.md` (the next
   rule, unmeasured). Skills setup: `SKILLS.md`.

4. While working, register lasting facts:
   `~/.optmem/memo note "<one line, max 280 bytes>"`.
   Decisions, verdicts, receipt hashes, user rulings. Not session
   narration. Not a fact already in memory. If `note` asks a
   compression, settle it before the next action.

5. When you need an old fact, search.
   `~/.optmem/memo recall <regex>` matches every memory, word for word.
   Wake also prints a binary tree of one-line summaries (`#0-1`,
   `#2-3`, `#0-3`, ...). `~/.optmem/memo zoom <a-b>` opens one node
   into its two halves, down to the raw memories. Use zoom when a
   summary line might hold the fact and recall is too broad.

6. If you spawn a subagent, put this in its brief: `You are a
   subagent. Don't run memo.` Parallel sessions on this machine may
   all write memories. A subagent cannot judge what is already known.
   Its notes would land duplicated and wrong.

Fallback, only if `memo wake` itself fails: read
`/workspace/CONTINUITY.md` then `/workspace/STATE.md`. Those are a
short overwritten snapshot, not the default. Do not dump CONTINUITY
into every turn.

Repo files remain authority for what was decided. OptMem is recall so
the next session finds it. Update `STATE.md` when the live stage
moves. A note without a STATE cursor is a memory the next agent will
not treat as current.

Zero learned economics have ever been published. Every number here is a
2021 diagnostic on 67 days (11-21 days per block). 2021 can kill a rule.
It cannot promote.

## The short way to the goal

**As of 2026-08-23 the frame changed and the goal is closer than it has ever
been.** Verdicts: `design/entry_reset/T35_VERDICT_20260823.md` (the frame and
the live rule) and `design/entry_reset/T29_T34_VERDICT_20260823.md` (why the
old shape had to be abandoned). Receipts `extreme_events_20260823.json`,
`event_column_scan_20260823.json`, `hold_running_extreme_20260822.json`.

### The frame: new-extreme events

The score is static per name (its own 180 s row), so the name that ends a phase
as its side's extreme necessarily BEAT every earlier name when it became
eligible. Call that a **new-extreme event**. Two measured consequences:

1. The event set contains the paying name at **recall 1.000** on all three
   assets.
2. Every event is entered at 180 s of age, the only age this matrix labels
   exactly. No proxy, no unpriceable wait.

There are about 6 events per cell, down from 15 names.

### The numbers

| | HG (rung $2,000) | NKD ($1,500) | SI ($1,500) |
|---|---|---|---|
| Event oracle, exactly labelled | **2,772** (+3.3 SE) | 1,851 (+1.1 SE) | **2,396** (+2.7 SE) |
| Best LIVE rule (TRAIN) | 801, inside its null | 875 vs null 547 | **1,465** vs null 1,251 |
| Capture of the oracle | 29% | 47% | **61%** |
| Capture the rung needs | 72% | 81% | 63% |

**SI is two points of capture short of its rung**, with a fully causal rule and
exactly labelled cash. That is the closest this program has come, and the gap is
now a CAPTURE gap, not an identification gap or a pricing gap.

The live score is extension beyond a fixed location level
(`disc_prior_high_aligned_usd` and its family, inverse direction: further beyond
the level on the fade side marks the payer). It survives TRAIN, THRESHOLD and
FORWARD on NKD and SI in the column scan. HG carries no member of that family
and is the open per-asset question.

All Stage 5 numbers are TRAIN-selected and therefore EXPLORATORY. THRESHOLD is
read ONCE, for a frozen rule (ticket 39).

### Two things that are dead, and why it matters

- **Ticket 28's hold** (wait H minutes, enter the standing extreme) cannot be
  priced. It enters at 7,380-10,980 s of name age while the labelled grid stops
  at 600 s (`confirmation.training_offsets_seconds` refuses anything else). The
  window is still open there, so the error is pure entry-price drift, and a
  linear extrapolation of the measured decay is about $750 against HG's $1,610.
  Bound, not correction. Do not tune it.
- **Ticket 34's armed entry** (wait, then take the next fresh name) is inside
  its null on every asset. The hold's value is the IDENTITY of the held name,
  never a timing signal.

### The correction that unlocked all of it

The frozen spec's per-side extreme was INVERTED. `aligned = side * (mid - level)`,
so extended-on-the-fade-side is the MOST NEGATIVE value on BOTH sides.
`long_min_short_min` won 24 of 24 asset x score x block cells. Under it the
finished-cell oracle went from missing every rung to clearing HG's by 2.1-3.2 SE.
Every earlier closure that ranked by an aligned extreme without cashing both
ends is suspect; tickets 24-27 were checked and are unaffected
(`artifacts/cache/review/sibling_sweep_20260822.md`).

### Next

Ticket 39: one per-asset ranker over the location-extension family, per-side
z-scored inside the cell, plus nearest-beyond-level and count-of-levels-cleared
arms. TRAIN only until frozen; then ONE THRESHOLD read. If SI clears, ticket 33
(2022-2025H1, the cheap D-110 corpus) is the verdict tier, not another 2021 arm.

Do not rewrite G1. Do not fit CatBoost on 1,764 columns. Do not open exits.
2025H2 stays sealed. 2021 can kill a rule; it cannot promote one.

## What the goal needs, and what the generator already has

A one-entry-per-phase picker at 180 s after formation, on the frozen G1
reversal names, needs a within-cell score-to-value correlation of about
ρ 0.49 to 0.76 (winner-vs-loser AUC 0.77 to 0.95) to print the rung.
Receipt `rho_ruler_20260822.json`.

After live keep-first (formation VWAP, HG 2θ, NKD/SI 1θ), the hindsight
cell-max still prints TRAIN $2781 HG / $1860 NKD / $2409 SI. The
generator is not the bottleneck. Receipt `rho_on_dedup_20260822.json`
sha `3b5e69c8`. Ranking the remaining 15 unique paths still needs AUC
0.87 / 0.90 / 0.81. Dedup does not make a weak score print.

CatBoost is not the limiter. Unit-weight Dawes beat trees on this plane.
YetiRank on 1764 columns was not separated from shuffle.

## Oracles versus a model. Do not mix them.

| Number | What it is | TRAIN $ HG / NKD / SI |
|---|---|---|
| Cell-max of keep-first names | Finished-cell hindsight oracle. Illegal live (uses later names and later y). | 2781 / 1860 / 2409 |
| Side-first (ticket 24) | Oracle: know the finished cell's winning side, take the earliest name on it. Not a model. | 1986 / 985 / 1471 |
| MAX_EXT vs prior range | Finished-cell oracle: most extended versus yesterday. Ticket 28's first score. | 1411 / 1103 / 1521 |
| Enter-first (ticket 25) | Fully live. Take the first eligible keep-first name. No score. | 489 / -313 / -196 |
| Isolated Dawes as a picker | A score, live-legal. Cashes negative on the 15. | -50 / -160 / -267 |
| Clock / formation-order | One score at Δ=180. | 490 HG, negative NKD/SI |

Side-first already misses the rung. A live side call can only do worse.
Receipts: `side_split_20260822.json` sha `d64b1d68`,
`label_variants_20260822.json` sha `ca83d2d2`,
`crux_prefix_winner_20260822.json` sha `d2fe2753`.

## The live object

Names become eligible 180 s after they form, in formation order. When
the eventual paying name (cell-max) becomes eligible:

- It is the first-born in 21% HG / 6% NKD / 12% SI of cells.
- Median already-eligible keep-first names on the table: 4 / 7 / 5.
- You are ranking a live prefix of 4-7 names, not a finished list of 15.

## How long until the paying name exists (ticket 26)

Seconds from the first keep-first formation to the cell-max formation
(same as the eligibility gap). Receipt `crux_wait_scan_20260822.json`
sha `044cde9b`. TRAIN:

| | HG | NKD | SI |
|---|---|---|---|
| Median wait | 2442 s (41 min) | 2536 s (42 min) | 2214 s (37 min) |
| p25 | 204 s | 333 s | 237 s |
| p75 | 4850 s (81 min) | 7381 s (123 min) | 5723 s (95 min) |
| p90 | 8544 s (142 min) | 11434 s (191 min) | 7936 s (132 min) |
| Arrived by 0 s (is first) | 0.21 | 0.06 | 0.12 |
| Arrived by 60 s | 0.22 | 0.11 | 0.12 |
| Arrived by 180 s | 0.25 | 0.24 | 0.21 |
| Arrived by 300 s | 0.29 | 0.24 | 0.30 |
| Arrived by 600 s | 0.35 | 0.30 | 0.39 |
| Arrived by 1800 s (30 min) | 0.44 | 0.44 | 0.48 |
| Arrived by 3600 s (60 min) | 0.60 | 0.63 | 0.61 |

The 180 s / 300 s confirmation window sits on the first names. About
70% of the time the paying name is not even eligible yet. That is why
scoring confirmation 3-5 minutes after the first birth cannot print
the rung: the name that pays usually has not formed.

THRESHOLD and FORWARD wait medians are the same scale (HG 2580 / 2954 s).
This is not a TRAIN quirk.

## Is it missing information, or something else?

Split the claim. Do not collapse it.

**Until the paying name is born, the information cannot exist.** No
feature of the earlier names can point at a name that is not on the
table. Direct from the wait table. This is not a model defect and not
a generator defect. The decision time scale we used (180-300 s after
each birth, and especially after the first birth) is the wrong scale
for "the name that pays." The phase-scale wait is tens of minutes to
hours.

**Once it is born, among the 4-7 already-eligible names, the columns
we actually trained (confirmation Dawes, clock, location proximity)
do not identify it.** Ticket 25: prefix AUC ~0.46-0.51 HG/NKD, inside
shuffle. Clock remaining AUC is 0.0: remaining falls as later names
form, so it always prefers earlier names. Direct.

**We scanned every matrix column in that same prefix frame (ticket 26).**
Letter `only_clock` on all three assets. The top TRAIN columns are
session/phase elapsed and `ctx_*_age_seconds` at AUC 1.0. That 1.0 is
tautological: in the prefix-at-winner-time frame the winner is always
the last-born, so any clock that increases with formation time
"identifies" it. That is not a live rule. You would also pick "the
latest" at every earlier moment, which is not the winner. Zero
non-clock single columns survive TRAIN AUC >= 0.60 and THRESHOLD
AUC >= 0.60.

**What is still unknown.** Combinations of non-clock columns other
than Dawes. Dawes is already a combination of the confirmation family
and was chance on HG/NKD in the prefix frame. Identification at 600 s
or 1800 s after each name's own birth (not after the first name).
Zigzag `pivot_mid2` and G1 tape histograms, which are not columns on
this matrix. Those are the remaining ways information could still
exist. They are not measured. They are not an excuse to refit CatBoost
on the 1764-column isolated plane.

**What it is not.** Not CatBoost (trees lost to Dawes; the plane is
empty). Not the generator (cell-max prints the ceiling). Not the
dollar label (perfect ranker of y prints the ceiling, but that ranker
is illegal live). Not "good enough" classification (T23: too many
cells have no $600 name). Not location keep (leftover 83/73/52%).
Not Fable's side-then-earliest (oracle already under the rung). Not
rank-by-runway (T23 clock cash $490 HG).

## If you wait ~40 minutes, how much of the oracle is on the table

Ticket 27. Still an oracle: hindsight max y among names already born,
never names not yet born, never a model. Receipt
`wait_prefix_ceiling_20260822.json` sha `1630a2d4`. TRAIN:

| Wait after first name | HG $ (cap) | NKD $ (cap) | SI $ (cap) |
|---|---|---|---|
| 0 s (enter-first) | 489 (0.18) | -313 | -196 |
| 300 s (5 min) | 1123 (0.40) | 625 (0.34) | 510 (0.21) |
| 600 s (10 min) | 1445 (0.52) | 803 (0.43) | 1201 (0.50) |
| 1800 s (30 min) | 1921 (0.69) | 1127 (0.61) | 1488 (0.62) |
| 2400 s (~40 min) | 2117 (0.76) | 1262 (0.68) | 1777 (0.74) |
| 3600 s (60 min) | 2340 (0.84) | 1350 (0.73) | 1817 (0.75) |
| inf (finished cell) | 2781 (1.00) | 1860 (1.00) | 2409 (1.00) |

At ~40 min, about half the paying names are born (0.49 / 0.48 / 0.55).
The prefix oracle cashes $2117 HG TRAIN (clears $2000) and $1777 SI
TRAIN (clears $1500). NKD $1262 does not clear $1500 even at 60 min
($1350). THRESHOLD/FORWARD at 40 min: HG $1741 / $1787, both under
$2000. So "wait 40 min and pick perfectly among names on the table"
is not a held path. It is also still an oracle. Ticket 25 says this
plane cannot make that pick live.

## Is generation random, so we have to wait 40 minutes

No. G1 is a high-recall zigzag (D-065: generation stays high-recall,
pruning is selection). Early names are real local extrema. The phase's
remaining-move extreme often has not printed yet, so a later zigzag is
the paying name. That is not random placement and not a reason to
rewrite birth. You cannot select a name that does not exist yet. The
180-300 s confirmation window was attached to the first zigzags. The
paying zigzag usually arrives tens of minutes later.

## How to select the paying name (the next rule, unmeasured)

Identification is not a 3-minute confirmation score on the first
zigzag. The first zigzags are real swings. The paying swing is the
one that forms when the phase extreme is set, then holds. Anatomy:
the extreme is set mid-phase and holds; last-formed is never best;
causal "enter the first extended name" failed because the extreme
then ran further. 300 s patience failed because 300 s is not the
hold time. Ticket 26 says the hold time is tens of minutes.

Live rule, prefix-legal, generator untouched:

1. Let G1 print every zigzag. Keep-first coalesces nested rungs.
2. Track the running phase extreme among already-eligible keep-first
   names. Score is session (or phase) VWAP-aligned dollars, not
   prior-session extension. Prior-session MAX_EXT is a finished-cell
   oracle at $1411 / $1103 / $1521 TRAIN and cannot print.
3. Do not enter while a newer zigzag is still making a new extreme.
4. Enter the current extreme's path when nothing has beaten it for
   H minutes. H comes from TRAIN. One name per phase. Occupancy as
   today.

That is not RUNMAX (RUNMAX entered the first name that was extended
versus yesterday). That is not ranking 15 finished names. That is
not CatBoost on 1764 columns. That is not an exit.

The first measurement is the 2-name VWAP-extreme oracle, then the
causal hold only if that oracle clears. Ticket 28. If the oracle
misses, these columns are done; tag `pivot_mid2` next. If the hold
misses on THRESHOLD, the rule is dead on 2021. Do not add CatBoost.

Exits stay deferred (D-107, D-110). They are not a path until entries
print.

## Receipts (all under `artifacts/entry_v2/tabular_recovery/diagnostics/`)

Matrix `7e9e2588…` at
`artifacts/entry_v2/tabular_recovery/rehearsal/fit_only/e1r/curriculum/fits/round_0/component_matrix`.

| Ticket | Fact | File |
|---|---|---|
| 01 | Rung needs AUC 0.77-0.95. AUC 0.60 buys $200-650. Pool mean negative. | `rho_ruler_20260822.json` |
| 07 | `no single dimension` on top of the AUC 0.60 picker | `ceiling_split_20260822.json` |
| 11-12 | Location keep misses leftovers 83/73/52% | `oracle_retention_filters_20260822.json` |
| 18-20 | Live keep-first, ~15 paths, most of ceiling kept | `path_dedup_live_20260822.json` sha `4beb0045` |
| 22 | After dedup, AUC at rung still 0.87/0.90/0.81 | `rho_on_dedup_20260822.json` sha `3b5e69c8` |
| 23 | y is an aligned label. Dawes cash negative. Clock $490. good_enough cannot_reach HG/NKD | `label_variants_20260822.json` sha `ca83d2d2` |
| 24 | Side-first is an oracle and misses the rung ($1986/$985/$1471) | `side_split_20260822.json` sha `d64b1d68` |
| 25 | Live prefix identification `prefix_blind` HG/NKD. Enter-first $489/$-313/$-196 | `crux_prefix_winner_20260822.json` sha `d2fe2753` |
| 26 | Wait median ~40 min. Scan `only_clock` (tautological elapsed). No non-clock column holds | `crux_wait_scan_20260822.json` sha `044cde9b` |
| 27 | Prefix oracle after wait. 40 min: HG $2117 TRAIN (0.76 of max), NKD $1262, SI $1777. THRESHOLD HG $1741 | `wait_prefix_ceiling_20260822.json` sha `1630a2d4` |
| — | MAX_EXT vs yesterday is $1411/$1103/$1521 TRAIN at 180 s. Cannot be ticket 28's score. | `extension_prior_20260822.json` |
| 28 | Unmeasured. VWAP-extreme oracle, then hold. Not MAX_EXT. | `design/entry_reset/SELECTION_HOLD_EXTREME_20260822.md` |

## Fable and Opus (written, not to re-run)

Fable 5 xhigh session `6f11e029-99cc-45f6-9998-050986c3b51c`:
`design/entry_reset/FABLE5_XHIGH_LABEL_DIAGNOSIS.md`. Took
side-then-earliest. T24 killed it as a ceiling.

Opus 5 max session `18d4977a-f745-4f6d-857a-b1cfb0d7743c`:
`design/entry_reset/OPUS5_MAX_LABEL_DIAGNOSIS.md`. Took runway-offset.
T23 killed rank-by-clock.

Resume recipes: `artifacts/cache/review/cli_sessions_20260822.md`.
Never `--bare`. Restate the fence every resume.

## Laws in one screen

Rung $2000 HG, $1500 NKD and SI when that block's delayed ceiling
cannot support $2000. 5 real + 5 shuffle seeds. Exact replay dollars
only (D-095). Knobs from prior blocks. At most 12 entries per
portfolio-day. MDD under $1000. Entries only (D-107, D-110).
Generator frozen. Neural dead. 2025H2 sealed. Waiting after
formation is lawful. 300 s was a guess. Ticket 26 says the relevant
wait is tens of minutes.

## How you work here

OptMem first, as written above. Follow wake to the end, including every
`nap` it prints. Skills are law, not a menu. How they are wired, why
other agents in this repo skip them, and how `AGENTS.md` / `CLAUDE.md`
must be written so the table is mandatory: `SKILLS.md`. Reading
`/workspace/.claude/skills/<name>/SKILL.md` is the invocation. The user
will not name skills and will not say implement. Tests:
`python3 -m unittest`. pytest is not installed. Battery:
`bash tools/run_all_checks.sh`. Hardware: `HARDWARE.md` (`nproc` and
`free` lie: 13.6 cores, 263 GiB).

## Read next, in this order, only if you need depth

1. `~/.optmem/memo wake` (follow it to the end; this file has the recipe)
2. This file (you are here)
3. `SKILLS.md` (how the skill law is wired)
4. `STATE.md` (first NEXT_ACTION block)
5. `CURRENT.md` (closed questions with scope)
6. `design/entry_reset/HANDOFF_DECISION_PLANE_20260822.md`
7. `design/entry_reset/SELECTION_HOLD_EXTREME_20260822.md`
8. `AGENTS.md`, `HARDWARE.md`

## If the pod restarted

Reinstall from `HARDWARE.md`, then `bash tools/run_all_checks.sh --fast`.
The matrix, receipts and OptMem live on `/workspace`. Overlay `/` does not.
