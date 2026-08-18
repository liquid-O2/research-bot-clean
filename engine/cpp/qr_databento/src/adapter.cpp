#include "qr_databento/adapter.hpp"

#include <zstd.h>

#include <array>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>
#include <utility>

#include "databento/dbn_file_store.hpp"
#include "databento/enums.hpp"
#include "databento/exceptions.hpp"
#include "databento/flag_set.hpp"
#include "databento/ireadable.hpp"
#include "databento/log.hpp"
#include "databento/record.hpp"
#include "databento/symbol_map.hpp"
#include "qr_databento/build_authority.hpp"

namespace qr::databento {
namespace {

constexpr std::size_t kCompressedChunk = 1u << 20;

class InputOpenError final : public std::runtime_error {
 public:
  InputOpenError() : std::runtime_error("cannot open compressed DBN input") {}
};

struct StrictState {
  bool clean_eof = false;
};

class StrictZstdReadable final : public ::databento::IReadable {
 public:
  explicit StrictZstdReadable(const std::string& path,
                              std::shared_ptr<StrictState> state)
      : state_(std::move(state)), input_(kCompressedChunk) {
    file_ = std::fopen(path.c_str(), "rb");
    if (file_ == nullptr) {
      throw InputOpenError{};
    }
    stream_ = ZSTD_createDStream();
    if (stream_ == nullptr) {
      std::fclose(file_);
      file_ = nullptr;
      throw InputOpenError{};
    }
    const std::size_t rc = ZSTD_initDStream(stream_);
    if (ZSTD_isError(rc) != 0u) {
      ZSTD_freeDStream(stream_);
      stream_ = nullptr;
      std::fclose(file_);
      file_ = nullptr;
      throw ::databento::DbnResponseError{"ZSTD_initDStream failed"};
    }
  }

  ~StrictZstdReadable() override {
    if (stream_ != nullptr) ZSTD_freeDStream(stream_);
    if (file_ != nullptr) std::fclose(file_);
  }

  void ReadExact(std::byte* buffer, std::size_t length) override {
    std::size_t total = 0;
    while (total < length) {
      const std::size_t got = ReadSome(buffer + total, length - total);
      if (got == 0u) {
        throw ::databento::DbnResponseError{
            "clean end of stream before an exact DBN read completed"};
      }
      total += got;
    }
  }

  std::size_t ReadSome(std::byte* buffer, std::size_t max_length) override {
    return ReadSome(buffer, max_length, std::chrono::milliseconds{}).read_size;
  }

  Result ReadSome(std::byte* buffer, std::size_t max_length,
                  std::chrono::milliseconds) override {
    if (max_length == 0u) return {0u, Status::Ok};
    ZSTD_outBuffer output{buffer, max_length, 0u};
    while (output.pos == 0u) {
      if (input_pos_ == input_size_) {
        const std::size_t got = std::fread(input_.data(), 1, input_.size(), file_);
        if (got == 0u) {
          if (std::ferror(file_) != 0) {
            throw InputOpenError{};
          }
          if (frame_open_) {
            throw ::databento::DbnResponseError{
                "zstd frame truncated at physical end of file"};
          }
          state_->clean_eof = true;
          return {0u, Status::Closed};
        }
        input_pos_ = 0;
        input_size_ = got;
      }
      ZSTD_inBuffer input{input_.data(), input_size_, input_pos_};
      const std::size_t rc = ZSTD_decompressStream(stream_, &output, &input);
      input_pos_ = input.pos;
      if (ZSTD_isError(rc) != 0u) {
        throw ::databento::DbnResponseError{"zstd decompression refused input"};
      }
      frame_open_ = rc != 0u;
    }
    return {output.pos, Status::Ok};
  }

 private:
  std::shared_ptr<StrictState> state_;
  std::FILE* file_ = nullptr;
  ZSTD_DStream* stream_ = nullptr;
  std::vector<std::byte> input_;
  std::size_t input_pos_ = 0;
  std::size_t input_size_ = 0;
  bool frame_open_ = false;
};

class BoundaryLogger final : public ::databento::ILogReceiver {
 public:
  void Receive(::databento::LogLevel level, const std::string&) override {
    if (level >= ::databento::LogLevel::Warning) warning_or_error_ = true;
  }
  bool ShouldLog(::databento::LogLevel) const override { return true; }
  [[nodiscard]] bool warning_or_error() const noexcept { return warning_or_error_; }

