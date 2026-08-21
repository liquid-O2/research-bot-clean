# Entry V2 discretionary source-to-feature crosswalk

Status date: 2026-08-19. This document is an implementation ledger, not an
economic result and not launch authorization.

## Complete source audit

The complete on-disk union was read and visually inspected page by page: 31
unique PDFs / 411 pages. Text extraction was not treated as visual review;
every rendered page, screenshot, DOM/footprint example, chart, diagram, and
table was inspected.

| Source | Pages |
|---|---:|
| `10k-first-month (1).pdf` | 16 |
| `18k-payout-session.pdf` | 15 |
| `2345-funded-session (1).pdf` | 11 |
| `amt-lesson-1.pdf` | 14 |
| `anatomy-of-a-losing-start (1).pdf` | 12 |
| `average-unprofitable-trader.pdf` | 33 |
| `code-1-thesis.pdf` | 8 |
| `code-2-risk.pdf` | 8 |
| `code-3-orderflow.pdf` | 8 |
| `data-engine.pdf` | 9 |
| `dom-lesson-5.pdf` | 8 |
| `dom-lesson-6.pdf` | 8 |
| `dom-lesson-7.pdf` | 8 |
| `emotion.pdf` | 9 |
| `fp-lesson-8.pdf` | 8 |
| `fp-lesson-9.pdf` | 8 |
| `mastering-amt-vp (1).pdf` | 27 |
| `ny-am-session (1).pdf` | 12 |
| `only-trade-big-trades (1).pdf` | 19 |
| `origin-of-the-move (1).pdf` | 19 |
| `reading-delta.pdf` | 11 |
| `refill-effect (1).pdf` | 24 |
| `stop-re-entering.pdf` | 17 |
| `tpo-lesson-3.pdf` | 10 |
| `trapped-buyers-one-retest.pdf` | 13 |
| `vix-lesson-4.pdf` | 10 |
| `vp-lesson-2.pdf` | 9 |
| `vwap-lesson-10.pdf` | 9 |
| `whos-in-control.pdf` | 12 |
| `your-mistakes-with-absorption (1).pdf` | 14 |
| `gex-framework (2).pdf` | 22 |

The duplicated older copies of eight PDFs were hash/content duplicates and
were not double-counted. The older-only GEX document was included.

## Decision hierarchy implemented

The documents do not define one universal trigger. Their common causal grammar
is:

`slow auction/regime -> meaningful location and memory -> arrival/attack ->`
`effort versus reward -> control transfer -> reclaim/lift -> defended retest ->`
`viable objective and structural invalidation`

Entry V2 therefore exposes atomic state and path components. CatBoost is asked
to learn their context-dependent interactions. It is not taught a single
hard-coded “absorption” or “reclaim” rule.

## Feature-family ledger

