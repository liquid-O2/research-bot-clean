# E6 EXTRACTION — teacher round -> distillable evidence (D-082 / D-086 / D-078)

STATUS: complete. Produced by the extraction lane after the E6 round was unsealed and adjudicated
(`provenance/port_m2/ERA_NOTES_E6.md` §"E6 BLIND ADJUDICATION", `design/PORT_TEACHER_ROUND_SPEC.md` §1 EXTRACTION).
Scope = all six round days (3 study + 3 sealed blind), every episode, joined to realized outcomes.

MACHINE-READABLE COMPANIONS (committed beside this file):
* `provenance/port_m2/E6_PAIRING.tsv` — the 168-row D-086 full-spectrum pairing table (one row per paired episode).
* `provenance/port_m2/E6_CUE_CENSUS.tsv` — the name->count census, per block, per cue.
* `provenance/port_m2/E6_EPISODE_OUTCOMES.tsv` — per-episode realized outcomes for all six days (the join key).
* `design/TEACHER_FEATURES_V1.md` — the graded, computable feature list this document justifies.
* `engine/port_m2/e6_extract.py` — the tool that builds all three (`--all`); every number in this document
  is re-derivable from it. Verified: `--outcomes` reproduces the committed outcome file byte-for-byte, and
  the outcome file itself reproduces the sealed `E6_STUDY_D1_OUTCOMES.tsv` on all 584 rows.

---

## 0. HOW THE EVIDENCE WAS RECONSTRUCTED, AND WHAT IS MISSING

### 0.1 Sources actually used
| source | what it supplies | integrity |
|---|---|---|
| `provenance/port_m2/E6_CALLS_20240118.tsv`, `E6_BLIND_D1_20240419.tsv`, `E6_BLIND_20240422.tsv`, `E6_BLIND_20240423.tsv` | the SEALED per-episode call + probability + `why` for 4 of the 6 days | authoritative; committed pre-outcome |
| `engine/port_m2/e6_calls.py` `OVERRIDES` dict | every probability the reader typed BY HAND, with its verbatim one-paragraph reason | committed pre-outcome per day (commits `ec24643`, `31f64f9`, `8d9c75d`, `bacb979`) |
| `engine/port_m2/e6_calls.py` `rubric()` + inline comments | the reader's mechanical decision rule and its own stated rationale for each term | committed pre-outcome |
| `artifacts/cache/port/m2/episode_round/E6/DELTAS_*.txt` | the 52-field decision-second state the reader actually read, per episode | the round's own reading surface |
| `engine/port_m2/panel_score.outcome(rep_cid)` + `c_c_roster.dp_schedule` | `cert_close_usd`, `mae_before_argmax`, `walled`, `winner_close`, DP oracle seats | re-derived; **verified to reproduce the sealed `E6_STUDY_D1_OUTCOMES.tsv` on all 584 rows** and the adjudication's per-day DP ceilings ($14,961 / $15,180 / $12,393) exactly |
| reader transcript `wf_2c6f9019-93b/agent-a2a6ebc3f6c799770.jsonl` | the verbatim tool calls, the sealed-registration heredocs, the day-end consolidations, the exact column sets it scanned | 417 records, streamed |

Reproduction check: re-running `e6_calls.py --day D --dump` at HEAD reproduces the three sealed BLIND ledgers
**byte-for-byte** (861 / 740 / 627 lines). Study day 1 differs on 73 of 584 `why` labels and 38 probabilities
(**0 call flips**), because the rubric's capacity branch was amended between day 1 and day 3 — the sealed
file's `no_room` becomes `no_time` on 35 rows and a scored term-list on 38; the sealed day-1 file is
used as authoritative throughout. Study days 2 and 3 have no committed ledger and are reconstructed at HEAD: day 3
reproduces the contemporaneous record exactly (7 takes, −$1,835), day 2 does **not** (6 takes reconstructed vs
4 contemporaneous, because day 2 was scored under the pre-correction rubric). Day-2 RUBRIC rows are therefore
marked RECONSTRUCTED and carry no evidential weight; day-2 hand OVERRIDES are exact.

### 0.2 DEFECT X-1 (BLOCKING for the literal task, worked around): the reasoning transcript is content-stripped
The task names the reader's "VERBATIM reasoning transcripts" as source 1. **They do not contain reasoning.**
Both workflow transcripts carry `thinking` blocks with an empty `thinking` field and a signature only:

```
{"type": "thinking", "thinking": "", "signature": "CAIS7QIKhwEIEBgCKkBlVCMLJcjt…"}
```

87/87 thinking blocks in `wf_2c6f9019-93b` and 45/45 in `wf_0d7bee32-8e9` are empty. The reader's chain of
thought for the 4,227 episode reads is **not recoverable from disk**. What IS recoverable, and what every
"contemporaneous reason" quoted below is drawn from, is the reader's own *written* record:
1. the hand-typed `why` paragraph per OVERRIDE, committed on the day, before outcomes;
2. the `rubric()` source with its inline justifications, committed before each day;
3. the exact `cut -f…` column sets it scanned per day (transcript IDX 373-405) — i.e. which fields it
   could see when it decided;
4. the end-of-day consolidations it wrote into `ERA_NOTES_E6.md`.
This is sufficient for the census (every call carries a stated reason) but it is **not** the per-episode
deliberation D-082(2) promises. CONSEQUENCE FOR THE NEXT ROUND: if the pairing is to reach the deliberation,
the reader must be required to WRITE its reasoning to a file (it already does this for overrides), because the
harness does not persist thinking. Filed as a round-design defect, not an extraction failure.

### 0.3 DEFECT X-2 (material, affects the adjudication): the sealed ledgers record a policy the reader disowned
On study day 3 the reader established, and committed as binding, that **the rubric never trades**:

> "STUDY-DAY-3 LESSON, applied to every later day: the generic rubric, taking seats on its own, LOST money —
> 7 takes, -$1,835, three of them into the $900 wall, zero oracle overlap… The rubric is a background
> probability, not a trader. A seat is only spent on an episode the reader named."
> — `engine/port_m2/e6_calls.py`, `schedule()`, committed at `31f64f9`

and it reported the blind block as **8 TAKEs**, all hand-named. But the sealed ledgers were dumped with
`--dump` and **without** `--overrides-only` (transcript IDX 391, 407), so their TAKE column is the
rubric+override schedule: **22 TAKEs**. The adjudication scored those 22. The split matters more than the
total:

