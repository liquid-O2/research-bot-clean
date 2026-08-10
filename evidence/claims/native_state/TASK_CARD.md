# Candidate-prefix native causal learnability — frozen task card V3.3.3

Status: **FROZEN FOR ADVERSARIAL REVIEW; NO PROBE OR MODEL MAY RUN UNTIL GREEN.**
Cache-only Plan-mode test. The one claim is whether causal IWM stock/NBBO and option-print
information can rank fresh entries during a candidate's first 60 seconds. Certificate
value is a hindsight entry-quality label and never establishes a deployable exit.

## 1. Walls, folds, and bound authorities

Only sessions 125..749 are admissible. F4 is train 125..395, inner embargo 396..397,
calibration 398..497, outer embargo 498..499, test 500..624. F5 is train 125..520,
inner embargo 521..522, calibration 523..622, outer embargo 623..624, test 625..749.
Any path/session >=750, fold 6/7, 2026, RTY/RUT/RUTW, old event-model outcome, fixed-
horizon target, teacher target, or realized-MAE eligibility filter is refused before
payload resolution.

The runner binds fresh-entry Pass A
`cee03e7eecfe3c2a50bd3b12e2d955cf01e2f96ce87eb8f82a1230c0658776cc`, Pass B
`6357598fa1f60461e2227cd6700a7eeac62002a90e4f3a75610dc44f181fb176`, A/B preflight
`aea384ae1797c4515c23ff58874fd0fefde41d646055b8748eede4fc9a01ae95`, fresh kernel
`3c9206c0dc7d259b24bae40301d5108bb06dc701979f4919222720c695ea9a1a`, and candidate
registry `f7a9a4d4b9b83fac467044251ec1947ef0019fae69113c2911291f74af2a9d71`.
The raw CANDIDATE physical key comes only from explicit session rowgroups125..749 of
`events.4_stage_run/pub/truth_relation_projection.parquet` SHA
`c41b889b24305a87149eb48089afc0b06470faa09e72f979f3a090b1c35cc322`, bound by manifest
SHA `3d381095e0b100153347841a6959a539a8bd9699fd98690d81fb624256995ab3` and session index
SHA `f54cc08bcf7af04f7175afe7b224b57609439e7048c45c87d490c035a0af3556`.
The projection physically stores neither `session_ordinal` nor `member_count`. A session
ordinal is derived only by selecting physical rowgroup `i`, requiring index row `i` to
have `ordinal=i<=749`, requiring that rowgroup's `day` statistics have min=max equal to
the indexed day, requiring every decoded `day` to equal it, and requiring decoded row
count equal the index row count. No predicate scan or later rowgroup is permitted.
Projection is restricted to `day,row_kind,candidate_id,physical_event_id,
stream_policy_name,stream_reversal_bps,visible_ts_ns,member_signal_ids`; no side, final
relation, matrix, label, score, outcome, or nonexistent derived column may be opened.
Matrix presence, side, cluster disposition/size, and membership never supply admission,
side authentication, features, sampling, or labels.

Raw decoding uses a new thin immutable adapter around the one-sweep `select_v2::sources`
readers plus `corpus::SessionClock` SHA
`8f7a95572adfb2dfef902fe3b73cd19289029a9e43bf365fe96026ace25df058`. The adapter
hard-codes only `/workspace/data/tokens/{stock_trades,stock_quotes,options_prints}`, IWM,
and 125..749, projects the clock fields below, never opens
`cutoff_context`, labels, option quotes, or a freely selected root, and publishes every
leaf/schema/source SHA. Existing adapters that admit s0750 are not authorities.

## 2. Causal candidate roster and side authentication

Every candidate-registry row with `row_kind=CANDIDATE`, a valid own
`visible_ts_ns`, `event_scorable=true`, and primitive policy in the frozen 12-policy
vocabulary `{dc001,dc002,dc003,dc004,dc005,dc006,dc007,dc008,dc010,dc012,dc015,dc020}`
is admitted at its **own visibility**. Registry rows with `stream_policy_name=UNION` or
any unknown/nonprimitive policy remain in a typed census but are `NONPRIMITIVE_CENSUS_ONLY`:
they create no watch/action, enter no prefix set, feature, sampler, denominator, fit, or
score, and are never silently zero/unknown-coded. This is a label-blind formulation rule,
not a result-selected subset. Final
`cluster_disposition`, final `cluster_size`, and final sibling/member aggregates are not
projected. `physical_cluster_id` is an opaque foreign key only and is never a feature,
gate, sampler, tie-breaker, or scientific denominator.

Side authentication comes only from a new sealed <=749 event-signal prefix. Its source
is `event_signals.tsv` manifest SHA
`1941d5cbd068fb12a7d17a83a71671dcc6757f83ffd98dacb39f6c2cf8519419`. `t14_bounds`
SHA `8fe7049c465de312c8e283b7d4c319d82c04e19e2fbe9fd316e3b13d6e46fae8` and the
session-row-group compact census SHA
`bdd6303a26aa7024e06546bbfef76d2287b0ec26c5ef897f07bd382dd3772ab7` establish that
exactly the first 10,684,134 data rows are ordinals0..749; only125..749 are retained.

