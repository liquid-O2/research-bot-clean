// qr_sources/session_source.hpp — one admitted session's payload, projected,
// RTH-bounded, and delivered as EQUAL-TIME GROUPS.
//
// SPEC (design/DESIGN_SUBSTRATE.md APPENDIX C3, verbatim):
//   "`open(DayScope, Profile)` refuses wrong schema pre-payload; `next_group()`
//    equal-time iterator, rows unordered within group."
// SPEC (WP4 brief, fixtures): "equal-time group iterator: multi-row same-ms
//   group delivered unordered with group multiplicity, prior-group boundary
//   correct (permutation of in-group row order => byte-identical groups
//   fixture)".
// Reference semantics (read-only): select_v2/src/sources/mod.rs (calendar
//   bound, frame B in / frame B out, row-group pruning) and
//   corpus/src/reader.rs:842-940 (the group machine the registry's
//   `complete_group_count` counts).
//
// THREE PROPERTIES, INHERITED FROM THE FROZEN REFERENCE (mod.rs:8-22):
//
//   1. CALENDAR-BOUNDED. Every constructor takes a `qr::DayScope`, which only
//      `DayScope::admit` mints, and a path is formed FROM the scope. An
//      unadmitted day is refused before any filesystem call — that is what
//      seals 2026, the warmup years and everything past s749 across all four
//      streams at once.
//   2. FRAME B IN, FRAME B OUT. Token parquet timestamps are naive-ET
//      (frame B). The RTH filter is the session clock's own half-open frame-B
//      window, applied BEFORE any conversion, and nothing here produces a
//      frame-A instant. qr_clock remains the single frame boundary.
//   3. U6 PRICES / SHARE SIZES. Every price is normalized to dollars x 1e6 and
//      every NBBO size to shares, at this boundary, so no consumer sees a
//      profile or an era.
//
// "ROWS UNORDERED WITHIN A GROUP", MECHANICALLY. Rows that share a millisecond
// have no order: the tape's order among them is an artifact of the vendor's
// writer, and treating it as information is exactly the equal-time hazard the
// Validity lattice reserves a state for. This tape therefore CANONICALIZES each
// group — the rows of a group are sorted by their own content — so that any
// input permutation of an equal-time run produces byte-identical output.
// Multiplicity is preserved: two identical rows in one millisecond stay two
// rows, because a repeated print or quote is a fact about the tape.
#ifndef QR_SOURCES_SESSION_SOURCE_HPP
#define QR_SOURCES_SESSION_SOURCE_HPP

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_parquet/reader.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_sources/normalize.hpp"
#include "qr_sources/stream_spec.hpp"

namespace qr::sources {

// ---------------------------------------------------------------------------
// Path forming — only ever FROM an admitted scope.
// ---------------------------------------------------------------------------

/// `<corpus_root>/<YYYY>/<YYYY-MM-DD>.parquet` (reference `mod.rs:139-145`).
/// A MEMBER-LIKE free function over DayScope: it takes a scope, never a raw
/// day string, so the wall is upstream of every path this module forms.
[[nodiscard]] std::filesystem::path day_file(const std::filesystem::path& corpus_root,
                                             const DayScope& scope);

/// Every parquet shard of an admitted session, covering both measured layouts
/// (reference `mod.rs:147-190`): flat `<root>/<YYYY>/<day>.parquet`, or
/// per-expiry sharded `<root>/<YYYY>/<day>/exp<YYYY-MM-DD>.parquet`. Shards
/// come back SORTED, so a pass over them is deterministic. Neither layout
/// present is MODALITY_ABSENT — a registered day the corpus does not cover,
/// which is a different fact from being outside the calendar.
[[nodiscard]] Expected<std::vector<std::filesystem::path>, Refusal> day_shards(
    const std::filesystem::path& corpus_root, const DayScope& scope);

// ---------------------------------------------------------------------------
// Cell accessors — one decoded column chunk, read by its resolved form.
// ---------------------------------------------------------------------------

[[nodiscard]] inline bool cell_is_null(const ColumnData& column, std::int64_t row) noexcept {
  return column.is_null(row);
}

/// An integer / frame-B millisecond cell.
[[nodiscard]] Expected<std::int64_t, Refusal> cell_i64(const ColumnData& column, ColumnForm form,
                                                       std::int64_t row) noexcept;
/// A price or strike cell, normalized to u6.
[[nodiscard]] Expected<std::int64_t, Refusal> cell_u6(const ColumnData& column, ColumnForm form,
                                                      std::int64_t row) noexcept;
/// A real-valued cell (greeks, implied vol, underlying price).
[[nodiscard]] Expected<double, Refusal> cell_f64(const ColumnData& column, ColumnForm form,
                                                 std::int64_t row) noexcept;
/// A UTF-8 cell, as a view into `column`'s own bytes.
[[nodiscard]] Expected<std::string_view, Refusal> cell_text(const ColumnData& column,
                                                            ColumnForm form,
                                                            std::int64_t row) noexcept;
/// A date cell, as days since the Unix epoch.
[[nodiscard]] Expected<std::int32_t, Refusal> cell_day_ordinal(const ColumnData& column,
                                                               ColumnForm form,
                                                               std::int64_t row) noexcept;

// ---------------------------------------------------------------------------
// SessionSource — the projected payload of one file (or shard chain).
// ---------------------------------------------------------------------------

/// One session's projected payload, decoded a row group at a time.
///
/// It owns the gate (`open`), the pruning, and the decode; it owns NO row
/// semantics — which rows are admitted and what a row means is each stream's
/// own law, because APPENDIX B gives each stream its own.
class SessionSource {
 public:
  SessionSource(const SessionSource&) = delete;
  SessionSource& operator=(const SessionSource&) = delete;
  SessionSource(SessionSource&&) = default;
  SessionSource& operator=(SessionSource&&) = default;
  ~SessionSource() = default;

