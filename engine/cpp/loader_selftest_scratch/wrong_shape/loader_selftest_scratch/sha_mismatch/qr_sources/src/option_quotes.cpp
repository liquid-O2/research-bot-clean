#include "qr_sources/option_quotes.hpp"

#include <array>
#include <string>

#include "qr_clock/session_clock.hpp"

namespace qr::sources {
namespace {

constexpr const char* kOpenSite = "qr_sources::OptionQuoteReader::open";
constexpr const char* kRowSite = "qr_sources::OptionQuoteReader::row";

}  // namespace

bool canonical_less(const OptionQuoteRow& left, const OptionQuoteRow& right) noexcept {
  if (left.ts_ms_b != right.ts_ms_b) return left.ts_ms_b < right.ts_ms_b;
  if (left.expiration_day != right.expiration_day) return left.expiration_day < right.expiration_day;
  if (left.strike_u6 != right.strike_u6) return left.strike_u6 < right.strike_u6;
  if (left.right != right.right) return left.right < right.right;
  if (left.bid_size != right.bid_size) return left.bid_size < right.bid_size;
  if (left.bid_u6 != right.bid_u6) return left.bid_u6 < right.bid_u6;
  if (left.ask_size != right.ask_size) return left.ask_size < right.ask_size;
  if (left.ask_u6 != right.ask_u6) return left.ask_u6 < right.ask_u6;
  return left.null_mask < right.null_mask;
}

void append_serialized(const OptionQuoteRow& row, std::vector<std::uint8_t>& out) {
  append_i32(row.expiration_day, out);
  append_i64(row.strike_u6, out);
  append_u8(static_cast<std::uint8_t>(row.right), out);
  append_i64(row.ts_ms_b, out);
  append_i64(row.bid_size, out);
  append_i64(row.bid_u6, out);
  append_i64(row.ask_size, out);
  append_i64(row.ask_u6, out);
  append_i64(static_cast<std::int64_t>(row.null_mask), out);
}

void OptionQuoteDigests::fold(const OptionQuoteRow& row) noexcept {
  const std::array<std::int64_t, 8> values{static_cast<std::int64_t>(row.expiration_day),
                                           row.strike_u6,
                                           static_cast<std::int64_t>(row.right),
                                           row.ts_ms_b,
                                           row.bid_size,
                                           row.bid_u6,
                                           row.ask_size,
                                           row.ask_u6};
  for (std::size_t slot = 0; slot < values.size(); ++slot) {
    if (row.is_null(slot)) {
      field[slot].add_null();
    } else {
      field[slot].add_i64(values[slot]);
    }
  }
}

std::string_view OptionQuoteDigests::field_name(std::size_t slot) noexcept {
  static constexpr std::array<std::string_view, 8> kNames{
      "expiration_day", "strike_u6", "right",    "ts_ms_b",
      "bid_size",       "bid_u6",    "ask_size", "ask_u6"};
  return slot < kNames.size() ? kNames[slot] : std::string_view{"?"};
}

FileExpected<OptionQuoteSchemaCheck> check_option_quote_schema(const parquet::File& file) {
  FileExpected<std::vector<ColumnForm>> forms =
      gate_schema(view_of(kOptionQuoteSpec), file, std::span<const ColumnForm>{});
  if (!forms.has_value()) {
    return FileExpected<OptionQuoteSchemaCheck>::refuse(forms.error());
  }
  OptionQuoteSchemaCheck out;
  out.forms = std::move(forms).value();
  out.num_rows = file.num_rows();
  out.num_row_groups = file.num_row_groups();
  out.num_leaves = file.leaves().size();
  return out;
}

FileExpected<OptionQuoteReader> OptionQuoteReader::open(const DayScope& scope,
                                                        const std::filesystem::path& corpus_root) {
  const std::filesystem::path flat = day_file(corpus_root, scope);
  Expected<SessionClock, Refusal> clock = SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    return parquet::refuse_file<OptionQuoteReader>(clock.error().code(), kOpenSite,
                                                   "the session clock refuses this registry row",
                                                   flat.string(), scope.day(), scope.ordinal());
  }
  const std::int64_t open_ms = clock.value().open_b().ns() / kNanosecondsPerMillisecond;
  const std::int64_t close_ms = clock.value().close_b().ns() / kNanosecondsPerMillisecond;

  Expected<std::vector<std::filesystem::path>, Refusal> shards = day_shards(corpus_root, scope);
  if (!shards.has_value()) {
    return parquet::refuse_file<OptionQuoteReader>(
        shards.error().code(), kOpenSite, shards.error().detail(), flat.string(), scope.day(),
        scope.ordinal());
  }

  OptionQuoteReader reader(std::move(shards).value(), open_ms, close_ms);
  // Gate the FIRST shard now: a wrong schema must refuse at open, not at the
  // first group a caller asks for.
  FileExpected<bool> opened = reader.open_next_shard();
  if (!opened.has_value()) {
    return FileExpected<OptionQuoteReader>::refuse(opened.error());
  }
  return reader;
}

std::int64_t OptionQuoteReader::decoded_values() const noexcept {
  return decoded_values_ + (source_.has_value() ? source_->decoded_values() : 0);
}

std::span<const ColumnForm> OptionQuoteReader::forms() const {
  if (!source_.has_value()) {
    return {};
  }
  return std::span<const ColumnForm>(source_->forms());
}

