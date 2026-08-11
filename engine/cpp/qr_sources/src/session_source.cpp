#include "qr_sources/session_source.hpp"

#include <cstring>
#include <system_error>

namespace qr::sources {
namespace {

constexpr const char* kShardSite = "qr_sources::day_shards";
constexpr const char* kCellSite = "qr_sources::cell";
constexpr const char* kChunkSite = "qr_sources::SessionSource::next_chunk";

constexpr std::uint64_t kFnvOffsetBasis = 0xCBF29CE484222325ULL;
constexpr std::uint64_t kFnvPrime = 0x100000001B3ULL;

[[nodiscard]] Refusal wrong_form(const char* what, ColumnForm form) noexcept {
  return Refusal(RefusalCode::CONFIG, kCellSite, what, static_cast<std::int64_t>(form));
}

}  // namespace

// ---------------------------------------------------------------------------
// Paths.
// ---------------------------------------------------------------------------

std::filesystem::path day_file(const std::filesystem::path& corpus_root, const DayScope& scope) {
  const std::string& day = scope.day();
  return corpus_root / day.substr(0, 4) / (day + ".parquet");
}

Expected<std::vector<std::filesystem::path>, Refusal> day_shards(
    const std::filesystem::path& corpus_root, const DayScope& scope) {
  const std::filesystem::path flat = day_file(corpus_root, scope);
  std::error_code error;
  if (std::filesystem::is_regular_file(flat, error)) {
    return std::vector<std::filesystem::path>{flat};
  }
  const std::string& day = scope.day();
  const std::filesystem::path sharded = corpus_root / day.substr(0, 4) / day;
  if (std::filesystem::is_directory(sharded, error)) {
    std::vector<std::filesystem::path> shards;
    for (const std::filesystem::directory_entry& entry :
         std::filesystem::directory_iterator(sharded, error)) {
      if (entry.path().extension() == ".parquet") {
        shards.push_back(entry.path());
      }
    }
    if (error) {
      return refuse<std::vector<std::filesystem::path>>(
          Refusal(RefusalCode::IO, kShardSite, "cannot list the session's shard directory"));
    }
    // Sorted iteration is a law (FINAL_PLAN section 6): a directory's natural
    // order is not deterministic and two-run byte identity is a gate.
    std::sort(shards.begin(), shards.end());
    if (!shards.empty()) {
      return shards;
    }
  }
  return refuse<std::vector<std::filesystem::path>>(Refusal(
      RefusalCode::MODALITY_ABSENT, kShardSite,
      "this corpus covers no payload for this registered session", scope.ordinal()));
}

// ---------------------------------------------------------------------------
// Cells.
// ---------------------------------------------------------------------------

Expected<std::int64_t, Refusal> cell_i64(const ColumnData& column, ColumnForm form,
                                         std::int64_t row) noexcept {
  const auto index = static_cast<std::size_t>(row);
  switch (form) {
    case ColumnForm::TimestampMsI64:
    case ColumnForm::IntI64:
      return column.i64[index];
    case ColumnForm::IntI32:
      return static_cast<std::int64_t>(column.i32[index]);
    default:
      break;
  }
  return refuse<std::int64_t>(wrong_form("cell is not an integer form", form));
}

Expected<std::int64_t, Refusal> cell_u6(const ColumnData& column, ColumnForm form,
                                        std::int64_t row) noexcept {
  const auto index = static_cast<std::size_t>(row);
  switch (form) {
    case ColumnForm::CentI32:
    case ColumnForm::MillI32:
      return price_to_u6(form, static_cast<std::int64_t>(column.i32[index]), 0.0);
    case ColumnForm::CentI64:
      return price_to_u6(form, column.i64[index], 0.0);
    case ColumnForm::DollarF64:
      return price_to_u6(form, 0, column.f64[index]);
    default:
      break;
  }
  return refuse<std::int64_t>(wrong_form("cell is not a price form", form));
}

Expected<double, Refusal> cell_f64(const ColumnData& column, ColumnForm form,
                                   std::int64_t row) noexcept {
  if (form == ColumnForm::FloatF64) {
    return column.f64[static_cast<std::size_t>(row)];
  }
  return refuse<double>(wrong_form("cell is not a real-valued form", form));
}

Expected<std::string_view, Refusal> cell_text(const ColumnData& column, ColumnForm form,
                                              std::int64_t row) noexcept {
  if (form == ColumnForm::TextUtf8 || form == ColumnForm::DateText) {
    return column.byte_array(row);
  }
  return refuse<std::string_view>(wrong_form("cell is not a text form", form));
}

Expected<std::int32_t, Refusal> cell_day_ordinal(const ColumnData& column, ColumnForm form,
                                                 std::int64_t row) noexcept {
  if (form == ColumnForm::DateI32) {
    return date_to_day_ordinal(form, static_cast<std::int64_t>(column.i32[
                                   static_cast<std::size_t>(row)]),
                               {});
  }
  if (form == ColumnForm::DateText) {
    return date_to_day_ordinal(form, 0, column.byte_array(row));
  }
  return refuse<std::int32_t>(wrong_form("cell is not a date form", form));
}

// ---------------------------------------------------------------------------
// SessionSource.
// ---------------------------------------------------------------------------

FileExpected<SessionSource> SessionSource::open(std::filesystem::path path, const SpecView& spec,
                                                FormsResolver resolve_pinned,
                                                std::int64_t open_ms_b, std::int64_t close_ms_b) {
  FileExpected<parquet::File> opened = parquet::File::open(path.string());
  if (!opened.has_value()) {
    return FileExpected<SessionSource>::refuse(opened.error());
  }
  parquet::File file = std::move(opened).value();
  FileExpected<std::span<const ColumnForm>> pinned = resolve_pinned(file);
  if (!pinned.has_value()) {
    return FileExpected<SessionSource>::refuse(pinned.error());
  }
  FileExpected<std::vector<ColumnForm>> forms = gate_schema(spec, file, pinned.value());
  if (!forms.has_value()) {
    return FileExpected<SessionSource>::refuse(forms.error());
  }
  std::vector<std::size_t> kept =
      file.rth_row_groups(spec.timestamp_leaf(), open_ms_b, close_ms_b);
  return SessionSource(std::move(path), std::move(file), spec, std::move(forms).value(),
                       std::move(kept), open_ms_b, close_ms_b);
}

FileExpected<SessionSource> SessionSource::open(std::filesystem::path path, const SpecView& spec,
                                                std::span<const ColumnForm> pinned,
                                                std::int64_t open_ms_b, std::int64_t close_ms_b) {
  // The dialect gate first: qr_parquet refuses any file outside the pinned
  // dialect before a payload byte exists.
  FileExpected<parquet::File> opened = parquet::File::open(path.string());
  if (!opened.has_value()) {
    return FileExpected<SessionSource>::refuse(opened.error());
  }
  parquet::File file = std::move(opened).value();

  // Then the SCHEMA gate: names, count, and the form of every projected column.
  FileExpected<std::vector<ColumnForm>> forms = gate_schema(spec, file, pinned);
  if (!forms.has_value()) {
    return FileExpected<SessionSource>::refuse(forms.error());
  }

  // Then pruning — a SPEED lever, never a correctness one: `rth_row_groups`
  // keeps every row group whose statistics can overlap the window, and keeps
  // them all the moment any statistics are missing.
  std::vector<std::size_t> kept =
      file.rth_row_groups(spec.timestamp_leaf(), open_ms_b, close_ms_b);

  return SessionSource(std::move(path), std::move(file), spec, std::move(forms).value(),
                       std::move(kept), open_ms_b, close_ms_b);
}

FileExpected<std::int64_t> SessionSource::next_chunk() {
  if (next_group_ >= kept_.size()) {
    return std::int64_t{0};
  }
  const std::size_t row_group = kept_[next_group_];
  ++next_group_;

  std::int64_t rows = -1;
  for (std::size_t slot = 0; slot < spec_.projection().size(); ++slot) {
    // THE ONLY DOOR: even this module reaches a leaf through the wall.
    FileExpected<std::int64_t> decoded = read_pinned_column(
        spec_, file_, row_group, spec_.projection()[slot], workspace_, chunks_[slot]);
    if (!decoded.has_value()) {
      return decoded;
    }
    if (rows < 0) {
      rows = decoded.value();
    } else if (decoded.value() != rows) {
      std::string detail(spec_.stream());
      detail += ": row group ";
      detail += std::to_string(row_group);
      detail += " decodes ";
      detail += std::to_string(decoded.value());
      detail += " rows for column ";
      detail += std::to_string(spec_.projection()[slot]);
      detail += " and ";
      detail += std::to_string(rows);
      detail += " for an earlier one";
      return parquet::refuse_file<std::int64_t>(
          RefusalCode::CONTENT_MISMATCH, kChunkSite,
          "projected columns of one row group disagree on the row count", path_.string(),
          std::move(detail), static_cast<std::int64_t>(row_group));
    }
  }
  if (rows < 0) {
    rows = 0;
  }
  decoded_values_ += rows * static_cast<std::int64_t>(spec_.projection().size());
  return rows;
}

// ---------------------------------------------------------------------------
// Digest + serialization.
// ---------------------------------------------------------------------------

std::uint64_t double_bits(double value) noexcept {
  std::uint64_t bits = 0;
  std::memcpy(&bits, &value, sizeof(bits));
  return bits;
}

void ValueDigest::add_i64(std::int64_t value) noexcept {
  digest_ += static_cast<std::uint64_t>(value);
  ++non_null_;
}

void ValueDigest::add_f64(double value) noexcept {
  digest_ ^= double_bits(value);
  ++non_null_;
}

void ValueDigest::add_text(std::string_view value) noexcept {
  if (!text_started_) {
    digest_ = kFnvOffsetBasis;
    text_started_ = true;
  }
  const auto length = static_cast<std::uint32_t>(value.size());
  for (unsigned shift = 0; shift < 4; ++shift) {
    digest_ ^= static_cast<std::uint64_t>((length >> (shift * 8U)) & 0xFFU);
    digest_ *= kFnvPrime;
  }
  for (const char byte : value) {
    digest_ ^= static_cast<std::uint64_t>(static_cast<std::uint8_t>(byte));
    digest_ *= kFnvPrime;
  }
  ++non_null_;
}

void append_i64(std::int64_t value, std::vector<std::uint8_t>& out) {
  const auto bits = static_cast<std::uint64_t>(value);
  for (unsigned shift = 0; shift < 8; ++shift) {
    out.push_back(static_cast<std::uint8_t>((bits >> (shift * 8U)) & 0xFFU));
  }
}

void append_i32(std::int32_t value, std::vector<std::uint8_t>& out) {
  const auto bits = static_cast<std::uint32_t>(value);
  for (unsigned shift = 0; shift < 4; ++shift) {
    out.push_back(static_cast<std::uint8_t>((bits >> (shift * 8U)) & 0xFFU));
  }
}

void append_u8(std::uint8_t value, std::vector<std::uint8_t>& out) { out.push_back(value); }

void append_f64(double value, std::vector<std::uint8_t>& out) {
  append_i64(static_cast<std::int64_t>(double_bits(value)), out);
}

void append_text(std::string_view value, std::vector<std::uint8_t>& out) {
  append_i32(static_cast<std::int32_t>(value.size()), out);
  for (const char byte : value) {
    out.push_back(static_cast<std::uint8_t>(byte));
  }
}

}  // namespace qr::sources
