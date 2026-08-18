# Entry V2 Databento Clock and Book-State Law

> **Frozen substrate law; not a learned result.** The QRE2/Databento substrate,
> teacher, and candidate preflights produced useful retained evidence, and the
> v9 durable warm corpus completed in 518.133 seconds with zero physical source
> opens/fills. The replacement learner nevertheless never began: v9 failed at
> raw fidelity before C0. Execution is stopped and 2025H2 remains sealed. See
> [`../docs/ENTRY_V2_CURRENT_STATUS.md`](../docs/ENTRY_V2_CURRENT_STATUS.md)
> for the current boundary and exact attempt ledger.

## Status and authority

This is the frozen implementation law for the Entry V2 raw-event substrate. It
extends `ENTRY_V2_RECOVERY_PLAN.md` and its amendments. It was required after
the first production substrate wave failed closed on a real Databento snapshot
block. No result from that wave is authoritative. Section 7 incorporates the
user's 2026-08-16 clarification that the owned annual files may supply a
strictly bounded development prefix; the seal protects H2 from statistical use,
not from transport-layer decompression.

The law fixes causal-boundary defects, including the later-observed standalone
`BAD_TS_RECV` reconstruction bursts whose invalid receive clocks are not
snapshot markers. It does not change the Entry V2 goal,
candidate economics, teacher, replay caps, or certification denominator.
Certification remains strictly more than $2,000 per asset per trading day,
independently for SI, HG, and NKD; $2,000 is the low floor, not the objective.

## 1. Decoder boundary

Production Entry V2 decoding SHALL use a narrow adapter over the vendored,
upstream-identical `databento-cpp` v0.64.0 source at commit
`12eca77e70137ea848e4af3f4173ee0569cbf1aa`.

The adapter SHALL:

- own `databento::DbnFileStore` and `databento::TsSymbolMap`;
- iterate MBP-1 records in physical decoder order;
- use `Mbp1Msg::IndexTs()` as the availability timestamp for every record not
  marked standalone `BAD_TS_RECV`;
- use the UTC date of valid `IndexTs()` for symbol mapping, while deferring
  symbol lookup entirely for standalone `BAD_TS_RECV` transport rows;
- expose only a small repository-owned normalized record downstream;
- translate every SDK error and missing exact symbol mapping into a typed
  refusal; and
- pin the official vendor-tree hash, upstream commit, adapter source hash,
  executable hash, and input provider hash in receipts.

Official SDK types SHALL NOT escape the adapter. The existing `qr_dbn` decoder
remains an independent differential oracle only. Its output may never be the
production authority for Entry V2.

## 2. Exact clock law

Every normalized record carries both clocks without conversion:

- `ts_recv_ns`: Databento `IndexTs()` and the only causal-availability clock;
- `ts_event_ns`: exact exchange/source timestamp and a model feature only; and
- `source_ordinal`: physical MBP-1 decoder order within the ordered input
  manifest.

The binding rules are, except for the quarantined standalone-clock condition
defined in section 3:

1. Availability, ordering, session partition, phase assignment,
   `receive_session_sec`, cutoff, confirmation, decision, teacher traversal,
   horizon target, and forecast grid all use `ts_recv_ns`.
2. Trading day is `trade_date_for(ts_recv_ns)` under the declared Globex
   half-open session `[open, close)`.
3. Symbol lookup uses `floor_UTC_date(ts_recv_ns)`, which is deliberately
   separate from the Globex trading day.
4. `ts_recv_ns` must be nondecreasing in physical decoder order. A descent is
   a typed refusal and is never sorted away.
5. Equal `ts_recv_ns` records retain physical decoder order. `sequence` and
   `ts_event_ns` may not reorder ties.
6. A candidate prefix is exactly
   `lower_bound(ts_recv_ns, decision_ts_ns)`. Every record whose receive time
   equals the decision is future, as an indivisible equal-time batch.
7. `ts_event_ns` may decrease, fall outside the receive session, or be later
   than `ts_recv_ns`. None of those facts changes causal visibility.
8. H2 and source-window admission use receive/index time and the input seal law
   in section 7, never event time.

## 3. Snapshot and book-health law

All admitted non-clock-tainted source records and exact flag bytes remain
available to the causal student tape, but derived economic observations require
a trusted book state. A standalone `BAD_TS_RECV` payload is never admitted to
that tape.

### Snapshot blocks

A contiguous `SNAPSHOT | BAD_TS_RECV` block at one receive timestamp is an
atomic state initialization/reset at that timestamp. It SHALL:

- initialize the book in physical decoder order;
- reset pending motion, extrema, return continuity, and candidate machines;
- remain represented as typed raw-prefix input; and
- restore ordinary eligibility only after the first subsequent trusted,
  non-snapshot, sane MBP-1 observation.

It SHALL NOT contribute to:

