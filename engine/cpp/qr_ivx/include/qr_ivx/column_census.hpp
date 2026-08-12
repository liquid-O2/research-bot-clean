// qr_ivx/column_census.hpp — CC-013's COLUMN CENSUS: schema + footer statistics
// of the option-print files, and NOTHING ELSE.
//
// CHARTER: design/DESIGN_FEATURES.md §CC-013 PROPOSAL ("requires: column census
// first (presence/range/junk-rate per era) ... the amendment lands only with
// the census receipt").
//
// THE WALL THIS FILE STANDS BEHIND. The columns CC-013 proposes to admit —
// vomma(23), veta(24), vera(25), speed(26), zomma(27), color(28), ultima(29),
// dual_delta(32), dual_gamma(33) — are TODAY hard-refused by
// `qr::sources::kOptionPrintSpec.forbidden`, and `iv_error(35)` is outside the
// projection. A census that decoded their VALUES would be exactly the wall
// breach the amendment exists to authorize, so this module never decodes a
// page. It reads:
//
//   * the parquet SCHEMA (the leaf names and physical types), and
//   * the per-row-group COLUMN CHUNK STATISTICS the writer already stored in
//     the thrift footer (num_values, null_count, min_value/max_value).
//
// Both live in `FileMetaData`, i.e. in bytes the reader must parse to open the
// file at all. `qr::parquet::File::read_column` is NEVER called from here, and
// `qr_sources` is not even linked into this translation unit — the projection
// wall is not dodged, it is simply never approached.
//
// WHAT THE FOOTER CAN AND CANNOT SAY. Statistics give exact null counts and the
// writer's own extremes, so "populated at all", "range", "constant-zero" and
// "non-finite bound" are answerable. A per-row distribution (median, junk
// fraction inside the range) is NOT answerable from the footer and this module
// does not pretend otherwise: it emits what the footer holds, and every derived
// verdict below is a function of those numbers alone.
//
// TWO-RUN IDENTITY. No wall-clock value, no filesystem iteration order (shards
// are sorted), doubles printed with %.17g.
#ifndef QR_IVX_COLUMN_CENSUS_HPP
#define QR_IVX_COLUMN_CENSUS_HPP

#include <array>
#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_parquet/column.hpp"
#include "qr_registry/day_scope.hpp"

namespace qr::ivx {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;

/// The CC-013 candidate set, by the vendor's own leaf names as
/// `kOptionPrintSpec.names` pins them (APPENDIX B3's 62-name layout).
///
/// `vega` is listed because B3 registers it as a W2.4 EXTENSION that is not yet
/// projected — the census must say whether that registration is worth
/// implementing. `theta`/`rho` are listed as the CONTROL pair: they are
/// hard-refused for a reason that has nothing to do with population, so a
/// census in which they look identical to the third-order columns is a census
/// that measured nothing.
inline constexpr std::array<const char*, 16> kCandidateColumns{
    "theta",    "vega",       "rho",        "epsilon", "lambda",     "vomma",
    "veta",     "vera",       "speed",      "zomma",   "color",      "ultima",
    "dual_delta", "dual_gamma", "iv_error",  "implied_vol"};

/// Where each candidate stands TODAY in `kOptionPrintSpec` (recorded so the
/// census receipt states, per row, what the amendment would actually change).
enum class SpecStanding : std::uint8_t {
  /// In the 20-leaf projection already (the reference rows).
  PROJECTED = 0,
  /// In `.forbidden` with `ForbidReason::HardRefused`.
  HARD_REFUSED = 1,
  /// Neither projected nor forbidden: reachable only by a projection change.
  UNPROJECTED = 2,
};

[[nodiscard]] const char* spec_standing_name(SpecStanding standing) noexcept;
[[nodiscard]] SpecStanding standing_of(std::string_view column) noexcept;

/// The parquet physical types this census can turn into a number. Anything
/// else is reported by its raw enum value and left uninterpreted.
enum class StatKind : std::uint8_t { NONE = 0, INT32 = 1, INT64 = 2, FLOAT = 3, DOUBLE = 4, OTHER = 5 };

[[nodiscard]] const char* stat_kind_name(StatKind kind) noexcept;

/// One candidate column, censused over every row group of every shard of ONE
/// session. Counts are exact; the range is the writer's own min/max folded
/// across chunks.
struct ColumnStat {
  std::string name;
  SpecStanding standing = SpecStanding::UNPROJECTED;
  /// False when the file's schema does not carry the name at all.
  bool in_schema = false;
  /// Flat leaf index inside the file (the file's own order, not B3's).
  std::int64_t leaf = -1;
  /// The dialect-narrowed leaf type the reader gated the file against.
  qr::parquet::LeafType leaf_type = qr::parquet::LeafType::INT64;
  /// The dialect-narrowed converted type (UTF8/DATE/...), or NONE.
  qr::parquet::LeafConverted converted = qr::parquet::LeafConverted::NONE;
  /// Raw parquet.thrift `Type` enum of the column chunks.
  std::int32_t physical_type = -1;
  StatKind kind = StatKind::NONE;