| pool | n | total | mean/trade | winners | precision | vs base |
|---|--:|--:|--:|--:|--:|--:|
| BLIND, hand OVERRIDE (the reader's declared policy) | 7 | **+$3,846** | **+$549** | 2 | **0.286** | **4.0x** |
| BLIND, RUBRIC (disowned, scored anyway) | 15 | +$2,438 | +$162 | 2 | 0.133 | 1.9x |
| BLIND, all 22 (as adjudicated) | 22 | +$6,284 | +$286 | 4 | 0.182 | 2.5x |
| STUDY, hand OVERRIDE | 5 | +$2,700 | +$540 | 1 | 0.200 | 3.3x |
| STUDY, RUBRIC | 15 | −$4,662 | −$311 | 0 | 0.000 | 0.0x |
| ALL 6 DAYS, hand OVERRIDE | 12 | **+$6,546** | **+$546** | 3 | 0.250 | 3.8x |
| ALL 6 DAYS, RUBRIC | 30 | **−$2,224** | **−$74** | 2 | 0.067 | 1.0x |

Across all six days the hand-named seats make **+$6,546 at +$546/trade** and the mechanical rubric makes
**−$2,224 at −$74/trade, at exactly the base rate**. The reader's own day-3 conclusion is confirmed on
out-of-sample blind days it never saw scored. The +$6,284 headline is real but it is **60% hand / 40% rubric**,
and the rubric half is indistinguishable from picking at random.

---

## 1. THE PAIRING TABLE (D-086 full spectrum)

168 episodes paired. Every row carries: the call, the stated probability, the reader's contemporaneous
written reason, the realized close certificate / MAE / walled flag / D-021 winner flag, and the post-hoc
classification of which named cue(s) were actually present (computed from the same delta fields the reader
read; predicate definitions in §2.1).

| stratum | n | what it is |
|---|--:|---|
| BLIND_TAKE | 22 | every seat the sealed blind ledgers record |
| BLIND_HAND_SKIP | 1 | a hand-named p=0.20 seat the schedule crowded out |
| STUDY_TAKE | 20 | every study seat (7 / 6-reconstructed / 7) |
| STUDY_HAND_SKIP | 15 | every study episode the reader priced by hand but did not seat |
| BLIND_SKIP_CONVICTION | 62 | every blind SKIP carrying conviction-grade p >= 0.18 |
| BLIND_SKIPPED_WINNER | 20 | the 20 largest payers the reader passed on |
| BLIND_SKIP_CUED_CLEAN_LOSER | 15 | FALSE SAMPLE — skips carrying the named structure that lost cleanly |
| BLIND_SKIP_CUED_WALLED_LOSER | 13 | FALSE SAMPLE — skips carrying the named structure that hit the $900 wall |

Legend: `src` OVE = hand-typed override, RUB = rubric. `walled` **W** = the position hit the $900 wall.
`win` **Y** = D-021 winner (`cert_close_usd >= $1,000` AND `mae_before_argmax <= $500` AND not walled).
RUBRIC `why` strings are the rubric's own term labels, not prose — that is all the record the reader left
for those episodes (defect X-1).

#### A. EVERY BLIND TAKE (22)

| episode | sec | call | src | p | cert $ | MAE | walled | win | reader's contemporaneous reason (verbatim) | cues present |
|---|---|---|---|--:|--:|--:|:-:|:-:|---|---|
| `HG-20240419-L-E05` | 02:25 | TAKE | RUB | 0.182 | 538.75 | 668.75 | · | · | fresh+level_held+flow+fuel | `capacity_big`, `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240419-L-E02` | 02:31 | TAKE | RUB | 0.182 | 1495.00 | 25.00 | · | **Y** | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240419-L-E65` | 09:00 | TAKE | OVE | 0.200 | 351.25 | 475.00 | · | · | London/NY phase-open reset at 09:00 — the capacity resets to $970 unspent with 4h of phase, price is 6c off the session VWAP, trades/min z +5.2, and both the 5-minute and phase signed flow (+47/+47) run with the long. This is… | `phase_open_reset`, `level_at_price`, `one_sided_flow`, `fresh_extreme`, `tmz_burst`, `NAMED_TRIAD` |
| `NKD-20240419-S-E79` | 10:04 | TAKE | RUB | 0.182 | -605.00 | 1350.00 | **W** | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240419-S-E87` | 13:09 | TAKE | RUB | 0.182 | -930.00 | 12.50 | **W** | · | fresh+level_held+flow+fuel | `phase_open_reset`, `capacity_big`, `level_at_price`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `NAMED_TRIAD` |
| `SI-20240419-S-E79` | 13:12 | TAKE | OVE | 0.180 | -930.00 | 662.50 | **W** | · | NY-open capacity: $2,487 unspent and ~9h of runway, price 6c from a level, 5-min flow -85 and phase -102 both with the short, and the trapped map is 1,063 above vs 0 below | `phase_open_reset`, `capacity_big`, `level_at_price`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `poc_magnet`, `tmz_burst`, `wide_spread`, `NAMED_TRIAD` |
| `NKD-20240419-S-E106` | 15:14 | TAKE | RUB | 0.182 | 2057.50 | 325.00 | · | · | fresh+level_held+flow+fuel | `capacity_big`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240422-S-E16` | 03:13 | TAKE | RUB | 0.182 | 1163.75 | 362.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240422-L-E14` | 03:50 | TAKE | RUB | 0.182 | -930.00 | 25.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `flow_flip`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-L-E59` | 09:00 | TAKE | OVE | 0.200 | 782.50 | 350.00 | · | · | 09:00 phase-open reset: capacity resets to $836 unspent, price sits ON the level (6c), and the 5-minute flow +149 with the phase +81 both run with the long — the same three-part structure that paid on study days 1 and 2 | `phase_open_reset`, `level_at_price`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `tmz_burst`, `NAMED_TRIAD` |
| `SI-20240422-S-E55` | 10:20 | TAKE | RUB | 0.182 | 157.50 | 575.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `NKD-20240422-S-E59` | 10:43 | TAKE | RUB | 0.182 | -405.00 | 887.50 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240422-S-E67` | 13:01 | TAKE | OVE | 0.180 | 2545.00 | 25.00 | · | **Y** | 13:01 NY-open reset on SI: $2,034 unspent and the full phase ahead, 5-minute flow -98 with the short. Level distance (68c) is the weak leg; capacity + one-sided flow at a phase open is the part that has paid | `phase_open_reset`, `capacity_big`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `poc_magnet`, `tmz_burst` |
| `HG-20240422-L-E90` | 13:54 | TAKE | RUB | 0.182 | -917.50 | 156.25 | **W** | · | fresh+level_held+flow+fuel | `phase_open_reset`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `NKD-20240422-L-E88` | 17:19 | TAKE | RUB | 0.182 | 1620.00 | 112.50 | · | **Y** | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240423-L-E10` | 03:30 | TAKE | OVE | 0.180 | -917.50 | 25.00 | **W** | · | 03:30 Tokyo: price on a level that has already been tested (12c, 1 touch), 5-minute flow +57 and phase +34 with the long, $820 unspent with 5h of phase left | `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `fuel_trapped`, `tmz_burst` |
| `SI-20240423-L-E13` | 03:52 | TAKE | RUB | 0.182 | -205.00 | 950.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `SI-20240423-S-E41` | 09:33 | TAKE | RUB | 0.182 | 7.50 | 162.50 | **W** | · | fresh+level_held+flow+fuel | `phase_open_reset`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `poc_magnet`, `tmz_burst` |
| `HG-20240423-L-E69` | 10:40 | TAKE | RUB | 0.182 | 345.00 | 500.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240423-L-E78` | 13:08 | TAKE | OVE | 0.200 | 145.00 | 787.50 | · | · | 13:08 NY-open reset: $1,357 unspent, price 2c off a level, and the flow is one-sided with the long at both windows (+71 5-min, +117 phase) right at the phase open — capacity, level and flow all pointing the same way | `phase_open_reset`, `capacity_big`, `level_at_price`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `NAMED_TRIAD` |
| `SI-20240423-L-E52` | 13:28 | TAKE | OVE | 0.180 | 1870.00 | 100.00 | · | **Y** | 13:28 NY: price exactly ON a level (0c), $2,080 unspent, phase flow +119 with the long; the 5-minute window is flat (-9), which is why this is 0.18 and not 0.20 | `phase_open_reset`, `capacity_big`, `level_at_price`, `flow_flip`, `wide_spread` |
| `NKD-20240423-S-E72` | 15:58 | TAKE | RUB | 0.182 | -955.00 | 50.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `flow_flip`, `fresh_extreme`, `fuel_trapped` |

#### B. THE HAND-NAMED BLIND SEAT THE SCHEDULE CROWDED OUT (1)

| episode | sec | call | src | p | cert $ | MAE | walled | win | reader's contemporaneous reason (verbatim) | cues present |
|---|---|---|---|--:|--:|--:|:-:|:-:|---|---|
| `HG-20240419-S-E88` | 13:14 | SKIP | OVE | 0.200 | -930.00 | 0.00 | **W** | · | NY phase, 13:14: the day's strongest one-sided flow — 5-min -396 and phase -431 with the short — into 1,320 of trapped volume above vs 39 below, a level 37c away, and $1,282 of unspent phase move to travel into | `phase_open_reset`, `capacity_big`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `tmz_burst`, `NAMED_TRIAD` |

#### C. EVERY STUDY TAKE (20)

| episode | sec | call | src | p | cert $ | MAE | walled | win | reader's contemporaneous reason (verbatim) | cues present |
|---|---|---|---|--:|--:|--:|:-:|:-:|---|---|
| `NKD-20240118-L-E05` | 00:56 | TAKE | OVE | 0.220 | 895.00 | 187.50 | · | · | Tokyo low w/ $1,932 unspent and 6.5h runway; trapped volume 134 above vs 3 below = fuel for a squeeze up; mid $312 below prior-session POC = a magnet with room; vol contracting (rv60 98 vs rv1800 394) so the seller push is spent | `phase_open_reset`, `capacity_big`, `flow_flip`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240118-S-E05` | 02:13 | TAKE | RUB | 0.182 | -211.25 | 218.75 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240118-S-E30` | 08:00 | TAKE | OVE | 0.220 | 632.50 | 31.25 | · | · | London open FAST_OPEN, extreme 39s old, trades/min z 7.1 into a fresh phase with $665 unspent — the phase-open reset is the seat | `phase_open_reset`, `level_at_price`, `fresh_extreme`, `tmz_burst` |
| `SI-20240118-L-E27` | 09:28 | TAKE | RUB | 0.182 | -55.00 | 962.50 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240118-L-E56` | 14:53 | TAKE | RUB | 0.182 | 882.50 | 150.00 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240118-L-E50` | 15:39 | TAKE | OVE | 0.250 | 1495.00 | 125.00 | · | **Y** | the burst seat: OR_EXT at 0.0c, 1,590 events in 60s, rv60 211 vs rv1800 478, 5-min flow +95 with the long, refill 0.72, and the last four lows all at the same price with the highs stepping up (A2 refail on the SHORT side = the… | `level_at_price`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fuel_trapped` |
| `NKD-20240118-S-E93` | 15:52 | TAKE | RUB | 0.182 | -955.00 | 0.00 | **W** | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240320-L-E06` | 03:06 | TAKE | OVE | 0.200 | 32.50 | 962.50 | **W** | · | the Tokyo seat: 5-min flow +199 and phase flow +183 with 2,954 trapped below vs 151 above, 737 events/60s, trades z +5.4, VWAP 2.9 away, $690 unspent | `level_at_price`, `one_sided_flow`, `flow_strong`, `tmz_burst` |
| `SI-20240320-L-E18` | 09:01 | TAKE | OVE | 0.180 | -355.00 | 850.00 | · | · | London-open reset: fresh phase, $820 unspent, 4h runway, prior-day level exactly at price, flow +30/+35 with the long | `phase_open_reset`, `level_at_price`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `NAMED_TRIAD` |
| `HG-20240320-L-E48` | 11:09 | TAKE | RUB | 0.182 | 82.50 | 162.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `SI-20240320-S-E79` | 20:13 | TAKE | RUB | 0.182 | -930.00 | 87.50 | **W** | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `NKD-20240320-S-E54` | 20:16 | TAKE | RUB | 0.129 | -930.00 | 262.50 | **W** | · | fresh+level_held+flow+fuel+wide | `level_at_price`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `wide_spread` |
| `HG-20240320-S-E103` | 20:32 | TAKE | RUB | 0.129 | -711.25 | 18.75 | · | · | level_held+flow+fuel | `level_tested_held`, `flow_flip`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `HG-20240416-L-E10` | 03:22 | TAKE | RUB | 0.182 | -917.50 | 437.50 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240416-L-E21` | 04:38 | TAKE | RUB | 0.182 | -930.00 | 62.50 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `NKD-20240416-L-E34` | 05:31 | TAKE | RUB | 0.129 | 95.00 | 400.00 | · | · | fresh+level_held+flow+fuel+wide | `level_tested_held`, `flow_flip`, `fresh_extreme`, `fuel_trapped`, `wide_spread` |
| `HG-20240416-S-E49` | 09:00 | TAKE | RUB | 0.182 | 363.75 | 400.00 | · | · | fresh+level_held+flow+fuel | `phase_open_reset`, `capacity_big`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `poc_magnet`, `tmz_burst` |
| `SI-20240416-S-E82` | 15:03 | TAKE | RUB | 0.182 | -930.00 | 950.00 | **W** | · | fresh+level_held+flow+fuel | `capacity_big`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240416-L-E111` | 16:37 | TAKE | RUB | 0.182 | 226.25 | 62.50 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `NKD-20240416-S-E120` | 20:14 | TAKE | RUB | 0.182 | 257.50 | 0.00 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst` |

#### D. EVERY STUDY HAND-PRICED CALL NOT SEATED (15)

| episode | sec | call | src | p | cert $ | MAE | walled | win | reader's contemporaneous reason (verbatim) | cues present |
|---|---|---|---|--:|--:|--:|:-:|:-:|---|---|
| `NKD-20240118-L-E06` | 01:01 | SKIP | OVE | 0.180 | 757.50 | 75.00 | · | · | same low, ignition version: 10 members, +300 1-min slope, trades/min z 6.6, rv60 262 — the reclaim actually firing | `phase_open_reset`, `capacity_big`, `level_tested_held`, `fresh_extreme`, `event_burst`, `fuel_trapped`, `tmz_burst`, `wide_spread` |
| `NKD-20240118-L-E08` | 01:16 | SKIP | OVE | 0.120 | -955.00 | 975.00 | **W** | · | fuel map flips (515 below vs 21 above) but unspent already down to $1,257 | `capacity_big`, `level_tested_held`, `one_sided_flow`, `wide_spread` |
| `HG-20240118-L-E13` | 04:03 | SKIP | OVE | 0.150 | 532.50 | 37.50 | · | · | phase H/L level 6c away, extreme 305s old, 60s flow +13 with the long, refill 0.68 = book restocking; $465 unspent on a $1,017 range_hat day is proportionally live | `level_at_price`, `level_tested_held`, `flow_flip`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240118-L-E10` | 04:06 | SKIP | OVE | 0.150 | 620.00 | 687.50 | · | · | OR_EXT confluence 44c away, cross-class RCL, extreme only 486s old, 5-min flow +21 with the long; $781 unspent and 3.9h of phase left | `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240118-L-E34` | 12:01 | SKIP | OVE | 0.180 | 807.50 | 875.00 | · | · | NY open reset: $1,918 unspent, OR_EXT 25c away, 10h runway — the largest capacity of SI's day | `phase_open_reset`, `capacity_big`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `wide_spread`, `NAMED_TRIAD` |
| `NKD-20240118-L-E69` | 12:01 | SKIP | OVE | 0.220 | 2095.00 | 0.00 | · | **Y** | NY open reset on NKD: $1,598 unspent, sitting on an OR_EXT, 11h runway, flow flat rather than against | `phase_open_reset`, `capacity_big`, `fresh_extreme`, `poc_magnet`, `wide_spread` |
| `HG-20240118-L-E57` | 15:03 | SKIP | OVE | 0.150 | 945.00 | 87.50 | · | · | fvol ladder level 1c away, 5-min flow +88, $456 unspent against a $1,017 range_hat | `level_at_price`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fuel_trapped` |
| `SI-20240118-L-E47` | 15:12 | SKIP | OVE | 0.120 | 1220.00 | 400.00 | · | · | OR_EXT at 0, +200 slope5m, flow +127 — momentum but the phase is 60% spent | `level_at_price`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `tmz_burst` |
| `SI-20240118-L-E51` | 15:47 | SKIP | OVE | 0.200 | 1145.00 | 300.00 | · | · | same thesis 8 minutes later, bigger burst (3,981 events/60s, trades/min 187) | `level_at_price`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `tmz_burst` |
| `NKD-20240320-L-E10` | 02:06 | SKIP | OVE | 0.150 | -55.00 | 250.00 | · | · | Tokyo, $1,668 unspent and 6.4h runway, sitting on an fvol band 2.6 away, event count 477/60s with trades z +2.1 — the first real push of the session | `phase_open_reset`, `capacity_big`, `level_at_price`, `level_tested_held`, `poc_magnet`, `wide_spread`, `stale_extreme` |
| `NKD-20240320-L-E12` | 02:27 | SKIP | OVE | 0.160 | -930.00 | 950.00 | **W** | · | same phase, fuel map now 927 below vs 12 above and 1-min slope +100: the squeeze fuel is under price and the phase still has $968 | `level_at_price`, `level_tested_held`, `one_sided_flow`, `poc_magnet`, `wide_spread`, `stale_extreme` |
| `HG-20240320-L-E08` | 03:16 | SKIP | OVE | 0.170 | 20.00 | 975.00 | **W** | · | continuation of the same push, flow +160/+373, trapped-below 3,709 | `phase_open_reset`, `level_at_price`, `one_sided_flow`, `flow_strong`, `NAMED_TRIAD` |
| `HG-20240320-L-E56` | 13:00 | SKIP | OVE | 0.170 | 1301.25 | 125.00 | · | **Y** | NY-open reset on HG: $1,092 unspent, trades z +15.3, 1,025 events/60s (HELD-flagged) | `phase_open_reset`, `capacity_big`, `level_at_price`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `NAMED_TRIAD` |
| `SI-20240320-L-E32` | 13:04 | SKIP | OVE | 0.200 | 3645.00 | 550.00 | · | · | NY-open reset: $1,922 unspent, 9.9h runway, OR_EXT 6.3 away, FAST_OPEN class — the biggest capacity of the day (HELD-flagged: FOMC sits inside the horizon) | `phase_open_reset`, `capacity_big`, `level_at_price`, `level_tested_held`, `fresh_extreme` |
| `SI-20240320-L-E71` | 20:20 | SKIP | OVE | 0.120 | 2245.00 | 650.00 | · | · | DELIBERATE PROBE of the expansion question: the phase has spent 138% of its expected move (unspent -$777) so my capacity rule refuses it, but this is the post-FOMC trend leg with 2,760 events/60s and flow +10/+18 with the long.… | `level_at_price`, `level_tested_held`, `one_sided_flow`, `poc_magnet`, `expanding`, `capacity_spent`, `stale_extreme` |

#### E. EVERY BLIND SKIP AT CONVICTION GRADE p>=0.18 (62)

| episode | sec | call | src | p | cert $ | MAE | walled | win | reader's contemporaneous reason (verbatim) | cues present |
|---|---|---|---|--:|--:|--:|:-:|:-:|---|---|
| `HG-20240423-L-E90` | 15:01 | SKIP | RUB | 0.259 | 601.25 | 331.25 | · | · | fresh+level_held+flow+fuel+burst | `level_at_price`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `event_burst`, `fuel_trapped` |
| `NKD-20240422-L-E89` | 17:27 | SKIP | RUB | 0.182 | 1595.00 | 25.00 | · | **Y** | fresh+level_held+flow+fuel | `level_tested_held`, `flow_flip`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240423-L-E48` | 12:04 | SKIP | RUB | 0.182 | 982.50 | 0.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-S-E18` | 03:19 | SKIP | RUB | 0.182 | 951.25 | 575.00 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst` |
| `HG-20240419-L-E06` | 02:29 | SKIP | RUB | 0.182 | 501.25 | 706.25 | · | · | fresh+level_held+flow+fuel | `capacity_big`, `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240419-L-E38` | 05:29 | SKIP | RUB | 0.182 | 445.00 | 337.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `HG-20240419-S-E84` | 12:17 | SKIP | RUB | 0.182 | 395.00 | 31.25 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `HG-20240419-L-E39` | 05:33 | SKIP | RUB | 0.182 | 382.50 | 400.00 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `SI-20240419-S-E122` | 19:31 | SKIP | RUB | 0.182 | 370.00 | 125.00 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-L-E100` | 15:12 | SKIP | RUB | 0.182 | 351.25 | 187.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `SI-20240419-S-E121` | 19:27 | SKIP | RUB | 0.182 | 345.00 | 150.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-L-E101` | 15:21 | SKIP | RUB | 0.182 | 338.75 | 100.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-L-E124` | 17:30 | SKIP | RUB | 0.182 | 313.75 | 143.75 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240423-L-E89` | 14:28 | SKIP | RUB | 0.182 | 307.50 | 625.00 | · | · | fresh+level_held+flow+fuel | `phase_open_reset`, `capacity_big`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `fuel_trapped`, `NAMED_TRIAD` |
| `HG-20240419-S-E81` | 11:57 | SKIP | RUB | 0.182 | 245.00 | 343.75 | **W** | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `HG-20240423-L-E70` | 10:43 | SKIP | RUB | 0.182 | 245.00 | 600.00 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240419-S-E82` | 12:02 | SKIP | RUB | 0.182 | 238.75 | 350.00 | **W** | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `SI-20240419-S-E123` | 19:37 | SKIP | RUB | 0.182 | 195.00 | 300.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-L-E125` | 17:35 | SKIP | RUB | 0.182 | 195.00 | 262.50 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `SI-20240419-S-E118` | 19:06 | SKIP | RUB | 0.182 | 120.00 | 375.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `SI-20240422-L-E99` | 18:54 | SKIP | RUB | 0.182 | 120.00 | 75.00 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240419-S-E10` | 03:09 | SKIP | RUB | 0.182 | 70.00 | 668.75 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `flow_flip`, `fresh_extreme`, `fuel_trapped`, `tmz_burst` |
| `NKD-20240422-S-E95` | 19:57 | SKIP | RUB | 0.182 | 45.00 | 500.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `NKD-20240419-L-E143` | 21:03 | SKIP | RUB | 0.182 | 32.50 | 237.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-S-E91` | 11:26 | SKIP | RUB | 0.182 | -11.25 | 50.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240423-S-E103` | 15:51 | SKIP | RUB | 0.182 | -11.25 | 206.25 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240423-S-E102` | 15:48 | SKIP | RUB | 0.182 | -23.75 | 218.75 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `NKD-20240419-L-E124` | 18:37 | SKIP | RUB | 0.182 | -42.50 | 137.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `NKD-20240419-L-E151` | 21:56 | SKIP | RUB | 0.182 | -67.50 | 200.00 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `flow_flip`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-S-E93` | 11:35 | SKIP | RUB | 0.182 | -98.75 | 137.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-S-E88` | 11:08 | SKIP | RUB | 0.182 | -123.75 | 162.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240423-L-E43` | 08:00 | SKIP | RUB | 0.182 | -230.00 | 975.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240423-L-E39` | 07:32 | SKIP | RUB | 0.182 | -280.00 | 1025.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `HG-20240423-L-E42` | 07:47 | SKIP | RUB | 0.182 | -292.50 | 1037.50 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240423-L-E41` | 07:43 | SKIP | RUB | 0.182 | -373.75 | 1118.75 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240419-S-E97` | 14:49 | SKIP | RUB | 0.182 | -386.25 | 237.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped` |
| `NKD-20240423-S-E76` | 16:37 | SKIP | RUB | 0.182 | -505.00 | 237.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `NKD-20240423-S-E77` | 16:47 | SKIP | RUB | 0.182 | -505.00 | 237.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `NKD-20240423-S-E83` | 17:49 | SKIP | RUB | 0.182 | -555.00 | 62.50 | · | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240423-L-E24` | 05:02 | SKIP | RUB | 0.182 | -567.50 | 287.50 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `HG-20240422-S-E73` | 09:17 | SKIP | RUB | 0.182 | -617.50 | 656.25 | · | · | fresh+level_held+flow+fuel | `phase_open_reset`, `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `NKD-20240423-S-E78` | 17:03 | SKIP | RUB | 0.182 | -630.00 | 362.50 | · | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst` |
| `HG-20240422-S-E75` | 09:35 | SKIP | RUB | 0.182 | -648.75 | 687.50 | · | · | fresh+level_held+flow+fuel | `phase_open_reset`, `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240422-S-E72` | 09:09 | SKIP | RUB | 0.182 | -673.75 | 712.50 | · | · | fresh+level_held+flow+fuel | `phase_open_reset`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `poc_magnet` |
| `HG-20240422-L-E91` | 13:59 | SKIP | RUB | 0.182 | -917.50 | 218.75 | **W** | · | fresh+level_held+flow+fuel | `phase_open_reset`, `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240422-L-E92` | 14:02 | SKIP | RUB | 0.182 | -917.50 | 87.50 | **W** | · | fresh+level_held+flow+fuel | `phase_open_reset`, `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240423-L-E11` | 03:34 | SKIP | RUB | 0.182 | -917.50 | 12.50 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `tmz_burst` |
| `HG-20240423-L-E13` | 03:41 | SKIP | RUB | 0.182 | -917.50 | 387.50 | **W** | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `tmz_burst` |
| `HG-20240423-L-E23` | 04:54 | SKIP | RUB | 0.182 | -917.50 | 350.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `SI-20240419-S-E07` | 03:15 | SKIP | RUB | 0.182 | -930.00 | 2650.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `SI-20240419-S-E11` | 03:38 | SKIP | RUB | 0.182 | -930.00 | 2025.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `HG-20240419-S-E91` | 13:57 | SKIP | RUB | 0.182 | -930.00 | 56.25 | **W** | · | fresh+level_held+flow+fuel | `phase_open_reset`, `capacity_big`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `fuel_trapped`, `NAMED_TRIAD` |
| `SI-20240419-S-E88` | 14:51 | SKIP | RUB | 0.182 | -930.00 | 75.00 | **W** | · | fresh+level_held+flow+fuel | `capacity_big`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240419-S-E98` | 14:56 | SKIP | RUB | 0.182 | -930.00 | 268.75 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240419-S-E106` | 17:03 | SKIP | RUB | 0.182 | -930.00 | 312.50 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240422-L-E23` | 05:30 | SKIP | RUB | 0.182 | -930.00 | 50.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `SI-20240422-L-E32` | 07:40 | SKIP | RUB | 0.182 | -930.00 | 375.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `expanding`, `capacity_spent` |
| `SI-20240422-L-E66` | 14:14 | SKIP | RUB | 0.182 | -930.00 | 250.00 | **W** | · | fresh+level_held+flow+fuel | `phase_open_reset`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240422-L-E75` | 15:42 | SKIP | RUB | 0.182 | -930.00 | 12.50 | **W** | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `expanding`, `capacity_spent` |
| `SI-20240423-L-E43` | 10:59 | SKIP | RUB | 0.182 | -930.00 | 900.00 | **W** | · | fresh+level_held+flow+fuel | `level_tested_held`, `fresh_extreme`, `fuel_trapped` |
| `NKD-20240419-L-E126` | 18:52 | SKIP | RUB | 0.182 | -955.00 | 87.50 | **W** | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped`, `poc_magnet`, `tmz_burst`, `expanding`, `capacity_spent` |
| `NKD-20240423-S-E73` | 16:10 | SKIP | RUB | 0.182 | -955.00 | 75.00 | **W** | · | fresh+level_held+flow+fuel | `level_at_price`, `level_tested_held`, `fresh_extreme`, `fuel_trapped` |

#### F. THE 20 BIGGEST PAYERS THE READER SKIPPED

| episode | sec | call | src | p | cert $ | MAE | walled | win | reader's contemporaneous reason (verbatim) | cues present |
|---|---|---|---|--:|--:|--:|:-:|:-:|---|---|
| `SI-20240422-S-E01` | 00:01 | SKIP | RUB | 0.129 | 4620.00 | 100.00 | · | **Y** | fresh+flow+burst | `phase_open_reset`, `capacity_big`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `event_burst`, `tmz_burst`, `expanding`, `NAMED_TRIAD` |
| `SI-20240422-S-E02` | 00:12 | SKIP | RUB | 0.091 | 4495.00 | 50.00 | · | **Y** | fresh+flow | `phase_open_reset`, `capacity_big`, `flow_flip`, `fresh_extreme` |
| `SI-20240422-S-E05` | 01:17 | SKIP | RUB | 0.045 | 4307.50 | 150.00 | · | **Y** | flow+wide | `phase_open_reset`, `capacity_big`, `level_at_price`, `one_sided_flow`, `wide_spread`, `NAMED_TRIAD` |
| `SI-20240422-S-E06` | 01:50 | SKIP | RUB | 0.032 | 4257.50 | 112.50 | · | **Y** | stale+flow+wide | `capacity_big`, `one_sided_flow`, `wide_spread`, `stale_extreme` |
| `SI-20240422-S-E07` | 01:53 | SKIP | RUB | 0.022 | 4257.50 | 112.50 | · | **Y** | stale+wide | `capacity_big`, `wide_spread`, `stale_extreme` |
| `SI-20240422-S-E04` | 00:42 | SKIP | RUB | 0.064 | 4245.00 | 237.50 | · | **Y** | flow | `phase_open_reset`, `capacity_big`, `one_sided_flow`, `NAMED_TRIAD` |
| `SI-20240422-S-E08` | 02:03 | SKIP | RUB | 0.064 | 3982.50 | 125.00 | · | **Y** | stale+level_held+flow+burst+wide | `capacity_big`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `event_burst`, `poc_magnet`, `tmz_burst`, `wide_spread`, `stale_extreme` |
| `SI-20240422-S-E09` | 02:08 | SKIP | RUB | 0.064 | 3970.00 | 100.00 | · | **Y** | stale+level_held+flow | `level_tested_held`, `one_sided_flow`, `flow_strong`, `poc_magnet`, `stale_extreme` |
| `SI-20240422-S-E10` | 02:42 | SKIP | RUB | 0.064 | 3870.00 | 100.00 | · | **Y** | stale+level_held+flow | `level_tested_held`, `one_sided_flow`, `stale_extreme` |
| `SI-20240422-S-E11` | 03:06 | SKIP | RUB | 0.010 | 3382.50 | 112.50 | · | **Y** | no_room | `level_at_price`, `level_tested_held`, `one_sided_flow`, `poc_magnet`, `capacity_spent`, `wide_spread`, `stale_extreme` |
| `SI-20240422-S-E12` | 03:13 | SKIP | RUB | 0.010 | 3357.50 | 137.50 | · | **Y** | no_room | `level_tested_held`, `one_sided_flow`, `poc_magnet`, `capacity_spent`, `wide_spread`, `stale_extreme` |
| `SI-20240422-S-E14` | 04:00 | SKIP | RUB | 0.022 | 3232.50 | 112.50 | · | **Y** | stale+wide | `expanding`, `capacity_spent`, `wide_spread`, `stale_extreme` |
| `SI-20240422-S-E13` | 03:46 | SKIP | RUB | 0.045 | 3195.00 | 300.00 | · | **Y** | stale+flow | `one_sided_flow`, `expanding`, `capacity_spent`, `stale_extreme` |
| `SI-20240422-S-E15` | 04:13 | SKIP | RUB | 0.032 | 3157.50 | 175.00 | · | **Y** | stale+flow+wide | `one_sided_flow`, `expanding`, `capacity_spent`, `wide_spread`, `stale_extreme` |
| `SI-20240422-S-E18` | 04:43 | SKIP | RUB | 0.045 | 3132.50 | 187.50 | · | **Y** | stale+level_held+flow+wide | `level_tested_held`, `one_sided_flow`, `expanding`, `capacity_spent`, `wide_spread`, `stale_extreme` |
| `SI-20240422-S-E20` | 04:55 | SKIP | RUB | 0.064 | 3120.00 | 62.50 | · | **Y** | stale+level_held+flow | `level_tested_held`, `one_sided_flow`, `expanding`, `capacity_spent`, `stale_extreme` |
| `SI-20240422-S-E19` | 04:46 | SKIP | RUB | 0.045 | 3107.50 | 212.50 | · | **Y** | stale+level_held+flow+wide | `level_tested_held`, `one_sided_flow`, `flow_strong`, `poc_magnet`, `expanding`, `capacity_spent`, `wide_spread`, `stale_extreme` |
| `SI-20240422-S-E16` | 04:16 | SKIP | RUB | 0.064 | 3095.00 | 237.50 | · | **Y** | stale+level_held+flow | `level_at_price`, `level_tested_held`, `one_sided_flow`, `poc_magnet`, `expanding`, `capacity_spent`, `stale_extreme` |
| `NKD-20240419-S-E01` | 00:24 | SKIP | RUB | 0.064 | 3082.50 | 12.50 | · | **Y** | fresh+flow+wide | `phase_open_reset`, `capacity_big`, `fresh_extreme`, `wide_spread` |
| `NKD-20240419-S-E02` | 00:54 | SKIP | RUB | 0.032 | 2945.00 | 25.00 | · | **Y** | wide | `phase_open_reset`, `capacity_big`, `wide_spread` |

#### G. FALSE SAMPLE — SKIPS CARRYING THE NAMED STRUCTURE, CLEAN LOSSES (15)

| episode | sec | call | src | p | cert $ | MAE | walled | win | reader's contemporaneous reason (verbatim) | cues present |
|---|---|---|---|--:|--:|--:|:-:|:-:|---|---|
| `HG-20240423-S-E92` | 14:14 | SKIP | RUB | 0.091 | -430.00 | 125.00 | · | · | level_held+flow | `phase_open_reset`, `capacity_big`, `level_at_price`, `level_tested_held`, `poc_magnet` |
| `HG-20240423-S-E93` | 14:31 | SKIP | RUB | 0.045 | -386.25 | 12.50 | · | · | level_held+flow_against | `phase_open_reset`, `capacity_big`, `level_tested_held`, `flow_flip`, `poc_magnet` |
| `HG-20240423-S-E90` | 13:53 | SKIP | RUB | 0.064 | -336.25 | 237.50 | · | · | level_held | `phase_open_reset`, `capacity_big`, `level_tested_held`, `flow_flip` |
| `HG-20240423-S-E91` | 14:09 | SKIP | RUB | 0.032 | -248.75 | 62.50 | · | · | flow_against | `phase_open_reset`, `capacity_big`, `flow_flip` |
| `HG-20240423-S-E89` | 13:38 | SKIP | RUB | 0.032 | -242.50 | 143.75 | · | · | flow_against | `phase_open_reset`, `capacity_big` |
| `HG-20240423-S-E86` | 13:15 | SKIP | RUB | 0.032 | -223.75 | 125.00 | · | · | flow_against | `phase_open_reset`, `capacity_big` |
| `HG-20240423-S-E87` | 13:21 | SKIP | RUB | 0.045 | -223.75 | 125.00 | · | · | base | `phase_open_reset`, `capacity_big`, `flow_flip` |
| `HG-20240423-S-E88` | 13:31 | SKIP | RUB | 0.064 | -198.75 | 100.00 | · | · | flow | `phase_open_reset`, `capacity_big`, `level_at_price`, `flow_flip` |
| `SI-20240422-S-E46` | 09:10 | SKIP | RUB | 0.091 | -142.50 | 875.00 | · | · | fresh+flow | `phase_open_reset`, `capacity_big`, `one_sided_flow`, `fresh_extreme`, `poc_magnet`, `NAMED_TRIAD` |
| `HG-20240423-S-E63` | 09:36 | SKIP | RUB | 0.064 | -80.00 | 243.75 | · | · | flow | `phase_open_reset`, `one_sided_flow`, `flow_strong`, `poc_magnet`, `NAMED_TRIAD` |
| `SI-20240422-S-E48` | 09:17 | SKIP | RUB | 0.091 | -42.50 | 775.00 | · | · | fresh+flow | `phase_open_reset`, `capacity_big`, `level_at_price`, `one_sided_flow`, `fresh_extreme`, `poc_magnet`, `NAMED_TRIAD` |
| `SI-20240422-S-E47` | 09:12 | SKIP | RUB | 0.064 | -30.00 | 762.50 | · | · | fresh+flow+wide | `phase_open_reset`, `capacity_big`, `one_sided_flow`, `fresh_extreme`, `poc_magnet`, `wide_spread`, `NAMED_TRIAD` |
| `HG-20240423-S-E64` | 09:39 | SKIP | RUB | 0.091 | -23.75 | 187.50 | · | · | flow+fuel | `phase_open_reset`, `level_at_price`, `one_sided_flow`, `fuel_trapped`, `poc_magnet`, `NAMED_TRIAD` |
| `SI-20240422-S-E51` | 09:42 | SKIP | RUB | 0.091 | -17.50 | 750.00 | · | · | flow+fuel | `phase_open_reset`, `one_sided_flow`, `fuel_trapped`, `tmz_burst`, `NAMED_TRIAD` |
| `HG-20240423-L-E56` | 09:10 | SKIP | RUB | 0.091 | -5.00 | 850.00 | · | · | fresh+flow | `phase_open_reset`, `level_at_price`, `one_sided_flow`, `fresh_extreme`, `NAMED_TRIAD` |

#### H. FALSE SAMPLE — SKIPS CARRYING THE NAMED STRUCTURE, WALLED (13)

| episode | sec | call | src | p | cert $ | MAE | walled | win | reader's contemporaneous reason (verbatim) | cues present |
|---|---|---|---|--:|--:|--:|:-:|:-:|---|---|
| `NKD-20240419-S-E68` | 08:43 | SKIP | RUB | 0.129 | -955.00 | 1937.50 | **W** | · | fresh+level_held+flow+fuel+wide | `phase_open_reset`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `tmz_burst`, `wide_spread`, `NAMED_TRIAD` |
| `NKD-20240419-L-E94` | 13:26 | SKIP | RUB | 0.129 | -955.00 | 150.00 | **W** | · | fresh+level_held+flow | `phase_open_reset`, `capacity_big`, `level_at_price`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `poc_magnet`, `tmz_burst`, `NAMED_TRIAD` |
| `NKD-20240423-S-E63` | 13:22 | SKIP | RUB | 0.129 | -955.00 | 50.00 | **W** | · | fresh+level_held+flow | `phase_open_reset`, `capacity_big`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `NAMED_TRIAD` |
| `HG-20240419-S-E03` | 00:38 | SKIP | RUB | 0.129 | -930.00 | 1275.00 | **W** | · | fresh+level_held+flow | `phase_open_reset`, `capacity_big`, `level_tested_held`, `one_sided_flow`, `flow_strong`, `fresh_extreme`, `poc_magnet`, `tmz_burst`, `NAMED_TRIAD` |
| `SI-20240419-L-E49` | 09:16 | SKIP | RUB | 0.129 | -930.00 | 2200.00 | **W** | · | fresh+level_held+flow | `phase_open_reset`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `poc_magnet`, `NAMED_TRIAD` |
| `SI-20240419-L-E51` | 09:35 | SKIP | RUB | 0.129 | -930.00 | 1875.00 | **W** | · | fresh+flow+fuel | `phase_open_reset`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `poc_magnet`, `NAMED_TRIAD` |
| `SI-20240419-S-E81` | 13:54 | SKIP | RUB | 0.129 | -930.00 | 12.50 | **W** | · | fresh+flow+fuel | `phase_open_reset`, `capacity_big`, `one_sided_flow`, `fresh_extreme`, `fuel_trapped`, `NAMED_TRIAD` |
| `SI-20240419-S-E86` | 14:34 | SKIP | RUB | 0.129 | -930.00 | 450.00 | **W** | · | fresh+level_held+fuel | `phase_open_reset`, `capacity_big`, `level_tested_held`, `flow_flip`, `fresh_extreme`, `fuel_trapped` |
| `SI-20240422-L-E02` | 00:07 | SKIP | RUB | 0.129 | -930.00 | 0.00 | **W** | · | fresh+flow+burst | `phase_open_reset`, `capacity_big`, `fresh_extreme`, `event_burst`, `poc_magnet`, `tmz_burst` |
| `SI-20240423-L-E38` | 09:12 | SKIP | RUB | 0.129 | -930.00 | 1000.00 | **W** | · | fresh+level_held+flow | `phase_open_reset`, `capacity_big`, `level_at_price`, `level_tested_held`, `one_sided_flow`, `fresh_extreme`, `NAMED_TRIAD` |
| `SI-20240423-S-E54` | 13:31 | SKIP | RUB | 0.129 | -930.00 | 0.00 | **W** | · | fresh+flow+fuel | `phase_open_reset`, `capacity_big`, `fresh_extreme`, `fuel_trapped` |
| `HG-20240422-S-E01` | 00:01 | SKIP | RUB | 0.129 | -917.50 | 1487.50 | **W** | · | fresh+flow+burst | `phase_open_reset`, `capacity_big`, `one_sided_flow`, `fresh_extreme`, `event_burst`, `tmz_burst`, `NAMED_TRIAD` |
| `HG-20240422-L-E83` | 13:00 | SKIP | RUB | 0.129 | -917.50 | 50.00 | **W** | · | fresh+level_held+flow | `phase_open_reset`, `capacity_big`, `level_tested_held`, `fresh_extreme` |


### 1.1 WHAT THE PAIRING SAYS, EPISODE BY EPISODE

**(a) The one structure the reader repeatedly named — the 09:00/13:00 phase-open reset — is real but it is
the CAPACITY half that carries it, not the level or the flow.** Its four cleanest instances:

| episode | reader called it | unspent | runway | near_d | f5m/fph | outcome |
|---|---|--:|--:|--:|--:|--:|
| `HG-20240419-L-E65` | "the capacity resets to $970 unspent with 4h of phase… both the 5-minute and phase signed flow (+47/+47) run with the long" | 970 | 14,361 | −6.6 | +47/+47 | +$351, no win |
| `HG-20240422-L-E59` | "capacity resets to $836 unspent, price sits ON the level (6c), and the 5-minute flow +149 with the phase +81" | 836 | 14,360 | −6.3 | +149/+81 | +$783, no win |
| `HG-20240423-L-E78` | "$1,357 unspent, price 2c off a level… capacity, level and flow all pointing the same way" | 1,357 | 35,495 | −1.9 | +71/+117 | +$145, no win |
| `SI-20240423-L-E52` | "price exactly ON a level (0c), $2,080 unspent, phase flow +119… the 5-minute window is flat (−9), **which is why this is 0.18 and not 0.20**" | 2,080 | 34,273 | 0.0 | −9/+119 | **+$1,870, WINNER** |

The three episodes where the reader's full three-part structure was present paid $351 / $783 / $145. The one
that paid $1,870 is the one the reader **downgraded to 0.18 because the flow leg was missing**. The same
inversion runs through the whole hand-priced set (§3.2).

**(b) The largest hand seat and the largest hand loss carry identical named evidence.** `SI-20240419-S-E79`
(p=0.18): "$2,487 unspent and ~9h of runway, price 6c from a level, 5-min flow −85 and phase −102 both with
the short, and the trapped map is 1,063 above vs 0 below" — capacity, level, one-sided flow at both windows,
and fuel, all four present, the most complete named structure in the blind block. It hit the wall: **−$930**.
`SI-20240422-S-E67` (p=0.18) has capacity and one-sided flow but **no level** ("Level distance (68c) is the
weak leg") and paid **+$2,545**. Level-at-price does not discriminate; §2 gives the population numbers.

**(c) The crowded-out seat.** `HG-20240419-S-E88` at 13:14 was hand-priced 0.20 — "the day's strongest
one-sided flow — 5-min −396 and phase −431 with the short — into 1,320 of trapped volume above vs 39 below" —
and never traded, because a RUBRIC take on the same asset five minutes earlier (`HG-20240419-S-E87`, 13:09)
had already spent HG's NY phase. It would have hit the wall: **−$930**. So the mechanism the reader disowned
happened to save $930 here — while `HG-20240419-S-E87` itself, the seat that displaced it, also lost $930.
Both readings of the same 13:09-13:14 window lost the wall. The reader's "strongest one-sided flow of the
day" was on the wrong side of a $900 wall.

**(d) The false sample is decisive.** Of the 98 blind episodes carrying the reader's full NAMED TRIAD, 10
were winners (10.2%) and **88 were not**; 41 of those 88 hit the wall. Of the 288 carrying a phase-open
capacity reset, 34 were winners and 254 were not. The named structure raises the odds; it does not select.

**(e) What it skipped.** 155 blind payers sat in SKIP rows. The 20 largest are in stratum F below; the
biggest is **+$4,215**. The reader's own instrument priced almost all of them in the 0.03-0.09 band — the
band where realized win rates run 8-10%, i.e. ABOVE the 0.129 and 0.182 bands (§3.1). The ordering inside
its probability scale is broken above ~0.10.

---

## 2. CUE CENSUS (the D-056 name->count law applied to the teacher's discretion)

### 2.1 The vocabulary, and how each name was made countable
Every cue below is one of the reader's OWN names, taken from `ERA_NOTES_E6.md` §1-§3/§6, the `rubric()`
source, or a hand-typed `why`. Each is turned into a predicate over the exact `triage_index` fields the
reader read (field names are `engine/port_m2/triage_index.py` FIELDS; the delta view is
`engine/port_m2/e6_round.py DELTA_COLS`). `side = +1` for L, `−1` for S.

| cue (reader's name) | predicate |
|---|---|
| phase open | `(sec − phase_open_sec) / (phase_close_sec − phase_open_sec) <= 0.15`, phase keyed exactly as `e6_calls.schedule()` keys it: `(asset, round((sec + runway_phase)/60))` |
| capacity state: room / big / spent | `unspent_phase_usd >= 400` / `>= 1000` / `< 400` |
| phase-open reset | phase open AND `unspent_phase_usd >= 400` |
| runway ok | `runway_phase >= 2400` |
| level AT price | `abs(near_d) <= 10` |
| level near | `abs(near_d) <= 60` |
| level tested-and-held | level near AND `min_tc_near >= 1` |
| fresh / stale extreme | `extreme_age <= 900` / `> 6000` |
| flow agrees (5-min) | `f5m_sflow * side > 0` |
| one-sided flow | `f5m_sflow * side > 0` AND `fph_sflow * side > 0` |
| one-sided flow, strong | one-sided flow AND `abs(f5m_sflow) >= 50` |
| flow flip | `f60_sflow * side > 0` AND `f5m_sflow * side <= 0` (the 60s window has turned, the 5-min has not) |
| fuel / trapped map | `(side>0 ? trap_ab : trap_bl) / (trap_ab + trap_bl) >= 0.65` |
| event burst | `n_ev_60 >= 400` AND `rv60 > 0.4 * rv1800` |
| trades/min z burst | `tm_z >= 3` |
| wide spread | `spread_dec >= 50` |
| expanding phase | `ladder_pos` in `at_or_above_q5*/q7*/q9*` OR `rv60 > 0.9 * rv1800` |
| POC magnet with room | `d_POC * side > 0` AND `abs(d_POC) >= 200` |
| book refilling | `refill_frac >= 0.60` |
| phase coverage low | `cov_phase <= 40` |
| NAMED TRIAD | phase-open reset AND level near AND one-sided flow (the reader's stated blind rule, `ERA_NOTES_E6.md` §6, verbatim: "phase-open capacity reset, price ON a level that has already been tested, and signed flow one-sided with the trade at both the 5-minute and phase windows") |

REFAIL CHAIN (E6-H1) is **not countable from the round's own reading surface.** The reader named it from the
S3 pivot zigzag ("four lows at the same price… while the highs stepped up"), and the delta view carries no
pivot chain — only `n_pivots` exists in `triage_index` and it was not in `DELTA_COLS`. It therefore appears
in this census with n = 0 observations and is carried to `TEACHER_FEATURES_V1.md` as an UNTESTED HYPOTHESIS
with a build order. Same for the FLOW FLIP as the reader actually described it (a *sequence* of S6 digest
clusters); the proxy above is a two-window sign test, which is a weaker object and is graded as such.

Target event throughout = `panel_score.outcome(rep_cid)['winner_close']` (D-021: `cert_close_usd >= $1,000`
AND `mae_before_argmax <= $500` AND not walled) — the event the round's bar was written on.

### 2.2 The census
"lift" = cue win-rate / block base rate. "take-prec" = the reader's precision among the episodes it seated
that carried the cue. "skipped winners" = the FALSE-sample side: payers carrying the cue that it passed on.

### BLIND (2,225 episodes, base 0.0715)
| cue | reader's name | n | winners | win-rate | lift | takes | take-wins | take-prec | take $ | take losses | skipped winners |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `capacity_big` | capacity state: room >= $1,000 | 401 | 64 | 0.1596 | 2.23x | 7 | 2 | 0.286 | 5,296 | 5 | 62 |
| `event_burst` | event burst | 16 | 2 | 0.1250 | 1.75x | 0 | 0 | . | 0 | 0 | 2 |
| `capacity_room` | capacity state: room >= $400 | 921 | 112 | 0.1216 | 1.70x | 19 | 4 | 0.211 | 8,024 | 15 | 108 |
| `cov_low` | phase coverage <= 40% | 357 | 43 | 0.1204 | 1.69x | 9 | 2 | 0.222 | 6,430 | 7 | 41 |
| `phase_open_reset` | phase-open reset | 288 | 34 | 0.1181 | 1.65x | 9 | 2 | 0.222 | 2,924 | 7 | 32 |
| `NAMED_TRIAD_soft` | named triad, soft (room + level + flow) | 256 | 30 | 0.1172 | 1.64x | 7 | 0 | 0.0 | -1,904 | 7 | 30 |
| `phase_open` | phase open (first 15% of phase) | 299 | 34 | 0.1137 | 1.59x | 9 | 2 | 0.222 | 2,924 | 7 | 32 |
| `NAMED_TRIAD` | NAMED TRIAD (open-reset + level + one-sided flow) | 98 | 10 | 0.1020 | 1.43x | 5 | 0 | 0.0 | -581 | 5 | 10 |
| `wide_spread` | wide spread (>= $50) | 764 | 73 | 0.0955 | 1.34x | 2 | 1 | 0.5 | 940 | 1 | 72 |
| `fresh_extreme` | fresh extreme (<= 900s) | 536 | 46 | 0.0858 | 1.20x | 21 | 3 | 0.143 | 4,414 | 18 | 43 |
| `refill_book` | book refilling (>= 0.60) | 913 | 72 | 0.0789 | 1.10x | 12 | 2 | 0.167 | 734 | 10 | 70 |
| `runway_ok` | runway >= 40min | 2085 | 159 | 0.0763 | 1.07x | 22 | 4 | 0.182 | 6,284 | 18 | 155 |
| `flow_agree_5m` | flow agrees (5-min) | 1209 | 88 | 0.0728 | 1.02x | 19 | 3 | 0.158 | 6,299 | 16 | 85 |
| `one_sided_flow` | one-sided flow (5-min AND phase) | 674 | 48 | 0.0712 | 1.00x | 8 | 1 | 0.125 | 641 | 7 | 47 |
| `level_near` | level near (d$ <= 60) | 1843 | 128 | 0.0695 | 0.97x | 21 | 3 | 0.143 | 3,739 | 18 | 125 |
| `flow_flip` | flow flip (60s with, 5-min not yet) | 322 | 22 | 0.0683 | 0.96x | 3 | 1 | 0.333 | -15 | 2 | 21 |
| `flow_against_5m` | flow against (5-min) | 457 | 30 | 0.0656 | 0.92x | 0 | 0 | . | 0 | 0 | 30 |
| `flow_strong` | one-sided flow, strong (|f5m| >= 50) | 169 | 11 | 0.0651 | 0.91x | 5 | 1 | 0.2 | 1,625 | 4 | 10 |
| `tmz_burst` | trades/min z >= 3 | 467 | 30 | 0.0642 | 0.90x | 8 | 1 | 0.125 | 704 | 7 | 29 |
| `level_tested_held` | level tested-and-held | 1589 | 100 | 0.0629 | 0.88x | 18 | 2 | 0.111 | 1,372 | 16 | 98 |
| `poc_magnet` | POC magnet with room | 788 | 49 | 0.0622 | 0.87x | 3 | 1 | 0.333 | 1,622 | 2 | 48 |
| `fuel_trapped` | fuel / trapped map one-sided | 805 | 49 | 0.0609 | 0.85x | 16 | 2 | 0.125 | 1,520 | 14 | 47 |
| `level_at_price` | level AT price (d$ <= 10) | 636 | 38 | 0.0597 | 0.84x | 9 | 2 | 0.222 | 2,718 | 7 | 36 |
| `stale_extreme` | stale extreme (> 6000s) | 914 | 51 | 0.0558 | 0.78x | 0 | 0 | . | 0 | 0 | 51 |
| `expanding` | expanding phase | 839 | 39 | 0.0465 | 0.65x | 3 | 0 | 0.0 | -1,740 | 3 | 39 |
| `capacity_spent` | capacity state: spent (< $400) | 1304 | 47 | 0.0360 | 0.50x | 3 | 0 | 0.0 | -1,740 | 3 | 47 |

### ALL SIX DAYS (4,227 episodes, base 0.0660)
| cue | reader's name | n | winners | win-rate | lift | takes | take-wins | take-prec | take $ | take losses | skipped winners |
|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| `capacity_big` | capacity state: room >= $1,000 | 740 | 94 | 0.1270 | 1.92x | 10 | 2 | 0.2 | 5,625 | 8 | 92 |
| `NAMED_TRIAD` | NAMED TRIAD (open-reset + level + one-sided flow) | 197 | 23 | 0.1168 | 1.77x | 6 | 0 | 0.0 | -936 | 6 | 23 |
| `event_burst` | event burst | 36 | 4 | 0.1111 | 1.68x | 0 | 0 | . | 0 | 0 | 4 |
| `NAMED_TRIAD_soft` | named triad, soft (room + level + flow) | 637 | 68 | 0.1068 | 1.62x | 12 | 1 | 0.083 | -779 | 11 | 67 |
| `cov_low` | phase coverage <= 40% | 802 | 78 | 0.0973 | 1.47x | 16 | 2 | 0.125 | 6,858 | 14 | 76 |
| `phase_open_reset` | phase-open reset | 578 | 55 | 0.0952 | 1.44x | 13 | 2 | 0.154 | 4,460 | 11 | 53 |
| `phase_open` | phase open (first 15% of phase) | 597 | 55 | 0.0921 | 1.40x | 13 | 2 | 0.154 | 4,460 | 11 | 53 |
| `capacity_room` | capacity state: room >= $400 | 2243 | 204 | 0.0909 | 1.38x | 35 | 5 | 0.143 | 8,550 | 30 | 199 |
| `wide_spread` | wide spread (>= $50) | 1366 | 110 | 0.0805 | 1.22x | 4 | 1 | 0.25 | 105 | 3 | 109 |
| `one_sided_flow` | one-sided flow (5-min AND phase) | 1311 | 101 | 0.0770 | 1.17x | 13 | 2 | 0.154 | 1,766 | 11 | 99 |
| `refill_book` | book refilling (>= 0.60) | 1753 | 132 | 0.0753 | 1.14x | 26 | 3 | 0.115 | -1,630 | 23 | 129 |
| `poc_magnet` | POC magnet with room | 1429 | 101 | 0.0707 | 1.07x | 4 | 1 | 0.25 | 1,986 | 3 | 100 |
| `runway_ok` | runway >= 40min | 3980 | 278 | 0.0698 | 1.06x | 42 | 5 | 0.119 | 4,321 | 37 | 273 |
| `tmz_burst` | trades/min z >= 3 | 846 | 59 | 0.0697 | 1.06x | 15 | 1 | 0.067 | 431 | 14 | 58 |
| `fresh_extreme` | fresh extreme (<= 900s) | 958 | 66 | 0.0689 | 1.04x | 38 | 3 | 0.079 | 1,635 | 35 | 63 |
| `flow_agree_5m` | flow agrees (5-min) | 2316 | 157 | 0.0678 | 1.03x | 35 | 4 | 0.114 | 3,425 | 31 | 153 |
| `flow_strong` | one-sided flow, strong (|f5m| >= 50) | 342 | 23 | 0.0673 | 1.02x | 8 | 2 | 0.25 | 4,035 | 6 | 21 |
| `level_near` | level near (d$ <= 60) | 3650 | 241 | 0.0660 | 1.00x | 40 | 4 | 0.1 | 881 | 36 | 237 |
| `flow_flip` | flow flip (60s with, 5-min not yet) | 614 | 40 | 0.0651 | 0.99x | 6 | 1 | 0.167 | 264 | 5 | 39 |
| `stale_extreme` | stale extreme (> 6000s) | 1785 | 113 | 0.0633 | 0.96x | 0 | 0 | . | 0 | 0 | 113 |
| `flow_against_5m` | flow against (5-min) | 833 | 51 | 0.0612 | 0.93x | 1 | 0 | 0.0 | 632 | 1 | 51 |
| `level_tested_held` | level tested-and-held | 3119 | 188 | 0.0603 | 0.91x | 35 | 3 | 0.086 | -2,150 | 32 | 185 |
| `level_at_price` | level AT price (d$ <= 10) | 1367 | 77 | 0.0563 | 0.85x | 20 | 3 | 0.15 | 2,862 | 17 | 74 |
| `fuel_trapped` | fuel / trapped map one-sided | 1458 | 77 | 0.0528 | 0.80x | 33 | 3 | 0.091 | -752 | 30 | 74 |
| `expanding` | expanding phase | 1066 | 52 | 0.0488 | 0.74x | 7 | 0 | 0.0 | -4,229 | 7 | 52 |
| `capacity_spent` | capacity state: spent (< $400) | 1984 | 75 | 0.0378 | 0.57x | 7 | 0 | 0.0 | -4,229 | 7 | 75 |

### 2.3 Significance and per-day stability
Two-sided binomial vs the block base rate. A cue that is significant only in pooled form and flips sign
across days is a regime artefact, so the per-day table is the grading instrument, not the pooled p.

| cue | BLIND lift | BLIND p | 0118 | 0320 | 0416 | 0419 | 0422 | 0423 | verdict |
|---|--:|--:|--:|--:|--:|--:|--:|--:|---|
| `SEAT_LIVE` (unspent>=700 & runway>=18000) | **2.62x** | 2.9e−18 | 2.16x | 1.95x | 1.90x | 3.02x | 1.56x | 3.86x | **positive on 6/6 days** |
| `runway_phase < 4800` (dead seat) | **0.04x** | 3.9e−09 | 0.00x | 0.00x | 0.62x | 0.00x | 0.10x | 0.00x | **negative on 6/6 days** |
| `capacity_spent` (unspent < $400) | 0.50x | 8.6e−08 | — | — | — | — | — | — | negative, pooled |
| `capacity_big` (unspent >= $1,000) | 2.23x | 2.3e−09 | 0.53x | 1.58x | 2.04x | 2.46x | 1.10x | 3.69x | positive 5/6 (fails 0118) |
| `cov_phase >= 80` (spent phase) | 0.54x | 2.5e−06 | 0.72x | 0.13x | 1.48x | 0.41x | 0.96x | 0.00x | negative 5/6 |
| `phase_open_reset` | 1.65x | 4.0e−03 | 0.90x | 0.96x | 1.69x | 1.78x | 0.97x | 2.77x | positive 3/6 |
| `NAMED_TRIAD` | 1.43x | 0.24 | 1.62x | 2.28x | 2.23x | 1.20x | 1.17x | 1.99x | positive 6/6 but n≈30/day |
| `expanding` | 0.65x | 3.9e−03 | 0.00x | 0.19x | 3.06x | 0.52x | 1.01x | 0.00x | **negative — the day-2 correction is falsified** |
| `one_sided_flow` | 1.00x | 1.00 | 1.95x | 1.16x | 1.29x | 0.51x | 1.30x | 1.14x | NULL |
| `level_tested_held` | 0.88x | 0.21 | 1.21x | 1.05x | 0.66x | 0.79x | 1.01x | 0.79x | **NULL / mildly negative** |
| `fuel_trapped` | 0.85x | 0.27 | 1.03x | 0.55x | 0.77x | 0.59x | 1.12x | 0.73x | **NULL / mildly negative** |
| `fresh_extreme` | 1.20x | 0.21 | 0.39x | 0.69x | 1.14x | 1.05x | 1.21x | 1.44x | NULL |
| `event_burst` | 1.75x | 0.32 | 4.06x | 0.00x | 2.29x | 0.00x | 1.98x | 0.00x | too sparse (n=16 blind, 36 all) |

### 2.4 THE FIVE THINGS THE CENSUS SAYS

**(1) CAPACITY IS THE WHOLE CUE, AND ITS TWO FIELDS ARE `unspent_phase_usd` AND `runway_phase`.**
The banded reading (BLIND):

| `unspent_phase_usd` | n | winners | rate | lift |   | `runway_phase` | n | winners | rate | lift |
|---|--:|--:|--:|--:|---|---|--:|--:|--:|--:|
| < 0 | 836 | 38 | 0.046 | 0.64x |  | < 1,200s | 63 | 0 | 0.000 | 0.00x |
| 0-200 | 215 | 0 | 0.000 | 0.00x |  | 1,200-2,400 | 77 | 0 | 0.000 | 0.00x |
| 200-400 | 253 | 9 | 0.036 | 0.50x |  | 2,400-4,800 | 173 | 1 | 0.006 | 0.08x |
| 400-700 | 221 | 7 | 0.032 | 0.44x |  | 4,800-9,000 | 292 | 12 | 0.041 | 0.58x |
| **700-1,000** | 299 | 41 | **0.137** | **1.92x** |  | 9,000-18,000 | 689 | 36 | 0.052 | 0.73x |
| **1,000-1,500** | 250 | 35 | **0.140** | **1.96x** |  | **18,000-30,000** | 751 | 86 | **0.115** | **1.60x** |
| **>= 1,500** | 139 | 29 | **0.209** | **2.92x** |  | **>= 30,000** | 180 | 24 | **0.133** | **1.87x** |

The reader put its capacity threshold at **$400**; the break is at **$700**, and $400-700 is the single
worst band on the whole day (0.44x, worse than a spent phase). Its time term was `runway_phase >= 2400s`;
the real cliff is at **4,800s** (1 winner in 313 blind episodes below it) and the payoff band starts at
**18,000s**. Both thresholds were mis-set, and the misses are in the same direction: the reader let in far
too much.

**(2) THE LEVEL CUE IS INVERTED.** The reader's E6-H3 said "Levels that have been TESTED AND HELD are the
evidence; a virgin level nearby is weaker." Measured on the blind block:

| | n | winners | rate | lift |
|---|--:|--:|--:|--:|
| `min_tc_near == 0` (virgin level) | 234 | 28 | 0.1197 | **1.67x** |
| `min_tc_near >= 1` (tested and held) | 1,811 | 116 | 0.0641 | 0.90x |

This is not academic: the rubric's `level_held` term requires `min_tc_near >= 1`, so the hypothesis was
wired into the probability of every one of the 4,227 episodes, in the wrong direction.

**(3) THE SINGLE LARGEST MISS OF THE ROUND WAS CAUSED BY TWO FALSIFIED CUES ACTING TOGETHER.**
SI, 2024-04-22, TOKYO, short side: **45 episodes, 29 of them D-021 winners (64%)**, payers up to **$4,620**.
The reader's highest probability anywhere in that block was **0.129**, and it took nothing. The **ten biggest payers of the entire blind round are all in this block** — `SI-20240422-S-E01…E10`,
+$4,620 down to +$3,870, nine of the ten D-021 winners, every one of them a SKIP. Their `why` strings say why they were priced down:

```
SI-20240422-S-E01  p=0.129  fresh+flow+burst        (no level_held: min_tc_near = 0, virgin level)
SI-20240422-S-E03  p=0.045  flow+wide               (spread_dec = 50 -> the "wide" penalty)
SI-20240422-S-E06  p=0.032  stale+flow+wide         (extreme_age 6,624s -> "stale" penalty)
SI-20240422-S-E07  p=0.022  stale+wide
```
All seven had `unspent_phase_usd` $1,033-$1,671 and `runway_phase` 25,600-32,300s — i.e. **`SEAT_LIVE` was
true on every one of them** (and on 10 episodes of that block, 9 of which were winners). The two cues that
suppressed them, `level_held` and `wide`, are the two the census scores at 0.90x and (inverted) 1.34x.

**(4) THE "WIDE SPREAD" PENALTY IS BACKWARDS, BUT FOR A REASON THAT IS NOT A CUE.** `spread_dec >= 50`
scores 1.34x on the blind block and the tightest band, `spread_dec` 5-15, scores **0.31x**. That is not a
spread effect — it is an asset effect: HG (the tight book) produced **22 winners in 857 blind episodes
(0.36x)** while SI produced 75 in 648 (1.62x). Any feature built on `spread_dec` would be laundering an
asset dummy. Recorded as a CONFOUND, proposed as an explicit asset/dollar-per-tick normaliser instead.

**(5) THE READER'S ALLOCATION WAS THE OPPOSITE OF THE PAYMENT MAP.** Blind block, per stratum:

| stratum | n | winner rate | lift | reader's takes | reader's $ |
|---|--:|--:|--:|--:|--:|
| HG | 857 | 0.026 | 0.36x | **9** | +$561 |
| NKD | 720 | 0.086 | 1.21x | 5 | +$1,712 |
| SI | 648 | 0.116 | 1.62x | 8 | +$4,010 |
| TOKYO | 953 | 0.097 | 1.35x | 6 | +$1,145 |
| NY | 897 | 0.073 | 1.01x | 9 | +$4,505 |
| LONDON | 375 | 0.005 | **0.07x** | 7 | +$634 |
| side S | 1,141 | 0.090 | 1.26x | 10 | — |
| side L | 1,084 | 0.052 | 0.72x | 12 | — |

It spent 9 of 22 seats on the asset with a 0.36x winner rate and 7 of 22 on the phase with a **0.07x** rate
(2 winners in 375 episodes). Four of the seven hand-named blind seats were HG; none of the four won. All four
blind winners were SI or NKD. Asset and phase are free, exactly-known conditioning variables and the
teacher was not using them.

---

## 3. CALIBRATION NOTE

### 3.1 The adjudication's calibration claim does not survive disaggregation
The adjudication recorded: *"stated p mean 0.185 vs realized winner rate 0.182 — near-perfect… the
confidence signal is REAL and distillable."* That is an average of 22 numbers, and it is an artefact of
averaging two miscalibrated halves. Every finer cut says the opposite.

**Whole-population Brier (every episode carries a probability, D-082):**

| block | n | base rate | reader Brier | constant-base Brier | verdict |
|---|--:|--:|--:|--:|---|
| STUDY | 2,002 | 0.0599 | 0.05715 | 0.05635 | WORSE than a constant |
| BLIND | 2,225 | 0.0715 | 0.06719 | 0.06635 | WORSE than a constant |
| BOTH | 4,227 | 0.0660 | 0.06244 | 0.06165 | WORSE than a constant |

**By stated-probability bucket (BLIND, the sealed block):**

| stated p | source | n | winners | realized | realized/stated | mean cert $ | walled % |
|--:|---|--:|--:|--:|--:|--:|--:|
| 0.010 | RUBRIC | 580 | 9 | 0.0155 | 1.55 | -79 | 43% |
| 0.016 | RUBRIC | 5 | 0 | 0.0000 | 0.00 | -135 | 40% |
| 0.022 | RUBRIC | 45 | 4 | 0.0889 | 4.04 | +320 | 38% |
| 0.032 | RUBRIC | 204 | 21 | 0.1029 | 3.22 | +50 | 49% |
| 0.045 | RUBRIC | 353 | 29 | 0.0822 | 1.83 | +75 | 46% |
| 0.064 | RUBRIC | 494 | 52 | 0.1053 | 1.64 | +75 | 46% |
| 0.091 | RUBRIC | 314 | 32 | 0.1019 | 1.12 | +23 | 46% |
| 0.129 | RUBRIC | 145 | 7 | 0.0483 | 0.37 | -239 | 59% |
| 0.180 | OVERRIDE | 4 | 2 | 0.5000 | 2.78 | +642 | 50% |
| 0.182 | RUBRIC | 76 | 3 | 0.0395 | 0.22 | -160 | 45% |
| 0.200 | OVERRIDE | 4 | 0 | 0.0000 | 0.00 | +87 | 25% |
| 0.259 | RUBRIC | 1 | 0 | 0.0000 | 0.00 | +601 | 0% |

**The 0.18 vs 0.20 distinction — every hand-priced call across all six days:**

| stated p | n calls | seated | winners | win-rate | mean cert $ |
|--:|--:|--:|--:|--:|--:|
| 0.120 | 3 | 0 | 0 | 0.000 | +837 |
| 0.150 | 4 | 0 | 0 | 0.000 | +511 |
| 0.160 | 1 | 0 | 0 | 0.000 | -930 |
| 0.170 | 2 | 0 | 1 | 0.500 | +661 |
| 0.180 | 7 | 5 | 2 | 0.286 | +540 |
| 0.200 | 7 | 4 | 0 | 0.000 | +739 |
| 0.220 | 3 | 2 | 1 | 0.333 | +1,208 |
| 0.250 | 1 | 1 | 1 | 1.000 | +1,495 |

**Take-pool aggregate (the adjudication's calibration claim):**

| block | pool | n | mean stated p | realized | Brier |
|---|---|--:|--:|--:|--:|
| BLIND | all takes | 22 | 0.1841 | 0.1818 | 0.14993 |
| BLIND | hand OVERRIDE | 7 | 0.1886 | 0.2857 | 0.21851 |
| BLIND | RUBRIC | 15 | 0.1820 | 0.1333 | 0.11792 |
| STUDY | all takes | 20 | 0.1820 | 0.0500 | 0.05896 |
| STUDY | hand OVERRIDE | 5 | 0.2140 | 0.2000 | 0.14634 |
| STUDY | RUBRIC | 15 | 0.1714 | 0.0000 | 0.02983 |

### 3.2 The 0.18 vs 0.20 distinction is INVERTED
Within the blind block the reader made exactly one confidence distinction among its hand-priced seats:
0.18 vs 0.20, and it explained the difference in its own words on `SI-20240423-L-E52`:

> "price exactly ON a level (0c), $2,080 unspent, phase flow +119 with the long; the 5-minute window is flat
> (−9), **which is why this is 0.18 and not 0.20**"

That episode paid **+$1,870 and is one of only four blind winners**. Aggregated over the sealed block:

| stated p | n hand-priced | winners | realized | mean cert $ |
|--:|--:|--:|--:|--:|
| 0.18 (the "one leg missing" grade) | 4 | 2 | **0.500** | +$642 |
| 0.20 (the "all three legs" grade) | 4 | 0 | **0.000** | +$87 |

Over all six days and all 28 hand-priced calls the same ordering holds: p=0.18 → 2 winners in 7 calls
(0.286); p=0.20 → **0 winners in 7 calls**; p=0.25 → 1 in 1; p=0.22 → 1 in 3. The reader's confidence is
**anti-monotone across its top two grades**, and the mechanism is identifiable from §2: the 0.20 grade was
reserved for episodes where the *flow* leg was also present, and flow is the cue the census scores at 1.00x.
Adding a null cue to a real one and calling it more confidence is exactly what produced the inversion.

### 3.3 The one thing the probability scale gets right is its floor
The bottom bucket is a genuine, large, and stable discovery:

| p bucket | n (blind) | winners | realized | vs base | what it is |
|--:|--:|--:|--:|--:|---|
| 0.010 | 580 | 9 | 0.0155 | **0.22x** | the rubric's `no_time` / `no_room` refusal |
| 0.022-0.091 | 1,410 | 138 | 0.0979 | 1.37x | "background" — the band the money is actually in |
| 0.129 | 145 | 7 | 0.0483 | 0.68x | — |
| 0.182 | 76 | 3 | 0.0395 | **0.55x** | the four-term rubric's "conviction" band |
| 0.18-0.20 (hand-priced) | 8 | 2 | 0.2500 | 3.50x | the 7 hand seats + the crowded-out one |

Read down that column: the reader's probability is **monotone decreasing in the wrong direction over its own
top three mechanical bands**. Its `no_time`/`no_room` refusal is worth 0.22x and its `fresh+level_held+flow+fuel`
conviction is worth 0.55x, both below base, while the undifferentiated 0.022-0.091 middle carries 1.37x and
138 of the block's 159 winners. This is the same finding as §2.4(1)-(2) seen through the probability: what
the rubric *rejects* is informative, what it *selects* is anti-informative.

### 3.4 Study vs blind
Whole-population Brier is worse than a constant base-rate forecast on **both** blocks and on the pool
(0.06244 vs 0.06165 over 4,227 episodes) — the reader's own day-1 diagnosis ("my probabilities are, so far,
worth nothing beyond the base rate") held on the blind days too, and its day-1 correction ("0.18+ is reserved
for episodes carrying §2 structure, and everything else is capped at 0.08") did not fix it, because the §2
structure it gated on is the part that does not discriminate. The *discrimination* claim survives only in
the hand-named pool: 12 hand seats over six days, 0.250 precision vs a 0.066 pooled base (3.8x), +$546/trade.
That is the distillable signal. The probability *magnitudes* are not distillable and should not be carried
into M3 as a feature; the hand/mechanical *distinction* should.

---

## 4. WHAT THIS ROUND HANDS TO M3

1. **A two-field screen that reproduces the teacher's entire measured edge at 24x its coverage.**
   `SEAT_LIVE = unspent_phase_usd >= 700 AND runway_phase >= 18000` covers 524 of 2,225 blind episodes
   (23.6%) at a 0.1870 winner rate = **2.62x base, p = 2.9e−18**, positive on all six days
   (1.56x-3.86x). The teacher's whole 22-seat pool scored 2.54x on n=22. One computable predicate, built
   from two fields the sheet already prints, matches the teacher's discretion and can be evaluated on every
   episode of every era.
2. **A hard negative screen.** `runway_phase < 4800` = 1 winner in 313 blind episodes (0.04x), ≤0.62x on
   every day. Combined with `cov_phase >= 80` (0.54x) this removes roughly half the day at almost no cost.
3. **Three named cues that must NOT become features**: `level_tested_held` (0.90x, and inverted vs virgin
   levels at 1.67x), `fuel_trapped` (0.85x), `expanding` (0.65x — the day-2 correction, falsified).
   `one_sided_flow` is a clean NULL (1.00x). These are the round's most valuable negative results because
   all four were wired into the reader's probability for 4,227 episodes.
4. **A confounded cue to normalise, not adopt**: `spread_dec` is an asset proxy (HG 0.36x / SI 1.62x).
5. **The conditioning variables the teacher ignored**: asset, phase and side are known ex ante and carry
   0.36x-1.62x, 0.07x-1.35x and 0.72x-1.26x spreads on the blind block.
6. **A costed instruction for the next round**: the reader's per-episode deliberation is not persisted by
   the harness (defect X-1); if the pairing is to reach it, writing it must be part of the task.

Feature definitions, field citations and grades: `design/TEACHER_FEATURES_V1.md`.

---

## 5. DEFECTS FOUND BY THE EXTRACTION

| # | defect | severity | evidence |
|---|---|---|---|
| X-1 | The reader's reasoning transcript is content-stripped: 87/87 `thinking` blocks in `wf_2c6f9019-93b` and 45/45 in `wf_0d7bee32-8e9` carry `"thinking": ""` plus a signature. D-082(2)'s "the reader's complete reasoning is already in its transcript" is **false as an operational assumption**. | HIGH — changes round design | §0.2 |
| X-2 | The sealed blind ledgers encode 22 TAKEs under a policy (`--dump` without `--overrides-only`) the reader had already committed against; the adjudication scored that pool. Hand seats +$546/trade at 3.8x base; rubric seats −$74/trade at 1.0x base. | HIGH — changes the reading of the headline | §0.3 |
| X-3 | `E6_STUDY_D1_OUTCOMES.tsv` rounds certificates to integers, and the sealed D1 ledger differs from HEAD on 73/584 `why` labels and 38 probabilities (0 call flips) because the rubric was amended mid-round without versioning the ledger it had already produced. | LOW | §0.1 |
| X-4 | Study days 2 and 3 have **no committed call ledger** — only `ERA_NOTES` prose. Day 3 reconstructs exactly; day 2 does not (6 takes at HEAD vs 4 contemporaneous). A round whose scoring artefacts are not all committed cannot be fully re-adjudicated. | MEDIUM | §0.1 |
| X-5 | `e6_calls.schedule()`'s one-position-per-asset rule let a RUBRIC seat crowd out a hand-named seat 5 minutes later (`HG-20240419-S-E87` displaced `HG-20240419-S-E88`). Under the reader's declared `--overrides-only` policy this cannot happen; under the ledger's actual policy it did. | MEDIUM | §1.1(c) |
| X-7 | LANE COLLISION, recorded for provenance: this extraction's six artifacts were staged by the extraction lane and then swept into a **different lane's commit** (`46301ba` "D-093: perfection gate…") by a concurrent `git add -A`, and pushed under that message. Content verified identical at HEAD. D-082/D-086's explicit-pathspec rule protects the *committing* lane; it does not protect a lane's *staged index* from another lane's blanket add. Concurrent lanes must stage-and-commit atomically. | LOW (provenance only) | this commit |
| X-6 | The reader's `E6-H1` (refail chain in the pivot sequence) and its true `E6-H2` (flow flip as a *sequence* of S6 digests) are **not computable from `DELTA_COLS`** — the round's own reading surface did not carry the fields the reader claimed to be reading. It named them from full sheets read on study day 1 and then decided 4,227 episodes without them. | MEDIUM | §2.1 |