 private:
  bool warning_or_error_ = false;
};

[[nodiscard]] std::int32_t yyyymmdd(date::year_month_day value) {
  const int year = static_cast<int>(value.year());
  const int month = static_cast<int>(static_cast<unsigned>(value.month()));
  const int day = static_cast<int>(static_cast<unsigned>(value.day()));
  return static_cast<std::int32_t>(year * 10000 + month * 100 + day);
}

[[nodiscard]] Metadata normalize_metadata(const ::databento::Metadata& source) {
  Metadata out;
  out.version = source.version;
  out.dataset = source.dataset;
  out.schema = static_cast<std::uint16_t>(*source.schema);
  out.start_ts_recv_ns = source.start.time_since_epoch().count();
  out.end_ts_recv_ns = source.end.time_since_epoch().count();
  out.limit = source.limit;
  out.stype_in = static_cast<std::uint8_t>(*source.stype_in);
  out.stype_out = static_cast<std::uint8_t>(source.stype_out);
  out.ts_out = source.ts_out;
  out.symbols = source.symbols;
  out.partial = source.partial;
  out.not_found = source.not_found;
  out.mappings.reserve(source.mappings.size());
  for (const auto& mapping : source.mappings) {
    SymbolMapping row;
    row.raw_symbol = mapping.raw_symbol;
    row.intervals.reserve(mapping.intervals.size());
    for (const auto& interval : mapping.intervals) {
      row.intervals.push_back(MappingInterval{yyyymmdd(interval.start_date),
                                              yyyymmdd(interval.end_date),
                                              interval.symbol});
    }
    out.mappings.push_back(std::move(row));
  }
  return out;
}

[[nodiscard]] Refusal decode_refusal(const char* site, const char* detail) {
  return Refusal(RefusalCode::DECODE_FAILED, site, detail);
}

}  // namespace

struct Mbp1File::Impl {
  BoundaryLogger logger;
  std::shared_ptr<StrictState> strict_state = std::make_shared<StrictState>();
  std::unique_ptr<::databento::DbnFileStore> store;
  std::unique_ptr<::databento::TsSymbolMap> symbol_map;
  Metadata metadata;
  std::uint64_t next_ordinal = 0;
  std::uint64_t records = 0;
  bool open = false;
};

const BuildAuthority& build_authority() noexcept {
  static constexpr BuildAuthority authority{
      "0.64.0", QR_DATABENTO_UPSTREAM_COMMIT,
      QR_DATABENTO_VENDOR_TREE_SHA256, QR_DATABENTO_ADAPTER_SOURCE_SHA256,
      QR_DATABENTO_CLOCK_LAW_SHA256,
      "date/json/httplib are hash-gated existing build-cache headers; no immutable dependency registry or download fallback"};
  return authority;
}

Mbp1File::Mbp1File() : impl_(std::make_unique<Impl>()) {}
Mbp1File::~Mbp1File() = default;
Mbp1File::Mbp1File(Mbp1File&&) noexcept = default;
Mbp1File& Mbp1File::operator=(Mbp1File&&) noexcept = default;

Expected<std::monostate, Refusal> Mbp1File::open(
    const std::string& path, std::uint64_t source_ordinal_base) {
  impl_ = std::make_unique<Impl>();
  impl_->next_ordinal = source_ordinal_base;
  try {
    auto readable =
        std::make_unique<StrictZstdReadable>(path, impl_->strict_state);
    impl_->store = std::make_unique<::databento::DbnFileStore>(
        &impl_->logger, std::move(readable),
        ::databento::VersionUpgradePolicy::AsIs);
    const ::databento::Metadata& metadata = impl_->store->GetMetadata();
    if (!metadata.schema.has_value() ||
        *metadata.schema != ::databento::Schema::Mbp1 ||
        !metadata.stype_in.has_value() ||
        (*metadata.stype_in != ::databento::SType::Continuous &&
         *metadata.stype_in != ::databento::SType::Parent) ||
        metadata.stype_out != ::databento::SType::InstrumentId || metadata.ts_out) {
      return refuse<std::monostate>(Refusal(
          RefusalCode::SCHEMA_MISMATCH, "qr_databento::Mbp1File::open",
          "metadata must be mbp-1 parent/continuous-to-instrument-id with ts_out=false"));
    }
    if (metadata.start >= metadata.end) {
      return refuse<std::monostate>(Refusal(
          RefusalCode::CONTENT_MISMATCH, "qr_databento::Mbp1File::open",
          "metadata receive-time range is empty or reversed"));
    }
    impl_->metadata = normalize_metadata(metadata);
    impl_->symbol_map = std::make_unique<::databento::TsSymbolMap>(metadata);
    if (impl_->symbol_map->IsEmpty()) {
      return refuse<std::monostate>(Refusal(
          RefusalCode::CONTENT_MISMATCH, "qr_databento::Mbp1File::open",
          "metadata produced an empty exact UTC IndexTs symbol map"));
    }
    impl_->open = true;
    return std::monostate{};
  } catch (const InputOpenError&) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::IO, "qr_databento::Mbp1File::open",
        "cannot open or read the compressed DBN input"));
  } catch (const ::databento::InvalidArgumentError&) {
    return refuse<std::monostate>(Refusal(
        RefusalCode::CONTENT_MISMATCH, "qr_databento::Mbp1File::open",
        "official metadata or exact symbol map is invalid"));
  } catch (const ::databento::DbnResponseError&) {
    return refuse<std::monostate>(decode_refusal(
        "qr_databento::Mbp1File::open", "official DBN metadata decode failed"));
  } catch (const std::exception&) {
    return refuse<std::monostate>(decode_refusal(
        "qr_databento::Mbp1File::open", "unexpected official adapter failure"));
  }
}