- dominance or activity tallies;
- phase fitting or spread priors;
- ATR/OHLC, returns, realized volatility, or forecast observations;
- zigzag motion, confirmations, entry anchors, or candidates;
- teacher path points, wall/MFE/MAE traversal, or horizon targets.

For snapshot rows, `ts_recv_ns - ts_event_ns` is source-state age, not ordinary
receive latency. The raw values remain exact and a typed snapshot mask tells the
model which interpretation applies.

### Other quality flags

- `BAD_TS_RECV` without `SNAPSHOT` is a standalone availability-clock defect,
  not evidence of a duplicate, correction, snapshot, or unusable provider
  order. The adapter exposes only the transport fields needed to identify and
  count the affected IID; it SHALL NOT use the invalid `IndexTs` for symbol
  lookup.
- The substrate SHALL quarantine each standalone `BAD_TS_RECV` row before
  receive-time validation, ordering, UTC symbol date, Globex date, economic
  state, event-pack serialization, feature construction, or model input. It
  SHALL NOT substitute `ts_event`, preserve a masked economic payload, dedupe
  by sequence, or update the previous-clean receive clock from the row.
- A burst is resolved only by bracketing it in physical provider order between
  the last and next clean, non-snapshot, non-`MAYBE_BAD_BOOK`, sane `F_LAST`
  records for the same IID. Both clean anchors must resolve to the same Globex
  trading day. Missing, cross-session, or end-of-input anchors are typed
  fail-closed clock refusals.
- After a same-session bracket, trusted-only tallies may continue and the
  quarantined count is attributed to that IID/session as audit metadata. The
  clean recovery anchor is a clock seed, not an economic tally observation.
- If the bracketed IID is the causally locked IID for that day, the event
  manifest status is exactly `BAD_TS_RECV_CLOCK_TAINT`; event count and trusted
  economic count are zero, `binary_file` and `binary_sha256` are absent, and no
  `.qre2` pack may remain. Candidate and teacher realization therefore stay
  empty and the locked asset-day remains in the certification denominator at
  exactly $0. Prior-only open-frozen forecast rows may remain, but the tainted
  day supplies no realization or state update.
- `MAYBE_BAD_BOOK` taints trusted book use until an explicit valid snapshot
  reset. If no reset occurs, the affected session cannot certify tallies,
  candidates, teacher paths, forecasts, or targets.
- `F_LAST` is retained as source data and does not ordinarily gate MBP-1
  economic observations; its sole additional role is closing a standalone
  receive-clock quarantine at a complete clean book-update boundary.
- Publisher-specific or reserved bits are preserved and do not become generic
  failures without an explicit documented law.

Every tally, event manifest, and receipt reports raw-record, trusted-economic,
snapshot, standalone-bad-receive-clock, and maybe-bad-book counts.

## 4. QRE2 V2 binary contract

The event row remains 76 bytes, but its clock semantics are intentionally
incompatible with V1:

| Byte offset | V2 field | Law |
| ---: | --- | --- |
| 0 | `ts_recv_ns` | availability/index time |
| 8 | `ts_event_ns` | exchange/source feature |
| 16..67 | existing exact MBP-1 fields | unchanged widths |
| 68 | `receive_session_sec` | derived from receive time |
| 72..75 | existing depth/reserved tail | unchanged widths |

Magic becomes `QRE2EVT2` and header version becomes 2. V2 readers hard-refuse
V1. No alias may reinterpret a V1 byte layout as V2.
Standalone `BAD_TS_RECV` payloads never appear in a QRE2 event pack; the
existing schema remains unchanged because a tainted locked session emits no
pack.

Event metadata and manifests name at least:

- `min_ts_recv_ns` and `max_ts_recv_ns`;
- diagnostic `min_ts_event_ns` and `max_ts_event_ns` where useful;
- `session_assignment_clock=ts_recv`;
- `symbology_date_clock=floor_utc(ts_recv)`;
- `causal_visibility_clock=IndexTs/ts_recv`;
- `exchange_feature_clock=ts_event`;
- `equal_receive_time=future`; and
- `tie_order=ordered_input_manifest_then_dbn_decode_ordinal`.

The prefix domain becomes `QRE2PREFIX2`. Candidate identity and every lineage
hash include the V2 event-pack hash, V2 prefix hash, and clock-law receipt hash.

## 5. Mandatory artifact-domain migration

All artifacts whose meaning depends on raw-event time, source eligibility,
candidate identity, future traversal, or model-array semantics receive a V2
schema/domain. At minimum this includes:

- input, tally, lock, phase, phase-profile, event manifest, event metadata,
  event pack, and substrate receipt;
- G1 prior, candidate, candidate manifest, teacher, teacher manifest, schedule,
  prefix, candidate identity/lineage, and all G1 receipts;
- forecast rows, model state, history, commits, source lineage, manifest, and
  receipt;
- Python event arrays, session-stream receipts, raw-prefix references, corpus,
  example lineage, teacher join, forecast join, normalizer, training trace,
  fold outputs, and frozen neural/policy artifacts.

