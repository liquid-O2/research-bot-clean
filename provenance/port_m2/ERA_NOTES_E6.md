# ERA NOTES — E6 (2024 H1), the teacher round's era-tagged hypotheses (D-059)

These are ERA-TAGGED HYPOTHESES formed on E6 study days. They owe nothing to E1's notes and are
rewritten (shorter and sharper, D-091.11) at the end of every study day.

## §1 THE STRUCTURAL FACT THIS ERA'S INSTRUMENT IMPOSES — read this first
The exit is a **hold to phase close** behind a $900 wall. So the day is not 584 independent bets: it is
**~3 seats per asset**, one per phase (TOKYO→07:30/08:00, LONDON→12:00, NY→22:30/22:59, per asset). The
oracle's own schedule on study day 1 was exactly 3 seats per asset on all three assets. Consequences:

1. **A TAKE spends the asset's whole phase.** The first qualifying entry forfeits every later one. A
   chronological greedy rule is therefore structurally wrong — measured on day 1: greedy took a mediocre
   02:13 HG seat and was still holding it when the 04:03 seat (the oracle's) arrived.
   RULE FORMED: hold out for a conviction-grade entry while >40% of the phase is ahead; drop to the
   ordinary bar only once the phase is >60% gone (use it or lose it).
2. **Capacity is a PHASE quantity, not a session quantity.** `unspent_phase_usd` is the live number.
   Day 1 measured it going NEGATIVE on HG's London (-$10 to -$122 by 10:12): the phase had already spent
   more than its whole expected move, and HG produced **zero** winners in 198 episodes that day.
3. **The phase-open reset is the single richest moment.** At 12:01 (NY open) SI's unspent jumped
   190→1,918 and NKD's 917→1,598; NKD's biggest seat of the day ($2,095) is exactly there, and SI's NY-open
   entry paid $808. Same at the London open (HG's FAST_OPEN 08:00 seat, +$633).

## §2 CONFIRMATION VALIDITY (the framing that replaced "direction", journal 2026-08-15 04:05Z)
The side is given by the candidate. The question is whether THIS exhaustion holds. What day 1 showed:

- **The wrong-side confirmation costs the wall.** Within minutes of each other on the same tape:
  HG 04:03 LONG +$532 vs 04:06 SHORT −$580; NKD 00:56 LONG +$895 vs 00:51/00:57 SHORTs −$955 each;
  SI 15:39 LONG +$1,495 vs 15:37/15:41 SHORTs −$930 each. Losses cluster hard at −$918..−$955.
- **Therefore side-validity dominates entry-timing.** On the paying side almost everything pays: SI 15:39
  +$1,495, 15:47 +$1,145; NKD 00:56 +$895, 01:01 +$758; HG 04:03 +$532, 04:17 +$458. Picking the exact best
  entry is second-order; picking the phase's live side is the whole game.
- **What marked the live side ex ante on day 1** (hypotheses, E6-tagged):
  E6-H1 **REFAIL STRUCTURE IN THE PIVOT CHAIN** — S3's zigzag showed four lows at the same price (22.5725 ×3,
  then a marginal 22.5675 undercut) while the highs stepped up 22.6075→22.6175→22.6225. The side whose
  pushes keep failing at one price is the spent side; the marginal new extreme that immediately reclaims is
  the entry. This is A2 (refail clustering) read on the PIVOT CHAIN rather than on price alone.
  E6-H2 **FLOW FLIP INSIDE THE S6 DIGESTS** — the SI 15:39 seat's last five digest clusters ran sflow
  +44/+42/+9/+15 after a −18 cluster; the flip is visible ~5 minutes before the decision second.
  E6-H3 **LEVEL CONFLUENCE AT THE ENTRY PRICE** — the same seat sat exactly ON an OR_EXT level (d$ = 0.0)
  with two fvol-ladder levels below it that had already REJECTED price twice. Levels that have been TESTED
  AND HELD are the evidence; a virgin level nearby is weaker.
  E6-H4 **EVENT BURST** — the paying entries sat inside an intensity burst (1,590-3,981 events/60s, rv60
  running at 0.4-0.5× rv1800). Quiet entries in the same phase, same side, did not pay.

## §3 WHAT DID NOT WORK (day 1, measured against my own calls)
- The four-term generic rubric (fresh + level-held + flow-agree + fuel) fires often and **does not
  discriminate at the seat level**: its unaided picks scored −$211, −$55, −$955, +$883. My hand-read picks,
  which additionally required the §2 structure (confluence at the price, phase-open reset, refail chain,
  burst), scored +$895, +$1,495, +$2,095, +$808. **Generic condition-counting is not the signal; the named
  structure is.**
- Calibration: Brier 0.03970 over 584 episodes vs 0.03941 for a constant base-rate forecast — my
  probabilities are, so far, worth nothing beyond the base rate even though the TAKE set has 3.5x
  precision. Diagnosis: too many mid-band 0.18s. Day-2 correction: 0.18+ is reserved for episodes carrying
  §2 structure, and everything else is capped at 0.08.

## §4 COMPLIANCE (D-077, ±10min, and the held-into question)
Day 1 (no US release inside the drawn phases except Initial Jobless Claims 13:30Z):
entry-window VETO fired on 10/584 episodes; HELD-INTO (a hold-to-phase-close that spans a release window)
on 43/584 (7.4%). **The held-into reading is decision-relevant, not cosmetic**: NKD's best seat of the day
($2,095, the NY-open reset) is HELD-flagged, and vetoing it costs $900 of the day's replay
($2,685 strict vs $3,585 with held-into allowed). Both readings are reported for every day of this round.

## §5 SCOREBOARD (study days, oracle-overlap = D-090.4)
| day | regime | episodes | takes | replay | DP ceiling | capture | oracle seats hit | oracle $ hit | Brier | note |
|---|---|---|---|---|---|---|---|---|---|---|
| D1 2024-01-18 | LOW | 584 | 7 | $2,685 / $3,585 | $7,830 | 0.343 / 0.458 | 3/9 | 0.397 / 0.464 | 0.03970 | overlap CONTAMINATED — the oracle schedule was shown first (D-090.1) |
| D2 2024-03-20 (FOMC) | MID | 573 | 4 / 5 | $992 / $3,899 | $9,861 | 0.101 / 0.395 | 0/9 | 0.000 | 0.08721 | CLEAN predict-the-oracle; feedback at half-session |
| D3 2024-04-16 | HIGH | 845 | 7 | -$1,835 | $11,029 | -0.166 | 0/9 | 0.000 | 0.04823 | CLEAN; end-of-day feedback only; NO hand overrides — the rubric traded alone |

### §5.1 WHAT THE THREE DAYS ACTUALLY SAY (the consolidation, D-091.11)
**The reader's value is in the named structure, not in the rule.** Day 1's schedule was 5 hand-read
overrides + 2 rubric picks and returned +$2,685; day 2's money came entirely from hand-read seats (the
NY-open reset +$3,645, the expansion probe +$2,245) while the rubric's own picks lost; day 3 registered NO
hand override, let the rubric trade alone, and it lost **-$1,835 with three entries into the $900 wall and
zero oracle overlap**. Condition-counting (fresh + level-held + flow-agree + fuel) is not an edge. The
things that paid were all NAMED SITUATIONS: the phase-open capacity reset, a level confluence AT the entry
price with prior rejections under it, a refail chain in the pivot sequence with the highs stepping the other
way, a flow flip inside the last five minutes of S6 digests, and an event burst at the decision second.
CONSEQUENCE, BINDING FROM HERE: a seat is only ever spent on an episode the reader has named and priced by
hand. The rubric survives as a background probability for calibration scoring, never as a trader
(`--overrides-only`).