The prefix reader is physically non-prefetching. It reads the header one byte at a time.
With `R` admitted data-row newlines remaining, it calls positional `pread` for exactly
`min(1MiB,R-1)` bytes while R>1; this cannot cross the boundary because reaching row750
requires consuming R newline bytes. At R=1 it reads one byte at a time through the final
newline and closes before any row750 byte. No BufReader, mmap, readline, or library
prefetch is permitted. Decoded ordinal must be monotone0..749. Every session must match
the exact `signal_count` and `signal_sequence_root` in `t14_bounds`; two independent
extractions must have identical schema, rows, leaves, per-session roots, and content root.

The bounded non-prefetch feasibility witness is source SHA
`12cf894248a371cbc98d7b6d0a65ab0fc1fc359cbe1e36a8b7c927eb8c1f6d3b`, receipt
`probe_s125_v3/receipt.json` SHA
`62e8d98805a97f42f016ce4b725d832f30fd968912180d50b7696dde69e87ccf`, and safe-leaf
SHA `549a9225000de0ba27b982434b379da5433eb712807d21756d52c6193c192eed` under
`side_prefix_feasibility_v1/`. It proves the physical stop at byte3,316,834,639 after
3,316,682 data rows, 126 session roots, 25,934/25,934 primitive s125 candidates resolved,
25,759 UNION rows census-only, three-run leaf identity, RSS56,256KiB, and a measured
305.55s linear 0..749 projection. It is feasibility evidence, not the full release: the
V3.3.3 production probe must add the physical-event-key mutants/check and full-scope release
must independently seal through749 before any model.

The safe leaf retains `ordinal,signal_id,physical_event_id,policy_name,reversal_bps,
extreme_side,causal_visible_ts_ns`. Exact-join each admitted registry candidate to one raw
`row_kind=CANDIDATE` projection row by `(derived_session_ordinal,candidate_id)` and require
equal policy, reversal, visibility, and member IDs. Parse projected `member_signal_ids`
strictly as a nonempty comma-separated list of unique lowercase 64-hex IDs in ascending
lexicographic canonical order, with no whitespace or empty token; `raw_member_count` is
only `len(parsed_member_ids)`. Require the exact parsed member list and this derived count
to match the registry member list/count. That raw row's nonnull
`physical_event_id` is `candidate_physical_key`; missing/duplicate/mismatch is fatal.
Every admitted primitive candidate member ID must resolve in its own session. The unique
common `physical_event_id` of its resolved members must equal `candidate_physical_key`;
cardinality other than one is fatal. Every member's `physical_event_id` must equal that
candidate-row key, all members must agree
on side, every member visibility must be <= candidate visibility, and each member's
policy/reversal must equal that primitive candidate's own declared policy/reversal. The
registry `physical_cluster_id` remains an unrelated opaque audit foreign key and never
substitutes for this member-derived physical key. No equality is inferred through or
required across a derived UNION row, because UNION never enters the scientific roster.
LOW->LONG and HIGH->SHORT. Missing/mixed/mismatched members make the primitive candidate
`SIDE_UNAVAILABLE`, retain it in the primitive denominator, and forbid ENTER; the full
scientific launch requires 100% resolution among admitted primitive candidates. There is
no matrix or covered-subset fallback. Deleting any later-visible candidate sibling must
leave every earlier primitive candidate's admission, side, state, and clocks unchanged.
A singleton fail-first mutates only the candidate-row physical key; a multi-member
fail-first mutates one member physical ID to split the set. Both must refuse the candidate/
session and may not be repaired by registry cluster identity.

At a decision, the causal context is the full set of admitted primitive candidates whose
own visibility is strictly earlier than the decision and no more than 60s old. Candidate
member IDs are foreign keys only; own `member_count` is lawful because that primitive
candidate's member set is fixed at its visibility. No nonprimitive row or later-visible
sibling contributes.

## 3. Watches, unique actions, labels, and masks

Each side-authenticated admitted primitive candidate creates three watches:

* D0: first registered whole-second clock strictly after own visibility;
* D30: first whole-second clock at or after visibility +30s;
* D60: last registered whole-second clock at or before visibility +60s, still strictly
  after visibility. Thus the focal candidate remains inside the inclusive age<=60s set.

Out-of-session watches are `CLOCK_UNAVAILABLE`. No D90/D120 row exists in this test.
Many watches may converge. First compute `decision_second` from the registered session
clock and require `decision_ts_ns=session_start_ns+decision_second*1e9`. Authority
`decision_ordinal` is nonlinear: reconstruct the sealed authority clock roster as the
sorted union of every registered whole second and every sealed evidence-change timestamp,
and verify all persisted label/evidence ordinals. Then exact-join
`(session_ordinal,decision_ts_ns,side)` and carry that authority ordinal. The scientific/
prediction key `(session_ordinal,decision_ordinal,side)` plus timestamp must be one-to-one;
`decision_second` is never substituted for ordinal. A separate many-to-one watch ledger
retains candidate ID, opaque physical key, own visibility, stage, policy/reversal/member
count, and action key. No candidate multiplicity duplicates a fit or score row.

For every unique action row, the sealed dual-envelope kernel produces its own native
fresh label: first eligible IWM quote group strictly after the decision; LONG entry
ask_max/mark bid_min, SHORT entry bid_min/mark ask_max; adverse wins equal-ms; 576 cents
cost once. `certificate_net_cent` is the uncapped best positive executable mark before
the first net -30,000-cent adverse wall, otherwise the wall or final eligible group;
`certificate_mae_cent` is exact marked MAE from entry through that exit. Existing shared
labels may be used only as an exact-key/value cross-check; they do not define this roster.