  /// Opens ONE file: the dialect gate (qr_parquet), then the schema gate
  /// (`gate_schema`), then row-group pruning against the frame-B RTH window.
  /// Nothing below the footer is touched.
  [[nodiscard]] static FileExpected<SessionSource> open(std::filesystem::path path,
                                                        const SpecView& spec,
                                                        std::span<const ColumnForm> pinned,
                                                        std::int64_t open_ms_b,
                                                        std::int64_t close_ms_b);

  /// A resolver of the admitted form vector FROM THE FILE'S OWN SCHEMA, for a
  /// stream whose profile no registry column declares. It is a plain function
  /// pointer, so the resolver is a pinned constant of the stream and never a
  /// caller's lambda: the closed set of admitted vectors stays in the spec.
  using FormsResolver = FileExpected<std::span<const ColumnForm>> (*)(const parquet::File&);

  /// Same gate, one step earlier: the file's own schema chooses which of the
  /// stream's admitted form vectors is pinned, and then EVERY projected column
  /// is checked against that vector. This is the dual-profile law for a stream
  /// with no registry-declared profile (B3's two print date encodings); it is
  /// not a fallback — a file matching neither vector is refused by name.
  [[nodiscard]] static FileExpected<SessionSource> open(std::filesystem::path path,
                                                        const SpecView& spec,
                                                        FormsResolver resolve_pinned,
                                                        std::int64_t open_ms_b,
                                                        std::int64_t close_ms_b);

  /// Decodes the next kept row group's projected columns. Returns the number of
  /// rows decoded, or 0 when the file is exhausted.
  [[nodiscard]] FileExpected<std::int64_t> next_chunk();

  [[nodiscard]] const ColumnData& cell(std::size_t slot) const noexcept {
    return chunks_[slot];
  }
  [[nodiscard]] ColumnForm form(std::size_t slot) const noexcept { return forms_[slot]; }
  [[nodiscard]] const std::vector<ColumnForm>& forms() const noexcept { return forms_; }
  [[nodiscard]] const SpecView& spec() const noexcept { return spec_; }
  [[nodiscard]] const std::filesystem::path& path() const noexcept { return path_; }
  [[nodiscard]] std::int64_t open_ms_b() const noexcept { return open_ms_b_; }
  [[nodiscard]] std::int64_t close_ms_b() const noexcept { return close_ms_b_; }
  [[nodiscard]] std::int64_t file_rows() const noexcept { return file_.num_rows(); }
  [[nodiscard]] std::size_t row_groups_total() const noexcept { return file_.num_row_groups(); }
  [[nodiscard]] std::size_t row_groups_kept() const noexcept { return kept_.size(); }
  /// Rows decoded x projected columns — the budget's "values".
  [[nodiscard]] std::int64_t decoded_values() const noexcept { return decoded_values_; }
  [[nodiscard]] const parquet::File& file() const noexcept { return file_; }

