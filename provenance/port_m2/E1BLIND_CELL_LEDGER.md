
## BLIND DAY 1 — 20211020 (sealed before any unblinding; policy RV1)

**BLIND DAY 1 — 2021-10-20, 948 candidates (SI 334, HG 456, NKD 158), 44 creation-class rows, 9 cells.** Policy RV1. The stepper (47 as-of cuts, 1,800s) drove every cell panel; no day-complete table was scanned to pick a read. Ten TAKEs, two seats, both at the 13:00 NY open and both LONG. **THE DAY'S ONE PIECE OF NEW EX-ANTE KNOWLEDGE, and it is a warning about my own declaration:** the S13 CLASS CENSUS CARD, printed on every sheet, gives OPEN-DYNAMICS at ERA scale as HG 946 cand / win_frac 0.0772 / mean_cert **-$21.29** and SI 1,283 / 0.0826 / **-$1.91** — against the +$152.57 mean certificate and 11.96% win rate my study round measured for that class on 209 rows of eight sessions. The class edge over the REVERSAL bulk survives in the win rate (7.7-8.3% vs a ~5.9% base) but the study block's mean-certificate number was small-sample. I am NOT changing the policy on it: the alternative is the 91% reversal bulk at 5.36% and a negative card of its own, and a policy retuned on day 1 of a blind block is exactly what CC-M2-4.3 forbids. It is logged here, in the ledger's `novel` column on both seats, and in BLIND_NOTES.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 95 | 0 | 0 | 0 | - | SHORT | MED | no | CLOSED/OPEN | S2 day_type_so_far AT_RANGE with range_so_far $2,494 = 93.3% of range_hat at the LONDON open; S8 f30m -76 on 233 and fph -43 on 117; mid 4.634 against a TOKYO first_sane_mid of 4.6868 (net -$1,150 on the session). The capacity half of that sentence is READ AND NOT TRADED (P017 inverts when the range expands). |
| HG/NY | 215 | 19 | 1 | 6 | HG-20211020-046895-L | LONG | MED | no | OPEN/CLOSED | S8 through_book_600s 7 of 8 prints clearing the ASK, 60s sflow +25 on 46, 5m +59 on 164, fuel map 66 below / 18 above — buyers lifting at the NY open. AGAINST IT: the session is -$1,056 and 93.3% of range_hat is spent, so this long fights both the day's direction and its arithmetic. |
| HG/TOKYO | 146 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/OPEN | S8 fuel 688 above / 2 below on 690 and the phase L printed 3 seconds before the cell's first row; fph_sflow 0. WOULD-ABSTAIN: HG/TOKYO study seat base rate 0.14 (P035) — recorded, not traded. |
| NKD/LONDON | 28 | 1 | 0 | 0 | - | NONE | - | no | CLOSED/CLOSED | S8 phase_total = 0 contracts at the cell open and thru_n = 0: there is literally nothing to read. NKD/LONDON is also the lowest-base-rate cell in CC-M2-18.1's era census (0.123). |
| NKD/NY | 40 | 1 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | S8 phase 23 contracts, thru_n 0, f5m 1 on 5. No readable tape. |
| NKD/TOKYO | 90 | 0 | 0 | 0 | - | SHORT | LOW | no | CLOSED/OPEN | S8 fuel map 11 above / 0 below on a phase_total of 11 and fph_sflow -1 — there is no tape here yet (rv1800 93.5, vol_regime MID, q50 $1,893 unspent). A side read on 11 contracts is a coin flip and is recorded as one. |
| SI/LONDON | 44 | 0 | 0 | 0 | - | LONG | LOW | no | CLOSED/OPEN | S8 f30m +51 on 516 into the LONDON open against fph -40 on 338 — the horizon disagreement P022 names (concentrator 1.78x, compass FALSIFIED); mid 23.84 is the session high with the day INSIDE at 48.3% of range_hat. Read as LONG at LOW confidence precisely because the object that produced it has no direction value. |
| SI/NY | 242 | 23 | 0 | 4 | SI-20211020-046908-L | LONG | MED | no | CLOSED/CLOSED | S3 sess_ret +$1,625 into the NY open, S5 trades/min z=6.88 and mid_slope +$137.5/min with accel +137.5, S7 L1 11x11 with c2f 3.65 — a one-way up-tape arriving at the NY open. AGAINST IT: coverage 80.6% of the session's expected move is already spent and S8's 5m stream is -44 on 274. SI/NY is the highest-base-rate cell in the study round (0.86). |
| SI/TOKYO | 48 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/CLOSED | S8 fuel 157 above / 4 below (97% of the phase's volume sits ABOVE the mid) with f5m -14 on 57; mid 23.69 sits on the phase L (916s old). WOULD-ABSTAIN: SI/TOKYO is 0-for-7 winner-bearing cells in the study round (P035, the lowest seat base rate on the board) — recorded, NOT traded. |

**AS-OF DISCIPLINE:** `triage_index.py --drive-step 1800 --drive-out E1BLIND_D1_DRIVE` produced 47 stamped prefixes; every cell panel above was computed from the last cut at or before that cell's first candidate row (`e1blind_cellbrief.py`). No S14 appendix exists for this reader.

**THE TWO SEATS ARE ONE OBJECT:** HG-20211020-046895-L (13:01:35) and SI-20211020-046908-L (13:01:48) are both G1_FAST_OPEN / OPEN-DYNAMICS longs at the NY open, 13 seconds apart, in two metals that S11 shows moving together. Day 1 is a one-bet day dressed as two.

## BLIND DAY 2 — 20211021 (sealed before any unblinding; policy RV1)

**BLIND DAY 2 — 2021-10-21, 1,291 candidates (SI 425, HG 488, NKD 378), 58 creation-class rows, 9 cells, 28 TAKEs, 4 seats.** Policy RV1, 47 as-of cuts. The day is an EXPANSION day for two of three assets by the LONDON/NY opens (HG range_so_far 135.5% of range_hat, NKD 171.1%, SI 68.9% AT_RANGE) — the regime in which every capacity term inverts and in which my refusal core has no capacity term to invert, by design. Three of four seats are SHORT at a phase open; the fourth is the SI/TOKYO seat in the cell my own P035 table says has NEVER held a winner (0-for-7) and whose phase q50 is **$937, below the $1,000 bar** — I am taking it anyway because the policy has no abstention and no capacity gate, and both refusals are unproven. That seat is the round's cleanest test of my own declared refusal to gate.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 156 | 0 | 0 | 0 | - | LONG | MED | no | CLOSED/OPEN | S8 f30m +50 on 316, f5m +32 on 126, fuel 101 below / 56 above, thru 3 of 3 clearing the ASK, mid 4.743 within a tick of the phase H — the only cell of the day whose flows and book agree at magnitude (briefing A3). |
| HG/NY | 255 | 18 | 3 | 13 | HG-20211021-047000-S | SHORT | MED | no | OPEN/CLOSED | S2 EXPANDED 135.5%; S8 f30m -190 on 2,129 with the fuel map 109 above / 2 below on the phase; through_book 35 prints, 21 clearing the BID; mid on the phase L. Same shape as SI/NY at the same minute — the metals are one bet again (S11). |
| HG/TOKYO | 77 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/OPEN | S8 fuel 161 above / 8 below on 169 with fph_sflow -36; mid 4.727 on the phase L (760s). WOULD-ABSTAIN: HG/TOKYO study base rate 0.14. |
| NKD/LONDON | 90 | 2 | 0 | 0 | - | SHORT | LOW | no | OPEN/CLOSED | S2 day_type EXPANDED at 133.6% of range_hat with unspent_sess -$747 (the capacity arithmetic is already NEGATIVE — the anti-signal regime); S8 f30m -36 on 160 and a 5-contract phase. Read SHORT, traded not at all. |
| NKD/NY | 129 | 13 | 0 | 2 | NKD-20211021-056023-L | SHORT | LOW | no | CLOSED/CLOSED | S2 EXPANDED at 171.1%; S8 f30m -45 on 85 and through_book 4 of 4 clearing the BID; S10 d_POC -$937.50 (mid far below developing value). The seat the policy actually spent here is a LONG two and a half hours later — my read and my policy disagree and the policy wins by construction. |
| NKD/TOKYO | 159 | 1 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | S8 phase_total 10 contracts, fuel 6 above / 0 below, thru_n 0 at the cell open. Nothing to read; rv1800 155.1 with rv_collapse 1.03 says the vol is live but the tape is empty. |
| SI/LONDON | 93 | 1 | 0 | 0 | - | SHORT | LOW | no | CLOSED/OPEN | S8 f30m -67 on 393 into the open, S10 d_POC -$312.5 with in_VA=1, mid 24.43 on the phase L (15s old). The 20-contract phase total makes this a read on almost nothing. |
| SI/NY | 261 | 22 | 0 | 12 | SI-20211021-046925-S | SHORT | MED | no | OPEN/CLOSED | S8 f30m -120 on 746 and phase -27 on 183 with the fuel map 85 above / 16 below; S10 d_POC -$987.50, in_VA=0 (price is below the whole developing value area); S5 mid_slope -$75/min into the open. Four independent lines, one direction — and my direction reads are 5-for-14 lifetime, which is why this gates nothing. |
| SI/TOKYO | 71 | 1 | 0 | 1 | SI-20211021-000252-L | LONG | LOW | YES | CLOSED/CLOSED | S8 fuel 5 above / 107 below on 112 and f60 +7 on 23 into a mid sitting on the phase H (24.3975, 15s old). WOULD-ABSTAIN (P035 SI/TOKYO 0-for-7) and the S3 card says TOKYO exp_move_q50 = $937 against a $1,000 bar — RECORDED, NOT TRADED, and the policy seats this cell anyway. |

**THE DAY'S STRUCTURAL FACT:** two of three assets entered NY already EXPANDED (HG 135.5% of range_hat, NKD 171.1%). CC-M2-11.1 ruled the day_type flag LAGGING (it fires ~1-2h after the winners' decision seconds), so this is a description, not an instrument — and my policy reads neither.

