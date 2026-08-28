# START HERE (2026-08-26)

You are working on **Entry V2**, a tabular entry policy for SI, HG and NKD
futures that must bank more than **$2,000 per asset-day on HG** and **$1,500 on
NKD and SI**, from one contract per asset, on held pre-2025H2 blocks, in exact
chronological replay dollars, with at most **12 entries per portfolio-day**, one
position per asset, and maximum drawdown under $1,000.

The goal is the user's and is non-negotiable (D-110). Neural is dead. The
candidate generator is frozen. 2025H2 is sealed.

**Read this file first.** Every host, every model. Compaction summaries are
not the record. `MEMORY.md` plus this page are.

## Live cursor (2026-08-28, the mill era, read this first)

The overnight mill ran sweeps 1 through 29 and closed on a USER stop
order after the tranche-2 Sol ruling. A fresh session needs exactly this
reading order, nothing else first:

1. `.audit/briefs/mill-side-resolution.md`, the charter. The newest
   rulings are stacked ABOVE the section "Sol's closure ruling after
   sweep 14"; read from "SESSION CLOSE" at the top of that stack down
   as far as needed. Every sweep, refusal, stamp, and adopted ruling of
   the era is in there in order.
2. `.audit/briefs/mill-tranche2-sol-out.md`, the LIVE ruling. It fixes
   the next unit: **F25-PATHWISE-CAPACITY**, a deterministic certified
   bound over the 3,497 priced break-close opportunities (its exact
   spec, fixtures, and stop rules are in that page's section D).
   CAPACITY-EMPTY stops the mill and hands the USER the measured
   law-interaction fact; CAPACITY-ROOM routes to the cash-free
   F26 source census; F27 only behind both gates. Do not dispatch
   anything before reading it.
3. The other Sol pages, in order if context is needed:
   `mill-sweep14-sol-out.md` (closure), `mill-fixhold-sol-out.md`
   (F13 death, magnitude route), `mill-pinpoint-sol-out.md` (the root
   cause: hold-or-break is barrier against impulse and the plane
   carries only the impulse; the candidate answer; the path),
   `mill-structbreak-sol-out.md` (the zone-miscentering REFUSAL of
   sweeps 22-23 and the fixed-zone corrections),
   `mill-powerplan-sol-out.md` (power arithmetic, F22/F23/F24 specs).
4. `.audit/mill-hypothesis-log.tsv`: 1,006 data rows, 831 KILL, 144
   UNRESOLVED, 31 deliberately unstamped (sweep 23, refused lineage,
   never judged). Receipts `.audit/mill-sweep15.json` through
   `mill-sweep29.json`, plus `mill-levels-build.json`,
   `mill-levels-zone-build.json`, `mill-zone-history-build.json`.
   Code in `tools/mill/` (sweep15-29, levels.py, levels_zone.py,
   zone_history.py). Ledger notes #644-758 cover the era.

The standing facts a new session must not re-derive: the state predicts
session-scale move SIZE out of fold on both deciders and never
direction; timing works as a FILTER (ordinal-2, confirmation, the
USER's break-close and box-exit events); formed universes carry 9x-55x
of the rungs in hindsight while the best causal book reached 0.14x;
the genealogy increment is the one positive two-decider result
(frozen UNRESOLVED); the sub-minute grain lever is DEAD with a receipt
(sweep 26 ORDER-POOR, both halves of the evidence bar); and THE
FEASIBILITY FACT: at observed trade sizes the two deciders need about
23 seats a day against the 12-seat law, and even the zero-wall
hindsight terminal oracle fails the portfolio event-time MDD at 5,894
against 1,000. Sol priors at close: program 15 percent, current laws
2 percent, judgments not stop rules. HOLD (131/129/127), 2021
(kill-only), and 2025H2 are sealed and unspent. No USER law has a
measured case for change.

Seat corrections that supersede anything below: the parent seat is
FABLE on Claude Code (this session's lineage), not Grok. Sol is invoked
PLAIN, `codex exec -m gpt-5.6-sol -c model_reasoning_effort="max"
-c service_tier="fast" --dangerously-bypass-approvals-and-sandbox`,
with NO model_instructions_file (USER order 2026-08-27, revoking the
sol-instructions override). Implementation goes to Opus subagents;
Fable stays main-thread; Sol reviews every design decision and every
major result before the parent acts (USER standing law). USER
directives of the era live in the Claude memory files
user-working-style, unslop-exact, and fable-failings-2026-08-27
(14 recorded failings with fixes) under
/home/algo/.claude/projects/-workspace/memory/.

## Prior cursor (2026-08-27, superseded by the mill era)

The 2022-2024 ceiling is already known. Do not re-prove it. Capture miss is
the work. `.audit/threshold-capture-gap.json` verdict MISS. Identity is 99.98%
of the $2.09M gap. Cell-best on the gated join: HG 2758.95 / NKD 3815.22 /
SI 3880.47 (`.audit/threshold-2022-2024-ceiling.json`).

Every unfitted stored read is closed. Pivot Stage 1 KILL closed unfitted
geometry at age 180. C Stage 0 PASS, C Stage 1 KILL
(`.audit/briefs/threshold-cfit-stage1-judge-out.md`): fitted identity at age
180 posted HG -173.50 / NKD +31.20 / SI -150.45, MDD 75608.75. No second C
config. S0 LIVE. Oracle side plus within-side price posts 2753.53 / 3806.71 /
3869.82, MDD 192.50 (`.audit/briefs/threshold-side-split-judge-out.md`). S1
KILL. Causal within-side at 180 cannot carry the rungs even with oracle side
(`.audit/briefs/threshold-s1-sidecaller-judge-out.md`). Covering after that
KILL named **B0**, mechanism-funded by late-arriving extremes
(`.audit/briefs/threshold-covering-after-s1-fable-out.md`).

B0 Stage 0 PASS. B0 Stage 1 LIVE, Fable judged from the bytes
(`.audit/briefs/threshold-b0-stage1-judge-out.md`). Age-600 cell-best posts
2726.81 / 3775.72 / 3847.62, envelope 2874.91 / 3942.93 / 4058.61, MDD 0,
max 9 entries. HG at 10800 s misses (1582.77). `picker_started` is false.
B2 LIVE, Fable judged
(`.audit/briefs/threshold-b2-price-picker-judge-out.md`).
`recside_effprice_all` HG 600 / NKD 600 / SI 2400 posts 2059.78 / 2653.88 /
2987.05, MDD 967.50. Teacher-cash cannot promote. Covering after that LIVE named **V0**. Sol peer named B3 common-clock
replay, recorded not executed
(`.audit/briefs/threshold-covering-after-b2-sol-out.md`). V0 Stage 0 STOP, Fable judged
(`.audit/briefs/threshold-v0-stage0-judge-out.md`). Frozen era gate cannot
run on 2021. Census streamed 2025H1 forecast headers. No 2021 late store.
2021 license unspent. Covering after that STOP named **B3**, age-2400
common-clock record-side causal replay
(`.audit/briefs/threshold-covering-after-v0-stop-fable-out.md`). Sol named
the same shape. B2 LIVE stays an optimistic batch cap, not an executable
clock. B3 STOP stays locked
(`.audit/briefs/threshold-b3-common-clock-judge-out.md`). Covering after
B3 named **B4**, Fable designer
(`.audit/briefs/threshold-covering-after-b3-fable-out.md`). Sol peer named
the same unit. Cell identity is the scheduled phase instance. Locked-era
CLEAR collisions are 52 cells, 22 HG / 10 NKD / 20 SI. Era-wide files 249.
Covering after B4 split. Fable named **B5**
(`.audit/briefs/threshold-covering-after-b4-fable-out.md`). Sol peer
named a dead end
(`.audit/briefs/threshold-covering-after-b4-sol-out.md`). B5 KILL, Fable judged
(`.audit/briefs/threshold-b5-common-clock-judge-out.md`). Causal
cheap-on-side at 2400 is dead under every scoring of the four silent
cells. USER forbade auto-starting E1. Next is a minutes mill on when
the side is known, not another ranker. No exits.
2021 can kill. 2021 cannot promote. 2025H2 stays sealed.

The mill is chartered (`.audit/briefs/mill-side-resolution.md`, Fable
2026-08-27, parent seat moved to Claude after Grok's weekly limit).
Exploratory tier: can kill, cannot promote. Quarantine split frozen in
`.audit/mill-split.json`: EXPLORE 66/65/64 asset-days (d8 rank mod 3 == 0
over the B5 locked 582), HOLD 131/129/127 untouched until a survivor rule
is frozen in writing for one read. Mill cash comes from the frozen outcome
law on raw suffixes; teacher and late stores stay shut. Substrate and
frontier tooling live in `tools/mill/`, caches in `artifacts/cache/mill/`.

Cursor Ultra is exhausted (~97% monthly). Do not use Cursor as the overnight
parent. Daily parent is this Grok TUI. Sol specified walks: `codex exec`
with `model_instructions_file=/workspace/.codex/sol-instructions.md` (vendor
prompt plus `.codex/follow-rules.md`). Fable: `claude -p --append-system-prompt-file
.codex/follow-rules.md`. Do not point Codex at follow-rules.md alone. After
compact, read this file first.

---

# 1. How to work here

Any host, any model. This file is the index. `AGENTS.md` also says to
follow `.cursor/rules/` as a backup if the one-line append is missing.

## First read

1. This file, live cursor then this section.
2. Memory: last 12 notes if injected, else `python3 tools/memory_ledger.py tail 12`.
3. Covering map: `.audit/briefs/threshold-covering-after-cfit-kill-out.md`.
4. The one live brief named in live cursor. Nothing else until that unit is judged.

Do not rediscover closed kills. Compaction summaries are not the record.

## Memory

`MEMORY.md` and `tools/memory_ledger.py` live in this repo. They outlive
every session, compaction, model, and vendor change.

1. Older facts: `python3 tools/memory_ledger.py recall '<regex>'`.
2. Lasting fact: `python3 tools/memory_ledger.py note "<one line, 280 bytes>"`. The parent writes notes. Not narration.
3. Subagent briefs include exactly once: `You are a subagent. Don't run memo.`

Lock helper is `engine/entry_v2/pod_local_lock.py` (the ledger already finds it). Unslop lint is `tools/unslop_lint.py`.

## Seats

Cursor Ultra is exhausted (~97% monthly). Do not use Cursor as the overnight parent.

| Seat | Who | How |
|---|---|---|
| Parent / overnight | Grok 4.6 xhigh on this TUI | `/poteto-mode`. Hillclimb against the rungs. Writes MEMORY notes. Does not stop at a child receipt. |
| Playbook workers | Grok `poteto-agent` | `.grok/agents/poteto-agent.md`. Reads poteto-mode SKILL.md first. Not `general-purpose`, `explore`, or `plan`. |
| Designer / covering / Stage judge | Fable `claude-fable-5-thinking-max` only | `claude -p --append-system-prompt-file .codex/follow-rules.md`. No thinking-high. Not a Grok subagent. |
| Peer on covering / planning | Sol `gpt-5.6-sol-max` | Same brief as Fable, parallel. `codex exec` with `model_instructions_file` already set. Does not execute a plan it just wrote. |
| Specified hard walks | Sol `gpt-5.6-sol-max` | Fresh child, different brief, the sequence Fable named. |

Send parent-facing prompts to the parent. Do not write "You are Fable" into a
parent paste. Do not `/model` the parent onto Sol or Fable.

CLI children match Cursor Tasks: envelope
`.cursor/prompts/cli-child-header.md`, then the role brief from
`.cursor/prompts/cli-dispatch.md`. Overnight paste:
`.cursor/prompts/overnight-c.md`. No Claude or Codex hooks.

Paste files:

- Covering: `.cursor/prompts/threshold-covering.md`
- C Stage 0: `.audit/briefs/threshold-cfit-stage0.md`

## Method

`/poteto-mode` owns playbooks and the principle catalog. Plugin:
`.cursor/plugins/pstack-lab`. Always-on layer is `.cursor/rules/` (Cursor `.mdc`)
and `.grok/rules/` (Grok `.md`, same bodies). Matching principle leaves are
mandatory. The 21 leaves are not stuffed into the prompt. Equal-standing: open
the leaf when its trigger matches. Do not install stock Pstack.

The path to the rungs is the **hillclimb** playbook, not Feature and not the
2026-08-23 ticket plan. Metric: HG 2000, NKD 1500, SI 1500, MDD under 1000, at
most 12 entries, dollars per trade. The covering map is the hypothesis log.
The unblocked frontier is not E1. B5 KILL is judged. User 2026-08-27:
covering queue is pre-decided. Next is a cheap mill on side-resolution
timing. No exits.
Wayfinder tickets only when a question is sharp and unnamed. Do not invent a
picker from the judge page. `/tdd` only for a cheap local test.
Covering units already fail selftest plus mutants before the run.
Named STOP seams get a cheap probe on locked bytes before a specified
Sol or Fable walk. A seam that fires is covering work. Do not spend a
40-minute walk to discover it. B3's cell-identity collision and B4's
four empty suffixes were both this class.

Overnight follows principle-never-block-on-the-human and
`playbooks/autonomous-run.md`. A unit ends at a check
(principle-sequence-verifiable-units). The parent then continues. A specified
CLI child stops at its named receipt. The parent does not.

On this Grok host, the order is this file, covering map, live brief. Fable and
Sol keep their vendor system prompts plus `.codex/follow-rules.md`.

## Commands

- Tests: `python3 -m unittest <module>`. pytest is not installed.
- Full battery: `bash tools/run_all_checks.sh --fast`
- Every probe carries `--selftest`. Run it, then mutate the code and confirm the
  selftest goes red. A fixture no mutant kills is decoration.
- Hardware: `HARDWARE.md`. `nproc` and `free` lie here. 13.6 cores, 263 GiB.
- Pod restarts wipe the overlay. Reinstall recipe is in `HARDWARE.md`. Install
  with `uv`, not pip.

## Durability

Two copies, two jobs. GitHub is the code. R2 is the volume.

| Layer | What | Where |
|---|---|---|
| GitHub | Code, MEMORY, briefs, receipts that fit git | `https://github.com/liquid-O2/research-bot-clean` branch `main` |
| R2 `runp` | Full `/workspace` backup (artifacts, data, `.git`) | `rclone` remote `r2:runp` |
| R2 `nkd-hg`, `rty`, `russel` | Source tapes. Walls. | List only. Never write. Never purge. |

Git does not hold `/data/`, `/artifacts/`, `.optmem/`, node_modules, or session
binaries. Those ride R2. Do not put secrets in git. Rclone keys live at
`.secrets/rclone-r2.conf` (mode 0600, gitignored). Fallback `/tmp/rclone-r2.conf`.

Backup command: `bash tools/r2_backup.sh`. GitHub push first, then that script.

## New pod

Keys are not in git. Put `.secrets/rclone-r2.conf` (or `/tmp/rclone-r2.conf`)
on the box first. Then pull the volume:

    bash tools/r2_restore.sh

If the tree is empty and the script is not there yet:

    rclone copy r2:runp /workspace --config /tmp/rclone-r2.conf \
      --transfers 64 --fast-list --no-check-dest --s3-no-check-bucket \
      --s3-use-x-id=false --s3-no-head --s3-use-unsigned-payload=true \
      --s3-disable-checksum --s3-sign-accept-encoding=false

Do not write `nkd-hg`, `rty`, or `russel`. Overlay `/` is empty after a pod
start, so reinstall from `HARDWARE.md` with `uv`. Skills come with the tree
under `.cursor/plugins/pstack-lab`. After restore run
`bash tools/install_pstack_skills.sh` so `.claude/skills`, `.codex/skills`,
`.cursor/skills`, and `.agents/skills` all symlink that tree. Do not install
stock Pstack.

Codex `model_instructions_file` replaces the vendor prompt. It must be
`.codex/sol-instructions.md` (vendor Sol prompt plus `.codex/follow-rules.md`).
Build it with `python3 tools/build_sol_instructions.py`. Fable only appends
`.codex/follow-rules.md`. Do not point Codex at follow-rules.md alone.

    model_instructions_file = "/workspace/.codex/sol-instructions.md"

Grok loads `.grok/rules/follow.md` by itself. Same one line Fable appends.

---

# 2. What the problem actually is

## The frame

A **cell** is one (asset, day, phase). G1 emits zigzag reversal candidates
throughout it. After live keep-first dedup about 15 unique names survive per
cell. A **new-extreme event** is a name that sets a new running extreme on its
own side at its own eligibility moment (formation + 180 s).

Two facts make events the right universe, both measured:

- The paying name is **always** an event: recall **1.000** on all three assets.
- Every event is entered at 180 s of age, the only age this matrix labels
  exactly. No proxy.

There are about **6.3 events per cell** and about 3 cells per asset-day.

## The payoff, and it is the whole problem

`diagnostics/entry_economics_20260823.json`. Mean y of an event, TRAIN:

| Asset | Mean per event | % profitable | r0 | r1 | r2 | r3 |
|---|---|---|---|---|---|---|
| HG | **-$95** | 43% | $924 | $431 | -$2 | -$240 |
| NKD | **-$51** | 44% | $617 | $378 | $127 | -$50 |
| SI | **-$71** | 40% | $799 | $447 | $235 | -$49 |

The pool mean is negative, ranks 0-2 are non-negative, ranks 3+ are not.

**The target, stated correctly: land in the TOP TWO of about six.**

| Asset | Need per trade | Top-2 mean | Top-3 mean | All-6 |
|---|---|---|---|---|
| HG | $667 | **$678** | $451 | -$95 |
| NKD | $500 | $498 | $374 | -$51 |
| SI | $500 | **$623** | $494 | -$71 |

Top-2 clears HG and SI and is $2 short on NKD. Top-3 clears nothing.

**The rung must be met by dollars per trade, not by trade count** (user ruling,
2026-08-23). A "two entries per rich cell" lever was proposed and **withdrawn**:
two simultaneous positions in one asset is leverage if same-side and
self-cancelling if opposite, and `_cell_pick` already refuses it — occupancy runs
a median 17,000-25,000 s, so a second entry in a cell would never seat. Adding
size or count to reach the rung is a shortcut, not a path.

## The ceiling is real and exactly labelled

`diagnostics/extreme_events_20260823.json`, best event per cell cashed at its own
180 s row:

| Asset | Event oracle | SE | Letter |
|---|---|---|---|
| HG | **$2,772** | $238 | event_clears_rung |
| NKD | $1,851 | $321 | event_not_resolved |
| SI | **$2,396** | $329 | event_clears_rung |

**There is more money in the candidate set than the goal needs.** The generator
is not the bottleneck and never was.

## Where the live rule stands

`diagnostics/location_ranker_20260823.json`, frozen on TRAIN before any held read:

| Asset | Arm | TRAIN | THRESHOLD | FORWARD | Rung |
|---|---|---|---|---|---|
| HG | MAX_BEYOND | $1,000 | $857 | $790 | $2,000 |
| NKD | BEST_SINGLE | $875 | $940 | $807 | $1,500 |
| SI | BEST_SINGLE | $1,465 | $1,061 | $868 | $1,500 |

Every asset clears its shuffled null on every block. Every asset letters
`loc_insufficient`. Roughly half the rung.

The picker is **not** weak: it lands top-2 **65-77%** of the time against a
30-34% random baseline, and rank-0 41-56%. Occupancy skips: **zero**.

---

# 3. What has been ruled out, and why

Do not re-run these. Each is closed WITH its scope.

| Closed | Why | Scope |
|---|---|---|
| The generator | Cell-best clears the per-trade requirement on all three assets | Not a bottleneck at any grain tried |
| Model family | Unit-weight Dawes beat trees; YetiRank on 1,764 cols was inside shuffle | This plane |
| Ticket 28's hold | Enters at 7,380-10,980 s of name age while labels stop at 600 s, so it cannot be priced. Its pick averages 23-58% of the cell best — it is NOT the payer | This matrix's label grid |
| Ticket 34 armed entry | Arm on the held extreme, take the next fresh name: inside its null on all three assets. The hold's value is the held name's IDENTITY, never a timing signal | That shape |
| Ranking at <= 300 s | 1,764 columns scanned in the prefix frame and the event frame, raw and side-resolved. The only survivor was entry-price arithmetic | These columns, these ages |
| The "location extension" story | `prior_high` and `prior_low` are per-day constants and pick the SAME name within a side 100% of the time (91/91, 97/97, 49/49). Within a side the score IS `side x entry_price`; the level is a fitted cross-side offset | See `T44_TAUTOLOGY_AUDIT_20260823.md` |
| Two-regime split | Every split arm loses to plain EXTREME_ALL on all three assets and both blocks; CHEAP_ONLY is catastrophic | That rule shape |
| Abstention on score magnitude | Cash falls monotonically with the threshold on all three assets | The score's size carries nothing; only its within-cell ORDER does |

**One retraction worth knowing about.** On 2026-08-23 I claimed "the picker is
right in cheap cells and wrong in rich ones" from a hit-versus-miss table. It had
no null. Against 40 within-cell shuffles the null's own gap reaches $431-658, and
all nine real gaps sit inside it. **Retracted.** What survived is narrower: the
count-controlled version shows the payer's percentile position in the picker's
order going 0.309 (cheap) to 0.502 (chance) in rich cells **on HG only**; NKD and
SI do not resolve. The lesson generalises: **every comparison in this program
gets its own null before it is believed.**

---

# 4. What is alive

## The conditioner: cell richness is causally predictable

`diagnostics/regime_split_20260823.json`. A unit-weight composite of activity,
sweep speed, path variation and prior range, read from the FIRST event's own row,
split at the TRAIN median:

| Asset | TRAIN cheap → rich | THRESHOLD cheap → rich |
|---|---|---|
| HG | $662 → $1,209 (1.83x) | $649 → $1,206 (**1.86x**) |
| NKD | $413 → $828 (2.00x) | $360 → $715 (**1.99x**) |
| SI | $568 → $1,079 (1.90x) | $566 → $1,178 (**2.08x**) |

Nine of nine, and the separation WIDENS out of sample. It is the strongest
out-of-sample result this program has produced.

It predicts cell VALUE. It does **not** locate the picker's failures — that is
why the two-regime rule failed, and the reason rescues the conditioner rather
than burying it.

## The forward-vol model, which the entry line has never used

`design/entry_reset/T54_FORWARD_VOL_20260823.md`. Already built and audited:

- `artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json`: 84 slices,
  3 assets x 4 phases (TOKYO, LONDON, NY, SESSION), predicting phase **range in
  dollars** at **20.8-28.4% gain over baseline on all twelve slices**, with
  q10-q90 calibrated coverage and an existing REGIME_HIGH / MID / LOW taxonomy.
- `artifacts/runs/e6_vol_forecasts_v2/vol_service_forecasts.tsv`: 37,427 rows,
  **twelve horizons** (daily plus intraday_30 through intraday_330 in 30-minute
  steps), two arms, walk-forward folds, every row gate-passed.

**Why it was never used:** the 2021 component matrix carries **zero** forecast
columns. Its eight `disc_fvol_*` are realized range and clocks. The forecast
starts 2022-03-09; ticket 19 recorded this as `READY overlap 0`. Every regime
attempt was forced onto realized proxies by a data wall nobody had named.

## The 2022-2024 substrate, built 2026-08-23

`artifacts/cache/corpus_2022_2024/`. Decode HG 936 days / 390.5M records,
NKD 937 / 215.5M, SI 936 / 615.3M, zero file failures. Assemble 931 / 932 / 925
session receipts — **2,788 sessions against 2021's 586.**

2025 is EXCLUDED: the Copper and NKD raw ships as ANNUAL bundles, so the 2025
bundle contains sealed H2 bytes. It was left out of the staged window rather than
filtered afterwards.

**708 days overlap the forward-vol service**, all pre-seal, 2022-03-09 to
2024-12-31. That is the corpus's real justification: it is the only era where the
forward-vol plane and the entry plane can be joined at all.

---

# 5. The frontier

The live unit is in Live cursor. B5 KILL judged. Do not start E1. Side
resolution mill is the open object.

`design/entry_reset/tickets/` and `ENTRY_PLAN_20260823.md` are the 2026-08-23
plan-flow backlog, written when Pstack plan-flow was added. Poteto covering
never replaced them with new tickets. That folder is not a queue. Finding it
is not a reason to execute it. Do not walk 37, 47, 45, 48, 51, or 54.

B0's grid-refusal amendment is closed on Stage 0 PASS. Ticket 47 as a copy
of the 2021 schema is dead spend. The picker does not start from the Stage 1
judge page.

## The protocol that must not be broken

2021's held blocks died of read-peek-amend: eight or more reads across three rule
families, each amendment individually principled and the aggregate fatal. **There
is no third corpus behind 2022-2024.** Everything frozen in writing before the
first outcome is read, **one read per rule**, anything else labelled exploratory
in the same sentence it is reported.

## Standing controls, learned the hard way

- Every comparison gets its own **null** before it is believed.
- Any candidate score is tested against the **entry price** it may be collinear
  with. Eleven of 33 aligned columns provably are.
- A margin under **2 standard errors** of the block's own per-day spread letters
  `not_resolved`, never `clears_rung`.
- Clock columns (`phase_remaining_sec`, `phase_index`, elapsed, ages) correlate
  with everything for capacity reasons. Flag, never promote.
- 2021 can kill a rule. It can never promote one.

---

# 6. Where things live

| What | Where |
|---|---|
| This file | `START_HERE.md` |
| Mill charter (the era's record, newest rulings on top) | `.audit/briefs/mill-side-resolution.md` |
| LIVE ruling and next unit F25 | `.audit/briefs/mill-tranche2-sol-out.md` |
| Sol pages of the era, in order | `.audit/briefs/mill-sweep14-sol-out.md`, `mill-fixhold-sol-out.md`, `mill-pinpoint-sol-out.md`, `mill-structbreak-sol-out.md`, `mill-powerplan-sol-out.md`, `mill-tranche2-sol-out.md` |
| Hypothesis log (1,006 rows, stamped) | `.audit/mill-hypothesis-log.tsv` |
| Mill receipts | `.audit/mill-sweep15.json` ... `mill-sweep29.json`, `mill-levels-build.json`, `mill-levels-zone-build.json`, `mill-zone-history-build.json` |
| Mill code | `tools/mill/` (sweep15-29.py, mill.py, levels.py, levels_zone.py, zone_history.py, build_levels.py) |
| Level caches | `artifacts/cache/mill_levels/` (R2, not git) |
| Discretionary library distillations | `research/discretionary/*.md` (crosswalks, diagram notes with the gap addendum, delta notes) |
| USER directives and failings memory | `/home/algo/.claude/projects/-workspace/memory/` (user-working-style, unslop-exact, fable-failings-2026-08-27) |
| Agent pointer | `AGENTS.md` |
| Session memory | `MEMORY.md`, `tools/memory_ledger.py` |
| Covering map (live) | `.audit/briefs/threshold-covering-after-cfit-kill-out.md` |
| Sol covering peer | `.audit/briefs/threshold-covering-after-cfit-kill-sol-out.md` |
| B0 Stage 0 | `.audit/briefs/threshold-covering-after-cfit-kill-out.md` Stage 0 |
| pstack-lab skills (canonical) | `.cursor/plugins/pstack-lab/skills/` |
| Same skills on every host | `.cursor/skills`, `.claude/skills`, `.codex/skills`, `.agents/skills` (symlinks). Re-run `tools/install_pstack_skills.sh`. |
| Grok poteto-agent | `.grok/agents/poteto-agent.md` |
| Hillclimb playbook | `.cursor/plugins/pstack-lab/skills/poteto-mode/playbooks/hillclimb.md` |
| Fable one-line append | `.codex/follow-rules.md` |
| Sol instructions | `.codex/sol-instructions.md` (vendor plus follow-rules; `python3 tools/build_sol_instructions.py`) |
| Canonical always-on bodies | `.cursor/rules/*.mdc` |
| Grok always-on (loaded) | `.grok/rules/*.md` (same bodies, plus seats.md) |
| Principle catalog | poteto-mode SKILL.md Principles section. Matching leaves only. |
| R2 backup / restore | `tools/r2_backup.sh`, `tools/r2_restore.sh`, keys in `.secrets/rclone-r2.conf` |
| Archived onboarding | `archive/lean-repo-20260825/` (STATE, DIRECTIVES, gates, unlazy) |
| 2026-08-23 plan (not live) | `design/entry_reset/ENTRY_PLAN_20260823.md` |
| 2026-08-23 tickets (not a queue) | `design/entry_reset/tickets/` |
| Verdicts, newest first | `design/entry_reset/T54_FORWARD_VOL_20260823.md`, `T53_REGIME_SPLIT_20260823.md`, `T52_REGIME_20260823.md`, `T50_DIAGNOSIS_20260823.md`, `T44_TAUTOLOGY_AUDIT_20260823.md`, `T41_R6_SPEED_20260823.md`, `T42_CORPUS_GRID_20260823.md`, `T43_RESOLUTION_20260823.md`, `T39_VERDICT_20260823.md`, `T35_VERDICT_20260823.md`, `T29_T34_VERDICT_20260823.md` |
| Receipts | `artifacts/entry_v2/tabular_recovery/diagnostics/` |
| Probe logs | `artifacts/cache/t28_logs/` |
| Hardware truth | `HARDWARE.md` |
| Data inventory | `DATA_INVENTORY.md` |

## If the pod restarted

Reinstall from `HARDWARE.md`, then `bash tools/run_all_checks.sh --fast`. The
matrix, receipts and memory ledger live on `/workspace`. The overlay `/` does not.