  /// Wraps a core refusal as a file refusal naming this file. Every stream
  /// reader funnels its per-row refusals through here so no refusal is ever
  /// anonymous about which payload produced it.
  template <class T>
  [[nodiscard]] FileExpected<T> refuse(const Refusal& refusal, std::string detail = {}) const {
    return FileExpected<T>::refuse(
        parquet::FileRefusal(refusal, path_.string(), std::move(detail)));
  }

 private:
  SessionSource(std::filesystem::path path, parquet::File file, const SpecView& spec,
                std::vector<ColumnForm> forms, std::vector<std::size_t> kept,
                std::int64_t open_ms_b, std::int64_t close_ms_b)
      : path_(std::move(path)),
        file_(std::move(file)),
        spec_(spec),
        forms_(std::move(forms)),
        kept_(std::move(kept)),
        chunks_(spec.projection().size()),
        open_ms_b_(open_ms_b),
        close_ms_b_(close_ms_b) {}

  std::filesystem::path path_;
  parquet::File file_;
  SpecView spec_;
  std::vector<ColumnForm> forms_;
  std::vector<std::size_t> kept_;
  std::vector<ColumnData> chunks_;
  DecodeWorkspace workspace_;
  std::size_t next_group_ = 0;
  std::int64_t open_ms_b_ = 0;
  std::int64_t close_ms_b_ = 0;
  std::int64_t decoded_values_ = 0;
};

// ---------------------------------------------------------------------------
// Nullable field reads — "absent" is a MASK BIT, never a sentinel value.
// ---------------------------------------------------------------------------
//
// The frozen Rust readers spell absence as `i64::MIN` / `NaN` sentinels. This
// port does not: a sentinel is a value, and a value can collide with a real
// datum or be summed into a statistic by accident. Every row here carries a
// null MASK, one bit per projection slot, and a null field holds 0.

template <class Mask>
[[nodiscard]] Expected<std::int64_t, Refusal> read_nullable_int(const SessionSource& source,
                                                                std::size_t slot, std::int64_t row,
                                                                Mask& mask) noexcept {
  const ColumnData& column = source.cell(slot);
  if (column.is_null(row)) {
    mask |= static_cast<Mask>(Mask{1} << slot);
    return std::int64_t{0};
  }
  return cell_i64(column, source.form(slot), row);
}

template <class Mask>
[[nodiscard]] Expected<std::int64_t, Refusal> read_nullable_u6(const SessionSource& source,
                                                               std::size_t slot, std::int64_t row,
                                                               Mask& mask) noexcept {
  const ColumnData& column = source.cell(slot);
  if (column.is_null(row)) {
    mask |= static_cast<Mask>(Mask{1} << slot);
    return std::int64_t{0};
  }
  return cell_u6(column, source.form(slot), row);
}

template <class Mask>
[[nodiscard]] Expected<double, Refusal> read_nullable_f64(const SessionSource& source,
                                                          std::size_t slot, std::int64_t row,
                                                          Mask& mask) noexcept {
  const ColumnData& column = source.cell(slot);
  if (column.is_null(row)) {
    mask |= static_cast<Mask>(Mask{1} << slot);
    return 0.0;
  }
  return cell_f64(column, source.form(slot), row);
}

// ---------------------------------------------------------------------------
// GroupTape — the equal-time iterator.
// ---------------------------------------------------------------------------

/// Collects rows in FILE ORDER and hands them back as equal-millisecond
/// groups, canonically ordered inside each group.
///
/// A group is complete only when a row with a DIFFERENT timestamp has been
/// seen, or the session has ended: the run that touches the end of a chunk is
/// CARRIED into the next chunk, because a millisecond does not respect row
/// group boundaries. `Row` must provide `group_ts_ms()` and an ADL-visible
/// `canonical_less(const Row&, const Row&)`.
template <class Row>
class GroupTape {
 public:
  /// Starts a chunk. The carried (incomplete) run becomes its head, so a group
  /// that straddles a row-group boundary is delivered ONCE and whole.
  void begin_chunk() {
    rows_.clear();
    runs_.clear();
    next_run_ = 0;
    complete_runs_ = 0;
    if (!carry_.empty()) {
      rows_.insert(rows_.end(), carry_.begin(), carry_.end());
      runs_.push_back(0);
      carry_.clear();
    }
  }

  /// Appends one admitted row, in file order.
  void push(Row row) {
    if (rows_.empty() || row.group_ts_ms() != rows_[runs_.back()].group_ts_ms()) {
      runs_.push_back(rows_.size());
    }
    rows_.push_back(std::move(row));
  }

