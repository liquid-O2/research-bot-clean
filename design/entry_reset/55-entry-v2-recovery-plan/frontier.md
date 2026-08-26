# Open causal frontier for Entry V2

## Components found

### Evidence state

| Claim | State | Owner |
|---|---|---|
| The candidate set contains enough payoff. The event oracle is $2,772 HG, $1,851 NKD, and $2,396 SI per asset-day. | `ESTABLISHED` | `design/entry_reset/T35_VERDICT_20260823.md`, `artifacts/entry_v2/tabular_recovery/diagnostics/extreme_events_20260823.json` |
| The economic target is one top-two event from about six events per cell. Top-three is insufficient. | `ESTABLISHED` | `design/entry_reset/T50_DIAGNOSIS_20260823.md`, `artifacts/entry_v2/tabular_recovery/diagnostics/entry_economics_20260823.json` |
| The current price-order rule lands in the top two 65% to 77% of the time, yet its bottom-tail mistakes leave direct cash below every rung. | `ESTABLISHED` | `design/entry_reset/T50_DIAGNOSIS_20260823.md`, `design/entry_reset/T39_VERDICT_20260823.md` |
| A causal activity composite predicts cell value about twofold out of sample. It does not identify the paying event or the price rule's failures. | `ESTABLISHED` | `design/entry_reset/T53_REGIME_SPLIT_20260823.md`, artifact key `predicted_rich` in `regime_split_20260823.json` |
| The broad claim that the price rule fails in rich cells was supported by an uncontrolled comparison. Only the HG payer-percentile result survived its own null. | `RETRACTED`, with an HG-only residual | `design/entry_reset/T50_DIAGNOSIS_20260823.md` |
| The long hold identifies the payer. | `RETRACTED` | `design/entry_reset/T50_DIAGNOSIS_20260823.md` measures only 23% to 58% of cell-best capture and a $37 to $74 worse entry price |
| QRE2 event packs preserve every selected MBP-1 event with receive and exchange clocks, prices, top-book sizes and counts, sequence, action, side, flags, and depth. Visibility uses a strict receive-time cutoff. | `ESTABLISHED` | `engine/entry_v2/event_pack.py` symbols `EVENT_DTYPE` and `EventPack.cutoff`; `engine/cpp/qr_entry_v2/include/qr_entry_v2/substrate.hpp` symbol `EventRow` |
| `CandidateRow` keeps entry BBO and candidate identity but does not keep the zigzag pivot or G1 birth tape. | `ESTABLISHED` | `engine/cpp/qr_entry_v2/include/qr_entry_v2/g1.hpp` symbol `CandidateRow`; `design/entry_reset/tickets/37-tag-pivot-mid2.md` |
| The existing feature plane already has generic attack, lift, reload, pull, and ordered-event summaries around the formation tick. Its price state stops at 601 seconds. | `ESTABLISHED` | `engine/entry_v2/discretionary_features.py` symbols `_event_micro_map` and `_state_series` |
| Forward volatility predicts phase range and has 708 pre-seal overlap days with the new substrate. Whether it predicts the value of waiting or event identity is unmeasured. | `ESTABLISHED` for range skill, `UNRESOLVED` for entry use | `design/entry_reset/T54_FORWARD_VOL_20260823.md`, `artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json` |
| Event identity at a short confirmation age can retain enough exact payoff after entry-price decay. | `UNRESOLVED` | No age-by-age information and payoff receipt exists |

### Recommended mechanism 1. Event frontier with elimination and delayed commitment

This is the cheapest new decision shape. It does not add another score column. It changes the unit of state from one isolated event row to the causal frontier of all events known in the cell.