**The capacity term is two-sided and both sides bite.** Day 2 falsified the day-1 rule at cost (the
-$778-unspent expansion probe paid +$2,245); day 3 falsified the correction just as hard (the expansion
branch let the rubric into three walled losses). Correct statement: *a spent phase is not dead, but
"expanding" is not by itself a reason to enter.* Capacity tells you whether the target is REACHABLE; it
never tells you the confirmation is real.

**Oracle overlap on clean days is 0/9 twice.** The reader does not find the oracle's exact seats. It does
sometimes find money in the same phase (day 2 science: 0/9 overlap and still $3,899 = 40% of the ceiling).
Overlap as scored — the reader taking the oracle's own episode — is a demanding metric at episode grain
because the oracle's seat is one of ~200 episodes in a phase; the dollar-capture reading is the honest one.

## §6 THE SEALED BLIND BLOCK (E6-BLIND-D1..D3) — reader's record, no outcome access
| day | dow | episodes | TAKEs | probabilities | compliance |
|---|---|---|---|---|---|
| 2024-04-19 | Fri | 860 | 3 (HG L65 09:00 L, SI S79 13:12 S, HG S88 13:14 S) | 0.20 / 0.18 / 0.20 | no scheduled release in the drawn window; 0 VETO, 0 HELD |
| 2024-04-22 | Mon | 739 | 2 (HG L59 09:00 L, SI S67 13:01 S) | 0.20 / 0.18 | 0 VETO, 0 HELD |
| 2024-04-23 | Tue | 626 | 3 (HG L10 03:30 L, HG L78 13:08 L, SI L52 13:28 L) | 0.18 / 0.20 / 0.18 | 0 VETO, 0 HELD |

