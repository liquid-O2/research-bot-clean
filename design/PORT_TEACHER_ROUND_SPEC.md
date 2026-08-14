# PORT_TEACHER_ROUND_SPEC — the corrected round, E6 increment (FROZEN 2026-08-15)

## 1. DESIGN
SCOPE: ONE era increment — E6 (2024H1), fully instrumented (D-083). Walk-forward, era-matched (D-034/D-088):
STUDY = 3 stratified E6 days (D-076/D-087: spread across months/regimes per the coverage table, warm-up/taint
excluded) -> SEALED BLIND = 3 later E6 days (chronological, day-complete). Day-one token burn measured; the
orchestrator sets further scale from it (D-081/D-086) before any continuation.
READER: Opus, pinned MAX effort (workflow per-agent effort; D-072/D-078). EPISODE GRAIN (D-080): every episode
of every round day deep-read — session-brief + per-episode delta views (D-085 lossless format; builder tooling
= episode_round.py + ribbon.py at HEAD), the on-demand ribbon for any causal window, retrieval over prior
studied history only. ~478 deep reads per 3-asset day (measured).
STUDY CURRICULUM (D-090/D-091 as evidence-graded in the journal 03:35Z; oracle exposure = study-taint):
worked examples from the era's oracle schedules FIRST; contrast sets; predict-the-oracle then instant oracle
feedback per rep (fading to end-of-day feedback on study day 3); ORACLE OVERLAP/CAPTURE as primary metric
beside the D-086 full-spectrum extraction goals; self-explanation of missed picks; Brier-scored probability
per call; post-day consolidation rewrite of the era notes. (Perceptual flash: DROPPED for this increment —
flagged weakest + budget law.) The information-ceiling measurement runs lane-side on E6 (hindsight-fit bound)
and is reported beside the round.
BLIND (D-082 natural decisions): the reader ONLY trades — call + probability + light what-I-looked-at line
per episode; pre-mortem per TAKE; compliance flags (D-077 ±10min incl. held-into) = hard veto; V2 advisory
(RETAIN_UNPROVEN); no other constraint. ALL blind days sealed before ANY unblinding; scoring is the
orchestrator's, on the corrected bars: (a) margin vs the PRE-REGISTERED baseline arm (median reported beside;
max-of-N retired), (b) take-pool mean > 0 AND precision >= 1.3x base (D32 restatement), (c) capture vs the
era's day ceilings, plus ORACLE-OVERLAP and the per-era curve entry (D-088). Compliance coverage reported
per era (CC-M2-24.4a).
EXTRACTION (post-round, D-082/D-086): transcript+outcome pairing across the full spectrum; features derive
per D-078 primacy. The orchestrator's OWN capped read (D-086: <=100k tokens, natural-decision, sealed) runs
on ONE of the blind days beside the reader.

