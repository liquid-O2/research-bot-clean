# ERA NOTES — E6 (2024 H1), TEACHER ROUND 2 study block (D-059 era-tagged hypotheses)

These are ERA-TAGGED, and more narrowly than round 1's: every number below is measured on **three
HIGH-vol April-2024 sessions** (2024-04-15 / 04-17 / 04-18, 2,320 episodes), the vol class of the round-2
blind block. They owe round 1's notes nothing except the obligation to RE-TEST them, which is done here
mechanically rather than in prose (`engine/port_m2/library_retest.py`, D-059.2).

## §0 WHAT THE STUDY BLOCK IS FOR THIS ROUND
Round 1 taught on 58% LOW-vol days and was tested on 86% HIGH-vol days, and its cue table did not survive
the crossing. Round 2's study days are drawn from the SAME vol class as the blind block (the draw's own
filter left exactly three eligible days, so there was no choice to make). The question the study block had
to answer was therefore not "what works" but "**does last round's answer still work when the regime is held
fixed?**" It does not, and that is the headline.

## §1 THE LIBRARY RE-TEST (D-059.2), RUN ON ALL THREE DAYS
Winner = D-021 `winner_close` (`cert_close >= $1,000` AND `mae_before_argmax <= $300` — note the THRESHOLD
IS $300 in `panel_score.WINNER_MAE_USD`, not the $500 that `TEACHER_FEATURES_V1.md` §0 prints; defect filed).

| cue (round-1 verdict) | R1 blind | 0415 | 0417 | 0418 | round-2 reading |
|---|--:|--:|--:|--:|---|
| `SEAT_LIVE` PROVEN 6/6 | 2.62x | 1.79x | 1.57x | 0.97x | **decays to ~1.4x mean; positive 2/3** |
| `SEAT_DEAD_TIME` PROVEN 6/6 | 0.045x | 0.00x | 0.87x | 0.70x | **negative 3/3 but nothing like fatal** |
| `capacity_big` PROVEN | 2.23x | 0.59x | 0.99x | 1.19x | **gone** |
| `LEVEL_VIRGIN` PROVEN | 1.67x | 0.13x | 0.90x | 1.48x | **unstable, sign flips** |
| `COV_SWEET_20_60` PROVEN | 2.00x | 0.30x | — | — | **gone** |
| `PHASE_SPENT` PROVEN(neg) | 0.55x | 1.02x | 0.81x | 0.55x | mild negative, holds 2/3 |
| `one_sided_flow` FALSIFIED | 1.00x | 0.75x | 0.91x | 0.46x | **falsification CONFIRMED and strengthened** |
| `flow_agree_5m` NULL | 1.02x | 0.89x | 0.78x | 0.73x | **now negative 3/3** |
| `fuel_trapped` FALSIFIED | 0.85x | 0.76x | — | — | confirmed |
| `fuel_extreme` (mine, >=90%) | — | 0.66x | 0.60x | 0.13x | **born and killed inside study** |
| `expanding` FALSIFIED | 0.65x | 0.73x | 1.31x | 0.53x | confirmed on 2/3 |
| `wide_spread` CONFOUNDED | 1.34x | 1.20x | 2.01x | 1.04x | still an asset dummy (NKD) |

**The ledger's own forecast lost to a constant on all three days** (Brier 0.0719 / 0.0824 / 0.0905 vs
0.0653 / 0.0681 / 0.0737). A probability built out of last round's PROVEN lifts is worse than saying
"7%" to everything. That is the most important negative result of the study block and it is the reason
round 2's blind probabilities are built from structure and floored low, not from cue arithmetic.

**What actually survives three HIGH-vol days:** (a) the *arithmetic* half of capacity — a hold-to-phase-close
trade needs phase left and room left, and `runway_phase < 4,800s` is at or below base on 3/3 days; (b) the
falsifications — every flow-agreement cue is now negative on 3/3; (c) asset identity — NKD >= 1.0x on 3/3
(1.65 / 1.78 / 1.08) while HG is 0.74 / **0.00** / 1.23 (0 winners in 267 episodes on 04-17).