**THE SI/TOKYO SEAT IS THE ROUND'S ABSTENTION TEST:** flagged would-abstain at the cell open on P035 (0-for-7) AND carrying a phase expected move below the bar ($937), and taken anyway because both refusals are unproven. Whatever it scores, the counterfactual is in the arms file.

## BLIND DAY 3 — 20211022 (sealed before any unblinding; policy RV1)

**BLIND DAY 3 — 2021-10-22, 1,258 candidates (SI 459, HG 445, NKD 354), 45 creation-class rows + 1 SHOCK-RESOLUTION, 9 cells, 16 TAKEs, 3 seats.** Policy RV1, 47 as-of cuts. **THE DAY'S FINDING IS THE S13 CARD TABLE, READ OFF THE SHEETS THEMSELVES (ex ante, no outcome):** per asset, era E1 — SI REVERSAL 5.90% win / -$29.54, RECLAIM 6.20% / -$67.81, OPEN-DYNAMICS **8.26%** / -$1.91; HG REVERSAL 4.63% / -$32.65, RECLAIM 3.84% / -$65.74, NEWS-WINDOW **6.53%** / -$23.35, OPEN-DYNAMICS **7.72%** / -$21.29; NKD REVERSAL 4.67% / -$44.97. **The direction of my declaration survives — the creation classes beat their own asset's bulk by 1.3-1.7x on win rate and are the least negative on mean certificate — but the MAGNITUDE does not: this is a 1.4x class effect at era scale, not the 2.6x my eight study sessions measured.** Policy unchanged; there is no better class to be in and the core is what turns a class into a call.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 115 | 2 | 0 | 2 | HG-20211022-025468-L | LONG | MED | no | CLOSED/OPEN | S8 f30m +40 on 237, f5m +31 on 49, f60 +15 on 19, through_book 5 of 7 clearing the ASK, mid on the phase H 7 seconds old; S10 in_VA=1 with d_POC -$193.75. Flow, book and price agree at the open (A3). |
| HG/NY | 256 | 13 | 0 | 7 | HG-20211022-052246-L | SHORT | LOW | no | CLOSED/OPEN | S8 fuel 89 above / 32 below with f30m +10 on 529 — flow and fuel disagree, which is why this is LOW. The policy's actual seat here is a LONG 84 minutes later at the 14:30 release, against this read. |
| HG/TOKYO | 74 | 0 | 0 | 0 | - | LONG | LOW | YES | CLOSED/OPEN | S8 fph +69 on 494, 440 of 494 below the mid, f5m +37 on 65; the mirror image of day 2's HG/TOKYO. WOULD-ABSTAIN (0.14 base rate). |
| NKD/LONDON | 34 | 1 | 0 | 0 | - | NONE | - | no | OPEN/CLOSED | S2 EXPANDED at 112% of range_hat with unspent_sess -$224; S8 phase_total 3 contracts. The regime flag is lagging (CC-M2-11.1) and the tape is empty — nothing here is actionable. |
| NKD/NY | 102 | 3 | 0 | 0 | - | NONE | - | no | CLOSED/CLOSED | S8 phase_total 7 contracts, fuel 0 above / 5 below, thru_n 0. No readable tape; NKD/NY is CC-M2-18.1's 0.29 cell. |
| NKD/TOKYO | 218 | 3 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | S8 15 contracts at the cell open (11 above / 4 below), thru_n 0, rv60 0. No tape. |
| SI/LONDON | 67 | 0 | 0 | 0 | - | LONG | LOW | no | CLOSED/OPEN | S8 f30m +53 on 151 and f5m +22 on 38 into a 55-contract phase; INSIDE day at 22.3% of range_hat. Thin agreement, low conviction. |
| SI/NY | 342 | 23 | 1 | 7 | SI-20211022-046855-S | SHORT | MED | no | CLOSED/OPEN | S8 f30m -139 on 760, phase -52 on 156 with **156 of 156 phase contracts ABOVE the mid**, f60 -53 on 159; mid on the NY L 13 seconds old. The single most one-sided fuel map of the round so far. |
| SI/TOKYO | 50 | 1 | 0 | 0 | - | LONG | LOW | YES | CLOSED/CLOSED | S8 fph +28 on 242 with 213 of 242 contracts BELOW the mid and f5m +26 on 46; mid within a tick of the phase H (66s). WOULD-ABSTAIN (P035 0-for-7) — recorded, not traded. TOKYO exp_move_q50 = $924, below the bar again. |