  std::int64_t chunks = 0;
  std::int64_t chunks_with_statistics = 0;
  std::int64_t chunks_with_null_count = 0;
  std::int64_t chunks_with_range = 0;
  /// Chunks whose stored min or max did not decode to a finite double.
  std::int64_t chunks_nonfinite_bound = 0;
  /// Chunks whose stored min and max are both exactly zero.
  std::int64_t chunks_zero_range = 0;

  std::int64_t num_values = 0;
  std::int64_t null_count = 0;

  bool has_range = false;
  double min_value = 0.0;
  double max_value = 0.0;
};

/// One session's census of every candidate column.
struct SessionColumnCensus {
  std::int64_t ordinal = 0;
  std::string day;
  /// How many parquet files this session's payload occupies (1 = flat era).
  std::int64_t files = 0;
  std::int64_t file_rows = 0;
  std::int64_t row_groups = 0;
  /// Leaf count of the file's schema — 62 is B3's layout.
  std::int64_t schema_leaves = 0;
  std::vector<ColumnStat> columns;
};

/// The population verdict of one column over one session, derived from the
/// footer numbers alone.
enum class ColumnVerdict : std::uint8_t {
  /// No payload rows at all (nothing can be said).
  NO_ROWS = 0,
  /// The schema does not carry the name.
  ABSENT = 1,
  /// Every value is null.
  ALL_NULL = 2,
  /// Values exist but every stored extreme is exactly zero.
  CONSTANT_ZERO = 3,
  /// Values exist, the range is non-degenerate, and no bound was non-finite.
  REAL = 4,
  /// Values exist but at least one chunk's bound is non-finite (NaN/Inf).
  REAL_WITH_NONFINITE = 5,
  /// Values exist but the writer stored no usable min/max anywhere.
  POPULATED_NO_RANGE = 6,
};

[[nodiscard]] const char* column_verdict_name(ColumnVerdict verdict) noexcept;
[[nodiscard]] ColumnVerdict verdict_of(const ColumnStat& stat) noexcept;

/// Presence fraction in parts per million of `num_values` (exact integer
/// arithmetic; `num_values == 0` yields -1, "undefined", never 0).
[[nodiscard]] std::int64_t presence_ppm(const ColumnStat& stat) noexcept;

/// Censuses ONE admitted session of the option-print corpus. The scope wall
/// fires first: only `DayScope::admit` can mint the argument.
[[nodiscard]] Expected<SessionColumnCensus, Refusal> census_print_columns(
    const DayScope& scope, const std::filesystem::path& corpus_root);

}  // namespace qr::ivx

#endif  // QR_IVX_COLUMN_CENSUS_HPP
