// qr_m25/tape.hpp — one session of the DecisionTape, loaded as the exact
// `ScoredAction` rows the FROZEN replay kernel consumes, plus the TRAIN wall.
//
// M2.5 IS A MEASUREMENT ON THE OBJECT, NOT A NEW OBJECT. FINAL_PLAN.md section 8:
//   "On the exact DecisionTape/menu/replay, TRAIN sessions only (F4 125-395;
//    F5 125-520)".
// So: the truth leaves are read verbatim into `qr::replay::LabelRow`, the rows
// of the LONG and SHORT shards are merged into ONE chronological stream (the
// kernel's clock is a timestamp, and the two sides of a clock are two rows of
// the same clock), and every score in this module is written into
// `ScoredAction::predicted_net_h_star` — the kernel is never reimplemented,
// never patched, and never bypassed.
//
// THE TRAIN WALL (the M2.5 refusal that has to exist). The fold ranges are
// card section 1, verbatim: "F4 is train 125..395, inner embargo 396..397,
// calibration 398..497, outer embargo 498..499, test 500..624. F5 is train
// 125..520, inner embargo 521..522, calibration 523..622, outer embargo
// 623..624, test 625..749."  A session outside its fold's TRAIN range is a typed
// ORDINAL_OUTSIDE_SCOPE refusal at LOAD time, before a single byte of its truth
// is mapped: the wall is a door, not a filter applied after the fact.
#ifndef QR_M25_TAPE_HPP
#define QR_M25_TAPE_HPP

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_m25/npy.hpp"
#include "qr_replay/action.hpp"

namespace qr::m25 {

/// The two registry folds M2.5 measures.
enum class Fold : std::uint8_t { F4, F5 };

[[nodiscard]] const char* fold_name(Fold fold) noexcept;
[[nodiscard]] bool parse_fold(const std::string& text, Fold* out) noexcept;

/// Inclusive TRAIN ordinal range of a fold (card section 1).
struct TrainRange {
  std::int64_t first = 0;
  std::int64_t last = 0;
};

[[nodiscard]] TrainRange train_range(Fold fold) noexcept;

/// THE WALL. `ORDINAL_OUTSIDE_SCOPE` for anything that is not a TRAIN session of
/// `fold` — a CAL, embargo or TEST ordinal smuggled into an M2.5 run is refused
/// here and nowhere else needs to remember.
[[nodiscard]] Status assert_train_session(Fold fold, std::int64_t session_ordinal);

/// One session's action rows, both sides, in the kernel's chronological order.
///
/// `rows` is sorted by (decision_ts_ns, side) with LONG before SHORT, which is
/// exactly what the kernel's "equal-timestamp rows are ONE clock" grouping
/// wants; `clock_starts` indexes the first row of each clock so the callers that
/// need per-clock work do not re-scan.
struct SessionTape {
  std::int64_t session_ordinal = 0;
  std::int32_t year = 0;
  std::string day;  ///< "YYYY-MM-DD" from the campaign session receipt.

  /// The kernel's rows. `predicted_net_h_star` / `predicted_stop_prob_h_ref` are
  /// left at zero by the loader: every M2.5 arm writes its own scores.
  std::vector<qr::replay::ScoredAction> rows;
  std::vector<std::size_t> clock_starts;  ///< size = clock count; each an index into `rows`.

  /// Census of what was loaded (published in the receipts).
  std::int64_t long_rows = 0;
  std::int64_t short_rows = 0;
  std::int64_t label_ok_rows = 0;
  std::int64_t label_entry_unavailable_rows = 0;
  std::int64_t label_exit_unavailable_rows = 0;

  [[nodiscard]] std::size_t clock_count() const noexcept { return clock_starts.size(); }
  /// Half-open row range of clock `c`.
  [[nodiscard]] std::size_t clock_end(std::size_t c) const noexcept {
    return c + 1 < clock_starts.size() ? clock_starts[c + 1] : rows.size();
  }
};

/// Where a campaign run published its tapes and receipts.
struct TapeRoot {
  std::filesystem::path tapes;    ///< <run>/tapes
  std::filesystem::path receipts; ///< <run>/receipts
};

[[nodiscard]] TapeRoot tape_root(const std::filesystem::path& run_dir);

/// Load ONE TRAIN session (both sides) of `fold`.
///
/// Refusals: ORDINAL_OUTSIDE_SCOPE (the TRAIN wall), IO/SCHEMA_MISMATCH/
/// CONTENT_MISMATCH from the leaf reader, CONTENT_MISMATCH when the two shards
/// disagree with their own manifests, when a shard's `truth/keys.npy` differs
/// from its `features/keys.npy` (the C4 join), when a key's session ordinal is
/// not this session, or when the merged stream is not strictly ordered.
[[nodiscard]] Expected<SessionTape, Refusal> load_session(const TapeRoot& root, Fold fold,
                                                          std::int64_t session_ordinal);

/// The `card_sha256` census row of a shard's manifest — the frozen-card check
/// the runner performs once before it measures anything.
[[nodiscard]] Expected<std::string, Refusal> shard_card_sha(const TapeRoot& root,
                                                            std::int64_t session_ordinal);

}  // namespace qr::m25

#endif  // QR_M25_TAPE_HPP
