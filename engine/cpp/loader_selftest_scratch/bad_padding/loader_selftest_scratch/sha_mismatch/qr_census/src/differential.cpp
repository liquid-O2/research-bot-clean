#include "qr_census/differential.hpp"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <numeric>

namespace qr::census {
namespace {

constexpr const char* kParseSite = "qr_census::parse_dump";

// ---------------------------------------------------------------------------
// The intersections. Order is this port's own digest order, restricted to the
// columns the frozen Rust readers also produce.
// ---------------------------------------------------------------------------

// B1: this port projects leaves 0..8; the frozen reader projects [0,1,3,5,7].
constexpr std::array<DiffColumn, 5> kStockQuoteCompared{
    DiffColumn{"ts_ms_b", DiffKind::I64, NullModel::RowAdmission},
    DiffColumn{"bid_shares", DiffKind::I64, NullModel::RowAdmission},
    DiffColumn{"bid_u6", DiffKind::I64, NullModel::RowAdmission},
    DiffColumn{"ask_shares", DiffKind::I64, NullModel::RowAdmission},
    DiffColumn{"ask_u6", DiffKind::I64, NullModel::RowAdmission},
};

constexpr std::array<UncomparedColumn, 4> kStockQuoteUncompared{
    UncomparedColumn{"bid_exchange", ColumnSide::CppOnly,
                     "B1 projection EXTENDED vs the frozen reader's [0,1,3,5,7]"},
    UncomparedColumn{"bid_condition", ColumnSide::CppOnly,
                     "B1 projection EXTENDED vs the frozen reader's [0,1,3,5,7]"},
    UncomparedColumn{"ask_exchange", ColumnSide::CppOnly,
                     "B1 projection EXTENDED vs the frozen reader's [0,1,3,5,7]"},
    UncomparedColumn{"ask_condition", ColumnSide::CppOnly,
                     "B1 projection EXTENDED vs the frozen reader's [0,1,3,5,7]"},
};

// B2: this port projects leaves 0..18; the frozen reader projects
// [0,2,7,8,9,10,11,13,15,17].
constexpr std::array<DiffColumn, 10> kStockTradeCompared{
    DiffColumn{"ts_ms_b", DiffKind::I64, NullModel::RowAdmission},
    DiffColumn{"sequence", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"condition", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"size", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"exchange", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"price_u6", DiffKind::I64, NullModel::RowAdmission},
    DiffColumn{"bid_shares", DiffKind::I64, NullModel::AttachedBlock},
    DiffColumn{"bid_u6", DiffKind::I64, NullModel::AttachedBlock},
    DiffColumn{"ask_shares", DiffKind::I64, NullModel::AttachedBlock},
    DiffColumn{"ask_u6", DiffKind::I64, NullModel::AttachedBlock},
};

constexpr std::array<UncomparedColumn, 9> kStockTradeUncompared{
    UncomparedColumn{"quote_ts_ms_b", ColumnSide::CppOnly,
                     "B2 projects 19 leaves; the frozen reader projects 10"},
    UncomparedColumn{"ext_condition1", ColumnSide::CppOnly,
                     "B2 projects 19 leaves; the frozen reader projects 10"},
    UncomparedColumn{"ext_condition2", ColumnSide::CppOnly,
                     "B2 projects 19 leaves; the frozen reader projects 10"},
    UncomparedColumn{"ext_condition3", ColumnSide::CppOnly,
                     "B2 projects 19 leaves; the frozen reader projects 10"},
    UncomparedColumn{"ext_condition4", ColumnSide::CppOnly,
                     "B2 projects 19 leaves; the frozen reader projects 10"},
    UncomparedColumn{"bid_exchange", ColumnSide::CppOnly,
                     "B2 projects 19 leaves; the frozen reader projects 10"},
    UncomparedColumn{"bid_condition", ColumnSide::CppOnly,
                     "B2 projects 19 leaves; the frozen reader projects 10"},
    UncomparedColumn{"ask_exchange", ColumnSide::CppOnly,
                     "B2 projects 19 leaves; the frozen reader projects 10"},
    UncomparedColumn{"ask_condition", ColumnSide::CppOnly,
                     "B2 projects 19 leaves; the frozen reader projects 10"},
};

// B3: this port projects 20 of 62 leaves; the frozen reader projects a
// different 25. Fourteen leaves are in both.
constexpr std::array<DiffColumn, 14> kOptionPrintCompared{
    DiffColumn{"expiration_day", DiffKind::I32, NullModel::SentinelI32},
    DiffColumn{"strike_u6", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"right", DiffKind::U8, NullModel::FoldedToValue},
    DiffColumn{"ts_ms_b", DiffKind::I64, NullModel::RowAdmission},
    DiffColumn{"size", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"price_u6", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"delta", DiffKind::F64, NullModel::SentinelNaN},
    DiffColumn{"gamma", DiffKind::F64, NullModel::SentinelNaN},
    DiffColumn{"vanna", DiffKind::F64, NullModel::SentinelNaN},
    DiffColumn{"charm", DiffKind::F64, NullModel::SentinelNaN},
    DiffColumn{"implied_vol", DiffKind::F64, NullModel::SentinelNaN},
    DiffColumn{"underlying_price", DiffKind::F64, NullModel::SentinelNaN},
    DiffColumn{"bid_u6", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"ask_u6", DiffKind::I64, NullModel::SentinelI64},
};

constexpr std::array<UncomparedColumn, 17> kOptionPrintUncompared{
    UncomparedColumn{"sequence", ColumnSide::CppOnly, "B3 projects it; the frozen reader does not"},
    UncomparedColumn{"condition", ColumnSide::CppOnly,
                     "B3 projects it; the frozen reader does not"},
    UncomparedColumn{"underlying_ts_text", ColumnSide::CppOnly,
                     "B3 projects it; the frozen reader does not"},
    UncomparedColumn{"bid_size", ColumnSide::CppOnly,
                     "B3 projects it; the frozen reader does not"},
    UncomparedColumn{"ask_size", ColumnSide::CppOnly,
                     "B3 projects it; the frozen reader does not"},
    UncomparedColumn{"quote_ts_ms_b", ColumnSide::CppOnly,
                     "B3 projects it; the frozen reader does not"},
    UncomparedColumn{"side", ColumnSide::RustOnly, "B3 HARD-REFUSED: aggressor is recomputed"},
    UncomparedColumn{"sweep_id", ColumnSide::RustOnly, "B3 HARD-REFUSED: sweep_*"},
    UncomparedColumn{"sweep_n", ColumnSide::RustOnly, "B3 HARD-REFUSED: sweep_*"},
    UncomparedColumn{"sweep_size", ColumnSide::RustOnly, "B3 HARD-REFUSED: sweep_*"},
    UncomparedColumn{"dte", ColumnSide::RustOnly, "not in the B3 ADDENDUM projection"},
    UncomparedColumn{"moneyness", ColumnSide::RustOnly, "B3 HARD-REFUSED"},
    UncomparedColumn{"prem", ColumnSide::RustOnly, "B3 HARD-REFUSED: prem/*_flow"},
    UncomparedColumn{"delta_flow", ColumnSide::RustOnly, "B3 HARD-REFUSED: prem/*_flow"},
    UncomparedColumn{"gamma_flow", ColumnSide::RustOnly, "B3 HARD-REFUSED: prem/*_flow"},
    UncomparedColumn{"vanna_flow", ColumnSide::RustOnly, "B3 HARD-REFUSED: prem/*_flow"},
    UncomparedColumn{"charm_flow", ColumnSide::RustOnly, "B3 HARD-REFUSED: prem/*_flow"},
};

// B4: both sides project leaves [1,2,3,4,5,7,9,11]. The intersection is total.
constexpr std::array<DiffColumn, 8> kOptionQuoteCompared{
    DiffColumn{"expiration_day", DiffKind::I32, NullModel::SentinelI32},
    DiffColumn{"strike_u6", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"right", DiffKind::U8, NullModel::FoldedToValue},
    DiffColumn{"ts_ms_b", DiffKind::I64, NullModel::RowAdmission},
    DiffColumn{"bid_size", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"bid_u6", DiffKind::I64, NullModel::RowAdmission},
    DiffColumn{"ask_size", DiffKind::I64, NullModel::SentinelI64},
    DiffColumn{"ask_u6", DiffKind::I64, NullModel::RowAdmission},
};

constexpr std::array<UncomparedColumn, 0> kOptionQuoteUncompared{};

[[nodiscard]] std::size_t kind_width(DiffKind kind) noexcept {
  switch (kind) {
    case DiffKind::I64:
    case DiffKind::F64:
      return 8;
    case DiffKind::I32:
      return 4;
    case DiffKind::U8:
      return 1;
  }
  return 0;
}

void append_le(std::uint64_t value, std::size_t bytes, std::vector<std::uint8_t>& out) {
  for (std::size_t index = 0; index < bytes; ++index) {
    out.push_back(static_cast<std::uint8_t>((value >> (8U * index)) & 0xFFU));
  }
}

}  // namespace

const char* diff_stream_name(DiffStream stream) noexcept {
  switch (stream) {
    case DiffStream::StockQuotes:
      return "stock_quotes";
    case DiffStream::StockTrades:
      return "stock_trades";
    case DiffStream::OptionPrints:
      return "options_prints";
    case DiffStream::OptionQuotes:
      return "option_quotes";
  }
  return "?";
}

bool parse_diff_stream(std::string_view name, DiffStream& out) noexcept {
  for (std::size_t index = 0; index < kDiffStreamCount; ++index) {
    const auto stream = static_cast<DiffStream>(index);
    if (name == diff_stream_name(stream)) {
      out = stream;
      return true;
    }
  }
  return false;
}

std::span<const DiffColumn> compared_columns(DiffStream stream) noexcept {
  switch (stream) {
    case DiffStream::StockQuotes:
      return kStockQuoteCompared;
    case DiffStream::StockTrades:
      return kStockTradeCompared;
    case DiffStream::OptionPrints:
      return kOptionPrintCompared;
    case DiffStream::OptionQuotes:
      return kOptionQuoteCompared;
  }
  return {};
}

std::size_t clock_column_index(DiffStream stream) noexcept {
  const std::span<const DiffColumn> columns = compared_columns(stream);
  for (std::size_t index = 0; index < columns.size(); ++index) {
    if (columns[index].name == "ts_ms_b") {
      return index;
    }
  }
  // Every stream's intersection contains its clock: the clock is what makes a
  // row addressable at all, so no projection can omit it.
  detail::fail_fast("qr::census::clock_column_index: stream has no ts_ms_b column");
}

std::size_t canonical_row_width(DiffStream stream) noexcept {
  std::size_t width = 0;
  for (const DiffColumn& column : compared_columns(stream)) {
    width += kind_width(column.kind) + 1;
  }
  return width;
}

const char* column_side_name(ColumnSide side) noexcept {
  return side == ColumnSide::CppOnly ? "cpp_only" : "rust_only";
}

std::span<const UncomparedColumn> uncompared_columns(DiffStream stream) noexcept {
  switch (stream) {
    case DiffStream::StockQuotes:
      return kStockQuoteUncompared;
    case DiffStream::StockTrades:
      return kStockTradeUncompared;
    case DiffStream::OptionPrints:
      return kOptionPrintUncompared;
    case DiffStream::OptionQuotes:
      return kOptionQuoteUncompared;
  }
  return {};
}

// ---------------------------------------------------------------------------
// SessionDiff
// ---------------------------------------------------------------------------

std::string canonical_prologue(DiffStream stream, std::string_view day, std::size_t width) {
  std::string prologue = "WP9-BYTES-V1\n";
  prologue += diff_stream_name(stream);
  prologue += '\n';
  prologue.append(day);
  prologue += '\n';
  prologue += std::to_string(width);
  prologue += '\n';
  return prologue;
}

SessionDiff::SessionDiff(DiffStream stream, std::string_view day, bool byte_mode)
    : stream_(stream),
      columns_spec_(compared_columns(stream)),
      clock_index_(clock_column_index(stream)),
      width_(canonical_row_width(stream)),
      byte_mode_(byte_mode),
      columns_(columns_spec_.size()),
      mask_nulls_(columns_spec_.size(), 0) {
  if (byte_mode_) {
    const std::string prologue = canonical_prologue(stream, day, width_);
    sha_.update(prologue);
  }
}

void SessionDiff::serialize(std::span<const DiffCell> cells, std::vector<std::uint8_t>& out) const {
  for (std::size_t index = 0; index < columns_spec_.size(); ++index) {
    const DiffCell& cell = cells[index];
    switch (columns_spec_[index].kind) {
      case DiffKind::I64:
        append_le(cell.is_null ? 0U : static_cast<std::uint64_t>(cell.integer), 8, out);
        break;
      case DiffKind::I32:
        append_le(cell.is_null ? 0U
                               : static_cast<std::uint64_t>(
                                     static_cast<std::uint32_t>(static_cast<std::int32_t>(
                                         cell.integer))),
                  4, out);
        break;
      case DiffKind::F64:
        append_le(cell.is_null ? 0U : sources::double_bits(cell.real), 8, out);
        break;
      case DiffKind::U8:
        append_le(cell.is_null ? 0U : static_cast<std::uint64_t>(cell.integer) & 0xFFU, 1, out);
        break;
    }
    out.push_back(cell.is_null ? std::uint8_t{1} : std::uint8_t{0});
  }
}

void SessionDiff::push(std::span<const DiffCell> cells, std::span<const bool> mask_null_flags) {
  ++rows_;
  for (std::size_t index = 0; index < columns_spec_.size(); ++index) {
    const DiffCell& cell = cells[index];
    if (cell.is_null) {
      columns_[index].add_null();
    } else if (columns_spec_[index].kind == DiffKind::F64) {
      columns_[index].add_f64(cell.real);
    } else {
      columns_[index].add_i64(cell.integer);
    }
    if (index < mask_null_flags.size() && mask_null_flags[index]) {
      ++mask_nulls_[index];
    }
  }
  if (!byte_mode_) {
    return;
  }
  const std::int64_t ts = cells[clock_index_].integer;
  if (run_open_ && ts != run_ts_) {
    flush_run();
  }
  run_ts_ = ts;
  run_open_ = true;
  scratch_.clear();
  serialize(cells, scratch_);
  run_.insert(run_.end(), scratch_.begin(), scratch_.end());
}

void SessionDiff::flush_run() {
  const std::size_t count = run_.size() / width_;
  // The canonical order of an equal-timestamp run: sorted by the row's OWN
  // image. Any permutation the vendor happened to write collapses to the same
  // sequence, and multiplicity survives because the sort is over all rows.
  // A run of one is already canonical — the overwhelmingly common case on the
  // print and trade tapes — so it skips the sort entirely.
  if (count > 1) {
    order_.resize(count);
    std::iota(order_.begin(), order_.end(), std::size_t{0});
    const std::uint8_t* base = run_.data();
    const std::size_t width = width_;
    std::sort(order_.begin(), order_.end(), [base, width](std::size_t left, std::size_t right) {
      return std::memcmp(base + (left * width), base + (right * width), width) < 0;
    });
    for (const std::size_t index : order_) {
      const std::uint8_t* image = run_.data() + (index * width_);
      pending_.insert(pending_.end(), image, image + width_);
    }
  } else {
    pending_.insert(pending_.end(), run_.begin(), run_.end());
  }
  if (pending_.size() >= kAbsorbBlock) {
    sha_.update(pending_.data(), pending_.size());
    pending_.clear();
  }
  run_.clear();
  run_open_ = false;
}

void SessionDiff::finish() {
  if (finished_) {
    return;
  }
  finished_ = true;
  if (!byte_mode_) {
    return;
  }
  if (run_open_) {
    flush_run();
  }
  if (!pending_.empty()) {
    sha_.update(pending_.data(), pending_.size());
    pending_.clear();
  }
  std::string trailer = "\n";
  trailer += std::to_string(rows_);
  sha_.update(trailer);
  row_sha256_ = sha_.finish_hex();
}

// ---------------------------------------------------------------------------
// The dump TSV
// ---------------------------------------------------------------------------

std::string dump_key(const DumpRow& row) {
  char ordinal[16];
  std::snprintf(ordinal, sizeof(ordinal), "%05lld", static_cast<long long>(row.ordinal));
  std::string key = row.kind;
  key += '|';
  key += ordinal;
  key += '|';
  key += row.stream;
  key += '|';
  key += row.name;
  key += '|';
  key += row.metric;
  return key;
}

Expected<std::vector<DumpRow>, Refusal> parse_dump(std::string_view text) {
  std::vector<DumpRow> rows;
  std::size_t line_start = 0;
  std::int64_t line_number = 0;
  bool header_seen = false;
  while (line_start <= text.size()) {
    const std::size_t line_end = text.find('\n', line_start);
    const std::string_view line =
        text.substr(line_start, line_end == std::string_view::npos ? std::string_view::npos
                                                                   : line_end - line_start);
    line_start = line_end == std::string_view::npos ? text.size() + 1 : line_end + 1;
    ++line_number;
    if (line.empty()) {
      if (line_end == std::string_view::npos) {
        break;
      }
      continue;
    }
    if (!header_seen) {
      if (line != kDumpHeader) {
        return Expected<std::vector<DumpRow>, Refusal>::refuse(
            Refusal(RefusalCode::SCHEMA_MISMATCH, kParseSite,
                    "dump header is not the WP9 dump header", line_number));
      }
      header_seen = true;
      continue;
    }
    std::array<std::string_view, 7> fields{};
    std::size_t field = 0;
    std::size_t start = 0;
    while (field < fields.size()) {
      const std::size_t stop = line.find('\t', start);
      if (stop == std::string_view::npos) {
        fields[field] = line.substr(start);
        ++field;
        start = line.size() + 1;
        break;
      }
      fields[field] = line.substr(start, stop - start);
      ++field;
      start = stop + 1;
    }
    if (field != fields.size() || start <= line.size()) {
      return Expected<std::vector<DumpRow>, Refusal>::refuse(
          Refusal(RefusalCode::SCHEMA_MISMATCH, kParseSite,
                  "dump row does not carry exactly seven tab-separated fields", line_number));
    }
    DumpRow row;
    row.kind = std::string(fields[0]);
    const std::string ordinal_text(fields[1]);
    char* end = nullptr;
    row.ordinal = std::strtoll(ordinal_text.c_str(), &end, 10);
    if (end == nullptr || *end != '\0' || ordinal_text.empty()) {
      return Expected<std::vector<DumpRow>, Refusal>::refuse(
          Refusal(RefusalCode::SCHEMA_MISMATCH, kParseSite, "dump row ordinal is not an integer",
                  line_number));
    }
    row.day = std::string(fields[2]);
    row.stream = std::string(fields[3]);
    row.name = std::string(fields[4]);
    row.metric = std::string(fields[5]);
    row.value = std::string(fields[6]);
    rows.push_back(std::move(row));
  }
  if (!header_seen) {
    return Expected<std::vector<DumpRow>, Refusal>::refuse(
        Refusal(RefusalCode::SCHEMA_MISMATCH, kParseSite, "dump is empty: no header row", 0));
  }
  return rows;
}

Expected<std::vector<DumpRow>, Refusal> load_dump(const std::string& path) {
  std::FILE* file = std::fopen(path.c_str(), "rb");
  if (file == nullptr) {
    return Expected<std::vector<DumpRow>, Refusal>::refuse(
        Refusal(RefusalCode::IO, kParseSite, "cannot open the dump file", 0));
  }
  std::string text;
  std::array<char, 1U << 16U> buffer{};
  while (true) {
    const std::size_t read = std::fread(buffer.data(), 1, buffer.size(), file);
    if (read == 0) {
      break;
    }
    text.append(buffer.data(), read);
  }
  const bool failed = std::ferror(file) != 0;
  std::fclose(file);
  if (failed) {
    return Expected<std::vector<DumpRow>, Refusal>::refuse(
        Refusal(RefusalCode::IO, kParseSite, "the dump file could not be read to the end", 0));
  }
  return parse_dump(text);
}

}  // namespace qr::census