## §2 THE THING THE RAW STREAM SHOWS THAT NO DIGEST DID (R2-1's premise, tested)
Round 1's diagnosis was that its 18% precision was the ceiling OF THE DIGEST. Round 2 opened the true event
stream. Three findings, in the order they happened:

**(1) A digest cannot tell a level that was TRADED THROUGH from one that was WITHDRAWN.** NKD 2024-04-15,
02:35 (long) and 02:36:37 (short), 72 seconds apart: price walked 15 index points UP with **three trades in
it**. The offers were not lifted, they were cancelled — `C A` at the touch, then a higher ask, over and over,
while `A B` records stacked the bid upward. `dBsz_min`/`dAsz_min` (a 60s net size delta) and `refill_frac`
cannot express this; the ordered action codes state it directly. The long paid, the short lost the wall
with $3,088 of adverse excursion.

**(2) So I named the cue `one_side_pull` — and the census killed it.** Over all 926 episodes of 04-15:
`pull_with_side > 0` = **0.96x**, `< 0` = 1.07x, the strong forms 0/7 and 0/54. A mechanism that is vivid in
two hand-read windows is worth nothing until it is counted; this one was worth nothing. Killed before it
could ever seat a blind trade (`engine/port_m2/seq_cues.py`, cue `one_side_pull`, verdict FALSIFIED).

**(3) The predict-then-reveal rep that corrected me.** 2024-04-18 Tokyo offered three opposite-side pairs
with nearly IDENTICAL digest rows (same phase, same unspent/runway/coverage, both levels virgin, flows ~0) —
the exact configuration where round 1 was blind. I read 60s of true tape before the HG short at 02:10,
called TAKE p=0.10 on the SHORT because the ask was stacking (`A A` x5) while the bid was being cancelled
(`C B` x6), and committed it to the journal before the reveal. Result:

| pair | LONG | SHORT |
|---|--:|--:|
| SI 01:20 / 01:23 | **+$1,608** | −$930 |
| NKD 01:46 / 01:50 | **+$2,032** | −$955 |
| HG 02:03 / 02:10 | **+$1,958** | −$918 (my take) |

All three longs paid $1,600–2,000; all three shorts lost the wall. **I read the tape and got the side exactly
backwards.** The post-mortem is the lesson: those `C B` cancels were 1-lot churn INSIDE a bid stack that was
6–12 orders deep and was never traded through, while the ask at 4.34 was **consumed by `T B` three times and
re-posted at the same price each time**. The durable side was the bid; the repeatedly-eaten side was the
offer. Cancels must be read against the order-count stack, never alone — and the thing that carries
information is not who withdraws, it is **who keeps having to come back to the same price and get hit again**
(A2 refail, read at book grain instead of on the pivot chain: this is round 1's own E6-H1 mechanism, finally
computable).

`ask_reload`/`bid_reload` are the corrected form and they are measured, not assumed:
`reload_with_side >= 1` = **1.19x** and `reload_against_side <= -1` = **0.82x** on 04-15 (n=466/418).
That is a real but modest separation from a cue that exists ONLY in the event sequence — and the honest
statement is that it is one day of measurement at ~1.2x, not a proven fact.

## §3 CONFIRMATION VALIDITY, RESTATED FOR THIS VOL CLASS (the journal's framing, judged)
The side is given; the question is whether the exhaustion is genuine. Three HIGH-vol days say:
- **The tape's answer is not "who is pushing" — every flow-agreement cue is negative on 3/3 days.**
  A confirmation that has signed flow behind it is, on these days, slightly WORSE than one that does not.
- **It is "who is being consumed and has to re-post".** A side that keeps rebuilding at one price and keeps
  being taken is spending inventory it will not get back; when it stops rebuilding, price goes.
