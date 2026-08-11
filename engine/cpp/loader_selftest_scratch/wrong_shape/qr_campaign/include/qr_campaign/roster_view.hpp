// qr_campaign/roster_view.hpp — ONE parse of the WP6-sealed roster, read by
// both halves of a session worker.
//
// THE ROSTER IS READ, NEVER DERIVED (the rule qr_carriers_probe already states):
// qr_candidates is the roster authority and `render_roster` is its published
// form. This view parses exactly that publication — header included, field by
// field — and hands back the three projections the campaign needs:
//
//   * `watch_candidates()`  — the SIDE-AUTHENTICATED admitted primitives, the
//     only rows that create watches (card §3);
//   * `admitted_visibilities()` — EVERY admitted primitive's own visibility,
//     side-resolved or not, because the authority decision-ordinal roster is the
//     sorted union of the registered seconds and ALL admitted visibilities
//     (card §3, CC-007);
//   * the rows themselves — the causal context of a decision is "the full set of
//     admitted primitive candidates whose own visibility is strictly earlier
//     than the decision and no more than 60s old" (card §2), which includes the
//     SIDE_UNAVAILABLE ones as MIXED/UNAVAILABLE relations.
//
// It is a SHARED parse because the feature builder and the label/emit process
// must derive the identical action-row order from the identical bytes; two
// parses of one file in two processes is the cheapest way to keep them in step,
// and the fixture that matters (the two shards' `keys` leaves are byte-equal) is
// enforced by the emitter writing both from one array.
#ifndef QR_CAMPAIGN_ROSTER_VIEW_HPP
#define QR_CAMPAIGN_ROSTER_VIEW_HPP

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

#include "qr_carriers/candidate_set.hpp"
#include "qr_core/refusal.hpp"
#include "qr_labels/watches.hpp"

namespace qr::campaign {

/// One published roster row, in the authority's own vocabulary.
struct RosterRow {
  std::string candidate_id;
  std::string candidate_physical_key;
  std::string policy_name;
  std::uint64_t reversal_bps = 0;
  std::uint64_t member_count = 0;
  std::int64_t visible_ts_ns = 0;
  /// True when the row authenticated a side; `side` is meaningless otherwise.
  bool side_available = false;
  qr::labels::Side side = qr::labels::Side::LONG;
  /// SIDE_UNAVAILABLE *because the members disagreed*, which the card keeps
  /// apart from every other cause and the candidate-set relation one-hot needs.
  bool mixed_members = false;
};

class RosterView {
 public:
  /// Parses `path`, requiring the WP6 authority's own header and exactly its
  /// eleven fields, and requiring every row to carry `ordinal`.
  [[nodiscard]] static Expected<RosterView, Refusal> load(const std::filesystem::path& path,
                                                          std::int64_t ordinal);

  [[nodiscard]] const std::vector<RosterRow>& rows() const noexcept { return rows_; }
  /// Rows ordered by (visible_ts_ns, candidate_id) — a total order that exists
  /// in the data, so the candidate-set block's row order is deterministic.
  [[nodiscard]] const std::vector<RosterRow>& by_visibility() const noexcept {
    return by_visibility_;
  }
  [[nodiscard]] const std::vector<std::int64_t>& admitted_visibilities() const noexcept {
    return admitted_visibilities_;
  }
  [[nodiscard]] const std::vector<qr::labels::WatchCandidate>& watch_candidates() const noexcept {
    return watch_candidates_;
  }
  [[nodiscard]] std::int64_t side_unavailable_rows() const noexcept { return side_unavailable_; }
  [[nodiscard]] std::int64_t long_rows() const noexcept { return long_rows_; }
  [[nodiscard]] std::int64_t short_rows() const noexcept { return short_rows_; }
  [[nodiscard]] const std::string& day() const noexcept { return day_; }
  [[nodiscard]] const std::string& sha256() const noexcept { return sha256_; }

  /// The card §2 causal context of one decision: every admitted primitive whose
  /// own visibility is strictly earlier than `cutoff_ns` and at most 60s old, in
  /// `by_visibility()` order, encoded as the 24-field rows of card §5.
  [[nodiscard]] Expected<std::vector<qr::carriers::CandidateSetRow>, Refusal> candidate_set(
      std::int64_t cutoff_ns, qr::carriers::Side side) const;

  /// The newest SAME-SIDE authorizing visibility strictly before `cutoff_ns` and
  /// at most 60s old — the phase split's one reference (card §4). Absent when
  /// the decision has none.
  [[nodiscard]] bool phase_reference(std::int64_t cutoff_ns, qr::labels::Side side,
                                     std::int64_t& reference_ns) const;

 private:
  RosterView() = default;

  std::vector<RosterRow> rows_;
  std::vector<RosterRow> by_visibility_;
  std::vector<std::int64_t> admitted_visibilities_;
  std::vector<qr::labels::WatchCandidate> watch_candidates_;
  std::int64_t side_unavailable_ = 0;
  std::int64_t long_rows_ = 0;
  std::int64_t short_rows_ = 0;
  std::string day_;
  std::string sha256_;
};

/// The card §2 visibility horizon: "no more than 60s old".
inline constexpr std::int64_t kContextHorizonNs = 60LL * 1'000'000'000LL;

}  // namespace qr::campaign

#endif  // QR_CAMPAIGN_ROSTER_VIEW_HPP
