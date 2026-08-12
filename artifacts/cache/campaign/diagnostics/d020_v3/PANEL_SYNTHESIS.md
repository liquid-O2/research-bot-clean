# PANEL_SYNTHESIS — what $70 of external readers actually taught us

Permanent record of the four-reader panel (Opus-max, Grok, GPT, DeepSeek) on the IWM
confirmed-extreme roster.  Sources: `OPUS_METHOD.md` + `OPUS_EXAM_CALLS.tsv`,
`grok_room/GROK_METHOD.md` + `STUDY_NOTES_GROK.md`, `gpt_room/STUDY_NOTES_GPT.md`,
`deepseek_room/STUDY_NOTES_DSK.md` + `DSK_METHOD.md`.

**The measurement that orders this document.**  Only ONE reader produced measured
positive lift on its own calls: Opus-max, 1.58x taken-vs-skipped on the blind round.
Grok, GPT and DeepSeek produced no measurable lift on their calls.  Their *verdicts*
are therefore not evidence, but their *observational constructs* are — three readers
who never saw each other's work naming the same object is a strong prior that the
object exists.  So: Opus's method is treated as the judgment to encode; the other
three are mined for feature ideas only, and weighted by convergence.

---

## 1. Per reader — the decisive evidence objects

### OPUS-MAX (the only positive-lift reader; 11/40 takes, 27.5%, all class B)

| # | object | fields it is computed from | why it was decisive |
|---|---|---|---|
| O-1 | **Capacity arithmetic ("can this pay $700 AT ALL?")** | `phase`, minutes-to-close, `sigma_scale_bps`, `ATR14`, `VB_BUDGET_CONSUMED`, realised range, bp distance to session high/low, intraday VWAP, prior close, prior high/low, 5d/20d edges | 36/40 declarations cite it in `primary` and 28/40 in `against` — it BEATS good signals rather than agreeing with them.  Roughly a third of the set died here before any signal was read.  It is the reason the take rate is 27.5% and the reason there are no class-A calls. |
| O-2 | **Give-back as a fraction of the objective + confirmation lag** | entry mid, pivot mid, distance to nearest magnet, `confirm_delay_s` | The single most-reused hand computation.  Refuse when give-back >= the first magnet (029: 41bp given back against a 24bp VWAP target); accept up to ~30% (015 cost 11bp against 51-107bp).  Fast confirmations (<90s) were systematically the better trades. |
| O-3 | **Cross-stream agreement AT MAGNITUDE** | `signed_flow` z and clock-norm ratio, `option_delta_dir` z and clock-norm ratio, section (10a) delta/gamma/vanna at `now` vs 60-minute cumulatives | The cleanest take in the set (006) had stock flow at -12.31 sigma and option delta at -12.52 sigma **at exactly the same 47.7x clock-norm multiple**.  The failure archetype is a one-stream extreme with the other contradicting (003: +9.89 vs -2.88; 016: -14.35 vs +17.54).  *"Build the agreement statistic, not the individual z-scores."* |
| O-4 | **Hedge durability = Greek flow x 0DTE composition** | `option_delta_dir`, vanna, `zerodte_share`, `PROXY_VOL` slope | The SAME \|z\| ~ 15-18 delta reading meant opposite things by 0DTE share.  Took the non-0DTE versions (021 at 2%, 034 at 0%, 039 at 12.7%) because the exposure must be carried and hedged; refused the 0DTE-heavy ones (005 at 56%, 022 at 53%, 026 at 58%) because the hedge expires with the contracts.  The one 0DTE-heavy take (015, 86%) required `PROXY_VOL` to be expanding. |
| O-5 | **Elasticity read as a pair, with a known defect** | `absorption` clock-norm ratio, `depth_at_touch` clock-norm ratio, `signed_flow` clock-norm ratio | The no-travel signature — absorption <= 0.3x norm with depth >= 1.5x norm — was the most reliable skip trigger (8 of 29 skips).  Caveat applied by hand every time: `absorption` = \|move\|/signed-kshares, so anomalous flow mechanically deflates it; whenever the flow ratio exceeded ~50x the absorption reading was discounted. |

