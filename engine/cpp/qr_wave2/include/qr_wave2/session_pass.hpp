// qr_wave2/session_pass.hpp — ONE SESSION, REDUCED TO WHAT THE TWO FAMILIES READ.
//
// SPEC: design/DESIGN_FEATURES.md sha bf70dd35e5407863 §W2.13-PIN-1 (the source
// series: the frozen 1s-grid eligible-NBBO mids, and the eligible-print VWAP of
// B2) and §CC-012 (warmup ordinals 0..124 reach exactly this entry point and
// nothing else).
//
// THE TWO SCOPES ARE TWO OVERLOADS, NOT ONE FUNCTION WITH A FLAG. `run_pass`
// takes a `DayScope` or a `WarmupScope`, and CC-012's "accepted ONLY by
// prior-state accumulator entry points" is therefore a property of the type
// system rather than of a caller's discipline: this header is the only place in
// the tree that names `WarmupScope` outside qr_registry and the readers, and it
// produces a `SessionSummary` — a bag of prior-state scalars with no decision
// second, no side, no candidate and no label in it.
//
// THE SUMMARY IS ALWAYS COMPUTED THE SAME WAY for a warmup and a scoped
// session, because a prior is a prior: the same grid, the same eligibility, the
// same reduction. Only the SERIES (retained for in-scope decision construction)
// differ, and only because a warmup session never has decisions to construct.
#ifndef QR_WAVE2_SESSION_PASS_HPP
#define QR_WAVE2_SESSION_PASS_HPP

#include <cstdint>
#include <filesystem>
#include <vector>

#include "qr_carriers/grid_1s.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_clock/session_clock.hpp"
#include "qr_core/refusal.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_registry/warmup_scope.hpp"
#include "qr_wave2/prior_state.hpp"

namespace qr::wave2 {

/// Where the two payload trees live. Composed onto by the scope, never by a
/// day string (the path-forming law of qr_sources).
struct CorpusRoots {
  std::filesystem::path stock_quotes;
  std::filesystem::path stock_trades;
};

/// One session's pass: always the summary, and — when asked — the series a
/// decision row needs.
struct SessionPassResult {
  SessionSummary summary;
  /// Present only when `retain_series` was set.
  carriers::MidpointGrid grid;
  std::vector<carriers::GroupRecord> stock_print_groups;
  std::vector<std::int64_t> vwap_notional_prefix;
  std::vector<std::int64_t> vwap_size_prefix;
  bool series_retained = false;
  /// Reader receipts, for the census.
  std::int64_t nbbo_rows = 0;
  std::int64_t nbbo_groups = 0;
  std::int64_t print_groups = 0;
};

/// The pure reduction: grid + print sums -> the summary. Separated from the I/O
/// so every value law in it is fixtured on hand-built series without payload.
[[nodiscard]] SessionSummary summarize_session(std::int64_t ordinal,
                                               const carriers::MidpointGrid& grid,
                                               std::int64_t vwap_notional_sum,
                                               std::int64_t vwap_size_sum,
                                               std::int64_t rth_seconds) noexcept;

/// A scoped (decision-calendar) session, 125..749.
[[nodiscard]] Expected<SessionPassResult, Refusal> run_pass(const DayScope& scope,
                                                            const CorpusRoots& roots,
                                                            bool retain_series);

/// CC-012: a WARMUP session, 0..124 — prior state only. There is deliberately
/// no `retain_series` parameter: a warmup session's series may not be handed to
/// a decision constructor at all.
[[nodiscard]] Expected<SessionPassResult, Refusal> run_pass(const WarmupScope& scope,
                                                            const CorpusRoots& roots);

/// THE DECISION-PATH GUARD (CC-012, "but NEVER as decision rows"). Every
/// wave-2 caller that is about to construct a DECISION row passes its session
/// ordinal through here first: warmup ordinals 0..124 refuse with the warmup
/// refusal, and anything outside the scoped calendar refuses too. It is the
/// runtime half of the compile-time disjointness — the type system stops a
/// WarmupScope from reaching a decision API, and this stops a raw ordinal from
/// doing the same.
[[nodiscard]] Expected<bool, Refusal> admit_decision_ordinal(std::int64_t ordinal) noexcept;

}  // namespace qr::wave2

#endif  // QR_WAVE2_SESSION_PASS_HPP
