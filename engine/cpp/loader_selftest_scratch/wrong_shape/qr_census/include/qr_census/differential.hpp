// qr_census/differential.hpp — WP9's DIFFERENTIAL VOCABULARY.
//
// SPEC (FINAL_PLAN.md section 6, "Correctness oracles", oracle 2, verbatim):
//   "Registry oracle, full scope: C++ pass must reproduce `raw_rth_row_count`
//    AND `complete_group_count` exactly for ALL 625 sessions (free, no Rust
//    needed) + per-column colsum/checksum differential vs Rust across all 625
//    (minutes) — WP9 merge gate."
// SPEC (FINAL_PLAN.md section 6, oracle 3, verbatim):
//   "Byte differential vs Rust on the ordinal ladder {125+20k, k=0..30} ...
//    (ordinal arithmetic, never hash selection) + era-boundary pair {646,647}
//    (flat->sharded option quotes, in scope)."
// SPEC (WP9 brief): "per session x stream x projected column: (n_nonnull,
//   n_null, digest) under WP3's digest rule ... note the Rust readers expose
//   only THEIR historical projections; diff the INTERSECTION of columns and
//   enumerate non-compared columns explicitly in the verdict".
// Reference semantics (read-only): the frozen Rust readers
//   /workspace/engine/crates/select_v2/src/sources/{stock_quotes,stock_trades,
//   options_prints,option_quotes}.rs.
//
// THREE THINGS THIS HEADER FIXES, AND THEY ARE THE WHOLE DIFFERENTIAL:
//
//  1. THE INTERSECTION. The C++ readers project MORE than the frozen Rust
//     readers do (B1 extends the quote projection from 5 leaves to 9; B2 from
//     10 to 19; B3 projects 20 of the 62 print columns where the reference
//     projects a different 25). A column only one side produces cannot be
//     differenced, and pretending otherwise would be a differential with a
//     hole in it. `compared_columns` is the intersection, in a fixed order, and
//     `uncompared_columns` enumerates EVERY column outside it with the side
//     that owns it and why — those rows are printed in the verdict, so the
//     coverage of the oracle is a published fact rather than an assumption.
//
//  2. THE SHARED NULL MODEL. The two sides spell absence differently: this
//     port carries a per-column null MASK and a zero value, while the frozen
//     readers write sentinels (`i64::MIN`, `i32::MIN`, `NaN`), fold the whole
//     attached-quote block of a print behind ONE presence flag, and fold a null
//     `right` into `Right::Other`. A digest can only be compared under ONE
//     model, so BOTH sides compute the compared digests under the model the
//     frozen readers can actually observe (`NullModel` below). Nothing is
//     hidden by that: the C++ side ALSO publishes its own per-column mask count
//     (`mask_null`) for every compared column, so any place where the coarser
//     model differs from the C++ truth is a printed census row, not a silence.
//
//  3. THE CANONICAL BYTE IMAGE. Rows that share a millisecond have no order
//     (qr_sources/session_source.hpp), so a byte differential must canonicalize
//     or it is comparing the vendor's writer. Both sides therefore group rows
//     into maximal equal-timestamp runs in reading order, sort each run by its
//     own fixed-width little-endian image, and absorb the images into one
//     sha256 in that order. Multiplicity is preserved: a repeated row is a fact
//     about the tape.
#ifndef QR_CENSUS_DIFFERENTIAL_HPP
#define QR_CENSUS_DIFFERENTIAL_HPP

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "qr_candidates/signal_root.hpp"
#include "qr_sources/session_source.hpp"