Its 466-case exam declarations reduce almost entirely to two numbers and one
conjunction: `giveback 22bp into a 90bp runway` (39 reasons cite a bare `runway Xbp`,
27 cite the give-back-vs-runway pair) and `flow +9.2z with opt delta +4.7z at 0pct
0DTE`.  Exam result: 5 TAKE / 461 SKIP.

### GROK

| # | object | fields | formula core |
|---|---|---|---|
| R-1 | **Four-cell flow x travel matrix** (their most portable object) | `EPISODE DIGEST net signed` x `travel bps`, `signed flow (shares)` at T-30m..now | cell = sign(flow vs side) x sign(travel vs side).  with x with = agreement; against x with = absorption, **trade the refusal**; with x against = absorbed, skip.  *"Raw signed-flow z as a veto is the most expensive standard error."* |
| R-2 | **S2-lite and the quiet-tape inverse** | same | `\|net signed\| > 50,000 AND \|travel\| <= 3bp` = absorption not agreement.  `\|net signed\| <= ~1k AND \|travel\| >= 8bp` at a reclaiming pivot = enough for B. |
| R-3 | **Leftover vs live** | last-60s ribbon direction, spot vs the extreme, confirm age | `leftover_frac = \|last-60s travel\| / \|impulse travel since pivot\|`.  Certificate candidates sit 60-120s after the extreme; if the last 60s already spent the move, the certificate is C.  A stale 12-21min confirm is lethal in a coil and payable at a named-level stall. |
| R-4 | **Runway to the next UNUSED level** | `runway`, the NAME of the nearest level, `day position` | Runway to the level you are already standing on is not a veto; gate the next unused print.  Skip < 8bp, C-cap 8-20bp. |
| R-5 | **0DTE asymmetry is location-conditional** | `0DTE share` at the pivot minute, `signed delta flow`, extreme type (LL/HL/LH/HH) | WITH you at an LL with no flow flip = poison; WITH you at a trend-day HL = dip-buy; AGAINST you at an HH with the stock also selling = fuel.  The standard "0DTE spike = climax fade" is half right. |

### GPT

| # | object | fields | formula core |
|---|---|---|---|
| P-1 | **Flow-to-travel inversion** | `EPISODE DIGEST net signed / travel bps`, `FINAL 60s RIBBON` | Aggressive flow is informative only through the price response it buys.  -569,755 shares with +158.87bp travel is bullish absorption. |
| P-2 | **Block-contamination quarantine** | ribbon `size / conc / flags` (BLOCK, THROUGH, SWEEP) vs episode net and Greek z | If one print is comparable to the episode net, recompute the read without it.  Extended by GPT into a **reclaim fraction**: `reclaim_frac = (p(t+D) - p(t0)) / -disp` over 30-60s of ORDINARY prints — *block size predicts nothing after reclaim*. |
| P-3 | **Boundary acceptance, not raw runway** | `day position`, `runway`, `LEVELS distance bps`, final executions relative to the exact day high/low | Tiny runway does not reverse a trade — 2.1bp and 0.3bp boundaries both broke and paid.  What kills is *aggression terminating exactly at the boundary* (case3121: perfect alignment, ask-throughs stopped at 173.570 against a 173.575 day high, immediate failure).  Feature = pressure per bp of boundary progress. |
| P-4 | **Completed state transition outranks the pivot label** | last 4-8 `SWING STRUCTURE` rows | Do not fade an HH because it is an HH.  Completed HH-HL transitions made the best longs; unrepaired LH-LL chains rejected them.  Qualifier: a 2-cent marginal new extreme is a probe, not a transition. |
| P-5 | **Translation freshness / residue** | episode spans, `pivot at / confirmed at / decision`, time-to-close | `residue = travel(last subepisode) / travel(governing episode)`; value required fresh post-confirmation translation AND clock. |