| Scientific field | Contract |
|---|---|
| New information | The ordered relationships among events. The state records event identity, side, formation time, eligibility time, current age, same-side overtakes, opposite-side arrivals, dominance duration, price displacement since eligibility, and whether each event remains on the frontier. None of the 1,764-column scans represented the cell as a changing set. |
| Causal availability time | Update the frontier only when an event becomes eligible or at a preregistered observation age. The current 2021 matrix can kill the shape at ages 180, 240, 290, and 300 seconds. Later ages require exact rows from the rebuilt corpus. |
| Decision target | One action per cell from `WAIT`, `COMMIT(event_id)`, or `SKIP`. Elimination predicts which events cannot finish in the top two. It does not regress raw dollars or pick a finished-cell winner. |
| Path to the required dollars | At each age, first price the best event among the causally known roster at that age using the entry price at that same age. The age stays alive only if this ceiling clears $667 per HG trade and $500 per NKD and SI trade by two standard errors. The live policy must then clear the same direct-dollar bar. This includes both the information gained by waiting and the price lost while waiting. |
| Smallest falsifier | On 2021, every preregistered frontier state either sits inside its lifecycle-shuffle null or fails to improve direct cash over its count-matched entry-price twin. An age also dies if its causally known top-two ceiling is below the per-trade bar. One of those results closes the shape before a new corpus read. |
| Data read | Ticket 35 event identities, chronological event arrivals, exact delayed rows, formation and snapshot clocks, side, entry BBO, and occupancy exits. No sealed outcome is needed to construct the state. |
| Null | Within each cell, permute lifecycle identities among events while preserving event count, side count, eligibility timestamps, observation ages, and the side-by-entry-price ordering. This destroys relational identity without giving the null an easier clock or price problem. |
| Price control | Run the same action capacity with only side times entry price and event count. Any structural score is residualized against that control before selection. Report identical picks and incremental dollars. |
| Replay receipt | For every decision, store the ordered observations, surviving event ids, action, commit timestamp, exact entry BBO, exit timestamp, occupancy refusal, daily dollars, maximum drawdown, null seed, and source hashes. Replay must enforce one position per asset and one entry per cell. |
| Build cost | Low for a 2021 kill test because the event frame and ages through 300 seconds are on disk. Medium for later ages because the observation records must be emitted into the 2022 through 2024 corpus. No product-code change is justified before the kill test. |
| Nearest prior failure it must not repeat | RUNMAX and the long hold reduced the sequence to one extreme and one age. Armed entry discarded identity and took the next name. Ticket 26 scanned static columns. This mechanism keeps the whole causal candidate lifecycle and prices the actual commit time. |

The first policy family should stay small. Test fixed elimination rules over same-side overtakes, opposite-side contradiction, and survival across one short observation interval. A learned policy over the same state is not a second hypothesis.

### Recommended mechanism 2. Pivot-centered G1 birth tape

This is the first new information source worth building. It asks whether the swing construction itself contains identity information that disappeared when G1 emitted only a candidate and an entry BBO.

| Scientific field | Contract |
|---|---|
| New information | The exact `pivot_mid2`, the leg start and pivot timestamps, signed leg size, retracement that confirmed the reversal, and tape summaries accumulated during G1 birth at the pivot. The tape summary should distinguish traded-through liquidity, reload, pull, attack, and opposite aggression at the actual zigzag pivot. |
| Causal availability time | The pivot and its birth tape are fixed when G1 confirms the candidate. They are therefore available before the candidate's 180-second eligibility decision. Any post-formation confirmation uses only raw events with `ts_recv_ns` strictly before the chosen commit timestamp. |
| Decision target | Top-two membership or elimination among new-extreme events. The pivot evidence may break ties within the event frontier, but it does not change the generator or mint candidates. |
| Path to the required dollars | Start at age 180 with no waiting cost. If a short post-formation tape sequence is needed, test the same age and dollar ceiling used by mechanism 1. The arm survives only when exact direct cash clears $667 per HG trade and $500 per NKD and SI trade after the entry-price change. |
| Smallest falsifier | On the 2021 kill corpus, the price-residualized pivot and birth-tape families do not beat both their within-cell null and the side-by-entry-price twin, or their direct cash stays below the rung by more than two standard errors. That result closes the build before the 2022 through 2024 promotion read. |
| Data read | `QRE2EVT2` raw prefixes and G1's internal zigzag state. `EventRow` already supplies nanosecond clocks, price, BBO size and count, action, side, flags, and depth. The new tag must carry source ordinals and a prefix hash. |
| Null | Within each asset, phase, side, and coarse formation-time bin, permute pivot and birth-tape records across events while preserving entry price, event age, and event count. A second null rotates tape windows to a non-pivot price in the same raw prefix. |
| Price control | Compare each pivot score with its side-by-entry-price twin. Also report the incremental score after residualizing both pivot location and leg size against entry price. The ticket 44 control is part of the schema, not a later audit. |
| Replay receipt | Store candidate id, pivot id, pivot timestamp and price, raw prefix cutoff, tape-window bounds, feature hash, commit timestamp, exact entry price, exact outcome read state, and chronological replay dollars. A future mutation after the cutoff must leave the record byte-identical. |
| Build cost | Medium. Add a narrow G1 tag and a rerunnable differential on one session, then materialize a 2021 kill slice. Only a surviving kill test earns new-corpus columns. Ticket 37 is the nearest implementation ticket. |
| Nearest prior failure it must not repeat | Ticket 36 scanned every existing column and found only price repackaging. Ticket 10 rejected S6 from generic formation-zone quote and memory columns through 290 seconds. This mechanism is viable only if it preserves the actual G1 pivot and the tape used to form that swing. Re-aggregating `_event_micro_map` at the existing formation tick is closed. |