**DEFECT D27 (new, day 3):** T5's relative clause `f5m_vol >= 0.08 * fph_vol` is unbounded below — on a phase whose total volume is 48 contracts it admits a 49-contract 5-minute window as 'magnitude'. Two of the round's nine seats so far exist only through that clause (SI/TOKYO day 2 at 112 contracts, HG/LONDON day 3 at 49). The CC-M2-16.4 repair fixed an NKD misfire and created a thin-phase hole. Not patched mid-round (the policy is frozen); logged for the fix lane.

**THE SEAT CLOCK IS COLLAPSING ONTO PHASE OPENS AND RELEASES:** of nine seats in three days, seven are within 5 minutes of a phase open and two are within a minute of a scheduled release. That is what the creation-class filter DOES, and it means my round is a bet on two clock windows, not on 12,418 candidates.

## BLIND DAY 4 — 20211025 (sealed before any unblinding; policy RV1)

**BLIND DAY 4 — 2021-10-25 (Monday), 928 candidates (SI 384, HG 293, NKD 251), 57 creation-class rows, 9 cells, 25 TAKEs, 6 SEATS — the widest day of the round so far.** Policy RV1, 47 cuts. **THE DAY'S STRUCTURAL FINDING (defect D28, and it is about my own core): AT A SESSION OPEN THE NESTED FLOW WINDOWS COLLAPSE.** On SI-20211025-000021-S the sheet prints 60s = 5m = 30m = phase = session = 30 events / 67 contracts / sflow -31, because the session is 21 seconds old. T4 (`|f5m_sflow|/f5m_vol >= 5%`) and T5 (`f5m_vol >= 8% of fph_vol`) are then TAUTOLOGIES — a window compared with itself — and both TOKYO seats of this day were minted in that hole, at seconds 19 and 21, with 75-cent spreads and phase expected moves of $876 (SI) and $1,431 (HG). The core's magnitude terms measure NOTHING in the first five minutes of a session, which is exactly where the OPEN-DYNAMICS class fires. Logged, not patched: the policy is frozen.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 65 | 1 | 0 | 0 | - | SHORT | LOW | no | CLOSED/OPEN | S8 phase -25 on 57, all 57 contracts above the mid, 5 of 5 through-book prints clearing the BID — but f30m is +41 on 265 the other way. Horizon disagreement (P022, compass falsified) so the read stays LOW. |
| HG/NY | 131 | 8 | 0 | 5 | HG-20211025-052547-S | SHORT | LOW | no | CLOSED/OPEN | S8 fuel 259 above / 74 below, f5m -52 on 148, against f30m +10 on 508. Same disagreement as HG/LONDON, same LOW. |
| HG/TOKYO | 97 | 3 | 0 | 2 | HG-20211025-000019-L | LONG | LOW | YES | CLOSED/OPEN | S8 +61 on 132 with 90 of 132 below the mid at second 19 — but every window is the same window (D28), so this is one 19-second reading wearing four names. WOULD-ABSTAIN (P035 0.14). |
| NKD/LONDON | 21 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/CLOSED | AT_RANGE at 71.8%; S8 essentially empty. No read. |
| NKD/NY | 53 | 4 | 0 | 1 | NKD-20211025-056023-S | NONE | - | no | CLOSED/CLOSED | 1 contract in the phase at the open. The seat the policy spends here comes 2.5h later. |
| NKD/TOKYO | 177 | 7 | 0 | 0 | - | NONE | - | no | OPEN/OPEN | 3 contracts at the cell open; rv1800 307 is the highest overnight state of the round so far but there is no tape to read it against. |
| SI/LONDON | 86 | 2 | 0 | 2 | SI-20211025-025237-S | SHORT | MED | no | CLOSED/OPEN | S8 f5m -57 on 158 and f60 -35 on 42 with 41 of 42 phase contracts above the mid; mid on the phase L 12s old; S10 d_POC +$687.50 with in_VA=0 (price below the whole value area). |
| SI/NY | 220 | 26 | 2 | 10 | SI-20211025-046924-L | LONG | MED | no | CLOSED/OPEN | S8 60s +47 on 69, phase +41 on 109 with 107 of 109 contracts BELOW the mid (the fuel sits under the trade), S5 trades/min z=4.36 with slope +$112.50/min; S10 in_VA=1, d_POC +$87.50 — price is at value, not extended. The cleanest LONG read of the round. |
| SI/TOKYO | 78 | 6 | 0 | 5 | SI-20211025-000021-S | SHORT | LOW | YES | CLOSED/CLOSED | S8 -31 on 67 with 63 of 67 contracts above the mid; S3 gap_vs_settle -$537.50 (-0.209xATR) — a real weekend gap down. WOULD-ABSTAIN (0-for-7) and TOKYO q50 = $876 against the bar. Both refusals recorded, neither traded. |

**SIX SEATS, AND FIVE OF THEM ARE OPENS:** TOKYO 00:00:19 and 00:00:21, LONDON 07:00:37, NY 13:02:04, plus two release-window seats at 14:35 and 15:33. The clock concentration noted on day 3 is now the round's defining shape.

**THE TWO TOKYO SEATS ARE THE D28 HOLE MADE VISIBLE** and they are graded B by my own rule-independent grade (q50 $876 and $1,431 against the $1,500 A band) — the grade is doing the one job the core is not.

## BLIND DAY 5 — 20211026 (sealed before any unblinding; policy RV1)