### DEEPSEEK

| # | object | fields | formula core |
|---|---|---|---|
| D-1 | **Spread explosion at the confirmed pivot** (their #1 cross-era field) | `spread bps` + clock-normed z | z > 2 (era-1/2), z > 5 (era-3, "ironclad"); observed 2.51 / 2.80 / 4.25 / 9.20 / 10.87.  A liquidity hole at the extreme is genuine stress. |
| D-2 | **Hollow flow / absorption asymmetry** | `signed flow` z, `absorption bps/kshare`, episode net x travel | `hollow = 1[\|flow z\| > theta] AND 1[absorption < 0.06]`, signed OPPOSITE the flow.  Same object as R-1/P-1 under a different normalisation. |
| D-3 | **THROUGH-cascade run length** | ribbon `touch` + `THROUGH` flag runs | longest run of consecutive same-touch through-prints; threshold >= 5 (observed 7-15).  Horizon-decaying: 30m+ in era-1, 2-15m in era-3 — emit as a SHORT-horizon channel. |
| D-4 | **Greek co-extremity count + charm sign** | delta/gamma/vanna/charm z, `0DTE share` | `n_extreme = sum 1[\|z_g\| > 3..4]`; a four-greek surge marks a dealer-engineered pivot (skip).  `charm_dir` with \|charm z\| > 10-15 is directional.  Also: the FREQUENCY of "all four greeks quiet" is itself a regime meter (13% in era-1 -> 57% in era-2/3). |
| D-5 | **runway / ATR14 with a hard cut, overridden by level proximity** | `runway`, `ATR14`, `LEVELS distance bps` | `runway_frac < 0.03` hard skip, `< 0.10` risky, `> 0.25` green — UNLESS the pivot is sitting within 10-15bp of a multi-day level with the charm sign aligned, in which case location beats the runway gate. |

---

## 2. Convergences — where independent readers landed on the same object

| convergence | who | strength |
|---|---|---|
| **C-1. Flow is informative only through the price response it buys.**  Signed flow crossed with realised travel, as a signed CELL with degenerate corners, not as a z-score. | Opus I-2 (hidden supply), Grok R-1/R-2, GPT P-1, DSK D-2 | **4/4 — unanimous.**  The single strongest convergence in the panel.  Also the one thing every reader says is the most expensive standard error to get wrong. |
| **C-2. Capacity/clock arithmetic beats every signal.**  Whether the remaining clock, the unspent range and the distance to the next magnet can physically pay the target — evaluated BEFORE any signal is read. | Opus O-1/O-2 (36/40), Grok R-4, DSK D-5, GPT P-3/P-5 | **4/4**, and it is the one object the positive-lift reader ranks first.  The readers disagree only on the metric (bp-to-magnet vs runway/ATR vs boundary acceptance). |
| **C-3. Location is BEHAVIOUR AT a named level, not distance to it.**  Stall-at vs already-through; acceptance beyond vs aggression terminating at; runway to the next UNUSED level. | Grok R-4, GPT P-3, DSK D-5 | 3/4 (Opus's magnet arithmetic is the distance-only version). |
| **C-4. Freshness / staleness / leftover.**  `pivot_age_s`, `confirm_lag_s`, leftover fraction, time-to-close — the certificate candidate sits 60-120s after the extreme and most of the impulse is often already in. | Opus O-2, Grok R-3, GPT P-5 | 3/4, and it is absent from v2 except as a raw `C_confirm_lag`. |
| **C-5. The pivot LABEL is not the pivot.**  Read the surrounding chain as a sequence; a marginal new extreme is a probe. | Opus I-8, GPT P-4, Grok R-4, DSK | 4/4 — but v2 measured this (`N_` tier) and found **no blind contribution**. |
| **C-6. 0DTE composition flips the meaning of the same Greek magnitude.** | Opus O-4, Grok R-5, DSK D-4 | 3/4, with the same direction of effect and different location conditioning. |
| **C-7. Block/anomalous-print contamination inverts the headline aggregate.** | Opus G1 (2 of 40 packs inverted), GPT P-2, DSK D-3 companion | 3/4 — but v2 built it (`K_` tier) and measured it firing on ~4% of seconds, too rare to move an AUC. |
| **NEGATIVE CONVERGENCE — the unanimous do-not-build list.**  Traded-IV call-put skew alone; urgency / at-touch fraction alone; `depth_at_touch` alone; prints/min alone; T-15m/T-30m flow bins alone; requote latency; `valid_bucket_fraction`; standalone charm/vanna/gamma \|z\|; block size after reclaim; PROXY_VOL *direction* (GPT dissents from Opus here). | 3-4/4 each | This list is as valuable as the positive one: it is a list of things v1/v2 already spend columns on. |

**The one place the panel splits.**  Opus makes `PROXY_VOL` slope a GATE on every flow
signal (O-4, I-6); GPT says it "appears in wins and failures" and must stay a modifier;
Grok says a zero reading is a dead sensor, not low vol.  v2's `Y_` tier measured no
blind contribution, which sides with GPT.

---

## 3. The codifiable shortlist — formula sketches

Marked `[v3]` where this lane built it, `[v2]` where it already existed, `[open]` where
it is specified but deferred.

**S-1 `[v3]` Net runway (capacity refinement).**  `runway_bps` = bp distance from the
entry mid to the NEAREST magnet in the trade direction (not the first payable one);
`net_runway = runway_bps - giveback_bps`; `giveback_over_runway = giveback / runway`;
`payable = min(erm_sigma_bps, objective_bps - giveback_bps)`.  Opus's own sentence
"giveback 22bp into a 90bp runway" is the difference, not the ratio v2 built.

**S-2 `[v3]` The gate conjunction as one integer.**  `gates_failed = 1[nearest magnet <
40bp] + 1[giveback >= runway] + 1[ATR-clock expectation < 70bp] + 1[phase > 0.72] +
1[budget >= 1.0 or range >= ATR] + 1[price already through the pivot]`.  Opus stopped at
the first hard failure, so the COUNT is the statistic; `gates_failed == 0` is the
capacity conjunction on its own, with no signal read at all.

**S-3 `[v3]` Joint z-magnitude agreement, graded by balance.**  `agree(streams, theta) =
sign * min|z|` when all streams share the candidate-oriented sign and `min|z| >= theta`,
for theta in {2, 3, 5} over {stock flow, option delta} and widened to {+vanna},
{+non-0DTE gamma}.  `z_balance = min|z| / max|z|` grades it (Opus's cleanest take was
-12.31 against -12.52).  Crossed with S-1 as `agree x net_runway` and with S-2 as
`agree x gates_clean`.

**S-4 `[v3]` 0DTE composition x agreement.**  `agree x (1 - zdte_share)` (durable),
`agree x zdte_share` (expiring), `poison = -1[zdte >= 0.40] x max(agree, 0) x (1 -
pv_expanding)`.  The true 0DTE share is recomputed from the option ribbon's own
expiration field rather than from the pack aggregate.

**S-5 `[v3]` Hedge durability MEASURED, not inferred.**  Split delta/gamma/vanna/vega
flow by DTE bucket at the print level: `durfrac = |non-0DTE flow| / (|0DTE| + |non-0DTE|)`,
plus the non-0DTE z-flows in their own right.  This is O-4 and D-4 as a measurement.

**S-6 `[v3]` The CC-013 second/third-order flows.**  vega, vomma, veta, vera, speed,
zomma, color, ultima, dual_gamma as signed event-grain flows with block-z, plus the
mean `iv_error`.  Not named by any reader — none of them could see these columns — but
they are the vol-of-vol and skew-convexity channels the readers kept asking for
indirectly (Opus G4 "implied-versus-realized divergence"; DSK D-4's dealer-surge object).

**S-7 `[v3]` The flow x travel cell with degenerate corners.**  `cell = 3*(sgn(oriented
flow)+1) + (sgn(oriented travel)+1)` at 60s and 600s; `s2lite = -sgn(flow)` when
`|flow| >= 50,000` and `|travel| <= 3bp`; `quiet = sgn(travel)` when `|flow| <= 1,000`
and `|travel| >= 8bp`.  This is C-1, the unanimous convergence, as a categorical rather
than as v2's continuous regression residual.

**S-8 `[v3]` Leftover vs live.**  `live60 = oriented bp travel over the last 60s`;
`live_vs_600 = live60 / |travel600|`; the flow-flip vector `sgn(live 300s) != sgn(stale
1800-300s)`.  This is C-4.

**S-9 `[v3]` Spread-z at the pivot and elasticity as a residual.**  `spread_z` = clock-
block z of the mean attached spread over 120s (DSK's #1 field, absent from v2).
`elasticity = |travel600| / (|signed shares|/1000)` z-scored against the same ratio over
the five prior blocks — Opus's G6 request that absorption be a residual rather than a
level.

**S-10 `[v3]` Dead tape as a conjunction.**  `1[urgency z <= -2] AND 1[print-rate z <=
-1] AND 1[|travel60| <= 2bp]` — Grok is explicit that all three legs are required and
that prints/min alone is not dead tape.

**S-11 `[v3]` Traded-IV surface objects at decision time.**  The `qr_ivx` census
publishes, per 1800s window, risk reversal / skew slope / curvature / ATM IV and their
innovations (print-weighted across expiries and for the 0DTE expiry alone), the near/far
term ratio and slope and their innovations, and the FD ratio / fd_chi / sigma_vv / A3
joint state / vol-of-vol.  Joined at window `t // 1800 - 1`.  This answers Opus's G4
directly.

**S-12 `[open]` Boundary acceptance and pressure-per-bp.**  `pressure = same-side
aggressor shares at the extreme / max(bp of boundary progress, eps)`, plus
`accepted_beyond_level = 1[two-sided trade held beyond the level for >= T seconds]`.
GPT's P-3 and the sharpest form of C-3.  Needs a per-print pass that this lane did not
run.

**S-13 `[open]` Reclaim fraction of a displacing print.**  `reclaim_frac = (p(t0+D) -
p(t0)) / -disp` over ordinary prints only; `unreclaimed_impact = disp x (1 -
clip(reclaim_frac, 0, 1))`.  GPT's P-2.  The correct successor to v2's `K_` corrector,
which measured the print but not the reclaim.

**S-14 `[open]` THROUGH-cascade run length**, signed by side, with an explicit
short-horizon tag.  DSK's D-3.

**S-15 `[open]` Runway to the next UNUSED level.**  Requires level bookkeeping — which
named levels the session has already traded through, and which level the pivot itself
IS.  Grok R-4; the sharpest single unbuilt object in the panel, because it says the v2
magnet arithmetic is measuring the wrong distance whenever the pivot is standing on a
level.

**S-16 `[open]` Climax-vs-continuation as a HORIZON label.**  Grok R-6 and DSK D-3 both
say the same signature pays for 15-30 minutes in one regime and holds to the close in
another.  That is a second target, not a second feature, and the harness currently
fits one.

---

## 4. What the panel cost and what it bought

Four readers, ~$70.  One of them (Opus-max) produced calls with measurable lift; three
did not.  The value delivered is not the calls: it is (i) a ranked, cross-validated list
of sixteen codifiable objects, (ii) a unanimous list of channels not to spend columns on,
and (iii) the discovery that the highest-conviction object in the whole panel — capacity
arithmetic evaluated before any signal — is a *refusal* mechanism, which is why it shows
up as a small AUC contribution and a large dollar contribution: it does not rank winners,
it removes candidates that cannot pay.
