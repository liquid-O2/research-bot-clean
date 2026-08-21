# RIBBON_LEGEND — the raw-stream data dictionary (R2-7)

STATUS: the reader loads this ONCE PER SESSION. It is session-constant, so it costs its tokens once
and every ribbon read afterwards is interpreted against it. **No raw view ships without its
dictionary** (R2-7). The column terms in §2 are the exact strings
`engine/port_m2/ribbon.py:ACTION_COLUMNS` prints as the action-grain header;
`engine/port_m2/test_r2views_fixlane.py:t05` pins the two together so they cannot drift.

SOURCES, NAMED
* **LIB** — read off the installed official library at build time (`databento_dbn` 0.66.0):
  `Action.variants()`, `Side.variants()`, `F_*` constants, `FIXED_PRICE_SCALE`, `UNDEF_PRICE`,
  `UNDEF_ORDER_SIZE`, `UNDEF_TIMESTAMP`. These are not retyped from memory; if the library changes,
  `ribbon.py` changes with it and this file's §3/§4 tables are re-derived from it.
* **AUDIT** — the Databento schema audit adjudicated 2026-08-15 ~14:30Z (JOURNAL.md), which quoted
  the official normative documentation field by field and proved a 3-way byte-identical decode
  (official C++ / official Python / our `qr_dbn`, 20 fields, 2 sessions including the 79.9M-record
  NKD yearly file).
* **MEASURED** — a number this program measured on its own corpus; the measurement is cited inline.
* **DECODER** — `engine/cpp/qr_dbn/include/qr_dbn/dbn.hpp`, the verified binary layout
  (`Mbp1Msg` = 80 bytes; `RecordHeader` 16; `BidAskPair` 32).

WHAT THE RIBBON IS. `ribbon.py --grain action` decodes the payload file with the OFFICIAL
`databento-dbn` Python library and prints **every** MBP-1 record of the session-dominant instrument
in the requested causal window — no sampling, no aggregation, no rounding, no row bound (D-092.1).
A window too large to read is narrowed BY THE READER. The tool never thins.

---

## 1. THE SCHEMA IN ONE PARAGRAPH

MBP-1 ("market by price, one level") is a per-EVENT stream. Each record says what happened
(`action`) on which side of the book (`side`) at what price and size, and then shows the **top of
book after that event** (`bid_px/bid_sz/bid_ct`, `ask_px/ask_sz/ask_ct`). It is a book-state feed
with the causing event attached — not a bar, not a sample, not a snapshot on a timer. Depth beyond
level 1 is not present at all: what you cannot see here is not "quiet", it is **not carried by this
schema**.

---

## 2. THE COLUMNS, IN PRINT ORDER

