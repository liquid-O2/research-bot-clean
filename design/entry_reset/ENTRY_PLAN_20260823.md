# Entry V2 — the plan, 2026-08-23

SUPERSEDED. Live work is START_HERE live cursor (covering C). This file is the
2026-08-23 plan-flow backlog. Do not walk it. Tickets 37, 46, 47 stay unstarted.

Written after the ticket-44 audit and with the 2022-2024 substrate on disk. It
names the main issue, which the program has never had written down in one line,
and it is deliberately not another arm over the 1,764 columns at ages <= 300 s.
That search is the null factory and it is closed.

## The main issue, named

**The one identity signal this program has confirmed is stranded on the wrong
side of a label ceiling.**

Three constraints, ranked by the evidence behind them.

**1. Information timing. This is the binding one.**

Ticket 28's hold FOUND the payer. SI $1,916 TRAIN / $1,717 THRESHOLD / $1,559
FORWARD, outside its null on every block. The identity was right. But the hold
identifies the payer 40 to 180 minutes after that name's own entry moment, and
`confirmation.training_offsets_seconds` refuses any expiry but 300 or 600
seconds, so the label grid stops at 600 s and the rule's cash is a proxy nobody
can price (T29: the entry-price drift bound extrapolates to about -$750 against
HG's $1,610).

Both escapes have been tried and both failed. Ticket 34 moved the entry to a
fresh name at arming time — inside its null on all three assets, so the timing
signal does not transfer. Tickets 25, 26 and 36-as-corrected looked for the
identity at age <= 300 s across every column, raw and side-resolved — the only
survivor was entry-price arithmetic (T44).

So the identity exists, it is late, and the ceiling that makes it unpriceable is
a build-time constant.

**2. Resolution.** Standard errors of $169 to $505 on 11 to 21 days per block.
At that resolution 2021 cannot tell a $1,500/day rule from a $1,000 one. A
meaningful share of the "nulls" this program has accumulated were measured at
plus or minus $300-700. The 2,788 assembled 2022-2024 sessions are the fix, and
they are on disk as of today.

**3. Plane exhaustion.** The 1,764 columns at <= 300 s have been scanned in the
prefix frame and the event frame, raw and side-resolved. Nothing survived that
was not the entry price. More rule shapes over these columns at these ages is
the factory. New information means later ages (constraint 1), more years
(constraint 2), or off-matrix ingredients (ticket 37, conditional).

## The decision that this rebuild forces, and it is once per cycle

**The new corpus must carry LATE label ages.**

Ticket 42 set a nine-age grid as "the union of what existing probes read". For
protecting existing probes that was right. For a fresh corpus it is **circular**:
those probes read <= 300 s because the old matrix only HAS <= 300 s. Shipping the
same ceiling enshrines constraint 1 for another whole cycle and leaves ticket 28
a bound rather than a verdict.

The grid is decided at build time. Preregistered from the hold's own measured
entry ages (7,380 s HG and NKD, 10,980 s SI), the corpus grid becomes the nine
plus a coarse late tail:

    0, 30, 60, 90, 120, 180, 240, 290, 300,
    600, 1200, 2400, 3600, 5400, 7200, 10800

Sixteen ages against nine is 1.78x of a 1.1 h row path, comfortably inside the
D-109 cap either way. The real cost is not compute: it is the
`max_delay_sec in (300, 600)` refusal, which is teacher-identity machinery.
Two things make that cheaper now than it will ever be again — the new corpus's
identity is new regardless, and ticket 42 just built the exact pattern to copy
(grid in the receipt, refusal on off-schedule ages, fixtures).

Feasibility is a one-session fact, not a design debate: whether the universe can
emit snapshots past 600 s and whether the atlas prices those decision timestamps
is answered by the pilot, and the pilot runs before the extension is built.

## Phases

**A — build integrity.** Gates on what is already running.
Decode: HG 936 days / 390.5M records, NKD 937 / 215.5M, SI 936 / 615.3M, zero
file failures. Assemble: 931 / 932 / 925 session receipts. **2,788 sessions
against 2021's 586.**
SI's 879 integrity flags are classified, not waved: 782 `FOREIGN_DAY_RECORDS_DROPPED`
are the census law working (SI ships daily multi-instrument files and
`DATA_INVENTORY` records that mixing inflates its ranges about 5x); 93
`MID_OUT_OF_BAND` are a stale sanity band, median mid 17.62-19.99 against a band
of (20, 40), because silver genuinely traded under $20 through much of 2022; 4
`TICK_GCD_MISMATCH` on a small day set shared by all three assets. No integrity
defect. The 93 band days are kept and the band is the thing that is stale.
Verify: `→ verify: bash tools/run_all_checks.sh --fast` plus the decode/assemble
receipt counts above, both as ledger CHECK lines.

**B — one-session pilot through `build_corpus`.** The gate everything blocks on
(running-evals slice law). One 2022 session end to end: candidates, features,
teacher, shard. It must catch the prior-absent first-day branch (R6's
`PriorSessionContext=None` has zero stored oracle bytes, which is also why the
pilot runs the ORACLE path), forecast-context wiring (READY exists from 2022 and
2021 never exercised it), schema drift, and the measured per-session cost that
turns the D-109 arithmetic from an anchor into a receipt.
`→ verify: one shard published, strict-reloadable, with its wall time recorded.`

**C — the extended age grid.** Blocked by B's feasibility answer. Red-first
against the 300/600 refusal, the ticket-42 receipt pattern, then the pilot again
at one session. `→ verify: a shard carrying a 10,800 s row that strict-reloads.`

**D — the corpus build, background.** **R6 adoption is DEFERRED and that is
deliberate.** The oracle path at nine ages is about 2.0-2.2 h wall for
2022-2024 and about 3.5-4 h at sixteen — inside the cap either way. Wiring the
native plane into a 2,000-line production file to save an hour or two of
background compute serialises the science behind harness work and risks the
build on unproven wiring. Run proven code. Adoption returns when it is on the
critical path, which it is not.
`→ verify: shard count equals session count per asset; strict reload on a sample.`

**E — the two preregistered measurements.** One protocol, written before any
2022+ outcome is read.
1. **The hold**, ticket 28's exact rule, frozen, H chosen on new-TRAIN only,
   with EXACT labels at real entry ages. This is the needle question.
2. **The entry-price arm**, frozen exactly as ticket 39 shipped it: does the
   +$400-558 margin over null replicate at about plus or minus $80 resolution.
`→ verify: one receipt per rule per block, with per-day SE and the rung letter.`

**F — conditional.** `pivot_mid2` and G1-tape tagging (ticket 37) only if the
hold dies with honest labels. The ticket-44 collinearity control is standing law
for any scan on the new corpus.

## The fresh-years protocol, and this is where the plan can fail

2021's held blocks died of read-peek-amend: eight or more reads across three rule
families, every amendment individually principled and the aggregate fatal. The
same pattern on 2022-2024 would burn the only promotion tier the program has.

Frozen in writing before the first 2022+ outcome is read: the era boundaries on
the new years, both rules verbatim, knob provenance (H and the side offset from
new-TRAIN only), the nulls, the noise floors, and the rung letters with
RESOLVE_SE. **One read of the new held blocks per frozen rule.** Anything else is
labelled exploratory in the same sentence it is reported.

## Out of scope, permanently or until named

No new arm shapes over the 1,764 columns at <= 300 s on 2021. No CatBoost until a
rule clears THRESHOLD. No exits (D-107). No 2025 until a splitter provably never
emits a day on or after 2025-07-01, with its own fixture — the 2025 annual bundle
contains sealed H2 bytes and was excluded from this build for that reason. No
wholesale re-litigation of scoped 2021 closures: the new corpus re-resolves the
two frozen questions above, not everything.

## What winning looks like, stated plainly

If the hold prices out on exact labels across three fresh years, the program has
a goal-candidate rule carrying the identity signal that already worked. If it
dies, it dies honestly on 2,788 sessions with the plane conclusively closed, and
the pivot to new ingredients is made on evidence instead of exhaustion. Either
outcome ends the ambiguity, which is what moving the needle means here.