### Conditional mechanism. Forward-volatility as an evidence budget

Forward volatility should not run as a standalone selector. It becomes useful only after mechanism 1 or 2 defines a causal localization policy.

| Scientific field | Contract |
|---|---|
| New information | The session-open range distribution, q10 through q90 width, current-phase forecast, next-phase forecast, and named regime. These are absent from the 2021 matrix and available on 708 pre-seal overlap days. |
| Causal availability time | Use only `READY` rows whose `availability_ts_ns` is strictly before the cell or event decision. The QRE2 forecast artifact already records this time. |
| Decision target | The maximum evidence budget before `COMMIT` or `SKIP`. It does not choose an event. High expected range may justify waiting for another event or another confirmation interval. Low expected range may require an earlier commit to preserve price. |
| Path to the required dollars | Measure the marginal improvement in the causally known top-two ceiling from one age to the next, minus exact entry-price decay. The forecast earns a place only if it predicts this marginal value of waiting and raises the localizer's exact replay dollars above the per-trade bars. |
| Smallest falsifier | The age-to-age value of waiting has no monotone held relationship with forecast level or quantile width, or the forecast-conditioned policy does not beat the identical localizer with a fixed evidence budget. |
| Data read | `QRE2FORECAST4` or the served walk-forward forecasts, the causal event frontier, and exact outcomes at each preregistered commit age. Do not open the forecast evaluation sidecar in the policy path. |
| Null | Shuffle forecast rows within asset, phase, walk-forward fold, and availability status. Preserve event paths and observation ages. |
| Price control | Compare against the same localizer with a fixed age, the ticket 53 activity conditioner, and an entry-price-only policy. |
| Replay receipt | Store the forecast lineage, availability time, quantiles, chosen evidence budget, observations consumed, commit price, and exact replay result. |
| Build cost | Low after the entry corpus exists. The join is already scoped by ticket 54. The policy comparison is small. |
| Nearest prior failure it must not repeat | Ticket 53 predicted cell value and then swapped arbitrary name rules in rich cells. Ticket 19 showed realized range cannot rank names. This mechanism tests forecast times marginal value of waiting and never treats range as event identity. |

### Parked mechanism. Intraday cross-market residual state

This is a real new data source, but it ranks behind the first two mechanisms. `CURRENT.md` closes cross-asset timing at the tried grains. A new test must use an event-aligned residual, not another timing or correlation feature.

| Scientific field | Contract |
|---|---|
| New information | The target event's move and tape response after removing the contemporaneous move of the other two causal futures streams. The hypothesis is that an idiosyncratic extension is more likely to reverse than a common continuation. |
| Causal availability time | Align peer `QRE2EVT2` packs by strict `ts_recv_ns` cutoffs at the target event's formation and commit timestamps. Never use the peer session close or a revised daily series. |
| Decision target | Event identity or side choice among the current event frontier. |
| Path to the required dollars | Use a short event-aligned interval whose target entry can be priced exactly. The peer residual must raise direct cash beyond the localizer and its own-price twin, not merely improve classification. |
| Smallest falsifier | Insufficient simultaneous session overlap, no stable pre-outcome beta estimate, or peer residual cash inside a phase-matched shuffled-peer null on 2021. |
| Data read | The three assets' existing raw event packs and their session clocks. Slow context in `ContextPack` is not a substitute. |
| Null | Shift the peer path to another same-asset, same-phase day with the same forecast regime. Preserve the target path and its entry price. |
| Price control | Target-only return and side-by-entry-price over the identical interval. The cross-market residual must add beyond both. |
| Replay receipt | Store all three pack hashes, cutoffs, clock alignment, beta provenance, residual, decision, entry price, and exact target outcome. |
| Build cost | Medium to high because session overlap and clock ownership need a new join. A small 2021 overlap receipt must precede any feature build. |
| Nearest prior failure it must not repeat | The prior cross-asset timing null. A coarse lead or shared clock repeats that closure. Only event-aligned residual response remains open. |

### Rejected approaches