namespace qr::census {

using qr::sources::ValueDigest;

// ---------------------------------------------------------------------------
// The four streams the differential covers.
// ---------------------------------------------------------------------------

enum class DiffStream : std::uint8_t {
  StockQuotes = 0,
  StockTrades = 1,
  OptionPrints = 2,
  OptionQuotes = 3,
};

inline constexpr std::size_t kDiffStreamCount = 4;

/// The stream's corpus name, identical on both sides of the differential.
[[nodiscard]] const char* diff_stream_name(DiffStream stream) noexcept;
/// Parses a stream name; `nullptr` name or an unknown one yields `false`.
[[nodiscard]] bool parse_diff_stream(std::string_view name, DiffStream& out) noexcept;

// ---------------------------------------------------------------------------
// A compared column.
// ---------------------------------------------------------------------------

/// The wire form of a compared column. It decides both the digest rule (WP3's:
/// wrapping i64 sum / f64 bit XOR) and the width of the canonical byte image.
enum class DiffKind : std::uint8_t {
  /// 64-bit integer; 8 bytes little-endian.
  I64 = 0,
  /// 32-bit integer (a day ordinal); 4 bytes little-endian.
  I32 = 1,
  /// IEEE-754 double; 8 bytes of its bit pattern, little-endian.
  F64 = 2,
  /// A small enumerated code (the contract right); 1 byte.
  U8 = 3,
};

/// HOW THE FROZEN RUST READER SPELLS ABSENCE for this column — the model both
/// sides compute the compared digest under.
enum class NullModel : std::uint8_t {
  /// The reader drops the whole row when this column is absent, so a retained
  /// row's value is always present. Divergence here would be a row-count
  /// divergence, which the differential already compares.
  RowAdmission = 0,
  /// Absent is `i64::MIN`.
  SentinelI64 = 1,
  /// Absent is `i32::MIN`.
  SentinelI32 = 2,
  /// Absent is `NaN`.
  SentinelNaN = 3,
  /// The whole attached-quote block (bid, ask, both displayed sizes) shares ONE
  /// presence flag: if any member is absent the reference writes zeros for all
  /// four and marks the block absent (`stock_trades.rs` `quote_present`).
  AttachedBlock = 4,
  /// Absence is FOLDED INTO A VALUE and is unrecoverable on the Rust side: a
  /// null `right` becomes `Right::Other`. The column is compared as always
  /// present; the C++ `mask_null` census carries what was folded.
  FoldedToValue = 5,
};

struct DiffColumn {
  /// The compared name. Identical on both sides — it is the join key.
  std::string_view name;
  DiffKind kind;
  NullModel null_model;
};

/// The intersection of the two projections, in a FIXED order. That order is
/// the canonical byte image's field order and the TSV's emission order.
[[nodiscard]] std::span<const DiffColumn> compared_columns(DiffStream stream) noexcept;

/// Index of the stream's clock column inside `compared_columns` — the column
/// whose equal values define a run for the canonical image.
[[nodiscard]] std::size_t clock_column_index(DiffStream stream) noexcept;

/// Width in bytes of one canonical row image for `stream`: per compared column,
/// the kind's fixed width plus ONE null-flag byte.
[[nodiscard]] std::size_t canonical_row_width(DiffStream stream) noexcept;

// ---------------------------------------------------------------------------
// The columns that CANNOT be compared, enumerated.
// ---------------------------------------------------------------------------

enum class ColumnSide : std::uint8_t {
  /// Projected by this port, absent from the frozen Rust reader's projection.
  CppOnly = 0,
  /// Projected by the frozen Rust reader, walled or unprojected here.
  RustOnly = 1,
};

[[nodiscard]] const char* column_side_name(ColumnSide side) noexcept;

struct UncomparedColumn {
  std::string_view name;
  ColumnSide side;
  /// Why it is outside the intersection, in the vocabulary of the appendix that
  /// decided it (never a sentence invented here).
  std::string_view reason;
};

/// EVERY column of either projection that the differential cannot cover. The
/// verdict prints one row per entry, so the oracle's coverage is published.
[[nodiscard]] std::span<const UncomparedColumn> uncompared_columns(DiffStream stream) noexcept;

// ---------------------------------------------------------------------------
// One row, as the differential sees it.
// ---------------------------------------------------------------------------

/// One compared cell. `integer` carries I64/I32/U8 values, `real` carries F64
/// ones, and `is_null` is the SHARED MODEL's answer, not this port's mask.
struct DiffCell {
  std::int64_t integer = 0;
  double real = 0.0;
  bool is_null = false;
};

// ---------------------------------------------------------------------------
// The per-session accumulator.
// ---------------------------------------------------------------------------

/// Folds one session's rows of ONE stream into the differential's three
/// products: the per-column (n_nonnull, n_null, digest) triples, the C++
/// mask-null census, and — when byte mode is on — the canonical sha256.
///
/// The digest rule is order-free by construction (wrapping sum / bit XOR), so
/// digests fold in reading order and only the byte image needs the run
/// canonicalization. That is what keeps the full-625 pass streaming.
class SessionDiff {
 public:
  /// `byte_mode` turns on the canonical row image and its sha256. It buffers
  /// ONE equal-timestamp run at a time, never a session.
  SessionDiff(DiffStream stream, std::string_view day, bool byte_mode);