Independent availability-stamped compliance and slow-context source schemas may
remain at their existing versions. Their V2 candidate/example join lineage must
still change.

Frozen weights, normalizers, and calibrators bind the exact ordered event-field
contract, event-array conversion-law hash, session-stream receipt aggregate,
corpus receipt, source lineage, and this law's receipt. Matching tensor widths
alone never permit a stale artifact to load.

## 6. Python model-array contract

Python readers expose exact `ts_recv_ns` and `ts_event_ns` names and search only
`ts_recv_ns` for candidate/horizon cutoffs. Public raw-prefix fields become
`first_availability_ts_ns` and `last_availability_ts_ns`; the ambiguous V1
`first_event_ts_ns` and `last_event_ts_ns` names are removed rather than aliased.

The existing continuous feature width is retained with explicit meanings:

- receive wall-clock second;
- receive microsecond and nanosecond remainders; and
- signed receive-minus-event microseconds and nanosecond remainder.

For exact signed delta `d = ts_recv_ns - ts_event_ns`, encode
`d = 1000*q + r` with signed integer `q` and `0 <= r < 1000`. Negative values
are neither clamped nor replaced by `max(ts_recv_ns, ts_event_ns)`.

## 7. Pre-H2 source seal

Until the pre-H2 system already exceeds the full asset-day goal for every
asset, the semantic development domain ends at the receive open of trading day
`20250701`: `2025-06-30T22:00:00Z` (`1751320800000000000` ns, 17:00
America/Chicago). Midnight UTC is not the trading-day boundary.

QRE2INPUT2 has two development access classes:

1. `DEVELOPMENT`: the provider-authenticated container is wholly before the
   boundary; and
2. `DEVELOPMENT_PREFIX`: the provider-authenticated container begins before and
   crosses the boundary, but only records with `IndexTs` strictly less than the
   boundary belong to the Entry V2 domain.

For `DEVELOPMENT_PREFIX`, the official decoder may decompress buffered bytes
and construct the first fixed-size record whose `IndexTs` is at or after the
boundary. Zstd may also have read a compressed chunk ahead. These are
transport-layer effects, not an H2 evaluation. Immediately after the adapter
returns that boundary sentinel, Entry V2 SHALL inspect only its `IndexTs` and
terminate the container before record-window validation, ordering, session or
symbol use, book state, tallies, counters, event artifacts, features, labels,
teacher paths, fitting, replay, or scoring. The sentinel and buffered tail never
enter any receipt count or economic artifact.

The owned provider-authenticated HG and NKD 2025 annual containers are therefore
admissible as `DEVELOPMENT_PREFIX` after their provider SHA-256 is checked once
at the raw admission boundary. A container beginning at or after the cutoff,
including every owned 2026 container, remains excluded before payload stat/open
from an ordinary pre-H2 list. H2 evaluation, labels, outcomes, campaign scoring,
and model selection remain prohibited. This transport stop does not count as
the one final H2 confirmation.

## 8. One consolidated adversarial gate

Before any production rebuild, one mechanical suite proves all of the
following:

1. reversed exchange times with monotone receive times retain provider order;
2. equal receive-time batches retain decode order and are wholly future at an
   equal decision;
3. decreasing receive time refuses and is never silently sorted;
4. sequence values cannot reorder receive-time ties;
5. a snapshot block is atomic in one receive session and initializes state
   without generating economic motion;
6. an HG-shaped standalone `BAD_TS_RECV` burst is omitted from symbol/date/
   ordering/economic/model inputs, brackets only on same-IID clean sane
   `F_LAST` rows, preserves trusted-only tallying, and makes a locked session
   `BAD_TS_RECV_CLOCK_TAINT` with no stale or new event pack;
7. `MAYBE_BAD_BOOK` taints until an explicit snapshot reset;
8. UTC symbol date and Globex trading day remain distinct and exact;
9. missing exact symbol mapping refuses with no interval fallback;
10. future `ts_event_ns` mutation cannot change an earlier prefix;
11. moving `ts_recv_ns` across a decision changes the prefix or refuses;
12. negative, zero, and large signed deltas reconstruct exactly;
13. a mixed annual prefix stops on the first boundary `IndexTs` before any Entry
    V2 state, count, or artifact, while an H2-only/2026 container is refused
    before payload open;
14. G1 confirmation, decision, prefix, and teacher traversal use receive time;
15. forecast grids remain receive ordered under reversed exchange times;
16. every V1 substrate, prefix, forecast, corpus, normalizer, and model artifact
    refuses under V2; and
17. official-vs-custom differential tools filter and stop by `IndexTs`, never by
    the assumed monotonicity of `ts_event_ns`; and
18. missing, cross-session, and end-of-input standalone-clock brackets refuse
    without substituting event time.

The suite includes the exact 45-row SI snapshot regression and an independent
synthetic construction for each refusal. Only after the entire gate passes may
the invalid partial cache be deleted and the substrate be rebuilt.