**BLIND DAY 5 — 2021-10-26, 858 candidates (SI 398, HG 274, NKD 186), 45 creation-class rows, 9 cells, 17 TAKEs, 2 seats (SI/NY and HG/NY, both LONG, 23 seconds apart at the 14:31 release).** Policy RV1, 47 cuts. No open fired today — every phase-open row failed the core or the class — so the day is a pure release bet. **THE DAY'S FINDING IS THE FULL EX-ANTE CARD TABLE**, assembled from the blind sheets themselves (S13, era E1, no outcome anywhere in it): SI NEWS-WINDOW n=2,696 cond_value $1,042.88 mean_cert **+$26.63** win_frac **0.1187** — the ONLY positive cell on the board; SI OPEN-DYNAMICS 1,283 / $848 / -$1.91 / 0.0826; HG OPEN-DYNAMICS 946 / $650 / -$21.29 / 0.0772; HG NEWS-WINDOW 1,609 / $705 / -$23.35 / 0.0653; NKD NEWS-WINDOW 1,013 / $720 / -$34.66 / 0.0800; NKD OPEN-DYNAMICS 1,237 / $728 / **-$58.49** / 0.0582; **HG SHOCK-RESOLUTION 13 / $184 / -$456.44 / 0.0000**; against the REVERSAL bulks SI 44,823 / -$29.54 / 0.0590, HG 43,387 / -$32.65 / 0.0463, NKD 47,797 / -$44.97 / 0.0467. Two cells of my class set FAIL their own asset's bulk on mean certificate: **NKD/OPEN-DYNAMICS and SHOCK-RESOLUTION** — the latter being my one registered increment, contradicted by the port's own committed census before it ever traded. The evolution note is written for day 6; today is sealed under RV1 and today's takes contain neither cell.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 68 | 0 | 0 | 0 | - | SHORT | MED | no | CLOSED/OPEN | S8 phase -50 on 176 and f30m -54 on 194 with 115 of 176 above the mid and 7 of 8 through-book prints clearing the BID; rv_collapse 11.99 is the highest of the round — the move is over and the tape is thin. |
| HG/NY | 141 | 8 | 0 | 4 | HG-20211026-052324-L | SHORT | LOW | no | CLOSED/OPEN | S8 f30m -130 on 687 with a 42-contract phase; 5 of 6 through-book prints clearing the BID. Thin. |
| HG/TOKYO | 65 | 1 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/OPEN | S8 fph -14 on 226, 224 of 226 above the mid, but f5m is -2 on 4 contracts — the phase read is 40 minutes stale relative to the decision (the CC-M2-19.1 anchor law in miniature). WOULD-ABSTAIN (0.14). |
| NKD/LONDON | 19 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/CLOSED | AT_RANGE 77.2%, empty phase. |
| NKD/NY | 59 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/CLOSED | 7 contracts in the phase; AT_RANGE 85.9% with unspent $444 — nothing to trade and nothing to read. |
| NKD/TOKYO | 108 | 1 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | S8 0 contracts in every window at the cell open. Nothing. |
| SI/LONDON | 61 | 0 | 0 | 0 | - | SHORT | LOW | no | CLOSED/OPEN | S8 f30m -22 on 172 into a 19-contract phase; mid on the phase L 16s old; rv_collapse 6.82 (the vol that made the level has already gone). |
| SI/NY | 302 | 35 | 2 | 13 | SI-20211026-052301-L | SHORT | LOW | no | CLOSED/CLOSED | S8 phase -36 on 213 and f30m -29 on 609 against f60 +28 on 118 — horizon disagreement into the open; 184 of 213 contracts BELOW the mid, which is fuel for a bounce. Genuinely mixed, and the policy's seat here is a LONG 90 minutes later at the release. |
| SI/TOKYO | 35 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/CLOSED | S8 fph -29 on 255 with 231 of 255 above the mid; mid at the phase L. WOULD-ABSTAIN (0-for-7), TOKYO q50 $859 below the bar. |

**A PURE RELEASE DAY:** both seats sit inside the same 14:31-14:32 release window, 23 seconds apart, in the two metals. Days 1, 3, 5 have now each produced a two-seat day where the seats are one bet.

**THE EVOLUTION IS WRITTEN FOR DAY 6, NOT TODAY:** dropping SHOCK-RESOLUTION and NKD/OPEN-DYNAMICS is argued in BLIND_NOTES from the card table above; neither cell appears in today's 17 takes, so today's seal is unaffected either way.

## BLIND DAY 6 — 20211027 (sealed before any unblinding; policy RV2)