`legal_enter` is determined only by the authenticated watch and clock. Label states
`OK`, `ENTRY_UNAVAILABLE`, and `EXIT_UNAVAILABLE` are separate outcome masks. Every row
is predicted and retained. An ENTER selected on an unavailable label becomes typed
`NO_FRESH_FILL`, makes no trade, closes those watches, and is never silently dropped.

Primary supervision is continuous checkpoint-own `certificate_net_cent/30000` plus
same-clock LONG-vs-SHORT ranking. Frozen auxiliary opportunity events are net >0,
net >=10,000 cents ($100), and net >=30,000 cents ($300); none is test-selected. Risk is
`certificate_mae_cent>30000`. The barrier auxiliary calls
`barrier_order(entry_idx,side,5000,5000)`: thresholds are +/-5,000 **net cents** after
cost (about +$55.76 gross versus -$44.24 gross), scanned over full RTH; same-group ties
map to ADVERSE_FIRST. Raw states are FAVORABLE_FIRST, ADVERSE_FIRST,
SAME_GROUP_ADVERSE, NEITHER; the three-class auxiliary maps SAME_GROUP_ADVERSE to
ADVERSE_FIRST and NEITHER to CENSORED. Barrier class never gates entry or defines a
positive opportunity.

## 4. Strictly causal native inputs

Feature windows are `[max(session_open, decision-120s), decision)`. Frame-B naive New
York timestamps are converted once through the pinned `SessionClock`; direct frame/host
timezone comparison is fatal. Current/equal-cutoff tokens are excluded.

The adapter extends the pinned readers to retain these causal fields:

* stock prints: trade timestamp, `quote_timestamp`, sequence, condition and four extended
  conditions, size, exchange, price, attached bid/ask, sizes, and bid/ask conditions;
* raw stock NBBO: timestamp, physical source ordinal, bid/ask, sizes, and conditions;
* IWM option prints: print timestamp, `quote_timestamp`, `underlying_timestamp`, sequence,
  condition, expiry/strike/right, size/price, attached bid/ask and sizes, implied vol,
  delta/gamma/vanna/charm, and underlying price. Persisted `LegacySide`/`tclf`, every
  persisted `FlowBlock` column, and `sweep_id/sweep_n/sweep_size` are forbidden. No sweep
  identity/count/size/presence channel exists in this first pass.

An attached stock/option quote or underlying value is temporally usable only when its
observed timestamp is nonnull and strictly `< print_timestamp < decision_cutoff`; an
underlying value must additionally be finite and positive. A quote
is signing/valuation-valid only when bid/ask are finite, bid>0, ask>0, **ask>bid**, and
every available bid/ask condition passes its pinned condition contract. Locked, crossed,
one-sided/nonpositive, nonfinite, or condition-ineligible quotes remain typed quality but
cannot sign an aggressor or supply midpoint/spread/depth/valuation. Equality is
`EQUAL_TIME_UNORDERED` and unavailable; a later timestamp is `ATTACHMENT_FUTURE`; null is
`ATTACHMENT_MISSING`. The print remains. Attachment age is a continuous channel; no
unregistered staleness cutoff gates it (age>5s is reported diagnostically). The 42 known
future option attachments must therefore be masked, not consumed. If quote signing is
invalid, fallback is only the immediate finite, positive, condition-eligible **timestamp
group** for the same stock instrument or exact option contract with strictly earlier
timestamp. Its prior price is the finite mean over all eligible members of that nearest
group. Every member of the current equal-time group compares to that one frozen prior-group
mean; only after the whole current group is reduced does its eligible finite mean replace
the prior state. An equal-time/missing/tied reference leaves aggressor unresolved.
Standalone stock NBBO rows obey the same finite/positive/ask>bid/condition law for all
price, size, midpoint, imbalance, and return channels; invalid rows remain as locked/
crossed/one-sided/condition quality tokens with those economic values masked.
Quote-dependent option fields (attached bid/ask/sizes, print-minus-mid, spread, quote age)
require a strict-prior quote. Underlying-dependent fields (underlying return/age and
moneyness) require a strict-prior underlying observation. IV, delta/gamma/vanna/charm,
and every derived Greek-flow value require **both** strict-prior attachments; any equal,
future, or missing dependency masks the value and its flow. DTE/right/print price/size
remain print-native. A causal option aggressor is recomputed per contract: with a valid
strict-prior quote, print>=ask is +1 and print<=bid is -1; otherwise use the sign of this
print price minus the prior strictly-earlier same-contract print (0 on tie/missing). The
quote branch is skipped, not imputed, when its attachment is unavailable. Derived flow is
`causal_aggressor * size * greek`; no persisted side or FlowBlock value participates.
Each option print uses only its own strict-prior attached underlying value for its current
underlying/moneyness/Greek inputs. Underlying return compares that value to a global prior
state constructed only from earlier **print-timestamp groups**. After a complete print
group is processed, find the greatest valid `underlying_timestamp` observed among its
members and update the global prior to the finite positive mean of only members sharing
that timestamp. An absent valid attachment leaves the prior unchanged. Same-group member
order and rows from any later print group can never enter that update.
All option prints remain as nondirectional context. Causal aggressor and signed-premium
flow require positive size, pinned single-leg condition in `{18,95,125,126}`, and either
a strict-prior quote or a strict-prior same-contract print. Greek-flow additionally
requires both strict-prior quote and underlying dependencies as above. Multileg, unknown,
and nonpositive-size prints are retained with exact typed reason and
`directional_eligible=0`; dependency failures retain their separate attachment state.
Each directional value's presence is the conjunction of base directional eligibility
and its declared dependency mask. No sign is guessed.
Vendor `price_lead_1` is never projected. Stock sequence is not an ordering key because
real inversions exist. Primary order is Frame-A timestamp; all messages at one timestamp
form an unordered group and are reduced permutation-invariantly. Sequence quality is also
groupwise and permutation-invariant: for each group take finite `seq_min` and `seq_max`;
against the nearest strictly-earlier sequence-valid group, `sequence_gap =
current_seq_min - previous_seq_max`, stored as signed-log, `sequence_monotone = (gap>=0)`,
and `sequence_inversion = (gap<0)`. The first sequence-valid group and groups with no
finite sequence have all three missing. The previous group updates only after the current
group is complete; the inversion-fraction denominator is adjacent valid-group pairs.
There is no within-group sequence/order statistic. Group interarrival is present only
from the second timestamp group onward. `same-ms=1` exactly when the complete Frame-A
timestamp group has multiplicity>1. Source ordinal and sequence remain audit/quality
fields only.

