// qr_sources/option_quotes.hpp — B4: the IWM option-NBBO reader.
//
// SPEC (FINAL_PLAN APPENDIX B4, verbatim): "option quotes (19 cols; 8
// projected): expiration(1), strike(2), right(3), ts(4), bid_size(5), bid(7),
// ask_size(9), ask(11). Flat <=2024-07-31 / sharded after; coverage s209+;
// W2.1 only."
// Reference semantics (read-only): select_v2/src/sources/option_quotes.rs and
// select_v2/src/sources/mod.rs:147-190 (`day_shards`).
//
// BUILT NOW, CONSUMED IN WAVE 2. B4 marks this stream W2.1-only, so WP4 builds
// the reader and exercises it at the SCHEMA and REFUSAL level (synthetic
// fixtures for both layouts and both profiles; the one already-opened real
// shard for a schema-level assertion). No new option-quote session payload is
// opened by this work package.
//
// TWO LAYOUTS, ONE READER. `day_shards` handles both measured layouts: flat
// `<root>/<YYYY>/<day>.parquet` and per-expiry sharded
// `<root>/<YYYY>/<day>/exp<YYYY-MM-DD>.parquet`, the latter chained in SORTED
// order so a pass is deterministic. A registered day the corpus does not cover
// is MODALITY_ABSENT — a different fact from being outside the calendar.
//
// TWO PROFILES, DETECTED FROM THE FILE. Unlike the stock-quote stream, no
// registry column declares an option-quote profile, so — exactly as the frozen
// reference does — each projected column's on-disk form is resolved against its
// ROLE's admitted set at open and anything outside that set is refused by name.
// The compact and wide profiles differ in whether `expiration` is a DATE
// ordinal or ISO text, whether `strike` is integer mills or dollars, and
// whether prices are integer cents or dollars; all of those are admitted forms
// of their roles, and the resolved forms are exposed by `forms()`.
//
// THE VENDOR `mid` IS WALLED (leaf 18). Measured: it is `bid + ask` in the
// compact profile and the true midpoint in the wide one. `OptionQuoteRow::
// mid_u6()` computes it instead.
//
// EQUAL-TIME GROUPS ACROSS SHARDS. Each shard is a different CONTRACT set, and
// shards are read one after another, so an equal-millisecond group is formed
// WITHIN a shard. Crossing shards closes the pending group: two contracts that
// happen to quote in the same millisecond are not one NBBO event, and merging
// them would invent a cross-contract group that no shard ever contained.
#ifndef QR_SOURCES_OPTION_QUOTES_HPP
#define QR_SOURCES_OPTION_QUOTES_HPP

#include <array>
#include <cstdint>
#include <filesystem>
#include <optional>
#include <span>
#include <string>
#include <vector>

#include "qr_registry/day_scope.hpp"
#include "qr_sources/normalize.hpp"
#include "qr_sources/session_source.hpp"
#include "qr_sources/stream_spec.hpp"

namespace qr::sources {

/// Projection slots of `kOptionQuoteSpec` == bit positions of `null_mask`.
enum OptionQuoteSlot : std::size_t {
  kOptionQuoteSlotExpiration = 0,  // leaf 1
  kOptionQuoteSlotStrike = 1,      // leaf 2
  kOptionQuoteSlotRight = 2,       // leaf 3
  kOptionQuoteSlotTimestamp = 3,   // leaf 4
  kOptionQuoteSlotBidSize = 4,     // leaf 5
  kOptionQuoteSlotBid = 5,         // leaf 7
  kOptionQuoteSlotAskSize = 6,     // leaf 9
  kOptionQuoteSlotAsk = 7,         // leaf 11
};

/// One retained option-NBBO row.
struct OptionQuoteRow {
  /// Naive-ET (frame B) milliseconds.
  std::int64_t ts_ms_b = 0;
  std::int64_t strike_u6 = 0;
  std::int64_t bid_u6 = 0;
  std::int64_t ask_u6 = 0;
  /// Displayed option depth in CONTRACTS. The F-34 lot/share law is a
  /// stock-NBBO fact and is deliberately NOT applied here (the reference does
  /// the same: `option_quotes.rs:253-262` passes the sizes through).
  std::int64_t bid_size = 0;
  std::int64_t ask_size = 0;
  /// Expiration as days since the Unix epoch.
  std::int32_t expiration_day = 0;
  Right right = Right::Other;
  std::uint16_t null_mask = 0;