| term | meaning | source |
|---|---|---|
| `ts_event` | Exchange matching-engine timestamp of the event, **UTC nanoseconds, full precision, never rounded**. THE clock: every causal bound, window, and ordering in this program is `ts_event`. | LIB / DECODER |
| `gap_ns` | `ts_event` minus the `ts_event` of the PREVIOUS record of this instrument. Derived by the ribbon, not a DBN field. This is the speed/burst signal: sub-millisecond gaps are a burst, multi-second gaps are a dead book. The FIRST printed row's gap is measured against the last record BEFORE the window (strictly earlier, so causal); when no predecessor exists in the session it prints `.`. **`N/A` means a BACKWARD step** — see §6. | ribbon.py |
| `sequence` | Venue sequence number of the record. Strictly increasing within an instrument's normal stream; the tie-break in our own sort key (`np.lexsort((sequence, ts_ns))`). Use it to detect that two records at the same `ts_event` are ordered, and to quote an exact record in a note. | LIB / DECODER |
| `action` | What happened. One ASCII letter — see §3. | LIB |
| `side` | Which side. One ASCII letter — see §4. **On a TRADE record this is the AGGRESSOR's side**, not the resting side. | LIB / AUDIT |
| `price` | The price of the EVENT (the order's price on add/cancel/modify, the fill price on a trade), raw `int64` divided by `FIXED_PRICE_SCALE = 1_000_000_000` (1e-9), printed exactly with trailing zeros dropped. **Printed on every record, not only on trades** — 14.5% of SI non-trade events touch a price off the printed top of book (MEASURED, audit), which is the "level wiped / level built" signal that a book-only view destroys. | LIB / AUDIT |
| `size` | Order or trade quantity in contracts. `UNDEF` = `UNDEF_ORDER_SIZE` (4294967295), the library's null sentinel. | LIB |
| `flags` | The raw flags byte AND every documented bit it carries, as `N=letters` (e.g. `130=LP`) — see §5. An undocumented set bit prints as `?<value>`; it is never dropped. | LIB |
| `bid_px` `bid_sz` `bid_ct` | Top-of-book BID **after** this event: price, total resting size, and **number of orders** at that price. `bid_ct` is the queue-composition discriminator: 30 lots in 2 orders and 30 lots in 15 orders behave differently under pressure. | LIB / DECODER |
| `ask_px` `ask_sz` `ask_ct` | Top-of-book ASK after this event, same three quantities. | LIB / DECODER |
| `ts_in_delta` | `ts_recv - ts_exchange_send`, in nanoseconds: the venue-side matching-engine/gateway latency for this record. Observed range on our corpus 0–169 µs (MEASURED, audit). A latency excursion during a burst is itself information about venue stress. | LIB |

`depth`, `publisher_id`, `rtype` and `ts_recv` are decoded but not printed: `depth` is always 0 at
MBP-1, `publisher_id`/`rtype` are constant within a session, and `ts_recv` is the capture clock
(§7). Ask for them if a question needs them — they are one line of code away, never withheld.

---

## 3. `action` — every code

| code | library name | the event it denotes |
|---|---|---|
| `A` | `ADD` | A new resting order joins the book at `price` on `side`. Queue GROWS. |
| `C` | `CANCEL` | A resting order is removed at `price` on `side`. Queue SHRINKS — the pull. |
| `M` | `MODIFY` | A resting order is changed (size and/or price). A size-down modify is a partial pull; a price modify moves the order. |
| `T` | `TRADE` | A trade PRINT. `side` = the AGGRESSOR. **The print does not itself apply the book update** — the resting size comes off on the FOLLOWING `C`/`M` record. MEASURED on SI 20210701: 24,258 of 24,259 trades show an unchanged L1 size at their own record; the audit re-proved it at 47,839/47,839. Read a trade and its next one or two records together. |
| `F` | `FILL` | A fill event (order-level). Not present in GLBX MBP-1 in our corpus. |
| `R` | `CLEAR` | Clear the book for this instrument — everything resting is gone. Note the letter is `R`, not `C`. |
| `N` | `NONE` | No action / padding. |

READING THE STORY: `A` is commitment, `C` is withdrawal, `M` is repositioning, `T` is someone
paying the spread. "Who adds, who pulls, who hits" is exactly this column read in sequence.

---

## 4. `side` — semantics, including on trades

| code | library name | on a RESTING-ORDER record (`A`/`C`/`M`) | on a `T` (TRADE) record |
|---|---|---|---|
| `B` | `BID` | the order rests on the BID | the **aggressor BOUGHT** — a buyer lifted the offer (+flow) |
| `A` | `ASK` | the order rests on the ASK | the **aggressor SOLD** — a seller hit the bid (−flow) |
| `N` | `NONE` | no side / not applicable | unsigned trade; contributes 0 signed flow |

The library's own docstring for `Side` states it is "the side of the market for resting orders, or
the side of the aggressor for trades" (LIB); the audit confirmed the same from Databento's
normative documentation (AUDIT). Every signed-flow number in this program uses this convention
(`tape.classify_trades`).

TRAP: on a trade record, `side=A` means a SELL. It is the aggressor's side, not the side the
liquidity was resting on. Read `T A` as "someone sold into the bid".

---

## 5. `flags` — every bit

| bit | value | library name | meaning | letter printed |
|---|---|---|---|---|
| 7 | 128 | `F_LAST` | Last record of the event at this `ts_event` — the book state on this record is the SETTLED state for that instant. A burst of records sharing one `ts_event` is ONE event; only the `L` row's book is final. | `L` |
| 6 | 64 | `F_TOB` | Record contains top-of-book data only. | `T` |
| 5 | 32 | `F_SNAPSHOT` | Record is from a book SNAPSHOT / replay, not a live event. Snapshots may carry stale or out-of-order `ts_event` — see §6. | `S` |
| 4 | 16 | `F_MBP` | Record is aggregated to price level (MBP), i.e. not order-by-order. | `M` |
| 3 | 8 | `F_BAD_TS_RECV` | `ts_recv` is known bad. `ts_event` is unaffected — it stays the clock. | `B` |
| 2 | 4 | `F_MAYBE_BAD_BOOK` | The book state on this record may be unreliable. | `K` |
| 1 | 2 | `F_PUBLISHER_SPECIFIC` | Publisher-defined bit. Present on essentially every GLBX record in our corpus (`130 = 128+2` is the common value). | `P` |
| 0 | 1 | — | Not named by the library. If set it prints as `?1`; a bit nobody names is still a bit that was set. | `?1` |

---

## 6. BACKWARD `ts_event` STEPS — the one ordering hazard

The schema audit found **57 records whose `ts_event` is EARLIER than their predecessor's**, all on
NKD yearly payload files, and **every one of them carries `F_SNAPSHOT`** (audit defect D3; the
related D2 finding counted 262 folded snapshots on NKD-2024, 257 inert + 4 benign restores).

These are book REPLAYS folded into the stream, not events that happened out of order. The ribbon
therefore prints `gap_ns = N/A` on such a row rather than a negative number — a backward step is
not a measurement of speed — and the row's own `flags` column carries the `S` that explains it. The
header names the count for the window whenever it is non-zero.

Read a run of `S` rows as "the feed restated the book here", and take your speed reading from the
non-snapshot rows around it.

---

## 7. THE THREE CLOCKS

| field | what it is | authoritative? |
|---|---|---|
| `ts_event` | Exchange matching-engine event time, UTC ns. | **YES.** Every window, causal bound, ordering and gap in this program is `ts_event`. The M0 spec §0 pins it ("clock: ts_event") and the causal guard tests it. |
| `ts_recv` | Databento capture-gateway receive time, UTC ns. Later than `ts_event` by the network+capture path. Unreliable when `F_BAD_TS_RECV` is set. Decoded, not printed. | no |
| `ts_in_delta` | `ts_recv - ts_exchange_send`, ns — venue-side send latency for this record. Printed. | no (it is a latency, not a clock) |

Never mix them. A window is `ts_event`; a latency reading is `ts_in_delta`.

---

## 8. PRICE, SIZE, NULL SENTINELS

* `FIXED_PRICE_SCALE = 1_000_000_000` (LIB). Every price field is an `int64` of 1e-9 units:
  `22790000000` is `22.79`. The ribbon prints the exact decimal with trailing zeros dropped — no
  rounding, ever.
* `UNDEF_PRICE = 9223372036854775807` (`int64` max, LIB) prints as `UNDEF`. It is a NULL, never a
  price; nothing arithmetic may touch it. (Our own guard constant `SENT_HI = 2**62` in
  `engine/port_m0/common.py` is the conservative threshold the derived layers test against.)
* `UNDEF_ORDER_SIZE = 4294967295` (`uint32` max, LIB) prints as `UNDEF`.
* `UNDEF_TIMESTAMP = 18446744073709551615` (`uint64` max, LIB) — a timestamp field that is null.
* A missing/undefined value is always PRINTED as its sentinel name. It is never silently zero, and
  a refusal is never a blank.

---

## 9. `sequence` AND `gap_ns` — how to read them

* **`sequence`** rises monotonically within an instrument's live stream. Same `ts_event`, rising
  `sequence` = one event decomposed into several records (an aggressive order sweeping several
  resting orders, for example): read them as ONE action and take the book from the `F_LAST` row.
  A `sequence` jump with no `ts_event` jump means records for other instruments were interleaved —
  not a gap in this instrument's story.
* **`gap_ns`** is the inter-arrival time and it is the cheapest read of market state on the sheet:
  * gaps of 10⁴–10⁶ ns (10 µs–1 ms) in a run = a burst, an algorithm working;
  * gaps of 10⁸–10⁹ ns (0.1–1 s) = a normal quiet book;
  * gaps > 10¹⁰ ns (10 s+) = nothing is happening; a "confirmation" formed here has almost no
    participation behind it;
  * `N/A` = backward step at a snapshot (§6);
  * `.` = the first record of the session, no predecessor.

---

## 10. WHAT THIS SCHEMA CANNOT TELL YOU

Stated so it is never inferred by accident:

* **No depth beyond level 1.** Size behind the top of book is invisible. An "empty" book above the
  offer is not evidence of thinness.
* **No order identity.** MBP-1 is aggregated to price level. A refill by a new participant and a
  re-post by the same one are indistinguishable; `bid_ct`/`ask_ct` give you the ORDER COUNT at the
  level, which is the closest available discriminator.
* **No participant identity, ever.**
* **Implied/spread-leg fills** can print a trade whose book reaction is absent
  (`sections._refill_after_trade` excludes exactly these from its denominator).
* **The trade print is not the book update** (§3, `T`).

---

## 11. HOW THE READER USES IT (D-092)

The digest row and the 3-point R2-2 trajectories NAVIGATE — they tell you which episodes to open.
The chart panels RENDER — they show the shape. **Neither decides.** Every TAKE is decided on the
true event sequence read through:

```
/usr/bin/python3 engine/port_m2/ribbon.py --cid <CID> --from T-<sec> --to T --grain action
```

and every such read is written to `artifacts/cache/port/m2/ribbon/RIBBON_ACCESS.tsv`, so what was
actually looked at is provable after the fact (R2-1, enforced in `episode_round.score`).