Per-side raw message channels are fixed:

The stock print eligibility contract is the production allowlist in
`engine/crates/select/src/execution_contract.rs` SHA
`ed45607dba65ea3bb172237d70cdf1e061ec80fc5f704fe8b57e37f4d295745d`:
`is_trade_condition_eligible(code)` admits exactly code0 (REGULAR), types40..44 as CANCEL,
and excludes every other code; `is_quote_condition_eligible(code)` likewise admits only
code0. The adapter/sentinel contract is
`adapters/stock_trades.rs` SHA
`ebc3f1b95147e6240816553422ca1a300073671f2092906b6a398c686f05c9af`: each of four
extended-condition slots is absent only at sentinel255, otherwise it too must be code0.
The production primary-plus-extended conjunction is witnessed by
`engine/crates/cli/src/f02_handoff_cmd.rs` SHA
`21d21f6cd020dc4c00dede55ba790323eef699f50a6590c02d6f7d4c4da7881c`; only its condition
contract is reused, while V3.3.3's stricter quote/timestamp signing law above controls sign.
Thus a direction-eligible stock print requires primary code0, every present extended code0,
finite positive price, and positive size. All other prints remain in raw counts/quality
with their typed reason, but cannot update price return, print-minus-mid, aggressor,
signed size, prior-tick state, or prefix VWAP. No condition set is inferred from frequency.
Per session/window the immutable quality ledger reports total, eligible, primary-nonzero,
extended-nonzero, CANCEL40..44, sentinel-absent, nonpositive-size, and nonfinite-price
counts. These rows remain in total raw context; the model receives the eligibility bit
and ordinary presence masks, never a silently filtered tape.

* stock-print (17): log interarrival, oriented print return, oriented print-minus-mid,
  oriented aggressor {-1,0,1}, log size, oriented signed size, spread bps, log own/opposite
  attached size, oriented size imbalance, log quote age, quote-present, attachment-valid,
  sequence-gap signed-log, sequence-monotone, same-ms, directional-eligible quality bit;
* stock-NBBO (16): log interarrival, oriented midpoint change, spread bps, log own/opposite
  size, oriented imbalance, own/opposite price change, own/opposite signed size change,
  locked, crossed, positive-two-sided, bid-changed, ask-changed, same-ms;
* option-print (22): log interarrival, oriented underlying return, oriented right direction,
  oriented causal aggressor, log size, oriented signed premium flow, oriented
  print-minus-mid, spread bps,
  oriented delta, gamma, oriented vanna/charm, IV, log DTE, oriented moneyness,
  recomputed delta/gamma/vanna/charm flow, log quote age, log underlying age, and
  directional-eligible quality bit.

Every value channel has a parallel presence bit; structurally observed binary quality
values use presence1. LONG/SHORT reflection changes only
the declared directional channels and swaps own/opposite fields; counts, spreads, gamma,
ages, masks, and quality remain unchanged. Continuous normalization is fit with equal
session weight on TRAIN sessions only, scale floor 1e-6->1, clipped [-8,8], then frozen.

The orientation law is exact: `sigma=+1` for LONG and -1 for SHORT; stock price/return
and signed-flow channels are multiplied by sigma, and own/opposite is ask/bid for LONG
and bid/ask for SHORT. For options, `rho=+1` CALL and -1 PUT; oriented right is
`sigma*rho`, causal aggressor is `sigma*rho*v` for causal buy/sell `v=+1/-1` (0 unknown),
where `v` is the recomputed causal aggressor above, never persisted side. Already signed
delta/vanna/charm and their recomputed flow columns are multiplied by sigma.
Gamma and recomputed gamma-flow remain side-invariant. Signed premium flow is
`sigma*rho*v*size*price_u6`. Oriented moneyness is
`sigma*rho*(underlying_u6-strike_u6)/strike_u6`; absent/nonpositive operands are masked.

`DIRECT_RAW` has per-modality summaries for windows {1,5,30,120}s: log count, valid
fraction, and mean/last of the four preregistered mechanism channels (stock print:
return/aggressor/signed-size/imbalance; NBBO: mid-change/spread/imbalance/own-size-change;
option: underlying-return/aggressor/premium-flow/delta-flow), plus 20 full-window clock/order/
attachment-quality statistics. Exactly 60 columns/modality.

