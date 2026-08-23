# 33: Replicate the hold rule off 2021

**What to build:** the ticket-28 rule, frozen, measured on 2022 to 2025H1.

2021 can kill a rule and can never promote one, and every ticket-28 number rests
on 67 days of it. THRESHOLD and FORWARD have now been read five times across
runs 1 to 5; their power as held blocks is spent for this rule family. The
promotion tier is fresh years.

D-110 makes the corpus cheap on purpose: build only the four Delta-grid rows per
series, not the 296-row replay store.

**Blocked by:** 29, and whichever of 30, 31, 32 the program decides to freeze.
Nothing is replicated until the rule stops moving.

**Status:** blocked

- [ ] Corpus build is roughly one box-hour, arithmetic written before the run
      (D-109)
- [ ] The rule is frozen BEFORE the new years are opened; no knob is touched
      after they are read
- [ ] Receipt reports per asset-day dollars, per-day SE, entry counts and MDD
      against the rung on every new block
- [ ] 2025H2 stays sealed

## Scoping, 2026-08-23 (measured, before any launch — D-109)

**The corpus does not exist and must be built from raw.** The durable store's
verified sessions are 2021 only: 586 sessions, HG 238 / NKD 238 / SI 110, 78 GB
at `provenance/entry_v2/.entry-v2-durable-store/`. A date scan over its
manifests finds 2021 stamps and nothing for 2022-2024.

**The raw inputs are on disk**, `artifacts/reference/futures_mbp1/`, 47 GB:

| Asset | Layout | Years present |
|---|---|---|
| Copper (HG) | annual bundles `glbx-mdp3-YYYY0101-YYYY1231.mbp-1.dbn.zst`, 13 GB | 2021-2026 |
| NKD | annual bundles, 7.6 GB | 2021-2026 |
| Silver (SI) | daily files, 1,565 of them, 27 GB | 2021-2026 |

2026 is sealed escrow and 2025H2 is sealed by law, so the buildable window is
2022, 2023, 2024 and 2025H1: roughly 875 sessions per asset, about 2,625 in
total, which is **4.5x the entire existing store**.

**No per-session build rate is recorded anywhere in the repo.** The journal has
no sessions-per-hour figure and the 2021 build predates the current receipts. So
the D-109 arithmetic cannot be written yet, and under D-109 nothing launches
without it.

**Therefore the next action is a rate measurement, not a build:** run
`engine/entry_v2/corpus.build_corpus` on ONE 2022 session end to end, receipt
the wall time, and multiply. That single session also proves the annual-bundle
path works for HG and NKD, which have never been read outside 2021 and whose
per-day slicing is untested.

If the measured rate puts the full window over six hours, D-109 is explicit: the
answer is faster code, not less science, and both the arithmetic and the speed
option go to the user BEFORE the run.

**A cheaper first cut exists and should be priced alongside it.** One year
(2022) is about 750 sessions total and would already give 5x the days per block
that every current verdict rests on, at roughly a quarter of the full cost. The
standard errors are the binding problem: $169-374 on cash of $790-1,061.