FileExpected<bool> OptionQuoteReader::open_next_shard() {
  if (next_shard_ >= shards_.size()) {
    return false;
  }
  const std::filesystem::path path = shards_[next_shard_];
  ++next_shard_;
  // The profile is DETECTED here (empty pin vector): no registry column
  // declares an option-quote profile, so each projected column's form is
  // resolved against its role's admitted set and anything else is refused.
  FileExpected<SessionSource> source = SessionSource::open(
      path, view_of(kOptionQuoteSpec), std::span<const ColumnForm>{}, open_ms_b_, close_ms_b_);
  if (!source.has_value()) {
    return FileExpected<bool>::refuse(source.error());
  }
  path_ = path;
  source_.emplace(std::move(source).value());
  has_last_ts_ = false;
  return true;
}

FileExpected<bool> OptionQuoteReader::fill() {
  while (true) {
    if (!source_.has_value()) {
      FileExpected<bool> opened = open_next_shard();
      if (!opened.has_value()) {
        return opened;
      }
      if (!opened.value()) {
        exhausted_ = true;
        return true;
      }
    }
    FileExpected<std::int64_t> decoded = source_->next_chunk();
    if (!decoded.has_value()) {
      return FileExpected<bool>::refuse(decoded.error());
    }
    const std::int64_t rows = decoded.value();
    const bool end_of_shard = rows == 0;
    tape_.begin_chunk();
    for (std::int64_t row = 0; row < rows; ++row) {
      // ADMISSION (reference `option_quotes.rs:227-229`): an instant and both
      // sides, or the row is not an NBBO state.
      if (source_->cell(kOptionQuoteSlotTimestamp).is_null(row) ||
          source_->cell(kOptionQuoteSlotBid).is_null(row) ||
          source_->cell(kOptionQuoteSlotAsk).is_null(row)) {
        ++skipped_null_rows_;
        continue;
      }
      Expected<std::int64_t, Refusal> timestamp =
          cell_i64(source_->cell(kOptionQuoteSlotTimestamp),
                   source_->form(kOptionQuoteSlotTimestamp), row);
      if (!timestamp.has_value()) {
        return source_->refuse<bool>(timestamp.error());
      }
      const std::int64_t ts_ms = timestamp.value();
      if (has_last_ts_ && ts_ms < last_ts_ms_) {
        return source_->refuse<bool>(Refusal(RefusalCode::OUT_OF_ORDER, kRowSite,
                                             "option quote shard descends in time", ts_ms));
      }
      last_ts_ms_ = ts_ms;
      has_last_ts_ = true;
      if (ts_ms < source_->open_ms_b() || ts_ms >= source_->close_ms_b()) {
        continue;
      }
      ++rth_rows_;

      OptionQuoteRow built;
      built.ts_ms_b = ts_ms;

      if (source_->cell(kOptionQuoteSlotExpiration).is_null(row)) {
        built.null_mask |= static_cast<std::uint16_t>(1U << kOptionQuoteSlotExpiration);
      } else {
        Expected<std::int32_t, Refusal> expiration =
            cell_day_ordinal(source_->cell(kOptionQuoteSlotExpiration),
                             source_->form(kOptionQuoteSlotExpiration), row);
        if (!expiration.has_value()) {
          return source_->refuse<bool>(expiration.error());
        }
        built.expiration_day = expiration.value();
      }

      if (source_->cell(kOptionQuoteSlotRight).is_null(row)) {
        built.null_mask |= static_cast<std::uint16_t>(1U << kOptionQuoteSlotRight);
      } else {
        Expected<std::string_view, Refusal> text = cell_text(
            source_->cell(kOptionQuoteSlotRight), source_->form(kOptionQuoteSlotRight), row);
        if (!text.has_value()) {
          return source_->refuse<bool>(text.error());
        }
        built.right = parse_right(text.value());
      }

      constexpr std::array<std::size_t, 3> kPriceSlots{kOptionQuoteSlotStrike, kOptionQuoteSlotBid,
                                                       kOptionQuoteSlotAsk};
      std::array<std::int64_t, 3> prices{};
      for (std::size_t index = 0; index < kPriceSlots.size(); ++index) {
        Expected<std::int64_t, Refusal> value =
            read_nullable_u6(*source_, kPriceSlots[index], row, built.null_mask);
        if (!value.has_value()) {
          return source_->refuse<bool>(value.error());
        }
        prices[index] = value.value();
      }
      built.strike_u6 = prices[0];
      built.bid_u6 = prices[1];
      built.ask_u6 = prices[2];

      constexpr std::array<std::size_t, 2> kSizeSlots{kOptionQuoteSlotBidSize,
                                                      kOptionQuoteSlotAskSize};
      std::array<std::int64_t, 2> sizes{};
      for (std::size_t index = 0; index < kSizeSlots.size(); ++index) {
        Expected<std::int64_t, Refusal> value =
            read_nullable_int(*source_, kSizeSlots[index], row, built.null_mask);
        if (!value.has_value()) {
          return source_->refuse<bool>(value.error());
        }
        sizes[index] = value.value();
      }
      built.bid_size = sizes[0];
      built.ask_size = sizes[1];

      tape_.push(built);
    }
    // A SHARD BOUNDARY CLOSES THE GROUP: each shard is its own contract set,
    // and merging two shards' equal milliseconds would invent a group no shard
    // ever held.
    tape_.end_chunk(end_of_shard);
    if (end_of_shard) {
      decoded_values_ += source_->decoded_values();
      source_.reset();
    }
    return true;
  }
}

FileExpected<bool> OptionQuoteReader::next_group(Group& out) {
  while (true) {
    if (tape_.next(out.ts_ms_b, out.rows)) {
      ++group_count_;
      return true;
    }
    if (exhausted_) {
      return false;
    }
    FileExpected<bool> filled = fill();
    if (!filled.has_value()) {
      return filled;
    }
  }
}

}  // namespace qr::sources