Definitions are frozen. Every stateful prior is built by taking the finite eligible mean
of each primitive scalar separately over the nearest strictly-earlier timestamp group:
stock-print price/tick fallback; stock-NBBO bid, ask, bid size, and ask size; and option-
print price per exact contract. NBBO prior/current midpoint and imbalance are derived only
**after** those scalar means, never by averaging per-row midpoint or imbalance. Option
underlying uses the attached-timestamp rule above. Every current-group member compares
only to the frozen prior; update occurs after the complete group, and an absent eligible
group yields missing/unresolved. A price return in bps is checked
truncating integer division `(px_u6-prev_px_u6)*10000/prev_px_u6`. Print aggressor is +1
when price>=valid prior ask, -1 when price<=valid prior bid, otherwise the sign of price
minus the prior print-group mean (zero on tie/missing), then reflected to action side. A timestamp-group mechanism value
is the finite member mean; its `last` is the greatest strictly-prior timestamp group.
For an empty window count/valid/mean/last are 0 and the full-window nonempty bit is 0.
The exact 20 full-window columns are: log1p token count; log1p timestamp-group count;
nonempty; all-four-mechanisms-finite group fraction; raw-channel missing fraction;
multi-token-group fraction; mean log1p group multiplicity; max log1p group multiplicity;
mean/p90/max log1p intergroup gap microseconds (nearest-rank p90); log1p covered span
microseconds; log1p age of last group; log1p approach-group count; log1p response-group
count; omitted/total approach-group fraction; omitted/total response-group fraction;
unusable-attachment fraction; vendor-sequence inversion fraction; and
`r_modality = finite-all-four group count / max(group count,1)` (0 when empty). For NBBO,
attachment-invalid and sequence-inversion are typed structural zeros.

The two phase counts exclude groups exactly equal to newest same-side visibility. A group
with timestamp `< visibility` is APPROACH, `> visibility` is RESPONSE, and `== visibility`
is typed `PHASE_EQUAL_UNORDERED`, receives no phase embedding, and enters neither phase
denominator. For each phase, omission is the number of its groups in the complete 120s
carrier that are truncated from recent128 divided by all complete-120s groups of that
phase; a zero denominator emits value0/presence0. Raw missing fraction is exactly absent
value cells divided by `token_count * declared_value_channel_count`; zero tokens emits
value0/presence0. For stock/option prints, unusable attachment is one union indicator per
print over every quote/underlying clock or validity dependency required by that print,
divided by all prints—never multiple counts for one print. NBBO remains structural0.

The transform table is exhaustive:

| Input kind | Exact pre-TRAIN transform and unit |
|---|---|
| nonnegative count/size | `log1p(x)` in raw shares (stock), contracts (options), or message count |
| time/gap/age/span | checked integer microseconds, then `log1p(us)` |
| signed size/flow/gap | `sign(x)*log1p(abs(x))` in raw shares, contracts, or `u6*contracts` for premium |
| price displacement | checked truncating integer bps `(num_u6*10000)/positive_den_u6`; invalid denominator is missing |
| fraction/reliability | `numerator/max(eligible_denominator,1)`; denominator zero emits value0, presence0 |
| raw Greek/IV | finite raw dimensionless value, no nonlinear transform before TRAIN normalization |
| DTE | nonnegative calendar days, then `log1p(days)` |

All token/group/bin means divide only by the number of finite present members; zero such
members emits value0/presence0. Max follows the same eligibility. Window `valid_fraction`
uses timestamp-group count as denominator and requires all four declared mechanism values;
attachment/condition-quality fractions use all prints in the window; reliability uses the
exact group-count formula above. No unavailable row is removed from a denominator.

For each continuous feature and TRAIN session s, use only finite present values to compute
`m_s=mean(x)` and `q_s=mean(x^2)`. Across the `S` TRAIN sessions having at least one
present value, `mu=mean_s(m_s)` and
`scale=sqrt(max(mean_s(q_s)-mu^2,0))`; S=0 gives `(mu,scale)=(0,1)` and scale<1e-6 becomes1.
Apply `(x-mu)/scale`, clip [-8,8], and write0 when missing while retaining its presence
bit. Binary/categorical/mask fields are never centered or scaled. This is equal-session,
TRAIN-only normalization; every per-feature `(S,mu,scale)` is hashed.

The prefix 1s midpoint grid never crosses a session. At each complete-second endpoint it
carries the last finite, positive, two-sided, strictly unlocked/noncrossed (`ask>bid`),
condition-eligible IWM NBBO midpoint whose timestamp is strictly before that endpoint;
before the first valid quote it is missing. Carry has no
hard timeout: source age in microseconds and `fresh_in_bin` are separate channels, and
`stale_gt_1s` is diagnostic only. These three fields are grid-audit fields, not additional
model columns. A carried unchanged midpoint contributes a zero return;
RV requires two present consecutive endpoints. The partial second containing cutoff and
all equal-cutoff groups are excluded.