## 2. CONFORMANCE RECEIPT (D-089 both halves; walked against DIRECTIVES.md at HEAD)
SATISFIED-HOW (applicable directives): D-001 (this spec = post-review design; one round, no fix loops) ·
D-002/D-005 (orchestrator-designed; lanes implement; reader=max per D-072) · D-016/D-081/D-086 (one increment,
day-one burn measurement, caps) · D-017 (no weak forms: full episode coverage, certified corpus, real ribbon)
· D-019/D-021/D-030/D-046/D-048 (bars/risk laws embedded in scoring + briefing) · D-033/D-035 (confirmed-
extreme object; one-way taint; used-case ledger) · D-034/D-058/D-088 (era-matched walk-forward, study->blind
within E6) · D-036/D-073 (day-complete; days are the draw unit; reader separates wheat) · D-042/D-056/D-057
(certified 0-leak corpus; all data incl. fvol/VI/context; availability-lagged; leak fixture green) · D-054
(sane mids throughout) · D-059 (era-tagged knowledge; library re-test opens study; per-era curve) · D-068-as-
corrected (graded briefing, duty-to-contradict, no forced formats) · D-070 (style-agnostic; confirmation-
validity framing per journal 04:05Z) · D-074 (watchers+heartbeat) · D-075/D-079 (teacher-first; bars pre-
registered; iterate-on-fail ladder intact) · D-076/D-087 (stratified days; coverage table attached to the
draw) · D-077+UPDATE (flag-based compliance, ±10, avoidance posture) · D-080 (episode grain; no summary-only
decisions; ranking objective folded into oracle-overlap + payment metrics) · D-082 (natural decisions in
blind; extraction post-hoc) · D-083 (E6 full instrumentation verified 2,240/2,240 forecaster joins, real VI)
· D-084/D-085 (model carries scale; this round is teaching+evidence) · D-089-EXT (evidence grades attached:
curriculum statuses per journal 03:35Z; oracle-overlap = metric not sole objective per P016 evidence; flash
dropped on evidence) · D-090/D-091+CORR (curriculum as amended; transfer map N/A this single-era increment).
N/A: IWM-specific (D-003/011/022/024/025), data-fetch (D-047/060), episode-grouping internals (D-065/066,
consumed via tooling), D-064 mechanisms (M3-stage), D-063 (portfolio-level). EVIDENCE HALF: every design
element above cites its evidence grade or law; no element contradicts a committed finding (checked against
the journal record 2026-08-13..15).

## 2. ROUND-1 DIAGNOSIS + ROUND-2 REVISIONS (2026-08-15; conformance: D-080/D-082/D-085/D-089 both halves)
ROUND-1 VERIFIED DEFECT (D-080 VIOLATION, orchestrator's): blind decisions were digest-only — the ribbon was
invoked 0 times in 158 tool calls; per-episode flow/book information was single-scalar-at-decision-second.
The reader's calibrated 18% precision = the information ceiling OF THE DIGEST (its cues were all path/level/
capacity; all 5 max-loss takes were wrong-side confirmations whose live-side markers — flow flip, erosion
sequence — are sequence-visible only). The view was the ceiling, not the judgment.
ROUND-2 (same laws + these revisions):
R2-1 RIBBON-MANDATORY TAKES: digest pass -> shortlist -> raw ribbon window read REQUIRED before any TAKE;
     enforced: episode_round.score refuses TAKEs whose access rows carry n_ribbon_cmds=0. (~+40k tok/day.)
R2-2 SEQUENCE DELTAS: f_sflow/dBsz/dAsz/refill/spread columns become 3-point trajectories (t-10m/t-5m/now);
     flips and erosion trends visible per episode. (~+25 tok/episode.)
R2-3 VOL-CLASS-MATCHED STUDY: study days may draw HIGH-vol days from the walk-forward past (E5 2023H2,
     era-tagged per D-059) so taught vol class matches tested class; blind stays era-matched (D-034/D-088).
R2-4 LOSER-SIGNATURE VETO: the extraction cue census's wrong-side signature enters the curriculum as a named
     veto pattern (tested, not assumed, in round-2 blind).
SEQUENCING: round 2 launches after (a) the extraction lane's cue census lands and (b) the view upgrades
R2-1/R2-2 are built+verified; budget per D-086 (~150k tok/day envelope measured).
R2-5 CHART IMAGES (user): every deep view includes RENDERED CHART PNGs — (a) session-so-far panel (causal
     mids, kept-family levels, phase boundaries, episode markers, VWAP/bands) and (b) episode approach panel
     (final ~30-45min zoom to the decision second, level lines + confirmation geometry). Strictly causal
     (nothing past decision_ts), deterministic rendering, committed receipts; the reader Reads them as images.
R2-6 ACTION-TYPED RAW RIBBON (user): the ribbon prints the DECODED DBN event stream — ts, ACTION
     (Add/Cancel/Modify/Trade/clear per Databento MBP-1 semantics), side, price, size, flags, seq, book state
     after — verified against the qr_dbn decoder's field semantics; the reader sees the true order-book story
     (who adds, who pulls, who hits), not derived summaries.