| Source concepts | Upgraded event-data implementation | Feature prefix | Decision role | Status / falsifier |
|---|---|---|---|---|
| AMT, VP, TPO, VWAP; balance/imbalance; value migration; acceptance/rejection; HVN/LVN; failed auction | Causal developing volume and time profiles at completed five-minute boundaries; VP/TPO disagreement; POC/VA/VWAP migration; time accepted above/below value | `disc_auction_` | formation context, regime, invalidation | Implemented. Future-truncation invariant; ablate auction coordinates and compare with level-destroyed control |
| Prior value, untouched/mature levels, second/third test, origin and prior defense | Immediately preceding authoritative session is summarized and closed before current pack opens; prior VP/VA/VWAP, high/low/close, per-price attack bursts, and completed 30s/120s reaction histories | `disc_prior_` | formation rank, level maturity | Implemented. Prior asset/date/hash are receipt-bound; absent prior is typed, not imputed |
| Aggressor bubbles, delta/CVD, highest delta print, diagonal footprint imbalance, stacked imbalance | Exact signed executions at price; max event and max one-second attack/lift; 350% diagonal counts and consecutive stacks; two-sided active levels | `disc_level_`, `disc_footprint_` | location-conditioned control | Implemented. Price-coordinate bijection preserves marginals and destroys candidate association |
| DOM speed, aggressive attack, tape acceleration, exhaustion | Nanosecond attack/lift timestamps; inter-arrival quantiles; 100ms/250ms peak counts; event size; short/long rate acceleration over 1/5/15/30/60/120/300s | `disc_evt_`, `disc_mhi_` | confirmation timing | Implemented. Equal one-second marginals with different nanosecond spacing produce different features |
| Adaptive tape clocks and participant-control evidence | Last 16/64/256/1024 trusted messages, 8/32/128/512 trades, and 64/256/1024 traded units; aggressor runs/autocorrelation/concentration; quote churn; aligned flow; defense commitment; opposing withdrawal; 30/120s speed slopes and acceleration | `disc_eclock_`, `disc_tclock_`, `disc_vclock_`, `disc_tape_`, `disc_behavior_` | confirmation timing and control transfer | Implemented. All 371 adaptive-clock columns are learner-reachable; 352 are dynamic on the three-asset real rehearsal |
| Refill, iceberg proxy, passive defense, spoof/pull, retreat | Trade-conditioned same-price add/modify; exact trade-to-reload latency; refill size/count; cancel after display with no intervening fill and exact lifetime; reload price centroid | `disc_level_`, `disc_evt_`, `disc_absorption_` | defense, exhaustion, invalidation | Implemented at MBP-1 fidelity. No order IDs means true individual-order iceberg identity is typed unavailable |
| Best-quote defense and queue response | Duration-weighted defended-best dwell at/near the formation level; same-best queue depletion/rebuild size and rate; depletion-to-rebuild latency; fragmentation; disappearance; favorable/adverse best changes over formation/30s/120s clocks | `disc_quote_` | defense persistence and confirmation | Implemented from exact economic BBO intervals. 99/105 columns are dynamic on the real rehearsal; coordinate destruction changes candidate association |
| Absorption and effort/reward | Attack volume and bursts divided by adverse price yield; reload per attack; price yield per attack/net aggression; opposite lift; two-sided absorption; pull-versus-refill | `disc_absorption_`, `disc_state_price_yield_` | control transfer | Implemented as continuous components. No author threshold is treated as truth |
| Repeated tests and response decay | Exact candidate-local attack bursts; first/last/slope volume; completed 1s/5s favorable/adverse response; defense rate; ordered attack→reload→lift count and latency | `disc_test_` | level maturity, exhaustion, response quality | Implemented. All 34 columns are dynamic on the real rehearsal and all respond to coordinate destruction |
| Squeeze/OFM, failed auction, reclaim, lift-off, protected structure, retest, failed reclaim, trapped inventory | Candidate-relative ordered state: adverse test -> reclaim -> two-tick lift -> retest; persistent invalidation; exact event attack->reload->lift ordering; separate completion flags | `disc_state_`, `disc_path_` | confirmation and veto | Implemented. Each component remains visible; state family is independently ablatable |
| Balance fade versus expansion continuation; identical flow with opposite meaning by regime | 60/300/1800s range, displacement, variation and efficiency; value acceptance side; slow/fast range ratios; separate balance-fade and expansion context states | `disc_regime_`, `disc_path_balance_`, `disc_path_expansion_` | thesis selection | Implemented. Context flags do not force entries |
| Volatility regime and expected range | Verified causal forward-vol session/phase sigma, range and quantile ladders; dispersion/curvature/asymmetry; realized/forecast consumption, headroom, overshoot, obstacle clearance, session-phase disagreement; strictly prior daily-vintage level/slope/acceleration/regime persistence | `disc_fvol_` | soft regime and target headroom | Implemented and receipt-bound. The current artifact has no intraday forecast vintages, so minute revision support is explicitly zero pending the separate publisher upgrade. Direct GEX is unavailable and is not faked |
| Origin of move, aggression memory, earlier defense/reaction | Candidate-price attack bursts before formation; only reaction windows completed before formation; 5/30/120s favorable/adverse reaction and large-origin counts | `disc_origin_` | formation rank, repeat-test quality | Implemented. Later reaction windows cannot enter an earlier snapshot |
| Structural targets, profile objectives, room before obstacle, stop where thesis is wrong | Nearest/second forward profile object, forward-object density at $300/$600/$900, nearest object behind, room/ATR and room/invalidation | `disc_target_` | target viability, risk context | Implemented from causal session/phase profile objects; prior objects are separately exposed |
| Candidate rung, phase, cost, spread, ATR, delayed watch state | Native G1 candidate and current BBO state, exact re-anchored cost/label at every snapshot | existing formation/current fields | eligibility and execution geometry | Existing exact Entry V2 path; retained |
| Cross-asset shared objective timing | Synchronized “who reached/rejected/consumed objective first” state | reserved `disc_xasset_` | thesis context | Not integrated. The earlier causal closed-cell/S11/P031 family was measured null: marginal capture `-0.0097 [-0.041,+0.022]`, wall-pair accuracy unchanged, and deliberate memorization found no gain. An event-level lead/lag version is a different hypothesis, but it must first clear a cheap synchronized destruction probe; the old null is not rebuilt under a new prefix |
| Calendar/news/external macro context | Strict-prior last-64 histories scattered into a frozen global series roster; per-channel last/mean/std/min/max/history coverage; revised vintages remain unopened | `ctx_` | slow context and regime prior | Implemented in the authoritative confirmation cache with provider receipt and per-row hashes. 498/1,806 columns are nonconstant on the one-day real rehearsal; FIT-only structural pruning removes unsupported/aliased columns before CatBoost |
| Stops, daily stop, re-entry, account limits, trailing/protected structure | Exact portfolio/replay policy, K=1 per asset, <=12/day, unlimited sequential re-entry subject to occupancy and risk laws | policy/replay, not learner columns | scheduling and risk | Existing policy layer. Must be re-rehearsed unchanged after learner selection |
| Emotion, discipline, prop-account anecdotes | No market predictor is manufactured from narrative | none | operational process | Converted only to preregistration, stopping, and audit discipline |