`NATIVE_ORDER` uses the same messages through two fixed carriers. First, for each modality
and timestamp group, identity token values plus presence bits are reduced by finite mean
and max over **all** equal-time members, concatenate log group multiplicity, then project
to a 64d base group embedding once per `(session,side,modality)`. The
micro carrier is the most recent 128 groups strictly before cutoff, chronological, with a
learned bias-free two-state 2x64 approach/response embedding added according to whether
each group is strictly before or after the newest same-side authorizing visibility.
Visibility-equal groups are retained as `PHASE_EQUAL_UNORDERED` with zero phase embedding,
and typed left pad and truncation counts are retained. Second, the full carrier is exactly
120 complete left-closed/right-open one-second bins
`[cutoff-120s+i,cutoff-120s+(i+1)s)`, `i=0..119`, spanning `[cutoff-120s,cutoff)`;
equal-cutoff groups are excluded. Within a bin, the 64d equal-time group embeddings
are reduced by mean+max plus log group count/nonempty, then projected `130->64`; pre-open
bins are typed zero left pad. The full-bin carrier uses base group embeddings only; the
prefix episode encoder carries authorizer age/state. Its ordered 120-bin sequence is never truncated. Thus every
native arm carries both native recent-group order and the complete two-minute 1s path,
in addition to the unchanged DIRECT {1,5,30,120}s summaries. A null micro increment may
not kill 1s-path information, and a null 1s-path increment may not kill subsecond order.

## 5. Exact model and arm ladder

The prefix candidate-set encoder receives, per visible candidate, 24 fields: one-hot
policy vocabulary exactly `{dc001,dc002,dc003,dc004,dc005,dc006,dc007,dc008,dc010,
dc012,dc015,dc020}`, reversal/20, log1p member count, log1p age seconds,
own/opposite/mixed/unavailable relation one-hot, and visibility-in-last-{1,5,15,30,60}s
flags. Shared element MLP 24->32->32 (SiLU); set mean+max gives64.

The exact 16 location/clock values are: session-time fraction; its sine/cosine; seconds-
to-close fraction; early-close bit; oriented bps from session open; oriented bps from
running high; oriented bps from running low; running range bps; oriented bps from prefix
VWAP; prefix RV over 1s,5s,30s; current spread bps; log1p seconds since last stock print;
and log1p seconds since last option print. Each has a parallel presence bit (the five
pure clock values are always present). The 32 values/bits project 32->64 and add to the
64d candidate-set embedding.

Location uses the last valid IWM NBBO midpoint strictly before cutoff as `m`; open/high/
low are the first/min/max such prefix midpoints, and VWAP is size-weighted IWM stock
prints strictly before cutoff that pass the frozen stock condition/size/price contract.
Every oriented distance is
`sigma*(m-reference)*10000/reference`; range is `(high-low)*10000/open`. Prefix RV at
1/5/30s is `sqrt(sum(log(m_t/m_{t-1})^2))` on the prior complete 1s midpoint grid and is
missing with fewer than two valid points. Time fractions use registered RTH open/close;
spread and last-print ages use only strict-prior observations.

Biases are frozen rather than implementation-selected: both candidate-element MLP
layers and the location projection use biases; raw value projections, direct residual
encoders, TCN convolutions, role projections, and interaction projections are bias-free.
The stock-print, NBBO, and option output heads are bias-free so an absent zero embedding
contributes exactly zero; the state head uses biases in both layers.

For stock print, equal-time mean+max over 17 values+17 masks plus log multiplicity is69
inputs; NBBO's 16-value analog is65 and option's 22-value analog is89. Bias-free base
group projections are69->32->64,65->32->64,or89->32->64; the shared bias-free two-state
phase table has128 parameters.
The 128-group micro carrier has four residual
causal TCN blocks, width64, kernel3, dilations1/2/4/8. Its role vector is approach, current,
current-approach, and mean of valid latent checkpoints at cutoff-{60,30,15,5,1,0}s plus
four presence bits: bias-free260->64, yielding `h_micro`. The 120-bin carrier uses the
bias-free130->64 reducer above followed by seven width64/kernel3 residual causal blocks
with dilations1/2/4/8/16/32/64 (receptive field255); its final position is `h_bin`.
Every block is bias-free depthwise conv (64*3 parameters) plus bias-free64x64 pointwise,
SiLU, no dropout. Left pad is exact zero with a separate validity mask and stays zero.
Each native modality embedding is `h_direct+h_micro+h_bin`; DIRECT is unchanged. Each
direct encoder is bias-free60->64 plus four bias-free64x64 residual SiLU blocks.

Capacity is algebraically frozen. One direct encoder has20,224 parameters. Stock-print
micro has `69*32+32*64+128+4*(64*3+64*64)+260*64=38,176`; NBBO micro has38,048;
option micro has38,816.
The bin carrier has `130*64+7*(64*3+64*64)=38,336`. Therefore each native stock/NBBO
encoder has96,736/96,608 parameters and option has97,376, including one direct encoder.
`DIRECT_CAPACITY_MATCH` sums exactly five independent direct encoders=101,120 parameters
per modality, gaps4.53%/4.67%/3.84%; widths may not change after this card.

Per action after shared group embeddings, each carrier has exact maximum lengths128 and
120. The micro TCN costs `4*128*(64*3+64*64)` MACs; the bin TCN costs
`7*120*(64*3+64*64)`, with projection/role MACs given by the matrix products above.
Shared raw group projection costs `G_s*(input*32+32*64)` once per session/side/modality, not
once per decision. Probe receipts report `G_s`, extraction/model wall, RSS/VRAM, and the
increment versus DIRECT_CAPACITY_MATCH; >20% of total frozen pipeline wall is COST_REFUSED.

