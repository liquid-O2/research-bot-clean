# R2 PERFECTION AUDIT — the pre-round-2 launch gate (D-093.1)

VERDICT: **BLOCKED** — 12 gaps found, 2 closed by lanes during the audit window, **10 open of which 6 are
launch-blocking** (G-2, G-3, G-4, G-5, G-11, G-12).

Auditor: independent audit lane (no design authorship in the r2-views / schema-audit / extraction lanes).
Method: D-093.1 as written — every row verified by **rendering or reading the actual artifact the reader
would see**, never by reading design intent. Where a document *claims* a mechanism, the mechanism itself was
looked for; a claim without a mechanism is recorded as a GAP even when the claim is in a committed file.

SAMPLE DAY: **E6 STUDY-D2, 2024-03-20 (FOMC decision day)**, all three assets, as specified. It is the day
the draw picked for release coverage (`provenance/port_m2/E6_ROUND_DRAW.md:39`), so the compliance machinery
is exercised live rather than hypothetically. Episodes inspected:

| asset | episode | dec_sec | UTC | why chosen |
|---|---|---|---|---|
| SI | `SI-20240320-S-E15` | 21418 | 03:56:58 | TOKYO, quiet book — the low-density end |
| SI | `SI-20240320-L-E67` | 72016 | 18:00:16 | **16 s after the FOMC statement** — NEWS-WINDOW class |
| HG | `HG-20240320-S-E98` | 71844 | 17:57:24 | 2 m 36 s BEFORE FOMC — inside the ±10 min veto |
| NKD | `NKD-20240320-L-E56` | 71566 | 17:52:46 | 7 m 14 s before FOMC — inside the veto, Nikkei VI live |

REPO STATE AT AUDIT: HEAD moved from `46301ba` to **`be9eec5`** across the window (D-093 → extraction
adjudication + R2-8/9/10 → schema-audit adjudication → R2-11 → the RED take-enforcement fixture). Re-pulled
five times; two checklist rows changed status mid-audit and are recorded as they finally stood.

**The r2-views and enforcement lanes' work is on disk but NOT COMMITTED at the end of the window** —
`engine/port_m2/ribbon.py`, `engine/port_m2/e6_round.py`, `engine/port_m2/episode_round.py` and
`engine/port_m2/test_r2views_fixlane.py` modified; `engine/port_m2/chart_panel.py` and
`design/RIBBON_LEGEND.md` untracked. Every row below marked `(uncommitted)` was verified by **running the
working-tree code** and is real, but **is not at HEAD and therefore cannot be launched against** (G-11).

---

## 1. RAW LAYER

### R-1 — ns event ribbon via the official databento-dbn decoder · **PASS (uncommitted)**

Rendered, not read about:

```
/usr/bin/python3 engine/port_m2/ribbon.py --cid NKD-20240320-071566-L \
    --from T-30 --to T --grain action --mode STUDY
```

Output, verbatim (first rows):

```
RIBBON ACTION-TYPED RAW EVENT STREAM (MBP-1, dominant iid=2917, clock=ts_event) cid=NKD-20240320-071566-L
  decoder databento-dbn 0.66.0 (THE official Databento Python library) -> DBNDecoder over the payload file;
          no cache and no parsing of ours between the file and this view
  source  /workspace/artifacts/reference/futures_mbp1/[NKD] .../glbx-mdp3-20240101-20241231.mbp-1.dbn.zst
  window  from=T-30 to=T+0 sec=[71536,71566] dec_sec=71566 n_events=12
  bound   permitted_end_ns=1710957167000000000 (= (decision_ts+1)*1e9, CausalGuard, D-057/D-080.4)
  fidelity EVERY record in the window is printed: no sampling, no aggregation, no rounding, NO ROW BOUND
             ts_event       gap_ns   sequence action side   price size    flags  bid_px bid_sz bid_ct ...
  1710957142843972689   7411895654  125224253      C    A   40125    1   130=LP   40120      3      3 ...
  1710957142923939449     79966760  125224266      A    A   40125    1   130=LP   40120      3      4 ...
```

Every column D-093.1 names is present: full-precision ns `ts_event`, inter-event `gap_ns`, `sequence`,
`action`, `side`, `price` (printed on non-trade records too), `size`, `flags` decoded bit-by-bit, book-after
(`bid_px/sz/ct`, `ask_px/sz/ct`), `ts_in_delta`. Decode is the official library straight off the payload file
(`ribbon.py:73` `import databento_dbn as DBN`; `ribbon.py:113-127` reads `Action.variants()`,
`Side.variants()`, `F_*`, `FIXED_PRICE_SCALE` off the library rather than retyping them).