const Metadata& Mbp1File::metadata() const noexcept { return impl_->metadata; }

Expected<std::optional<Mbp1Row>, Refusal> Mbp1File::next_mbp1() {
  if (!impl_->open || impl_->store == nullptr || impl_->symbol_map == nullptr) {
    return refuse<std::optional<Mbp1Row>>(Refusal(
        RefusalCode::CONFIG, "qr_databento::Mbp1File::next_mbp1",
        "next_mbp1 called before a successful open"));
  }
  try {
    const ::databento::Record* record = impl_->store->NextRecord();
    if (impl_->logger.warning_or_error()) {
      return refuse<std::optional<Mbp1Row>>(decode_refusal(
          "qr_databento::Mbp1File::next_mbp1",
          "official decoder emitted a warning or error"));
    }
    if (record == nullptr) {
      if (!impl_->strict_state->clean_eof) {
        return refuse<std::optional<Mbp1Row>>(decode_refusal(
            "qr_databento::Mbp1File::next_mbp1",
            "decoder stopped before a clean physical zstd boundary"));
      }
      return std::optional<Mbp1Row>{};
    }
    if (!record->Holds<::databento::Mbp1Msg>() ||
        record->Size() != sizeof(::databento::Mbp1Msg)) {
      return refuse<std::optional<Mbp1Row>>(decode_refusal(
          "qr_databento::Mbp1File::next_mbp1",
          "record is not an exact 80-byte MBP-1 message"));
    }
    if (impl_->next_ordinal == std::numeric_limits<std::uint64_t>::max()) {
      return refuse<std::optional<Mbp1Row>>(Refusal(
          RefusalCode::ARITHMETIC_OVERFLOW,
          "qr_databento::Mbp1File::next_mbp1", "source ordinal overflow"));
    }
    const ::databento::Mbp1Msg& source = record->Get<::databento::Mbp1Msg>();
    const std::uint8_t flags = source.flags.Raw();
    const bool standalone_bad_ts_recv =
        (flags & kFlagBadTsRecv) != 0u && (flags & kFlagSnapshot) == 0u;
    Mbp1Row row;
    row.source_ordinal = impl_->next_ordinal++;
    row.publisher_id = source.hd.publisher_id;
    row.instrument_id = source.hd.instrument_id;
    row.ts_recv_ns = source.IndexTs().time_since_epoch().count();
    row.ts_event_ns = source.hd.ts_event.time_since_epoch().count();
    row.sequence = source.sequence;
    row.price = source.price;
    row.size = source.size;
    row.action = static_cast<std::uint8_t>(source.action);
    row.side = static_cast<std::uint8_t>(source.side);
    row.flags = flags;
    row.depth = source.depth;
    row.ts_in_delta_ns = source.ts_in_delta.count();
    row.bid_px = source.levels[0].bid_px;
    row.ask_px = source.levels[0].ask_px;
    row.bid_sz = source.levels[0].bid_sz;
    row.ask_sz = source.levels[0].ask_sz;
    row.bid_ct = source.levels[0].bid_ct;
    row.ask_ct = source.levels[0].ask_ct;
    // A standalone BAD_TS_RECV explicitly says that IndexTs is not a valid
    // availability clock.  Do not let it select a UTC symbology interval;
    // the substrate brackets the transport row by clean records for this IID.
    if (!standalone_bad_ts_recv) {
      const auto symbol = impl_->symbol_map->Find(source);
      if (symbol == impl_->symbol_map->Map().end()) {
        return refuse<std::optional<Mbp1Row>>(Refusal(
            RefusalCode::CONTENT_MISMATCH,
            "qr_databento::Mbp1File::next_mbp1",
            "missing exact instrument mapping on floor_UTC(IndexTs)"));
      }
      row.raw_symbol = *symbol->second;
    }
    ++impl_->records;
    return std::optional<Mbp1Row>{std::move(row)};
  } catch (const InputOpenError&) {
    return refuse<std::optional<Mbp1Row>>(Refusal(
        RefusalCode::IO, "qr_databento::Mbp1File::next_mbp1",
        "I/O failure while reading compressed DBN input"));
  } catch (const ::databento::InvalidArgumentError&) {
    return refuse<std::optional<Mbp1Row>>(Refusal(
        RefusalCode::CONFIG, "qr_databento::Mbp1File::next_mbp1",
        "official adapter API misuse"));
  } catch (const ::databento::DbnResponseError&) {
    return refuse<std::optional<Mbp1Row>>(decode_refusal(
        "qr_databento::Mbp1File::next_mbp1", "official DBN record decode failed"));
  } catch (const std::exception&) {
    return refuse<std::optional<Mbp1Row>>(decode_refusal(
        "qr_databento::Mbp1File::next_mbp1", "unexpected official adapter failure"));
  }
}

std::uint64_t Mbp1File::records_read() const noexcept { return impl_->records; }

}  // namespace qr::databento