All arms have separate stock-print, stock-NBBO, option-print, and state heads
`64->32->8` (SiLU); logits add. Outputs are net regression, opportunity >0, >=$100,
>=$300, barrier three-class logits (three outputs), and MAE>$300 risk. The barrier
occupies indices4..6 and risk is index7.
Loss weights are Huber(delta1)=1, same-clock pairwise logistic=.5, opportunity BCEs
(.5,.25,.25), barrier CE=.1, risk BCE=1, all session-balanced and availability-masked.

The frozen ladder is:

1. `CLOCK_STATE` timing/state-only null, with market embeddings zero and identical heads;
2. `DIRECT_RAW` additive raw summaries;
3. `DIRECT_CAPACITY_MATCH`, the preregistered five-encoder no-order capacity control;
4. `NATIVE_ORDER`, unchanged direct summaries plus additive recent-group and 120-bin TCNs;
5. `NATIVE_INTERACTION`, identical additive logits plus rank-8 residual
   `2*tanh(W[(Us h_stock)*(Uo h_option)*(Ue h_state)*g])`, where stock is the reliability-
   weighted mean of print/NBBO embeddings and
   `g=(max(r_print,r_nbbo)*r_option*r_state)^(1/3)` from observed-group fractions;
6. `DYNAMIC_POLICY`, no new fit/parameters: the NATIVE_INTERACTION scores are replayed
   through the watch chronology below.

Here `Us,Uo,Ue` are bias-free 8x64 matrices, `W` is bias-free8x8 (eight outputs by rank),
`r_print/r_nbbo/r_option` are the frozen `r_modality` columns, and
`r_state=min(1,visible_candidate_count/4)`. The stock embedding is
`(r_print*h_print+r_nbbo*h_nbbo)/max(r_print+r_nbbo,1e-12)`, zero when both are absent.

No marginal result can kill NATIVE_INTERACTION. Seed 20260810, AdamW 1e-3, weight decay
1e-4, 10 epochs, no tuning/early stop. For the ordered unique clock roster of length N,
training selects ranks `floor((j+0.5)*N/256)`, j=0..255 (all ranks when N<256), includes
every authorized side at each selected clock, and weights each session equally. Each
chronological session is one optimizer minibatch; sessions and rows remain chronological
in every epoch and there is no shuffle. Float32, TF32 disabled,
`CUBLAS_WORKSPACE_CONFIG=:4096:8`, and deterministic algorithms are mandatory.
IDs/hashes/outcomes never select rows.
The net-ranking loss contains exactly one pair for an equal `(session,decision_ordinal)`
when both LONG and SHORT labels are OK and unequal; equal targets and missing sides are
masked. Pair weights are 1/(train pairs in session), row losses are 1/(train rows in
session), and each family is separately renormalized to mean weight1.

## 6. Fixed policy, chronology, and scorecard

Risk calibration and certification never inspect TEST. Each 100-session calibration
block is split chronologically: F4 Platt-fit398..447/risk-cert448..497 and F5
Platt-fit523..572/risk-cert573..622. For each fitted arm, unregularized float64 Platt
`p=clip(sigmoid(a*logit+b),1e-9,1-1e-9)` is fit on the first 50 sessions with
session-balanced BCE, initialization `(a,b)=(1,0)`, L-BFGS max1000 and gradient tolerance
1e-12; nonconvergence or a missing class is degenerate.