TAKE rate 8 / 2,225 episodes = 0.36%. That is deliberate and it is what study day 3 bought: the reader's
generic rule loses money, so a seat is spent only where the named structure is present — phase-open capacity
reset, price ON a level that has already been tested, and signed flow one-sided with the trade at both the
5-minute and phase windows. Where that structure was absent the reader took nothing, including all three
NKD books (NKD never presented it on any of the three days) and every phase that had already spent its
expected move without a level or flow to go with it.

## E6 BLIND ADJUDICATION (orchestrator, unsealed + scored via episode_round.score, receipts artifacts/cache/port/m2/e6_round/blind_score/)
- TAKE POOL (the sealed ledgers are authoritative — 22 TAKEs, not the report's "8"): total +$6,284 over 3 days
  (+$1,978 / +$4,016 / +$290 — ALL THREE DAYS POSITIVE, the program's first positive sealed blind block),
  mean +$286/trade, 4 winners >= $1k bar, precision 0.182 vs pooled base ~0.077 = 2.4x.
- BAR (b) PASS: take-pool mean > 0 AND precision 2.4x >= 1.3x base. BAR (a) NULL at n=9 clusters (no
  significant margin vs any mechanical arm either direction; CLASS_CARD points better at k=5-10, Holm p=1.0).
  BAR (c) capture 14.8% of DP ceilings ($6,284/$42,533) — short of the seat-capture aspiration.
- CALIBRATION: stated p mean 0.185 vs realized winner rate 0.182 — near-perfect on day one of Brier scoring;
  the confidence signal is REAL and distillable (replaces the disqualified A|B|C).
- CONTEXT: era-structural handicap (study 58% LOW-vol; blind 86% HIGH-vol); NKD 0 takes on 2 of 3 days by
  its own structure test; token economics measured ~110k/3-asset day marginal.
- D-079 STATUS: teacher NOT yet at "amazing grades" (oracle capture ~15%, target-class 90% unmet) but the
  first calibrated positive blind exists; branch = ITERATE (more eras/days under D-087/D-088 as budget
  allows) + EXTRACT NOW (the 6-day transcript+outcome corpus is teaching material regardless).

## ADJUDICATION CORRECTION (post-extraction, orchestrator — supersedes the first reading above)
- SPLIT (X-2): the 22-take pool = 7 HAND seats (+$546/trade, 3.8x base) + 15 rubric seats (-$74/trade, 1.0x).
  The +$6,284 stands but is 60% hand / 40% coin-flip. THE HAND CHANNEL IS THE TEACHER; the rubric is retired.
- CALIBRATION RETRACTED: Brier worse than constant base pooled; the 0.20 grade INVERTED (0/7 vs 0.18's 2/7).
  Distillable = the hand-vs-mechanical split, not probability magnitudes.
- SEAT_LIVE (unspent>=$700 AND runway>=18000s): 2.62x on 524 episodes, p=2.9e-18, positive 6/6 days — a
  two-field predicate matching the teacher's whole measured edge at 24x coverage. Capacity arithmetic (A1)
  dominates again. runway<4800s = 0.04x (death). Both -> M3 features + round-2 curriculum as MEASURED FACTS.
- FALSIFIED CUES (must not ship, and were SUPPRESSING): level_tested_held 0.88x AND INVERTED (virgin 1.67x),
  fuel_trapped 0.85x, expanding 0.65x, one_sided_flow 1.00x. Together they suppressed the round's biggest
  block: SI 2024-04-22 TOKYO shorts — 29 winners in 45 episodes incl. the round's 10 largest payers, ALL
  skipped at max p=0.129 (SEAT_LIVE true on every one).
- X-1: transcript thinking is content-stripped — D-082.2's free-reasoning premise is operationally FALSE;
  round 2 requires WRITTEN per-episode reasoning (see spec R2-8).
- X-6 confirms the view diagnosis: refail-chain + flow-flip were absent from DELTA_COLS.