- **A confirmation formed in dead air is not a confirmation.** `gap_ns` says this directly and no digest
  column does: on the NKD short at 02:36 the "confirmation" sat inside a book whose median inter-event gap
  was 0.5 ms in bursts separated by 1–5 SECONDS of nothing, with 3 trades in 30 seconds.
- **The wall is the risk, and it binds hard on the wrong side.** Every wrong-side pair member above lost
  −$918 to −$955, i.e. the wall, not a small loss. Side error costs a fixed −$930; side correctness pays
  $1,600–3,800. That asymmetry, not precision, is what a seat is spent on.

## §4 WHAT I WILL DO IN THE BLIND BLOCK (written before it opened)
1. **Seats are hand-named only** (R2-9). No rubric, no condition-counting; the round-1 rubric channel is
   retired and the study block re-confirmed why (a ledger-derived probability lost to a constant 3/3).
2. **Feasibility first, as arithmetic, not as a cue.** An episode is only a candidate if the phase can still
   pay: `runway_phase` large enough for a hold-to-phase-close to exist, and room left in the phase's expected
   move. This is the one round-1 fact that survived, and it survives because it is arithmetic.
3. **Every take reads the true event sequence** (R2-1), window sized to the book's own speed — I aim for
   ~250–450 events, which is 15–120s depending on the asset and the hour, and I widen when the story needs
   the earlier minutes. A 2-minute window on SI in a burst is 2,000+ events and unreadable; a 2-minute window
   on NKD at 03:00 is 300 and cheap. The window is a reading decision, not a constant.
4. **What I look for in the sequence**: which side is being consumed and re-posting (`reload`), whether the
   book is participating at all (`gap_ns`, trade count), whether the stack that has to break is thin in
   ORDER COUNT (a ribbon-only field), and whether the last approach was made of trades or of cancels.
5. **Probabilities are floored and honest.** Round 1's whole book sat at 0.18–0.20 and its Brier lost to a
   constant; its 0.20 grade was INVERTED. I price most takes 0.08–0.14 and reserve >0.18 for an episode
   whose sequence I have read and whose feasibility arithmetic is clean.
6. **Asset allocation is a decision, not an accident.** Round 1 spent 9 of 22 seats on the 0.36x asset and 7
   on the 0.07x phase. HG produced 0 winners in 267 episodes on one study day and is the weakest asset on
   2 of 3; NKD is >= 1.0x on 3/3. I will not spend a seat on HG without a sequence read that is unambiguous.

## R2 BLIND ADJUDICATION (orchestrator; scored via episode_round + panel_score, receipts r2_blind_score/)
- TAKES (3, one/day, all ribbon-decided, all protocol-valid): SI 0424 S -$930 | HG 0425 S -$930 | SI 0426 S +$1,157.
  POOL -$703. n=3 — no bar is decidable at this n; the wall variance ($930) dominates.
- SHORTLIST QUALITY (13 eps): 3 paid >=$1k (23% vs ~7% base = 3.3x enrichment) — the SHORTLIST is enriched;
  the final take/skip WITHIN it added nothing measurable this round (takes 1/3 vs skipped 2/10 winners).
  Two skipped winners sat at p=0.06 (NKD +$1,620, SI +$1,945).
- POOLED HAND CHANNEL (rounds 1+2): 10 takes, +$3,119 total, +$312/trade — positive, CI wide, undecided.
- PROTOCOL: PERFECT for the first time (enforcement live, journals written, ribbon-decided, compliance vetoes
  honored incl. the round's largest capacity refused on the release day).
- STUDY FINDING (library re-test, mechanical): round 1's PROVEN cues decay/invert day-to-day WITHIN era+vol
  class (SEAT_LIVE 2.62x -> 1.79/1.57/0.97) — cue lifts are day-regime-dependent at a granularity below eras;
  falsifications replicate better than proofs. Fed to the cue ledger (2 round blocks).
- RULING: EXTEND, don't redesign — the instrument is right, n is not. 5 more sealed blind days, same frozen
  protocol, no new study, target pooled hand n~15; then the two-round+extension verdict.