## Explicit confirmation paths

The following remain distinct model inputs rather than aliases for “reclaim”:

1. failed auction/rejection followed by re-entry into value;
2. attack absorbed at remembered location, poor adverse yield, opposite control;
3. repeated fill-conditioned refill, attack exhaustion, lift-off;
4. squeeze failure, re-squeeze/OFM drive, defended retest;
5. aggressive break, protected structure, pullback hold;
6. mature second/third test conditioned on earlier reaction quality;
7. delta/footprint extreme whose price reward diverges from effort;
8. balance fade after failed aggression;
9. expansion continuation after directional value acceptance;
10. failed reclaim/trapped inventory continuation;
11. VWAP/VP/TPO disagreement resolving through acceptance or snap-back;
12. the same paths conditioned on forecast headroom and volatility regime.

## Fidelity limits (never silently filled)

- The feed is MBP-1. It contains authoritative event order, aggressor side,
  executions, top-of-book price/size/count, and price-level actions. It does not
  identify individual resting orders across updates. “Iceberg” is therefore an
  execution/replenishment proxy, not order-ID truth.
- Direct options positioning/GEX is absent. Forward volatility is a useful
  regime/headroom input but is not renamed GEX.
- Cross-asset state is not valid until all asset prefixes share one durable
  synchronized decision boundary.  The earlier closed-cell cross-asset grain
  is already a measured null; only a materially different event-level
  lead/lag hypothesis can reopen that family.
- A feature being present, causal, or faithful to a PDF does not establish
  economic value.

## Required cheap evidence before a broader fit

1. future-truncation invariance on every family;
2. long/short mirror and price/volume-scale tests where symmetry applies;
3. event, volume, and price-ledger conservation;
4. coordinate destruction, event-order destruction, and fill-coupling
   destruction controls;
5. feature availability/non-constant census by asset, era, phase, and side;
6. CatBoost family-addition and family-ablation deltas against multiseed
   within-day shuffled nulls;
7. top-12 dollar opportunity capture on untouched threshold blocks;
8. only after cheap gates, exact K=1 portfolio replay and the mandatory >=80%
   candidate-ceiling recovery gate on both frozen rehearsal transitions.

No classification AUC can substitute for steps 7-8.

## Final v8 representation receipts

The v8 boundary binds both confirmation and discretionary source-code hashes
into the cache identity.  On authoritative HG/NKD/SI `20240103` it published
30,644 rows, 3,485 columns, and 1,352 discretion columns.  Of the discretion
columns, 1,290 were nonconstant across the three assets and 1,058 varied within
a watch path.  No `disc_*` family was unreachable by `MAX_W300`.

- feature census: `ced68552e613cd6912d824e916a1884f8d95a9c04d1581b3722c2d31ee380100`;
- level-association control: `5248d0dd9a08ec91820665c6503d9943f66cc1f7e39e3b1d6046b9aa1cfddf0b`;
- fill-coupling control: `2c51268c547d62c7af17cc5458cbe9f95e5f4d402b2d87879ca1d4ff0090d7c9`.

These are engineering/representation results only.  They do not establish
learning, opportunity capture, portfolio economics, or launch readiness.