Sub-checks:
* **No row bound** — `ribbon.py:41` states it and the SI 10-minute render below printed 4,798 rows unthinned.
* **Backward-`ts_event` hazard handled** — `ribbon.py:305-321` prints `gap_ns = N/A` on the F_SNAPSHOT
  replay rows the schema audit found (57 records, all NKD), rather than a negative "speed".
* **Aggressor semantics correct** — `tape.py:297-317`: `'B' = buy aggressor (+size), 'A' = sell aggressor`,
  "side = the side that initiates", matching the legend and the official docs.

NOTE: `ribbon.py:128-129` and `RIBBON_LEGEND.md:7` both cite `engine/port_m2/test_r2views_fixlane.py:t05`
as the mechanism pinning the printed header to the legend. That file did not exist when this row was first
walked; it landed at HEAD in `be9eec5` during the audit and `t05_legend_terms_are_the_printed_header_terms`
passes. Closed as G-6.

### R-2 — RIBBON_LEGEND.md complete · **PASS (uncommitted)**

`design/RIBBON_LEGEND.md`, 199 lines, appeared on disk mid-audit and was read in full. Checked against every
item D-093.1 enumerates:

| required | where | status |
|---|---|---|
| every action code | §3, lines 62-75 — A/C/M/T/F/R/N with the library name and the event | PASS (incl. the `R`=CLEAR-not-cancel trap and the measured "trade print is not the book update", 47,839/47,839) |
| side semantics incl. **aggressor on trades** | §4, lines 79-93 | PASS (with the explicit trap: `T A` = someone SOLD) |
| every flags bit | §5, lines 97-108 | PASS — all 8 bit positions, including bit 0 which the library does not name (prints `?1`, never dropped) |
| the three clocks + which is authoritative | §7, lines 128-136 | PASS — `ts_event` authoritative, `ts_recv` and `ts_in_delta` explicitly not |
| price scaling | §8, lines 142-144 | PASS — `FIXED_PRICE_SCALE = 1e9`, exact decimal, no rounding |
| size/depth semantics | §2 line 50, §10 lines 176-180 | PASS — and §10 states the schema's *limits* (no depth beyond L1, no order identity, no participant) so they are never inferred by accident |
| sequence and gap interpretation | §9, lines 155-168 | PASS — with numeric bands for burst / quiet / dead |
| null sentinels | §8, lines 145-149 | PASS — UNDEF_PRICE / UNDEF_ORDER_SIZE / UNDEF_TIMESTAMP by name |

Column terms in §2 are exactly the 15 strings `ribbon.py:ACTION_COLUMNS` prints. Verified by comparison of
the rendered header against the table — they match, term for term, in print order.

The legend's own two forward references are both false at audit time: the drift test (G-6) and
"R2-1, enforced in `episode_round.score`" (line 199 — see G-1).

### R-3 — chart panels rendered and LEGIBLE · **GAP (legibility)**

Rendered for the sample day, all three assets, then **read as images by the auditor**:

```
/usr/bin/python3 engine/port_m2/chart_panel.py --day 20240320 \
    --episodes SI-20240320-L-E67,HG-20240320-S-E98,NKD-20240320-L-E56
-> artifacts/cache/port/m2/e6_round/charts/20240320/*.png   (6 panels, 1434x1050)
   receipt: artifacts/cache/port/m2/e6_round/charts/CHART_RECEIPT.tsv
```