- Another model, loss, or top-two label over the current static matrix is a model-only variant. The missing information is unchanged.
- Another raw or composite scan of the 1,764 columns repeats tickets 25, 26, 36, and 44.
- Forward volatility as a name score repeats ticket 19 and confuses cell value with event identity.
- The 7,380 to 10,980 second hold is not the next experiment. Ticket 50 shows that it picks only 23% to 58% of cell-best value before its unknown entry-price decay.
- Extra entries, size, and simultaneous positions do not meet the per-trade goal. Ticket 51 still contains a multi-entry clause that conflicts with the user ruling in `START_HERE.md` and `T53_REGIME_SPLIT_20260823.md`.
- Intra-second reconstruction is a conditional data-quality fix. Ticket 43 must first show that within-second movement is common and material. It is not an entry hypothesis by itself.

## Flow

The present ticket order spends too much of the next cycle on a weak hold and on cell conditioning before it proves a new localization path. Use this order instead.

1. Rewrite ticket 51 as the event-policy benchmark. Remove the multi-entry clause. Freeze the rank distribution, exact per-trade bars, candidate lifecycle records, observation records, commit decisions, and replay records.
2. Run the mechanism 1 kill test on 2021 at the exact ages already on disk. This is the cheapest test of a new state and decision shape.
3. Move ticket 37 forward. Ticket 44 showed that the ticket 36 survivors are price repackaging, so the condition that once blocked pivot and G1 tape tagging has already been met in substance.
4. Run ticket 43 only as a granularity decision for the pivot-tape build. Keep nanosecond raw events if the one-second projection loses material movement. Otherwise keep the smaller event representation.
5. Run ticket 45 as the one-session end-to-end build pilot. Extend the pilot receipt to prove that candidate lifecycle, pivot evidence, forecast context, and exact outcome ages join without silent absence.
6. Replace ticket 46's hold-derived late tail with an information-and-payoff age grid. The 600 to 10,800 second tail earns its rows only where a preregistered mechanism may still gain enough information to offset price decay. Do not make the failed long hold foundational.
7. Move ticket 48 before the full corpus build and certainly before its first outcome read. Freeze each rule, observation age, null, price control, and read count. Corpus construction may be blind, but its schema choices already encode the experiment.
8. Build the corpus under ticket 47 with separate immutable shards and receipts.
9. Read mechanism 1 and mechanism 2 once on the frozen 2022 through 2024 blocks. Promote neither from 2021.
10. Run ticket 54 only as the forecast-by-value-of-wait interaction for a surviving localizer. A standalone forecast join stops after its conditioning receipt.
11. End with exact chronological replay under the 12-entry portfolio cap, one position per asset, and maximum drawdown below $1,000.

The sequence gives every expensive step a preceding kill. It also stops the age schema, forward-vol join, and raw tape build from making separate copies of candidate identity and commit time.

## Files read

### Current authority and contracts

- `AGENTS.md`
- `START_HERE.md`
- `CURRENT.md`
- `STATE.md`
- `DATA_INVENTORY.md`
- `design/entry_reset/55-entry-v2-recovery-plan/exploration-contract.md`
- `design/entry_reset/ENTRY_PLAN_20260823.md`

### Verdicts and prior design rounds

- `design/entry_reset/DIAGNOSIS_20260822.md`
- `design/entry_reset/DISCRETIONARY_REREAD_PLAN.md`
- `design/entry_reset/NOVEL_FILTERS_20260822.md`
- `design/entry_reset/LABEL_VARIANT_SCREEN_20260822.md`
- `design/entry_reset/HANDOFF_DECISION_PLANE_20260822.md`
- `design/entry_reset/SELECTION_HOLD_EXTREME_20260822.md`
- `design/entry_reset/FABLE5_MAX_GOAL_DISCUSSION.md`
- `design/entry_reset/FABLE5_XHIGH_LABEL_DIAGNOSIS.md`
- `design/entry_reset/OPUS5_XHIGH_MISSING.md`
- `design/entry_reset/T28_VERDICT_20260822.md`
- `design/entry_reset/T29_T34_VERDICT_20260823.md`
- `design/entry_reset/T35_VERDICT_20260823.md`
- `design/entry_reset/T39_VERDICT_20260823.md`
- `design/entry_reset/T44_TAUTOLOGY_AUDIT_20260823.md`
- `design/entry_reset/T50_DIAGNOSIS_20260823.md`
- `design/entry_reset/T52_REGIME_20260823.md`
- `design/entry_reset/T53_REGIME_SPLIT_20260823.md`
- `design/entry_reset/T54_FORWARD_VOL_20260823.md`

### Live tickets