**BLIND DAY 6 — 2021-10-27, 1,056 candidates (SI 367, HG 394, NKD 295), 62 creation-class rows, 9 cells, 23 TAKEs, 4 seats. FIRST DAY UNDER POLICY RV2 (the card rule).** The evolution bites exactly once and visibly: RV1 would have taken 24 rows and seated NKD/NY with an OPEN-DYNAMICS long at 13:01:21; RV2 drops that one row (NKD/OPEN-DYNAMICS fails its own asset's bulk on the era card, -$58.49 vs -$44.97) and the NKD/NY seat moves to a NEWS-WINDOW short at 16:03:35 — the class that DOES beat the NKD bulk (0.0800 vs 0.0467). One row changed, one seat changed, and the arms file records both arms on every row so the increment can be priced exactly.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 125 | 0 | 0 | 0 | - | SHORT | LOW | no | CLOSED/OPEN | S8 phase -42 on 161 with 140 of 161 above the mid, but f30m -17 on 236 is nearly flat. Thin conviction. |
| HG/NY | 201 | 16 | 0 | 7 | HG-20211027-052667-L | LONG | LOW | no | OPEN/CLOSED | S8 fuel 205 below / 19 above but f30m -123 on 1,152 the other way; AT_RANGE 93.6% with unspent $429. Mixed and nearly out of statistical room. |
| HG/TOKYO | 68 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/OPEN | S8 fph +1 on 337 (a dead-flat phase) with 268 of 337 above the mid; rv_collapse 10.65. WOULD-ABSTAIN (0.14). |
| NKD/LONDON | 51 | 0 | 0 | 0 | - | LONG | LOW | no | CLOSED/CLOSED | S8 fph +15 on 31 with all 31 contracts below the mid; a 31-contract phase is not evidence. |
| NKD/NY | 117 | 7 | 0 | 1 | NKD-20211027-057815-S | SHORT | LOW | no | CLOSED/CLOSED | S2 AT_RANGE 85.7% with unspent $447 (below the bar); S8 f30m -25 on 209 into an empty phase. The RV2 seat here (16:03 NEWS short) agrees with the read; the RV1 seat (13:01 OPEN long) would not have. |
| NKD/TOKYO | 127 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | 3 contracts at the open; every flow window identical (D28). |
| SI/LONDON | 84 | 1 | 0 | 1 | SI-20211027-025480-S | SHORT | MED | no | CLOSED/OPEN | S8 phase -30 on 34, f60 -26 on 26, f5m -28 on 36 — every window selling at the open with 30 of 34 contracts above the mid and the mid on a 15-second-old phase L. The policy's seat here agrees with the read for once. |
| SI/NY | 244 | 31 | 0 | 14 | SI-20211027-046949-L | LONG | MED | no | CLOSED/CLOSED | S8 phase +9 on 143 with **143 of 143 contracts BELOW the mid** and 60s +10 on 20; S10 d_POC -$12.50 with in_VA=1 — price is AT developing value; S7 book 11x11 with c2f 6.70 (the highest quote-to-fill of the round: a heavily quoted, orderly open). |
| SI/TOKYO | 39 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/CLOSED | S8 fph 0 on 114 with 91 of 114 above the mid and f5m -8 on 24; the phase read is flat and the mid sits at a 2-second-old phase H. WOULD-ABSTAIN (0-for-7); TOKYO q50 $890 below the bar. |

**RV2's FIRST BITE, measured:** 24 takes -> 23, and the NKD/NY seat moves from a 13:01:21 OPEN-DYNAMICS long to a 16:03:35 NEWS-WINDOW short. That is the whole footprint of the card rule on this day.

## BLIND DAY 7 — 20211028 (sealed before any unblinding; policy RV2)

**BLIND DAY 7 — 2021-10-28, 1,109 candidates in the rendered set (SI 478, HG 399, NKD 240 eligible; the index carries 1,109 sheets), 78 creation-class rows, 9 cells, 15 TAKEs, 2 seats — and for the first time the two metals seat OPPOSITE SIDES in the same minute:** HG/NY SHORT at 13:01:25 and SI/NY LONG at 13:01:55. Day 1 seated both long, day 2 both short, day 5 both long; today the same generator, the same clock second, opposite directions. That is the cleanest available statement that the policy carries NO side term at all — and it is also the first day whose two seats are genuinely independent bets. HG enters NY at 89.5% of its expected session move with **$315.80 of statistical room left against a $1,000 bar**; SI enters at 38.3% with $1,589. Both are traded, because capacity is not in the policy.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 124 | 0 | 0 | 0 | - | LONG | LOW | no | CLOSED/OPEN | S8 f30m +73 on 501 with 260 of 303 contracts ABOVE the mid — flow and fuel point opposite ways, which is the ambiguity the fuel map is worst at resolving. |
| HG/NY | 190 | 15 | 0 | 3 | HG-20211028-046885-S | SHORT | MED | no | CLOSED/CLOSED | S8 60s -21 on 85 and phase -11 on 109 with 75 of 109 contracts above the mid, 4 of 4 through-book prints clearing the BID, S5 slope -$81/min with accel -61 and trades/min z=4.85; S10 in_VA=1 with d_POC -$62.50. AGAINST: the session has spent 89.5% of its expected move. |
| HG/TOKYO | 85 | 0 | 0 | 0 | - | LONG | LOW | YES | CLOSED/OPEN | S8 fph +75 on 233 with 221 of 233 BELOW the mid and f5m +52 on 106; 3 of 3 through-book prints clearing the ASK. The strongest TOKYO agreement of the round — and the cell my base-rate table (0.14) says almost never pays. WOULD-ABSTAIN, recorded, not traded. |
| NKD/LONDON | 23 | 0 | 0 | 0 | - | SHORT | LOW | no | OPEN/CLOSED | S8 f30m -8 on 118 into a 7-contract phase; rv_collapse 7.80 with vol_regime LOW. |
| NKD/NY | 84 | 5 | 0 | 0 | - | SHORT | LOW | no | CLOSED/OPEN | S8 41 contracts, all above the mid, f5m -1 on 2. No tape. No seat fired here today. |
| NKD/TOKYO | 133 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | 5 contracts, all windows identical (D28). |
| SI/LONDON | 60 | 0 | 0 | 0 | - | LONG | LOW | no | CLOSED/OPEN | S8 f30m +49 on 234 and phase +17 on 75 against f5m -4 on 36 — horizon disagreement at the open (P022, compass falsified). |
| SI/NY | 355 | 50 | 0 | 12 | SI-20211028-046915-L | LONG | MED | no | CLOSED/OPEN | S8 every window buying (60s +36 on 64, 5m +29 on 117, 30m +56 on 356, phase +26 on 80) with 77 of 80 contracts BELOW the mid; S10 in_VA=1, d_POC +$87.50. The mirror image of HG at the same minute, and both reads are MED. |
| SI/TOKYO | 55 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/CLOSED | S8 fph +3 on 188 (flat) with 167 of 188 above the mid; f5m 0 on 12. Nothing is happening. WOULD-ABSTAIN (0-for-7); q50 $879 below the bar. |

**FIFTEEN TAKES, ELEVEN OF THEM IN THE 14:30 SI RELEASE WINDOW** (six longs and three shorts inside 43 seconds, at 14:30:16-14:30:59) — the generator fires both sides through a release and my policy takes every admitted row on both sides, spending the seat on the first. Under CC-M2-10.3 the SI/NY seat was already spent at 13:01:55, so all eleven release rows are forfeited by construction: they cost nothing and they earn nothing.

**THIS IS THE ROUND'S CLEAREST SEAT-ACCOUNTING LESSON:** 15 committed TAKEs, 2 spendable seats. The panel scores the seats; the takes are the thesis record.

## BLIND DAY 7 — 20211028 (sealed before any unblinding; policy RV2)

**BLIND DAY 7 — 2021-10-28, 1,109 candidates in the rendered set (SI 478, HG 399, NKD 240 eligible; the index carries 1,109 sheets), 78 creation-class rows, 9 cells, 15 TAKEs, 2 seats — and for the first time the two metals seat OPPOSITE SIDES in the same minute:** HG/NY SHORT at 13:01:25 and SI/NY LONG at 13:01:55. Day 1 seated both long, day 2 both short, day 5 both long; today the same generator, the same clock second, opposite directions. That is the cleanest available statement that the policy carries NO side term at all — and it is also the first day whose two seats are genuinely independent bets. HG enters NY at 89.5% of its expected session move with **$315.80 of statistical room left against a $1,000 bar**; SI enters at 38.3% with $1,589. Both are traded, because capacity is not in the policy.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 124 | 0 | 0 | 0 | - | LONG | LOW | no | CLOSED/OPEN | S8 f30m +73 on 501 with 260 of 303 contracts ABOVE the mid — flow and fuel point opposite ways, which is the ambiguity the fuel map is worst at resolving. |
| HG/NY | 190 | 15 | 0 | 3 | HG-20211028-046885-S | SHORT | MED | no | CLOSED/CLOSED | S8 60s -21 on 85 and phase -11 on 109 with 75 of 109 contracts above the mid, 4 of 4 through-book prints clearing the BID, S5 slope -$81/min with accel -61 and trades/min z=4.85; S10 in_VA=1 with d_POC -$62.50. AGAINST: the session has spent 89.5% of its expected move. |
| HG/TOKYO | 85 | 0 | 0 | 0 | - | LONG | LOW | YES | CLOSED/OPEN | S8 fph +75 on 233 with 221 of 233 BELOW the mid and f5m +52 on 106; 3 of 3 through-book prints clearing the ASK. The strongest TOKYO agreement of the round — and the cell my base-rate table (0.14) says almost never pays. WOULD-ABSTAIN, recorded, not traded. |
| NKD/LONDON | 23 | 0 | 0 | 0 | - | SHORT | LOW | no | OPEN/CLOSED | S8 f30m -8 on 118 into a 7-contract phase; rv_collapse 7.80 with vol_regime LOW. |
| NKD/NY | 84 | 5 | 0 | 0 | - | SHORT | LOW | no | CLOSED/OPEN | S8 41 contracts, all above the mid, f5m -1 on 2. No tape. No seat fired here today. |
| NKD/TOKYO | 133 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | 5 contracts, all windows identical (D28). |
| SI/LONDON | 60 | 0 | 0 | 0 | - | LONG | LOW | no | CLOSED/OPEN | S8 f30m +49 on 234 and phase +17 on 75 against f5m -4 on 36 — horizon disagreement at the open (P022, compass falsified). |
| SI/NY | 363 | 50 | 0 | 12 | SI-20211028-046915-L | LONG | MED | no | CLOSED/OPEN | S8 every window buying (60s +36 on 64, 5m +29 on 117, 30m +56 on 356, phase +26 on 80) with 77 of 80 contracts BELOW the mid; S10 in_VA=1, d_POC +$87.50. The mirror image of HG at the same minute, and both reads are MED. |
| SI/TOKYO | 55 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/CLOSED | S8 fph +3 on 188 (flat) with 167 of 188 above the mid; f5m 0 on 12. Nothing is happening. WOULD-ABSTAIN (0-for-7); q50 $879 below the bar. |

**FIFTEEN TAKES, ELEVEN OF THEM IN THE 14:30 SI RELEASE WINDOW** (six longs and three shorts inside 43 seconds, at 14:30:16-14:30:59) — the generator fires both sides through a release and my policy takes every admitted row on both sides, spending the seat on the first. Under CC-M2-10.3 the SI/NY seat was already spent at 13:01:55, so all eleven release rows are forfeited by construction: they cost nothing and they earn nothing.

**THIS IS THE ROUND'S CLEAREST SEAT-ACCOUNTING LESSON:** 15 committed TAKEs, 2 spendable seats. The panel scores the seats; the takes are the thesis record.

## BLIND DAY 8 — 20211029 (sealed before any unblinding; policy RV2)

**BLIND DAY 8 — 2021-10-29 (month end), 1,197 candidates (SI 510, HG 334, NKD 353), 77 creation-class rows, 8 cells, 18 TAKEs, 2 seats — both LONG inside the 14:30 release window (SI 14:30:39, HG 14:31:51).** Policy RV2, 47 cuts, render verified complete before indexing (the D30 guard is now in the tool). **THE CONTRAST CASE FOR THE `in_VA` HYPOTHESIS ARRIVES TODAY:** the SI seat is a LONG with `d_POC = -$612.50, in_VA = 0` — price extended BELOW the developing value area, the opposite of the days 4/5/6 seats — and it is also the row where the aggressive stream most strongly opposes the trade in the whole round (`f5m -195 on 1,434`, `f60 -170 on 1,017`, 43 of 54 through-book prints clearing the BID) while the fuel map holds 4,354 of 5,071 contracts above it. T4's de-signing is doing more work on this seat than on any other of the twelve days.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 72 | 0 | 0 | 0 | - | LONG | MED | no | CLOSED/OPEN | S8 f5m +29 on 61 and f30m +26 on 469 with 357 of 371 contracts below the mid. Same shape as SI, same minute — the metals agree again. |
| HG/NY | 202 | 15 | 0 | 7 | HG-20211029-052311-L | SHORT | LOW | no | CLOSED/OPEN | S8 f30m -99 on 804 and f5m -39 on 177 with 6 of 6 through-book prints clearing the BID, but the phase holds 33 contracts. Thin. |
| HG/TOKYO | 60 | 1 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/OPEN | S8 fph -18 on 134, f5m -13 on 53, but the fuel map is 70 below / 48 above — flow and fuel disagree. WOULD-ABSTAIN (0.14). |
| NKD/LONDON | 52 | 0 | 0 | 0 | - | NONE | - | no | OPEN/CLOSED | EXPANDED at 117.4% with unspent -$316; S8 phase empty. The regime flag is lagging and the tape is not there. |
| NKD/NY | 90 | 4 | 0 | 0 | - | NONE | - | no | CLOSED/CLOSED | 4 contracts. EXPANDED session with negative unspent. |
| NKD/TOKYO | 211 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | 4 contracts at the open. |
| SI/LONDON | 106 | 0 | 0 | 0 | - | LONG | MED | no | CLOSED/OPEN | S8 f30m +102 on 719, f5m +62 on 173, f60 +17 on 74 with 319 of 402 contracts BELOW the mid — every window buying with the fuel underneath. The best LONDON agreement of the round. |
| SI/NY | 365 | 41 | 2 | 11 | SI-20211029-052239-L | LONG | LOW | no | CLOSED/CLOSED | S8 f30m +44 on 525 and f60 +15 on 53 with 131 of 138 contracts below the mid, but f5m is +3 on 217 — flat at the moment that matters. |
| SI/TOKYO | 39 | 1 | 0 | 0 | - | NONE | - | YES | CLOSED/CLOSED | Nothing readable at the open; WOULD-ABSTAIN (0-for-7) and TOKYO q50 is below the bar as on every day of this round. |

**MONTH-END, and both seats are in the same release minute again.** Eight days in, the seat clock is: phase opens (12 seats) and the 14:30/16:00 release windows (10 seats). Nothing else has ever been seated.

**COVERAGE:** 1,197 of 1,197 sheets indexed and sealed (the D30 guard held); day-complete.

## BLIND DAY 9 — 20211101 (sealed before any unblinding; policy RV2)

**BLIND DAY 9 — 2021-11-01 (Monday), 842 candidates (SI 321, HG 250, NKD 271), 49 creation-class rows, 9 cells, 14 TAKEs, 6 SEATS** — the second six-seat day, and the widest spread of cells in the round (HG/TOKYO, SI/TOKYO, SI/LONDON, HG/NY, NKD/NY, SI/NY). Policy RV2, 47 cuts, coverage 842/842 verified. Three of the six seats are minted inside the first 76 seconds of the session, in the D28 window-collapse hole, and all three are graded B by the rule-independent grade (TOKYO q50 $845-$1,301). The other three are release-window shorts. **NKD gets a seat again under the card rule — a NEWS-WINDOW short, the class that beats the NKD bulk (0.0800 vs 0.0467) — while the OPEN-DYNAMICS rows that RV1 would have taken are refused.**

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 66 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | S8 fuel 147 below / 133 above — the most balanced fuel map of the round; f30m +33 on 286. No read. |
| HG/NY | 100 | 8 | 0 | 1 | HG-20211101-052357-S | SHORT | LOW | no | CLOSED/CLOSED | S8 f5m -17 on 158 into a 27-contract phase; AT_RANGE 71.2%. |
| HG/TOKYO | 84 | 2 | 0 | 2 | HG-20211101-000055-S | SHORT | LOW | YES | CLOSED/OPEN | S8 -17 on 53 with 48 of 53 above the mid and 5 of 6 through-book prints clearing the BID — a genuine one-sided open, on 53 contracts. WOULD-ABSTAIN (0.14). |
| NKD/LONDON | 27 | 0 | 0 | 0 | - | NONE | - | no | OPEN/CLOSED | EXPANDED 105.4% with unspent -$30; rv_collapse 28.74 (the highest of the round — the move is long over). 6 contracts. |
| NKD/NY | 74 | 2 | 0 | 2 | NKD-20211101-052423-S | SHORT | LOW | no | CLOSED/CLOSED | S8 fuel 50 above / 0 below on 114; EXPANDED session with negative unspent. The RV2 seat here is a 14:33 NEWS short and agrees. |
| NKD/TOKYO | 170 | 0 | 0 | 0 | - | SHORT | LOW | no | OPEN/OPEN | S8 -57 on 151 and f60 -59 on 132 with 148 of 151 contracts BELOW the mid — flow and fuel disagree hard; rv1800 299.5 with surprise 0.176, the most volatile NKD open of the round. |
| SI/LONDON | 84 | 1 | 0 | 1 | SI-20211101-025343-L | LONG | LOW | no | CLOSED/CLOSED | S8 phase +16 on 38 with all 38 contracts below the mid and f60 +16 on 28, against f30m -7 on 143. A 38-contract phase. |
| SI/NY | 189 | 20 | 1 | 7 | SI-20211101-055869-S | SHORT | MED | no | CLOSED/OPEN | S8 phase -37 on 191, f5m -36 on 70, f60 -30 on 32 with 157 of 191 contracts above the mid; rv_collapse 14.56 — every window selling into a collapsing vol state. The read and the 15:31 seat agree. |
| SI/TOKYO | 48 | 2 | 0 | 1 | SI-20211101-000076-S | SHORT | LOW | YES | CLOSED/CLOSED | S8 -13 on 59, 46 of 59 above the mid, mid on the 61-second-old phase L. WOULD-ABSTAIN (0-for-7); q50 $845. |

**SIX SEATS, THREE OF THEM IN THE FIRST 76 SECONDS.** The D28 window-collapse hole is not an edge case: on Mondays and after weekends the generator fires OPEN-DYNAMICS at the very top of the session and the core's magnitude terms cannot see anything there.

**THE CARD RULE IS NOW VISIBLY REDIRECTING NKD:** RV1's NKD seats were OPEN-DYNAMICS rows; RV2's are NEWS-WINDOW rows, which is the only NKD class that beats the NKD bulk on both axes of the era card.

## BLIND DAY 10 — 20211102 (sealed before any unblinding; policy RV2)

**BLIND DAY 10 — 2021-11-02 (FOMC eve), 800 candidates (SI 352, HG 294, NKD 154), 41 creation-class rows, 8 cells, 13 TAKEs, 3 seats.** Policy RV2, 47 cuts, coverage 800/800. Seats: HG/LONDON 07:02:53 SHORT (the round's first A-graded LONDON seat), SI/NY 14:31:57 LONG and HG/NY 14:32:15 LONG at the release. **NKD produced no seat at all today under the card rule** — its OPEN-DYNAMICS rows are refused and no NEWS-WINDOW row cleared the core, which is the first day the rule has removed an asset entirely rather than redirected it.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 113 | 3 | 0 | 2 | HG-20211102-025373-S | SHORT | MED | no | CLOSED/OPEN | S8 f5m -25 on 72 and 60s -22 on 28 into a session already -$981 and AT_RANGE 83.4%; S10 d_POC -$981 with in_VA=0 — price is far below the value area built overnight. The seat agrees with the read. |
| HG/NY | 117 | 8 | 0 | 6 | HG-20211102-052335-L | SHORT | MED | no | CLOSED/CLOSED | S8 phase -72 on 198 and f30m -140 on 768 at the open, with the session AT_RANGE 98.6% and **unspent $271.10 — a quarter of the bar**. The read is SHORT and the policy's seat 25 minutes later is a LONG; they disagree and the policy wins, as declared. |
| HG/TOKYO | 64 | 0 | 0 | 0 | - | LONG | LOW | YES | CLOSED/OPEN | S8 fph +16 on 149 with 89 of 149 below the mid and 5 of 6 through-book prints clearing the BID — flow and book disagree. WOULD-ABSTAIN (0.14). |
| NKD/LONDON | 19 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/CLOSED | 6 contracts, zero flow. |
| NKD/NY | 27 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | Opens 15:06 with 137 contracts, 130 of them above the mid; f5m -4 on 6. No seat, no read. |
| NKD/TOKYO | 108 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | 3 contracts. |
| SI/LONDON | 69 | 1 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | 10-contract phase; f30m +33 on 225 against f5m -6 on 34. No read. |
| SI/NY | 250 | 26 | 3 | 5 | SI-20211102-052317-L | LONG | LOW | no | OPEN/OPEN | S8 fph +64 on 675 with 543 of 675 contracts below the mid, but f5m -2 on 114 — flat at the moment. Cell opened late (13:34). |
| SI/TOKYO | 33 | 1 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/CLOSED | S8 fph -3 on 63 with 59 of 63 above the mid; f5m +2 on 10. Dead. WOULD-ABSTAIN (0-for-7). |

**FIRST DAY THE CARD RULE REMOVED AN ASSET:** no NKD seat at all — its OPEN-DYNAMICS rows are refused by RV2 and no NKD NEWS-WINDOW row cleared the core.

**FOMC EVE:** S12 shows the FOMC statement 1 day out. Tomorrow (day 11) is the largest creation-class day of the block (128 rows) and the round's biggest single test of the NEWS-WINDOW half of the declaration.

## BLIND DAY 11 — 20211103 (sealed before any unblinding; policy RV2)

**BLIND DAY 11 — 2021-11-03, FOMC DAY, 1,189 candidates (SI 549, HG 447, NKD 193), 128 creation-class rows (the largest of the block), 9 cells — and only 7 TAKEs and 2 seats.** Policy RV2, 47 cuts, coverage 1,189/1,189. **THE HEADLINE IS A STRUCTURAL ONE AND IT IS ABOUT SEATING, NOT SELECTION: on the day with the biggest scheduled event of the block, my policy spends the SI/NY seat at 13:02:50 — six hours and fifty-seven minutes BEFORE the FOMC statement (S12 prints the countdown on the row) — and the HG/NY seat at 14:31:17, five and a half hours before it.** Under CC-M2-10.3 phase-close seating with one position per (asset, phase) cell, the NY phase runs 13:00-22:59 and contains the entire FOMC; the earliest admitted row takes it. **Every FOMC candidate in this block is forfeited by construction.** That is not a judgement I made; it is the interaction of the seating rule with a filter that fires at opens.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 96 | 0 | 0 | 0 | - | LONG | LOW | no | CLOSED/OPEN | S8 f30m +33 on 322 but all 152 phase contracts sit ABOVE the mid. Contradictory; LOW. |
| HG/NY | 280 | 26 | 0 | 4 | HG-20211103-052277-S | LONG | LOW | no | CLOSED/CLOSED | S8 f5m +42 on 183 with the fuel map 152 below / 104 above, but the session is AT_RANGE 99% with **unspent $259** — a quarter of the bar — on FOMC day, which is precisely the day a range forecast should not be trusted. |
| HG/TOKYO | 71 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/OPEN | S8 f5m -29 on 83 with 75 of 109 above the mid and 8 of 13 through-book prints clearing the BID — the busiest TOKYO book of the round. WOULD-ABSTAIN (0.14). |
| NKD/LONDON | 20 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/CLOSED | Empty. |
| NKD/NY | 115 | 15 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | 7 contracts. |
| NKD/TOKYO | 58 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | Zero contracts in every window at the open. |
| SI/LONDON | 55 | 1 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | 8-contract phase on FOMC morning — the market is waiting. |
| SI/NY | 451 | 79 | 5 | 3 | SI-20211103-046970-L | LONG | MED | no | CLOSED/OPEN | S8 every window buying into the open (60s +16 on 30, 5m +43 on 95, 30m +57 on 378, phase +26 on 70) with 63 of 70 contracts below the mid and 3 of 3 through-book prints clearing the ASK; S3 sess_ret +$325. The seat agrees with the read. |
| SI/TOKYO | 43 | 0 | 0 | 0 | - | SHORT | LOW | YES | CLOSED/CLOSED | S8 fph -15 on 206 with 194 of 206 above the mid. WOULD-ABSTAIN (0-for-7). |

**SEVEN TAKES ON THE BIGGEST CREATION-CLASS DAY OF THE BLOCK (128 rows).** The core refused 121 of them — mostly T1 (dead book in the pre-FOMC hours) and T4/T5 (no magnitude while the market waits). The filter behaves exactly as designed and the day's opportunity is untouched by it.

**THE ROUND'S SEAT CLOCK, ELEVEN DAYS IN:** every seat sits either within ~5 minutes of a phase open or inside the 14:30/16:00 release windows. No seat has ever been spent between 08:00 and 13:00 or after 16:10.

## BLIND DAY 12 — 20211104 (sealed before any unblinding; policy RV2)

**BLIND DAY 12 — 2021-11-04 (the round's last day), 934 candidates (SI 364, HG 355, NKD 215), 59 creation-class rows, 9 cells, 18 TAKEs, 4 seats: HG/TOKYO 00:00:30 LONG, SI/TOKYO 00:01:49 LONG, SI/NY 13:03:05 LONG, HG/NY 14:30:59 LONG — every seat of the final day is a LONG.** Policy RV2, 47 cuts, coverage 934/934. Two of the four are minted inside the first 109 seconds of the session (the D28 window-collapse hole, both graded B, SI/TOKYO's phase q50 $870 again below the $1,000 bar); the other two are the usual open/release pair. **NKD is seatless for the third day running under the card rule.** The round ends exactly as it began: the creation-class filter fires at opens and releases, the core admits or refuses on five uncensused constants, and no term of the policy has ever expressed a direction.

| cell | rows | creation-class rows | V2 fires | TAKEs | seat | side read (NOT traded) | conf | would-abstain | rolling R1/R2b at cell open | evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| HG/LONDON | 75 | 0 | 0 | 0 | - | SHORT | LOW | no | CLOSED/OPEN | S8 fph -26 on 102 with all 102 contracts above the mid; f60 +4 on 18 disagrees. |
| HG/NY | 214 | 12 | 0 | 4 | HG-20211104-052259-L | LONG | LOW | no | OPEN/CLOSED | S8 f30m +67 on 1,763 into a 13-contract phase — the horizon disagreement is total; AT_RANGE 73.8%. |
| HG/TOKYO | 66 | 4 | 0 | 4 | HG-20211104-000030-L | LONG | LOW | YES | CLOSED/OPEN | S8 +10 on 52 with ALL 52 contracts below the mid and 5 of 8 through-book prints clearing the ASK, at second 30 (D28: one window wearing four names). WOULD-ABSTAIN (0.14) — and the policy seats it. |
| NKD/LONDON | 14 | 0 | 0 | 0 | - | NONE | - | no | CLOSED/CLOSED | 12 contracts. |
| NKD/NY | 65 | 5 | 0 | 0 | - | NONE | - | no | CLOSED/OPEN | No creation-class row cleared the core; the card rule removed NKD/OPEN-DYNAMICS and no NKD NEWS row qualified. Third seatless NKD day. |
| NKD/TOKYO | 136 | 0 | 0 | 0 | - | NONE | - | no | OPEN/OPEN | 16 contracts, fuel 8/8 — the most balanced and least informative map possible. |
| SI/LONDON | 70 | 0 | 0 | 0 | - | SHORT | MED | no | CLOSED/CLOSED | S8 phase -23 on 53, f5m -24 on 28, 44 of 53 contracts above the mid — every window selling into the open. |
| SI/NY | 237 | 28 | 0 | 9 | SI-20211104-046985-L | LONG | MED | no | CLOSED/OPEN | S8 phase +17 on 101 with ALL 101 contracts below the mid and f60 +2 on 32; INSIDE day at 54.5% with $1,160 unspent. The seat agrees. |
| SI/TOKYO | 57 | 1 | 0 | 1 | SI-20211104-000109-L | LONG | LOW | YES | CLOSED/CLOSED | S8 +5 on 45, all 45 contracts below the mid. WOULD-ABSTAIN (0-for-7 across the study round, seated four times in this blind round). TOKYO q50 $870. |

**THE ROUND CLOSES WITH 12 DAYS SEALED, 0 UNBLINDINGS, 0 S14 FILES OPENED.**

**FINAL SEAT CLOCK:** every one of the round's seats sits within ~5 minutes of a phase open or inside the 14:30-16:10 release band. The creation-class filter is, operationally, a clock filter with a flow floor.