  /// Appends one retained row. `cells` is in `compared_columns` order and
  /// carries the SHARED MODEL's null flags; `mask_null_flags` is this port's
  /// own per-column mask, in the same order, for the census.
  void push(std::span<const DiffCell> cells, std::span<const bool> mask_null_flags);

  /// Closes the trailing run. Must be called once, after the last `push`.
  void finish();

  [[nodiscard]] DiffStream stream() const noexcept { return stream_; }
  [[nodiscard]] std::int64_t rows() const noexcept { return rows_; }
  [[nodiscard]] const ValueDigest& column(std::size_t index) const { return columns_.at(index); }
  [[nodiscard]] std::int64_t mask_null(std::size_t index) const { return mask_nulls_.at(index); }
  /// Lowercase hex sha256 of the canonical image, or empty when byte mode is
  /// off. Only valid after `finish`.
  [[nodiscard]] const std::string& row_sha256() const noexcept { return row_sha256_; }

 private:
  void flush_run();
  void serialize(std::span<const DiffCell> cells, std::vector<std::uint8_t>& out) const;

  DiffStream stream_;
  std::span<const DiffColumn> columns_spec_;
  std::size_t clock_index_;
  std::size_t width_;
  bool byte_mode_;
  bool finished_ = false;
  std::int64_t rows_ = 0;
  std::vector<ValueDigest> columns_;
  std::vector<std::int64_t> mask_nulls_;

  // --- byte mode state ------------------------------------------------------
  qr::candidates::Sha256 sha_;
  std::string row_sha256_;
  /// The current equal-timestamp run's images, back to back, `width_` each.
  std::vector<std::uint8_t> run_;
  std::int64_t run_ts_ = 0;
  bool run_open_ = false;
  std::vector<std::uint8_t> scratch_;
  /// Canonically-ordered images waiting to be absorbed. The digest is over the
  /// same bytes in the same order either way; buffering only replaces one
  /// digest call per ROW (7.46 billion of them on the full-scope pass) with one
  /// per ~64KB, which is the difference between minutes and hours of call
  /// overhead. Flushed on every `kAbsorbBlock` boundary and once at `finish`.
  std::vector<std::uint8_t> pending_;
  /// Reused across runs so a 1.18-billion-run pass does not allocate per run.
  std::vector<std::size_t> order_;
};

/// Bytes of canonically-ordered row images buffered before one digest call.
inline constexpr std::size_t kAbsorbBlock = 1U << 16U;

/// The prologue absorbed before the first row image, so a stream or a session
/// mix-up cannot collide with a real digest.
[[nodiscard]] std::string canonical_prologue(DiffStream stream, std::string_view day,
                                             std::size_t width);

// ---------------------------------------------------------------------------
// The dump TSV — the one wire format both sides write.
// ---------------------------------------------------------------------------

/// `kind` values of a dump row.
inline constexpr std::string_view kDumpHeader = "kind\tordinal\tday\tstream\tname\tmetric\tvalue";

/// One parsed dump row. `name` is "-" where a metric is not per-column.
struct DumpRow {
  std::string kind;
  std::int64_t ordinal = 0;
  std::string day;
  std::string stream;
  std::string name;
  std::string metric;
  std::string value;
};

/// The join key of a dump row: `kind|ordinal|stream|name|metric`. Ordinal is
/// zero-padded so the key sorts in ordinal order as text.
[[nodiscard]] std::string dump_key(const DumpRow& row);

/// Parses a dump TSV. The header must match `kDumpHeader` exactly; a row with
/// the wrong field count is a refusal naming its line number.
[[nodiscard]] Expected<std::vector<DumpRow>, Refusal> parse_dump(std::string_view text);

/// Reads and parses a dump file.
[[nodiscard]] Expected<std::vector<DumpRow>, Refusal> load_dump(const std::string& path);

}  // namespace qr::census

#endif  // QR_CENSUS_DIFFERENTIAL_HPP