- Tickets 08, 19, 24 through 28, 35 through 38, 43, and 45 through 54 under `design/entry_reset/tickets/`

### Source and artifacts

- `engine/entry_v2/event_pack.py`
- `engine/entry_v2/context_pack.py`
- `engine/entry_v2/context_sources.py`
- `engine/entry_v2/discretionary_features.py`
- `engine/entry_v2/tabular_delayed_corpus.py`
- `engine/entry_v2/causal_label_atlas.py`
- `engine/entry_v2/exact_delayed_teacher.py`
- `engine/cpp/qr_entry_v2/include/qr_entry_v2/substrate.hpp`
- `engine/cpp/qr_entry_v2/include/qr_entry_v2/g1.hpp`
- `engine/cpp/qr_entry_v2/src/g1.cpp`
- `engine/cpp/qr_entry_v2/src/g1_artifacts.cpp`
- `engine/cpp/qr_entry_v2/src/forecast.cpp`
- `engine/cpp/qr_entry_v2/src/forecast_artifacts.cpp`
- `artifacts/entry_v2/tabular_recovery/diagnostics/entry_economics_20260823.json`
- `artifacts/entry_v2/tabular_recovery/diagnostics/extreme_events_20260823.json`
- `artifacts/entry_v2/tabular_recovery/diagnostics/location_ranker_20260823.json`
- `artifacts/entry_v2/forecast/forward_vol_audit_v4_exact.json`

## Boundaries

- Keep G1 frozen. Tagging its pivot and birth tape preserves candidate generation.
- Treat `CandidateCell`, `CandidateLifecycle`, `EventFrontierObservation`, `CommitDecision`, and `OutcomeRead` as separate records. A candidate can exist before it is observed, and an observation can exist without authorizing an outcome read.
- Join raw events, peer markets, and forecasts once at their strict availability boundaries. Pass trusted causal records into pure policy scoring.
- Every commit age needs an exact entry price and its own payoff ceiling. A 180-second label cannot price a later commit.
- Each comparison needs a lifecycle-preserving null, an entry-price twin, direct replay dollars, day-level standard error, and the two-standard-error verdict.
- Fit knobs only on the frozen training era. Read each held rule once. Label every other held calculation exploratory when it is reported.
- Keep 2025 out of the new build. The annual HG and NKD bundles contain sealed 2025H2 bytes.
- Do not infer success from top-two AUC, event recall, or forecast skill. Only exact chronological replay can satisfy the dollar and drawdown clauses.

## Non-obvious things

- A 65% to 77% top-two hit rate can still miss the dollar goal. The bottom ranks are sufficiently negative that the error distribution matters more than the headline hit rate. The policy receipt must publish rank-conditioned dollars.
- The candidate set and the observation schedule are different axes. A later observation may improve identity while making the same event uneconomic to enter. The plan needs both curves on one page.
- Ticket 46's age tail was chosen from a long hold that later lost its payer claim. Keeping that tail without an information-gain gate would encode a retired story into the next corpus.
- Ticket 54 has a strong input model and an unproved entry link. Running it before a localization policy would likely reproduce ticket 53 with better cell-value estimates.
- Ticket 37 is no longer blocked by a useful existing-column survivor. Ticket 44 showed that the apparent survivor was mostly entry-price order with a fitted side offset.
- The generic microstructure plane is not empty. A pivot-tape build earns its cost only by preserving G1-specific swing formation that `_event_micro_map` and the 601-second price state do not represent.
- Slow context already includes volatility, rates, positioning, and calendar series through strict availability joins. Another fit over those columns is not cross-market novelty. Only synchronized intraday peer response remains open.

## Open questions

These are experiment gates, not questions for the user.

1. At which exact commit ages does the causally known event ceiling still clear each per-trade bar after entry-price decay?
2. Does the event frontier retain the top two while eliminating enough negative-tail events to improve direct cash over the entry-price twin?
3. Does G1 pivot and birth-tape evidence add event identity after price residualization?
4. Is the forecast level or quantile width related to the marginal value of one more observation interval?
5. Does the 2022 through 2024 build have enough simultaneous peer-market coverage for a strict event-aligned residual test?
6. Which mechanism, if any, clears the rung by two standard errors and stays below $1,000 maximum drawdown in exact replay?

`PASS` with evidence. Two non-duplicate mechanisms satisfy the scientific contract. The first uses a new relational state and action shape on existing causal rows. The second adds G1 pivot and birth-tape information absent from the scanned matrix. Forward volatility is retained only as a conditional evidence-budget mechanism.