The primary candidate cutoff is fixed ex ante at `p<=.01`; no other cutoff may replace
it. On the latter 50 CAL sessions, apply predicted-net>0, the .01 cutoff, and the exact
chronological replay separately to all 32 headline cells (two folds times the five fitted
arms' D0/D30/D60 panels plus the interaction DYNAMIC panel). For a cell let n be selected
trades and k their literal `certificate_mae_cent>30000` breaches. The .01 policy is
admissible only if n>=500, at least30 distinct CAL-cert sessions trade, **and k==0**.
Any k>0, degenerate Platt fit, insufficient support, or nonfinite score deterministically
yields `PASS_ALL` (zero ENTERs) for that cell—never a looser cutoff.

Risk uncertainty is session-blocked. For each of all50 CAL-cert sessions (zero-trade days
included), let `Z_s=1` iff the cell's exact replay has at least one breach and K=sum Z.
Publish the simultaneous one-sided session-block Clopper-Pearson bound
`U_session=BetaQuantile(1-0.05/32; K+1,50-K)` for K<50, else1. It is a finite-sample
certificate only under the explicitly stated exchangeable Bernoulli-session assumption;
no within-session trade independence is asserted. The analogous per-trade bound
`BetaQuantile(1-0.05/32;k+1,n-k)` is descriptive only and cannot certify the policy.
Neither bound relaxes the k==0 admission law. TEST still requires literal zero realized
breaches; any TEST breach fails the cell.

Frozen nonbinding diagnostic panels cross net thresholds {0,10000,30000} cents with risk
thresholds {.01,.025,.05,.10}; all are reported and none is a test-fold champion or a
fallback when the primary cell is PASS_ALL.

At an equal decision timestamp, select the unique highest predicted-net legal side among
rows passing the frozen gate; an exact top tie abstains. A selected row uses only its own
fresh label/exit. A new entry requires `decision_ts > prior certificate_exit_ts`; there
is no cooldown and all zero days remain. Occupied clocks cannot enter.

CLOCK_STATE, DIRECT_RAW, DIRECT_CAPACITY_MATCH, NATIVE_ORDER, and NATIVE_INTERACTION each
publish three static replays, one using only D0-supporting rows, one D30, and one D60;
the prediction table is still unique and a stage view comes only from the watch ledger.
DYNAMIC_POLICY alone combines stages.

The watch ledger supplies implicit actions. At D0/D30, every unselected or occupied watch
automatically WAITs to its next registered checkpoint; at D60 it PASSes/expires. Selecting
an action closes all supporting watches for that action. Other same-clock watches WAIT or
PASS by their own stage. Thus DYNAMIC_POLICY changes chronology only; it has no learned
future/teacher/WAIT target and no arbitrary focal candidate.

Primary F4/F5 metrics are continuous-net Spearman/MAE and same-clock ranking accuracy;
action and candidate-watch precision/recall for net>0/>=$100/>=$300; selected delay and
regret versus the best own D0/D30/D60 checkpoint of that watch; and risk AUC/Brier/ECE,
breach count, and zero-breach feasibility. Watch recall uses inverse action-multiplicity
weights so converged watches do not inflate it. Barrier class/OVR and noncensored
FAVORABLE-vs-ADVERSE AUC are auxiliary only. Secondary hindsight replay reports
dollars/all-session, trades/day, MDD, MAE quantiles/max/>$300, zero days,
leave-top-10-out, and min-year. The diagnostic economic flag is $1600/session,
MDD<$1000, and zero MAE>$300 in both folds, but can never promote a certificate-exit
strategy.

MDD is exact zero-inclusive end-of-day drawdown: form one net-dollar value for every
chronological test session (zero on no-trade days), set equity E0=0 and
`Ek=sum_{i<=k} daily_i`, include E0 in the running maximum, and report
`max_k(running_max(E0..Ek)-Ek)`. No intraday interpolation or omission of zero days.

## 7. Executable controls and cost gate

Before lawful interpretation: (a) a clean same-architecture refit replacing only the
always-present session-time-fraction scalar with the TRAIN-normalized row's own future
`certificate_net_cent` must give the >0 opportunity head AUC>=.98 in both folds; (b) a
separate clean refit replacing that same scalar with the row's own future MAE-breach bit
must give the risk head AUC>=.98; width, parameters, optimizer, rows, and all other inputs
stay identical; (c) balanced XOR gives additive AUC [.45,.55] and rank-8
interaction >=.98; (d) mutating all tokens at/after cutoff is bit-invariant and moving
one token across cutoff affects only later rows; (e) reversing the valid recent-128
timestamp-group sequence is reported, while any within-timestamp permutation must be
bit-identical; (f) `BIN_ORDER_REVERSE` reverses the value+mask tuples only within the
ordered valid in-session support of the 120 bins, leaves fixed pre-open pads/validity in
place, keeps the valid-bin multiset and every DIRECT/micro input bit-identical, and is reported as the
matched full-path-order destruction; (g) the +17m
cross-stream control greedily pairs the earliest unused action with an exact unused
same-session/side/stage-mask/availability action 17m later, swaps option embeddings, and
evaluates only these common-support pairs (no wrap; exact operand multiset preserved);
(h) interaction-only derangement sorts within `(session,side,stage-mask,availability)`
and swaps adjacent option operands, excludes an odd last row, and must preserve every
additive logit bit-for-bit; (i) side reflection swaps LONG/SHORT and declared oriented
channels/masks with max absolute paired-logit error <=1e-6; and (j) label shuffle applies
PCG64 Fisher-Yates with `SeedSequence(20260810,sid,stage_mask,side_index)` inside
`(session,stage-mask,side,label-availability)` and moves the complete target bundle.
The equal-ms control permutes a real multirow timestamp group through the **actual stock,
NBBO, option, prior-state, DIRECT, micro, and bin constructors** and requires every output
bit and all later prior states to remain identical; a standalone reducer fixture is not
evidence. Production-constructor mutants also move a group across the newest-visibility
equality, drop the first/previous sequence-valid group, replace separate NBBO scalar means
with mean-of-derived values, duplicate one attachment failure reason, reverse a same-group
row order, and place a token on each bin/cutoff boundary; each must fail or change only the
declared typed output. Controls never tune the model. Failed
positive/causality/key/side gates make lawful nulls uninterpretable.

The production probe is exactly {125,500,625}, two runs, and must show late-sibling
deletion invariance; an exact primitive-versus-UNION/unknown census with zero nonprimitive
watch/context/action rows; complete primitive candidate->side FD; the one-member
candidate-key mismatch and multi-member split physical-event mutations must each refuse;
zero member/clock/key errors; explicit
SIDE/ENTRY/EXIT-unavailable censuses; raw attached-clock and single-leg/multileg witnesses;
locked/crossed/one-sided quote-sign refusal plus strict-prior tick fallback; stock
condition0/extended/cancel mutants; suffix/reflection/equal-ms/midpoint-carry/
BIN_ORDER_REVERSE controls; byte identity; and
measured wall/RSS/VRAM. Locke's reader-only
benchmark `bcfbd3049...` freezes four workers (85.12M rows/s, ~94s scoped projection);
the probe must replace model/extraction estimates and each incremental family must cost
<=20% of the frozen pipeline or be typed COST_REFUSED. Long jobs use `lab/run.sh`; all
cache publications stage then no-replace seal. No implementation or launch precedes a
GREEN review on these exact bytes.