**Approach panel: LEGIBLE.** `NKD-20240320-071566-L.approach.png` reads cleanly — 45-minute zoom, SANE mid
staircase, the three causal ZigZag pivots drawn as the confirmation geometry, the confirming pivot marked
with `conf_sec 19:50:46 lag 120s`, the decision second as a red rule, VWAP, and a traded-size / signed-flow
subpanel. The causal footer is on the face of the image ("STRICTLY CAUSAL: nothing after session second
71566 … D-092: this image RENDERS the data — the take is decided on the event sequence").

**Session panel: NOT LEGIBLE.** Both `NKD-...session.png` and `SI-...session.png` fail on the right-hand
level labels:
* labels are **clipped at the right figure edge** — `FVOL_LADDER OPEN_TOKYO q25 +1 402…` loses its price;
* labels **overprint each other** in dense level zones. On `SI-20240320-072016-L.session.png` roughly ten
  labels collapse into unreadable mush between 25.15 and 25.28;
* the decision annotation is itself overprinted — on the SI session panel
  `DECISION 20:00:16 entry_mid=25.245 side=L` is crossed by a level label, and on the NKD panel the entry
  mid is unreadable for the same reason.

A reader cannot name the level it is looking at on the session panel. That is a legibility failure, not a
cosmetic one, and the panel's whole purpose is to say *which levels are in play*.

Determinism: `--verify` reports byte-identical re-renders (`sha_a == sha_b`) for both panels. MINOR defect:
`chart_panel.verify_deterministic()` (lines 698-704) does not pass `episode_id` into `build`, so it proves
determinism of a **variant** render, not of the shipped bytes — the verify-mode approach PNG is 171,236
bytes against the production 173,185. Production renders repeated through both CLI entry points *were*
byte-identical (`f110c48620ae2a4c` twice), so determinism itself holds; the proof is aimed one inch off.

---

## 2. SHEET LAYER — S1..S13, real renders, all three assets

All four episode deep views rendered through the reader's own entry point:

```
/usr/bin/python3 engine/port_m2/episode_round.py --episode <EID> --view
```

Every one returned a full D-042 completeness certificate with **`n_sections=13  n_failed=0
n_leak_refusals=0`** (SI `guard_checks=838`, HG `774`, NKD `556`, SI-news `1137`). Per-row findings:

| row | required | evidence from the render | status |
|---|---|---|---|
| **S3** | path / coverage / runway | `SI_view:45-64` — session open + first sane mid, gap vs settle, phase H/L, `runway to_phase_close=10982s (09:00:00, SCHEDULED)` + `to_sess_close`, `runway_prior` trailing shortfall, **COVERAGE SESSION 31.4% unspent $1665.9** and **COVERAGE TOKYO 70.5% unspent $318.6**, `fvol_source`, 16-pivot causal ZigZag chain | PASS |
| **S4** | levels incl. all kept families + virgin flags | `SI_view:66-90` — 245 levels / 142 in band, `K`=kept `r`=retired per `m2_common.py:81` `KEPT_LEVEL_FAMILIES = FVOL_LADDER, FVOL_BAND, NDAY, PRIOR_DAY, PHASE_HL, VWAP, OR_EXT`; **`V` virgin column per row** (`sections.py:832`) and **`n_virgin` in the family rollup** (`sections.py:875`): `FVOL_BAND=15/178/12 FVOL_LADDER=17/391/12 … PHASE_HL=29/250/15`; OR state table with NOT_OPEN refusals, never prior-day | PASS |
| **S5** | trajectory | `SI_view:92-101` — T-30m/T-15m/T-5m/T-1m/NOW grid for mid, spread, bid_sz, ask_sz, trades/min, sflow/min, rv300, slope, with trailing-60-session z and pct and the MAD-floor `~` marker | PASS |
| **S6** | digests | `SI_view:103-204` — 14 gap-clustered episode digests + every raw event in the last 16.72 s (82 rows), header `n_ev_pre=809 n_ev_90s=207 n_raw=82` | PASS |
| **S7** | book/queue incl. **side-resolved** erosion | `SI_view:206-212` — L1 with spread and SANE flag; 60 s and 300 s windows carrying A/C/M/T counts, rev/s, L1life_ms, c2f, and **`dBsz/min` and `dAsz/min` separately** (that is the side resolution); `refill_after_trade frac=0.459 median_restore_ms=11.0` with swept/no-reaction denominators named | PASS |
| **S8** | flows/fuel incl. **aggressor-signed** streams | `SI_view:214-228` — 60 s/5 m/30 m/phase/session windows with `sflow`, `buy`, `sell`, `buy/sell_vol`; signing is `tape.classify_trades` (`tape.py:316`, DBN aggressor convention); FUEL MAP by ATR band with trapped-above/below; `through_book_600s` with the individual print | PASS |
| **S9** | vol state incl. fvol forecast + surprise + expected-move ladder + **real Nikkei VI on NKD** | `SI_view:230-238` / `NKD_view` S9 — rv nowcasts w60/300/900/1800, bipower + jump_frac, vol_of_vol, `fvol segment=TOKYO sigma_hat=$769.1 range_hat=$1009.7 surprise=0.755`, `move_ladder_$ q10..q90`, `ladder_position`. **Nikkei VI prints on NKD's S12 as `NIKKEI_VI 2024-03-19 … 19.5000`** | PASS — see sanity check below |
| **S10** | profile | `SI_view:240-245`, `NKD_view` S10 — developing POC/VAH/VAL + d_POC + in_VA, **phase_final rows for closed phases** (NKD: TOKYO and LONDON), prior session profile, HVN/LVN ladders, single prints | PASS |
| **S11** | cross-asset | **rendered, and it prints nothing** | **GAP — G-2** |
| **S12** | context, EACH series | see the per-series table below | PASS |
| **S13** | class census cards | `SI_view:274-285` — entry mechanics, cost_rt, wall, exit default, then the D-071 class card and the generation-family census card, both labelled STRICTLY-PRIOR eras only (E5 / 2023) | PASS |

### S12 — every series D-093.1 names, verified as printed values

From the three real renders (SI at 03:56:58Z, HG at 17:57:24Z, NKD at 17:52:46Z):

| required series | printed? | value seen |
|---|---|---|
| COT **disaggregated** | yes, per asset | SI `COT_DISAGG_SILVER net=25794 long=45521 short=19727 OI=144534 d_net_wk=10982`; HG `COT_DISAGG_COPPER net=5783 long=66445 short=60662 OI=219445`; NKD `COT_TFF_NIKKEI net=-1526 long=1464 short=2990 OI=18020` |
| SLV flows | yes (SI) | `SLV_FLOW_OZ 11787888.7789 426831228.5770 0.9138` |
| SHFE inventories | yes (SI, HG) | `SHFE_INV_SILVER 1044791.0000`; `SHFE_INV_COPPER 201687.0000` |
| FRED rates / dollar | yes | `FRED_DGS10 4.3400`, `FRED_T10YIE 2.3100`, `FRED_DFII10 2.0300`, `FRED_DTWEXBGS 120.4003`, `FRED_DEXJPUS 149.1400`, `FRED_DEXCHUS 7.1953` (HG) |
| JGB | yes, all three | `JGB_10Y 0.7740` |
| gold/silver ratio | yes, all three | `GOLD_SILVER_RATIO ratio=86.115 gc=2160.70 si=25.091` |
| release calendar + countdown (compliance windows) | yes | NKD: `next_scheduled FOMC statement 2024-03-20T18:00:00Z **in 0d 00:07:14**`; HG: `**in 0d 00:02:36**`; SI-news: `last_scheduled FOMC statement **16s ago**` |
| vol indices | yes | `GVZ 13.8300`, `VIX 14.3300`, `RVX 21.7500`, `NIKKEI_VI 19.5000` (NKD only) |

`availability_summary n_joined=13 n_refused=0` (SI), `11 / 0` (HG), `10 / 0` (NKD). Every row carries its
own `stamp`, `avail` (availability_ts) and `age_d`, and the revised-value series are named as such.

**Nikkei VI value sanity check (D-093.1 asks for it explicitly).** Sheet prints `19.5000` stamped
2024-03-19. Source `artifacts/reference/port_context/NIKKEI_VI_daily.csv` carries `2024/03/19 → 19.50` —
exact. The file's 2024 distribution is `n=245, min 16.04 (2024-07-01), max 70.69 (2024-08-05)`, with
2024/08/02 = 29.44 and 2024/08/05 = 70.69. That is the real Nikkei VI record for 2024 including the
August 5 yen-carry unwind spike. **This is real data at the right scale, not a placeholder.**

**Compliance windows actually fire.** The day's delta table flags, over 573 episodes:
`14 VETO / 189 HELD / 370 clean`, and the three SI episodes at 20:00-20:05 session time (18:00-18:05 UTC,
i.e. straddling the FOMC statement) all carry `VETO`. The D-077 ±10 min rule is exercised on this day, not
merely implemented.

---

## 3. STUDY LAYER

| row | evidence | status |
|---|---|---|
| oracle schedules renderable for study days | `e6_round.py --day 20240320 --oracle` returns all three assets: HG DP $2,491.25 / 3 seats, NKD $2,660.00 / 3 seats, SI $4,710.00 / 3 seats, each seat with dec / exit / $ / MAE / win / episode id, plus `episodes= rep_winners= oracle_episodes=` summary lines | PASS |
| blind days sealed from oracle | `e6_round.py --day 20240419 --oracle` → `REFUSED: 20240419 is a drawn BLIND day — no outcome access` (`e6_round.py:427-429`); `panel_score` is imported only inside `oracle()` and inside `episode_round.score()` | PASS |
| **contrast sets** | `e6_round.py:51-52` documents `--day D8 --contrast`. Running it: `error: unrecognized arguments: --contrast`. **No implementation anywhere** (`grep -rn contrast engine/port_m2` finds only the docstring and unrelated census code) | **GAP — G-3** |
| outcomes (S14) sequestered from blind trees | walked the actual directories: `artifacts/cache/port/m2/era/E6/BLIND/{SI,HG,NKD}/{20240419,20240422,20240423}` = **9,128 files, 0 matching `.S14.`**; S14 lives in the sibling `era/E6/BLIND_S14/` tree; `sheets.assert_no_s14_access` (`sheets.py:507-536`) walks the read directories at view time and the four audit views reported 556-1,137 guard checks each | PASS |

---

## 4. ENFORCEMENT LAYER

**THIS SECTION MOVED DURING THE AUDIT.** At first inspection none of R2-1 existed. The enforcement lane
then committed `be9eec5` ("port r2 (RED): R2-1 take-enforcement tests fail — take_protocol/n_chart_reads do
not exist yet") and implemented against it. The rows below record the state at the END of the audit window,
with the earlier state noted, because the earlier state is what the four documents asserting "enforced" were
describing.

| row | evidence | status |
|---|---|---|
| access ledger carries `n_ribbon_cmds` | **was broken, now fixed (uncommitted).** It used to be `len(ribbon_cmds)` = the commands the view *printed* = identically 1 — which is why round 1's ledger showed a full house while the ribbon was invoked zero times. `episode_round.py:135-140` now says so in the code and counts **ribbon reads ledgered for this episode**; the authority at score time is the mechanical ledger, not the snapshot | PASS (uncommitted) |
| access ledger carries `n_chart_reads` | added to `ACCESS_COLUMNS` (`episode_round.py:126-129`), with a named legacy default (`ACCESS_DEFAULT = {"n_chart_reads": "0"}`) so old rows migrate rather than being re-labelled | PASS (uncommitted) |
| access ledger carries brief reads | **still absent.** No brief column in `ACCESS_COLUMNS`, no brief ledger, and **no `--brief` entry point** — `e6_round.py:48` documents `--day D8 --brief ASSET`; the CLI still rejects it (`--help` shows only `--deltas --assets --oracle --ep-outcomes --show --with-outcomes --traj-check --traj-cost --no-traj`). `grep -rn "brief" engine/port_m2/episode_round.py` → nothing. | **GAP — G-4 (D-093.2)** |
| `episode_round.score` refuses/flags takes without raw reads | **now implemented (uncommitted).** `take_protocol()` (`episode_round.py:621-676`) joins **both** sides — the episode's own ACCESS row *and* the mechanical `RIBBON_ACCESS.tsv` (by member cid) and `CHART_RECEIPT.tsv` (by episode or rep cid) — and marks any TAKE with zero of both `PROTOCOL_INVALID`. Wired into `score()` at lines 1002-1007, with a `protocol` column on `SCORE_COLUMNS` and a `TAKE_COLUMNS` receipt naming every flagged take and why. It **flags rather than refuses** (docstring: "The day is still SCORED; the take is NAMED"), which D-093.1's "refuses/flags" permits but `PORT_TEACHER_ROUND_SPEC.md:61` ("refuses") does not yet say. | PASS (uncommitted) |
| red-first fixture, run by the auditor | `engine/port_m2/test_r2views_fixlane.py` now exists at HEAD (`be9eec5`, 422 lines) and was RED there by construction. Run in the working tree by this audit: **8/8 PASS** — `t01_take_without_ribbon_or_chart_is_protocol_invalid`, `t02_take_with_a_ribbon_read_is_not_flagged`, `t03_access_ledger_migrates_onto_n_chart_reads`, `t04_action_grain_prints_every_event_and_never_thins`, `t05_legend_terms_are_the_printed_header_terms`, `t06_backward_ts_event_gap_prints_na`, `t07_trajectory_now_point_reproduces_the_sheet`, `t08_chart_render_is_deterministic` | PASS (uncommitted) |

ONE SUBSTANTIVE OBJECTION TO THE RULE AS WRITTEN. `_zero_evidence()` (`episode_round.py:610-618`) marks a
take invalid only when ribbon reads **and** chart reads are both zero — so **a chart-only take is
PROTOCOL_OK**. D-092.1 and the chart module's own law 3 both say the image renders the data and never
replaces the sequence. Under the current rule a reader could satisfy R2-1 for a whole round without opening
the event stream once. The rule should require the ribbon; the chart should be recorded, not accepted as a
substitute. Recorded as G-12.

Also verified green: `ribbon.py` writes one row per invocation to
`artifacts/cache/port/m2/ribbon/RIBBON_ACCESS.tsv` with `cid, from_sec, to_sec, grain, n_events,
n_rows_printed, tokens_proxy, decoder, round, caller` — the consumption evidence the gate now reads.

Also verified green:
* **R2-2 trajectory differential** — `e6_round.py --day 20240320 --traj-check --assets NKD`:
  `compared=846 agree=846 disagree=0 refused_recompute=0 absent_in_triage=0`. The recomputed NOW point of
  every trajectory column matches the triage row's own number on every episode.
* **Access gate on ranking** — `missing_access()` (`episode_round.py:514-526`) names the episodes with no
  deep read and `score()` raises `AccessRefusal` rather than scoring a partially-read day.

---

## 5. THE ADDED ROWS (R2-8 / R2-9 / R2-10 / extraction artefacts)

| row | evidence | status |
|---|---|---|
| **R2-8** written-reasoning tooling (blind-safe decision journal, committed same-day) | `grep -rln "decision journal\|DECISION_JOURNAL\|R2-8" engine/ design/ provenance/` returns **only prose** — the spec, the journal, ERA_NOTES. There is no journal path, no writer, no schema, no blind-safety check, no commit point. | **GAP — G-5 (BLOCKING)** |
| **R2-9** ledger discipline mechanically supported | Partial. Per-day ledgers exist as *files* (`E6_CALLS_20240118.tsv`, `E6_BLIND_D1_20240419.tsv`, `E6_BLIND_20240422.tsv`, `E6_BLIND_20240423.tsv`) and were committed on their days (`8d9c75d "E6 day 1 sealed"`, `bacb979 "E6 BLIND SEALED"`) — so the *practice* has a precedent. But there is **no mechanism**: no per-day commit gate, and the rubric channel (`e6_calls.py`, unchanged since `bacb979`) still computes the seat schedule from the rubric that R2-9 retires from takes. | **GAP — G-7** |
| **R2-10** curriculum facts render in the briefing | The facts exist and are correct, in `provenance/port_m2/ERA_NOTES_E6.md:126-134`: `SEAT_LIVE (unspent>=$700 AND runway>=18000s): 2.62x on 524 episodes, p=2.9e-18, positive 6/6 days`; `runway<4800s = 0.04x (death)`; `FALSIFIED CUES … level_tested_held 0.88x AND INVERTED (virgin 1.67x)`; `SI 2024-04-22 TOKYO shorts — 29 winners in 45 episodes incl. the round's 10 largest payers, ALL skipped`. Cross-checked against `E6_EXTRACTION.md:476-477, 516, 671-679` — the numbers agree exactly. **But `design/READER_BRIEFING.md` (the document the spec calls "the briefing", frozen v1 2026-08-14) carries none of them**, and carries no ribbon dictionary either (R2-7 says "the round briefing carries a RAW-STREAM DATA DICTIONARY"). | **GAP — G-8** |
| `design/TEACHER_FEATURES_V1.md` at HEAD | present, committed (`846a54e`), 17,448 bytes | PASS |
| `provenance/port_m2/E6_EXTRACTION.md` at HEAD | present, committed (`846a54e`), 77,010 bytes | PASS |
| **R2-11** cumulative cue ledger (specced at HEAD `7429abc` during this audit) | `provenance/port_m2/TEACHER_CUE_LEDGER.tsv` does not exist | **GAP — G-9** |

---

## 6. ECONOMICS — the measured cost of one full-fidelity day, and the 1.3M arithmetic

All figures **measured on 2024-03-20 by this audit**, with `m2_common.count_tokens` (proxy `M2-PROXY-2`);
image cost at the standard `w x h / 750` for the 1434x1050 panels = **2,008 tokens per panel**.

### 6.1 What each piece actually costs

| piece | measurement | tokens |
|---|---|---|
| session brief, SI (full episode deep view incl. sheet) | rendered | 8,491 |
| session brief, HG | rendered | 8,236 |
| session brief, NKD | rendered | 8,230 |
| **3 briefs (one per asset)** | | **24,957** |
| day digest, 573 episodes x 3 assets, WITH R2-2 trajectories | `--traj-cost` | **82,250** |
| — the same digest, scalar-only (pre-R2-2) | `--traj-cost` | 63,737 |
| — R2-2's own cost | | +18,513 (32.3/episode) |
| ribbon legend (session-constant, once) | `RIBBON_LEGEND.md` | 4,678 |
| reader briefing (once) | `READER_BRIEFING.md` | 2,329 |
| era notes E6 (once) | `ERA_NOTES_E6.md` | 4,104 |
| chart pair (session + approach) | 2 x 2,008 | 4,016 |

### 6.2 The raw sequence — the number that decides everything

Action-grain ribbon, measured on real windows at the FOMC decision moment:

| window | SI | HG | NKD | 3-asset |
|---|---|---|---|---|
| `T-600 .. T` (10 min) | 4,798 ev → **237,089 tok** | 1,412 ev → 72,438 | 1,350 ev → 63,760 | 373,287 |
| `T-120 .. T` (2 min) | 2,438 ev → **120,522 tok** | 179 ev → 9,637 | 170 ev → 8,463 | 138,622 |

The rate is stable at **49.4 tokens per event row**. The whole cached session at full fidelity:

| asset | cached events | ev/s | tokens at full fidelity |
|---|---|---|---|
| SI | 826,567 | 12.2 | 40,832,410 |
| HG | 530,954 | 7.8 | 26,229,128 |
| NKD | 232,261 | 4.1 | 11,473,693 |
| **3-asset day** | **1,589,782** | | **78,535,231** |

**One 3-asset day, every event, is ~78.5M tokens. A 1.3M-token round is 1.7% of one day.** SI alone is 52%
of the day's events and 2.6x HG — a 3-asset full-fidelity round is dominated by SI's tape.

### 6.3 Depth over breadth, arithmetically (D-092.2)

Fixed cost per round day = 3 briefs + digest = **107,207**. One-time session-constant material (legend +
briefing + era notes) = **11,111**. Cost of one ribbon-decided take = sheet (8,300) + chart pair (4,016) +
ribbon:

* at a **2-minute** decision window, mean across assets = 46,207 → **58,523 per take**
* at a **10-minute** decision window, mean across assets = 124,429 → **136,745 per take**

| round shape | fixed | left of 1.3M | takes at 2 min | takes at 10 min |
|---|---|---|---|---|
| **6 days** (3 study + 3 blind, as drawn) | 654,353 | 645,647 | **11.0 total = 1.8/day** | **4.7 total = 0.8/day** |
| **4 days** | 439,939 | 860,061 | 14.7 total = 3.7/day | 6.3 total = 1.6/day |
| **3 days** | 332,732 | 967,268 | 16.5 total = 5.5/day | 7.1 total = 2.4/day |
| **2 days** | 225,525 | 1,074,475 | **18.4 total = 9.2/day** | 7.9 total = 3.9/day |

The oracle on this day pays **exactly 3 seats per asset = 9 seats/day** (§3 above). So the reader needs on
the order of **9 ribbon-decided takes per day** to be able to reach the oracle's seats at all.

**THE COLLISION, STATED (D-092.2 requires it surfaced, not resolved silently):** at 1.3M tokens, the drawn
6-day round buys **1.8 ribbon-decided takes per day** — it cannot reach the oracle's 9 seats, and R2-1 as
specified ("raw ribbon read REQUIRED before any TAKE") would be unsatisfiable across a normal take rate.
The only shape at 1.3M that supports ~9 full-fidelity takes/day is **2 days** at 2-minute windows.
D-093.3's "~4-6 days full fidelity" is affordable only at ~2-4 takes/day.

Two cheap levers, both measured:
1. **Drop the R2-2 trajectory columns** (they are triage hints only, per R2-6-CORRECTION): saves 18,513/day
   = 111k over 6 days ≈ **2 more full-fidelity takes**.
2. **Narrow the default decision window.** 10 min → 2 min is a 2.3x cut in take cost. On SI the events are
   heavily concentrated near the decision second (2,438 of 4,798 in the last 2 minutes of a 10-minute
   window), so the narrow window keeps most of the information that matters and drops the quiet tail.

---

## 7. THE GAP LIST

| id | gap | blocking? |
|---|---|---|
| ~~**G-1**~~ | ~~R2-1 is not enforced~~ — **CLOSED DURING THE AUDIT.** `take_protocol()` + `n_chart_reads` + the `protocol` column landed in the working tree against the RED fixture `be9eec5`; fixture 8/8 green when run by this audit. Remains uncommitted (G-11) and carries G-12. | closed |
| **G-2** | **S11 CROSS-ASSET is 100% dead.** `sections.py:1801-1826` computes the other asset's session second as `decision_ts - o_open`; all three assets share `open_utc = 1710885600`, so that second always **equals** the decision second, and `m2_common.CausalGuard.sec` (line 897, strictly `<`) refuses it every time. Measured: 800 refusals in 800 rows across a 400-sheet corpus sample; **zero populated cross-asset rows exist anywhere**. An entire owned data source renders as a refusal message on every sheet in the corpus. One-line fix (use `osec - 1`, which is what the section's own downstream `searchsorted(..., "left") - 1` already assumes). | **YES** |
| **G-3** | **Contrast sets (D-090.2) not implemented.** `e6_round.py --contrast` is documented and rejected by the CLI; no implementation exists. It is a named element of the frozen curriculum in the spec. | **YES** |
| **G-4** | **Briefs are not mandatory-daily-read and reads are not recorded (D-093.2).** No `--brief` entry point, no brief ledger, no column — and this survived the R2-1 pass that added `n_chart_reads` beside it. D-093.2 exists precisely because round 1 measured 2-3 context views/day across 3 assets. | **YES** |
| **G-5** | **R2-8 written-reasoning tooling absent.** No decision-journal path, writer, schema, blind-safety check, or commit point. R2-11 declares this journal to be the extraction substrate, so R2-11 depends on it. | **YES** |
| ~~**G-6**~~ | ~~no fixture for any R2 mechanism~~ — **CLOSED.** `engine/port_m2/test_r2views_fixlane.py` is at HEAD (`be9eec5`) and covers all eight R2 mechanisms including the `t05` legend/header drift guard that `ribbon.py:128` cites. | closed |
| **G-12** | **The R2-1 rule accepts a chart-only take.** `_zero_evidence()` requires ribbon reads **and** chart reads to both be zero before flagging, so a take backed only by a rendered panel is `PROTOCOL_OK`. D-092.1 and `chart_panel.py` law 3 both say the image never replaces the sequence. The rule should require the ribbon. | **YES** |
| **G-7** | **R2-9 has no mechanism.** Same-day ledger commits are practice, not gate; `e6_calls.py` still drives seats off the rubric R2-9 retires. | no |
| **G-8** | **R2-10 facts and the R2-7 dictionary are not in the briefing.** Both live elsewhere (ERA_NOTES_E6.md; RIBBON_LEGEND.md) and both are correct; `design/READER_BRIEFING.md` is still v1 and carries neither. | no |
| **G-9** | R2-11's `provenance/port_m2/TEACHER_CUE_LEDGER.tsv` does not exist (specced at `7429abc` during this audit). | no |
| **G-10** | **Session chart panel is not legible** — right-edge label clipping and label overprinting, including over the decision annotation. Approach panel is fine. | no |
| **G-11** | **The whole R2 view stack is UNCOMMITTED.** At HEAD `7429abc`, `ribbon.py --grain action`, `e6_round.py` trajectories, `chart_panel.py` and `RIBBON_LEGEND.md` are working-tree only. Nothing can launch against them until the r2-views lane commits. | **YES (mechanically)** |

---

## 8. VERDICT

**BLOCKED.**

What is genuinely excellent and needs no further work: the raw decode path (official library, every field,
every flags bit, the snapshot hazard handled), the ribbon legend, the sheet layer S3-S10 and S13, the S12
context layer (every series D-093.1 names prints, with real availability lags and a value-verified Nikkei VI),
the oracle/blind sequestration, the S14 wall, the R2-2 differential, and — as of the end of this audit
window — the R2-1 take-protocol gate with its red-first fixture.

What blocks launch:
* **G-2** — S11 delivers nothing on any sheet ever written. A whole owned data source is present in form and
  empty in fact, on all three assets, at every decision second in the corpus. One line.
* **G-12** — the new R2-1 rule lets a chart-only take pass, which is exactly the substitution D-092.1 forbids.
* **G-3 / G-4 / G-5** — contrast sets, brief consumption, and the R2-8 written journal are specified and
  unbuilt. G-5 is load-bearing twice over: R2-11 names that journal as the extraction substrate.
* **G-11** — the entire R2 view stack (action ribbon, trajectories, charts, legend, take-protocol) is
  working-tree only. Nothing can be launched against uncommitted code.

The pattern behind G-2, and behind the `n_ribbon_cmds`-was-always-1 defect the enforcement lane found and
fixed mid-audit, is the same one D-093 was written about: **a source is designed in, its section renders, and
nobody ever checked whether a value came out the other end.** That is the case for keeping this audit as a
standing pre-round gate rather than a one-off.

The economics are the other launch input: at 1.3M tokens the drawn 6-day shape supports **1.8** ribbon-decided
takes/day against an oracle that pays **9** seats/day. That is a law collision under D-092.2 and it is
surfaced here with its arithmetic rather than resolved.
