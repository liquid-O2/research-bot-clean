# Discretionary-course confirmation extraction — shared lane contract (2026-08-22)

USER RULING (verbatim source: DIRECTIVES_INBOX 2026-08-22): the confirmation framework is
THE framework — WAIT/PASS states were built on it; entry decisions may wait ≥5 minutes
after candidate formation (5 min is an UPPER-bound guess, confirmation may come later);
the PDFs' images/diagrams carry pattern information the text alone does not; extract the
book's confirmations AND look for better/more confirmations than the book describes.

PDFs: /workspace/artifacts/cache/book_pdfs_20260822/*.pdf (30 files, 389 pages).
Read EVERY page of your assigned PDFs with the Read tool (pages param, ≤20 pages/request)
so the figures are seen, not just the text layer. The figures are the point: prior pass
(artifacts/reference/discretionary_20260819/READ_NOTES.md) read text-first and produced
prose grammar with no computable output.

## What each lane returns (write to your own file, nothing else's)

A digest at /workspace/design/book_confirmations/<your-lane-file>.md with one entry per
confirmation/setup/pattern found in text OR figure:

- **NAME** (short, unique) + source (pdf, page numbers).
- **SETUP**: the context that must already exist (location: extreme / value edge / POC;
  HTF thesis state; what formed the candidate).
- **CONFIRMATION SIGNAL**: the exact observable sequence that licenses entry — tape/DOM/
  delta/profile events in order. Where a FIGURE shows structure the text under-specifies
  (wick geometry, delta bar sequence, ladder sizes refilling, profile shape, where the
  entry arrow actually sits relative to the pattern), describe what the figure shows
  explicitly and note "figure-only detail".
- **TIMING**: when after setup formation the confirmation appears (seconds/minutes/bars
  as the source states or the figure implies). This feeds a formation+Delta decision
  design — timing is first-class.
- **ENTRY TRIGGER + INVALIDATION** per the source (order type, placement, stop logic).
- **PASS / NO-TRADE** conditions (chop, POC magnet, unfinished value, no reward, etc.).
- **FEATURE MAPPING (best-effort)**: which of our per-second feature families could
  compute this — disc_evt_* (attacks/lifts/reloads/pulls), disc_quote_* (depletion/
  rebuild), disc_auction_*/disc_prior_*/disc_ib_* (levels/value), disc_level_z*
  (defense/reaction at levels), w{15..1800}_* (flow/displacement windows),
  disc_tclock/vclock (tape speed). Mark UNKNOWN where our stream lacks the observable —
  a named gap is a deliverable, not a failure.
- **BEYOND-BOOK**: anything the figures imply beyond the text; any confirmation idea the
  material suggests but does not name.
- **VERBATIM**: 1-3 exact quotes with page refs for the load-bearing rules.

End with: a TIMING TABLE (confirmation name → typical delay after formation) and a
PASS-RULE list. Session-walkthrough PDFs: extract the trades' confirmation sequences and
timings as CASES, same schema, plus what the trader REJECTED and why.

## Laws
- Read-only on the repo except your own digest file. You are a subagent. Don't run memo.
- Anchored evidence: every claim carries (pdf, page). No summary without pages.
- Do not evaluate our system, propose architectures, or discuss position sizing — this is
  extraction. The synthesis is the orchestrator's (D-002).
- Terminal state required: success (digest written, every assigned page read — state the
  page count you read per PDF) / blocked / exhausted.