  [[nodiscard]] std::int64_t group_ts_ms() const noexcept { return ts_ms_b; }
  [[nodiscard]] bool is_null(std::size_t slot) const noexcept {
    return (null_mask & static_cast<std::uint16_t>(1U << slot)) != 0;
  }
  /// The true midpoint — computed, never the walled vendor `mid`.
  [[nodiscard]] std::int64_t mid_u6() const noexcept { return midpoint_u6(bid_u6, ask_u6); }
};

[[nodiscard]] bool canonical_less(const OptionQuoteRow& left, const OptionQuoteRow& right) noexcept;
void append_serialized(const OptionQuoteRow& row, std::vector<std::uint8_t>& out);

struct OptionQuoteDigests {
  std::array<ValueDigest, 8> field{};
  void fold(const OptionQuoteRow& row) noexcept;
  [[nodiscard]] static std::string_view field_name(std::size_t slot) noexcept;
};

/// The schema-level answer for ONE option-quote file: what the pins say and
/// which forms the file actually carries. This is what a "reader built now,
/// exercised schema+refusal-level" (WP4 brief, B4) check consumes, and it is
/// footer-only work — no page of the file is touched.
struct OptionQuoteSchemaCheck {
  std::vector<ColumnForm> forms;
  std::int64_t num_rows = 0;
  std::size_t num_row_groups = 0;
  std::size_t num_leaves = 0;
};

/// Runs the name pin and the form resolution against an already-open file.
[[nodiscard]] FileExpected<OptionQuoteSchemaCheck> check_option_quote_schema(
    const parquet::File& file);

/// Streaming option-quote reader; chains this session's shards in sorted order.
class OptionQuoteReader {
 public:
  struct Group {
    std::int64_t ts_ms_b = 0;
    std::span<const OptionQuoteRow> rows;
  };

  OptionQuoteReader(const OptionQuoteReader&) = delete;
  OptionQuoteReader& operator=(const OptionQuoteReader&) = delete;
  OptionQuoteReader(OptionQuoteReader&&) = default;
  OptionQuoteReader& operator=(OptionQuoteReader&&) = default;
  ~OptionQuoteReader() = default;

  /// Opens every shard of an ADMITTED session. The first shard is gated
  /// immediately, so a wrong schema refuses at open rather than at first use.
  [[nodiscard]] static FileExpected<OptionQuoteReader> open(
      const DayScope& scope, const std::filesystem::path& corpus_root);

  [[nodiscard]] FileExpected<bool> next_group(Group& out);

  [[nodiscard]] const std::vector<std::filesystem::path>& shards() const noexcept {
    return shards_;
  }
  [[nodiscard]] std::int64_t rth_rows() const noexcept { return rth_rows_; }
  [[nodiscard]] std::int64_t group_count() const noexcept { return group_count_; }
  [[nodiscard]] std::int64_t skipped_null_rows() const noexcept { return skipped_null_rows_; }
  /// Values decoded across every shard, including the one currently open.
  [[nodiscard]] std::int64_t decoded_values() const noexcept;
  [[nodiscard]] const std::filesystem::path& path() const noexcept { return path_; }
  /// The forms resolved for the shard currently open.
  [[nodiscard]] std::span<const ColumnForm> forms() const;

 private:
  OptionQuoteReader(std::vector<std::filesystem::path> shards, std::int64_t open_ms_b,
                    std::int64_t close_ms_b)
      : shards_(std::move(shards)), open_ms_b_(open_ms_b), close_ms_b_(close_ms_b) {}

  [[nodiscard]] FileExpected<bool> fill();
  [[nodiscard]] FileExpected<bool> open_next_shard();

  std::vector<std::filesystem::path> shards_;
  std::filesystem::path path_;
  std::optional<SessionSource> source_;
  GroupTape<OptionQuoteRow> tape_;
  std::size_t next_shard_ = 0;
  std::int64_t open_ms_b_ = 0;
  std::int64_t close_ms_b_ = 0;
  std::int64_t rth_rows_ = 0;
  std::int64_t group_count_ = 0;
  std::int64_t skipped_null_rows_ = 0;
  std::int64_t decoded_values_ = 0;
  std::int64_t last_ts_ms_ = 0;
  bool has_last_ts_ = false;
  bool exhausted_ = false;
};

}  // namespace qr::sources

#endif  // QR_SOURCES_OPTION_QUOTES_HPP