  /// Ends a chunk. `end_of_session` completes the trailing run instead of
  /// carrying it. Canonicalization happens here, once per run.
  void end_chunk(bool end_of_session) {
    complete_runs_ = runs_.size();
    if (!end_of_session && !runs_.empty()) {
      const std::size_t start = runs_.back();
      carry_.assign(rows_.begin() + static_cast<std::ptrdiff_t>(start), rows_.end());
      rows_.resize(start);
      runs_.pop_back();
      complete_runs_ = runs_.size();
    }
    for (std::size_t index = 0; index < complete_runs_; ++index) {
      const std::size_t start = runs_[index];
      const std::size_t stop = (index + 1 < runs_.size()) ? runs_[index + 1] : rows_.size();
      std::sort(rows_.begin() + static_cast<std::ptrdiff_t>(start),
                rows_.begin() + static_cast<std::ptrdiff_t>(stop),
                [](const Row& left, const Row& right) { return canonical_less(left, right); });
    }
  }

  /// Pops the next complete group. False when this chunk has none left.
  [[nodiscard]] bool next(std::int64_t& ts_ms_b, std::span<const Row>& rows) noexcept {
    if (next_run_ >= complete_runs_) {
      return false;
    }
    const std::size_t start = runs_[next_run_];
    const std::size_t stop = (next_run_ + 1 < runs_.size()) ? runs_[next_run_ + 1] : rows_.size();
    ++next_run_;
    rows = std::span<const Row>(rows_.data() + start, stop - start);
    ts_ms_b = rows_[start].group_ts_ms();
    return true;
  }

  [[nodiscard]] bool has_carry() const noexcept { return !carry_.empty(); }

 private:
  std::vector<Row> rows_;
  std::vector<std::size_t> runs_;
  std::vector<Row> carry_;
  std::size_t next_run_ = 0;
  std::size_t complete_runs_ = 0;
};

// ---------------------------------------------------------------------------
// The value digest — the WP4 half of WP3's committed rule.
// ---------------------------------------------------------------------------

/// THE WP4 DIGEST RULE. WP3's committed rule (qr_parquet/column.hpp), applied
/// to the values a READER EMITS rather than to the raw column chunk, because
/// what WP9's differential must compare against the frozen Rust readers is the
/// normalized stream (u6 prices, share sizes, day ordinals), not the vendor's
/// encoding of it:
///
///   integers : wrapping uint64 sum of the non-null values;
///   doubles  : bitwise XOR of the IEEE-754 bit patterns of the non-nulls;
///   text     : FNV-1a 64 over, per non-null value in emission order, the
///              4-byte little-endian length followed by the value bytes.
///
/// Nulls contribute nothing and are counted separately.
class ValueDigest {
 public:
  void add_i64(std::int64_t value) noexcept;
  void add_f64(double value) noexcept;
  void add_text(std::string_view value) noexcept;
  void add_null() noexcept { ++nulls_; }

  [[nodiscard]] std::uint64_t digest() const noexcept { return digest_; }
  [[nodiscard]] std::int64_t digest_i64() const noexcept {
    return static_cast<std::int64_t>(digest_);
  }
  [[nodiscard]] std::int64_t non_null() const noexcept { return non_null_; }
  [[nodiscard]] std::int64_t nulls() const noexcept { return nulls_; }

 private:
  std::uint64_t digest_ = 0;
  std::int64_t non_null_ = 0;
  std::int64_t nulls_ = 0;
  bool text_started_ = false;
};

/// Field-by-field little-endian appends, for the two-run byte-identity and
/// permutation-identity fixtures. No padding, no pointers, no addresses.
void append_i64(std::int64_t value, std::vector<std::uint8_t>& out);
void append_i32(std::int32_t value, std::vector<std::uint8_t>& out);
void append_u8(std::uint8_t value, std::vector<std::uint8_t>& out);
void append_f64(double value, std::vector<std::uint8_t>& out);
void append_text(std::string_view value, std::vector<std::uint8_t>& out);

/// Total order on doubles by their bit pattern. Used by every canonical
/// comparator: NaN has no ordering under `<`, and a comparator that is not a
/// strict weak ordering is undefined behaviour in `std::sort`.
[[nodiscard]] std::uint64_t double_bits(double value) noexcept;

}  // namespace qr::sources

#endif  // QR_SOURCES_SESSION_SOURCE_HPP
