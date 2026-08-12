#include "qr_candidates/prefix_reader.hpp"

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdio>
#include <cstring>

#include "qr_candidates/parse.hpp"

namespace qr::candidates {
namespace {

constexpr std::size_t kMaxLineBytes = 2'000'000;

/// Splits `line` on every tab. Returns false when the field count is not
/// exactly `kSignalFieldCount`; an empty trailing cell still counts as a cell,
/// exactly as the sealing authority's `split('\t')` did.
[[nodiscard]] bool split_tabs(std::string_view line, std::string_view* out, std::size_t expected) {
  std::size_t count = 0;
  const char* begin = line.data();
  const char* end = begin + line.size();
  const char* cursor = begin;
  while (true) {
    const char* tab = static_cast<const char*>(
        std::memchr(cursor, '\t', static_cast<std::size_t>(end - cursor)));
    if (count >= expected) {
      return false;
    }
    if (tab == nullptr) {
      out[count++] = std::string_view(cursor, static_cast<std::size_t>(end - cursor));
      break;
    }
    out[count++] = std::string_view(cursor, static_cast<std::size_t>(tab - cursor));
    cursor = tab + 1;
  }
  return count == expected;
}

[[nodiscard]] Refusal io_refusal(const char* site, const char* what, std::int64_t context = 0) {
  return Refusal(RefusalCode::IO, site, what, context);
}

}  // namespace

const char* extreme_side_name(ExtremeSide side) noexcept {
  return side == ExtremeSide::LOW ? "LOW" : "HIGH";
}

PositionalSource::~PositionalSource() = default;

// --- FileSource -------------------------------------------------------------

Expected<std::unique_ptr<FileSource>, Refusal> FileSource::open(const std::string& path) {
  const int fd = ::open(path.c_str(), O_RDONLY | O_CLOEXEC);
  if (fd < 0) {
    return refuse<std::unique_ptr<FileSource>>(
        io_refusal("qr_candidates::FileSource::open", "cannot open the file", errno));
  }
  struct ::stat info {};
  if (::fstat(fd, &info) != 0) {
    ::close(fd);
    return refuse<std::unique_ptr<FileSource>>(
        io_refusal("qr_candidates::FileSource::open", "cannot stat the file", errno));
  }
  return std::unique_ptr<FileSource>(
      new FileSource(fd, static_cast<std::int64_t>(info.st_size), path));
}

FileSource::~FileSource() { close(); }

void FileSource::close() noexcept {
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
}

Expected<bool, Refusal> FileSource::read_at(std::uint8_t* out, std::size_t size,
                                            std::int64_t offset) {
  if (fd_ < 0) {
    return refuse<bool>(
        io_refusal("qr_candidates::FileSource::read_at", "read after close", offset));
  }
  std::size_t done = 0;
  while (done < size) {
    const ::ssize_t got = ::pread(fd_, out + done, size - done,
                                  static_cast<::off_t>(offset + static_cast<std::int64_t>(done)));
    if (got < 0) {
      if (errno == EINTR) {
        continue;
      }
      return refuse<bool>(io_refusal("qr_candidates::FileSource::read_at", "pread failed", errno));
    }
    if (got == 0) {
      return refuse<bool>(io_refusal("qr_candidates::FileSource::read_at",
                                     "end of file before the requested bytes",
                                     offset + static_cast<std::int64_t>(done)));
    }
    done += static_cast<std::size_t>(got);
  }
  return true;
}

// --- /proc/self/io ----------------------------------------------------------

IoAccounting read_io_accounting() noexcept {
  IoAccounting out;
  std::FILE* file = std::fopen("/proc/self/io", "rb");
  if (file == nullptr) {
    return out;
  }
  char line[128];
  while (std::fgets(line, sizeof(line), file) != nullptr) {
    unsigned long long value = 0;
    if (std::sscanf(line, "rchar: %llu", &value) == 1) {
      out.rchar = value;
      out.available = true;
    } else if (std::sscanf(line, "syscr: %llu", &value) == 1) {
      out.syscr = value;
    } else if (std::sscanf(line, "read_bytes: %llu", &value) == 1) {
      out.read_bytes = value;
    }
  }
  std::fclose(file);
  return out;
}

// --- SessionSignals ---------------------------------------------------------

void SessionSignals::begin(std::uint32_t ordinal) noexcept {
  ordinal_ = ordinal;
  rows_.clear();
}

void SessionSignals::append(SignalAuth row) { rows_.push_back(std::move(row)); }

void SessionSignals::clear() noexcept {
  rows_.clear();
  ordinal_ = 0;
}

Expected<bool, Refusal> SessionSignals::seal() {
  std::sort(rows_.begin(), rows_.end(),
            [](const SignalAuth& lhs, const SignalAuth& rhs) { return lhs.signal_id < rhs.signal_id; });
  for (std::size_t i = 1; i < rows_.size(); ++i) {
    if (rows_[i - 1].signal_id == rows_[i].signal_id) {
      return refuse<bool>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_candidates::SessionSignals::seal",
                                  "duplicate signal_id inside one session",
                                  static_cast<std::int64_t>(ordinal_)));
    }
  }
  return true;
}

const SignalAuth* SessionSignals::find(std::string_view signal_id) const noexcept {
  const auto at = std::lower_bound(
      rows_.begin(), rows_.end(), signal_id,
      [](const SignalAuth& row, std::string_view key) { return row.signal_id < key; });
  if (at == rows_.end() || at->signal_id != signal_id) {
    return nullptr;
  }
  return &*at;
}

// --- t14 bounds -------------------------------------------------------------

namespace {

/// Reads one line ONE BYTE AT A TIME through its newline. `class_header`
/// selects which counter the bytes land in, so the receipt can show that the
/// header really was walked bytewise.
[[nodiscard]] Expected<bool, Refusal> bytewise_line(PositionalSource& source, std::int64_t& offset,
                                                    ReadStats& stats, bool class_header,
                                                    std::string& out, Sha256* consumed) {
  out.clear();
  std::uint8_t byte = 0;
  while (true) {
    const auto step = source.read_at(&byte, 1, offset);
    if (!step) {
      return refuse<bool>(step.error());
    }
    offset += 1;
    stats.pread_calls += 1;
    stats.requested_bytes += 1;
    stats.max_request = std::max<std::size_t>(stats.max_request, 1);
    if (class_header) {
      stats.header_calls += 1;
    } else {
      stats.final_byte_calls += 1;
    }
    if (consumed != nullptr) {
      consumed->update(&byte, 1);
    }
    if (byte == '\n') {
      return true;
    }
    if (byte == '\r' || byte == 0) {
      return refuse<bool>(Refusal(RefusalCode::DECODE_FAILED, "qr_candidates::bytewise_line",
                                  "forbidden CR or NUL byte", byte));
    }
    out.push_back(static_cast<char>(byte));
    if (out.size() > kMaxLineBytes) {
      return refuse<bool>(Refusal(RefusalCode::DECODE_FAILED, "qr_candidates::bytewise_line",
                                  "line exceeds the 2MB guard",
                                  static_cast<std::int64_t>(out.size())));
    }
  }
}

}  // namespace

Expected<std::vector<T14Bound>, Refusal> load_t14_bounds(PositionalSource& source,
                                                          std::uint32_t stop, ReadStats& stats) {
  constexpr const char* kSite = "qr_candidates::load_t14_bounds";
  if (stop > kMaxPrefixOrdinal) {
    return refuse<std::vector<T14Bound>>(Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, kSite,
                                                 "stop ordinal is past the 917 wall",
                                                 static_cast<std::int64_t>(stop)));
  }
  std::int64_t offset = 0;
  std::string line;
  if (const auto step = bytewise_line(source, offset, stats, true, line, nullptr); !step) {
    return refuse<std::vector<T14Bound>>(step.error());
  }
  if (line != t14_header()) {
    return refuse<std::vector<T14Bound>>(
        Refusal(RefusalCode::SCHEMA_MISMATCH, kSite, "t14_bounds header is not the pinned header",
                static_cast<std::int64_t>(line.size())));
  }
  // Resolve the two cells by NAME against the pinned header, so a column added
  // upstream shifts nothing silently.
  std::size_t count_index = 0;
  std::size_t root_index = 0;
  std::size_t width = 0;
  {
    std::size_t at = 0;
    std::string_view header = t14_header();
    while (!header.empty()) {
      const std::size_t tab = header.find('\t');
      const std::string_view name = header.substr(0, tab);
      if (name == "signal_count") {
        count_index = at;
      } else if (name == "signal_sequence_root") {
        root_index = at;
      }
      ++at;
      if (tab == std::string_view::npos) {
        break;
      }
      header.remove_prefix(tab + 1);
    }
    width = at;
  }
  if (count_index == 0 || root_index == 0) {
    return refuse<std::vector<T14Bound>>(
        Refusal(RefusalCode::SCHEMA_MISMATCH, kSite, "pinned t14 header lacks the sealed columns"));
  }

  std::vector<T14Bound> bounds;
  bounds.reserve(static_cast<std::size_t>(stop) + 1U);
  std::vector<std::string_view> cells(width);
  for (std::uint32_t expected = 0; expected <= stop; ++expected) {
    if (const auto step = bytewise_line(source, offset, stats, false, line, nullptr); !step) {
      return refuse<std::vector<T14Bound>>(step.error());
    }
    if (!split_tabs(line, cells.data(), width)) {
      return refuse<std::vector<T14Bound>>(Refusal(RefusalCode::SCHEMA_MISMATCH, kSite,
                                                   "t14 row width differs from the header",
                                                   static_cast<std::int64_t>(expected)));
    }
    const auto ordinal = parse_u32(cells[0], kSite);
    if (!ordinal) {
      return refuse<std::vector<T14Bound>>(ordinal.error());
    }
    if (ordinal.value() != expected) {
      return refuse<std::vector<T14Bound>>(Refusal(RefusalCode::OUT_OF_ORDER, kSite,
                                                   "t14 ordinals are not the dense 0..stop ladder",
                                                   static_cast<std::int64_t>(ordinal.value())));
    }
    const auto signal_count = parse_u64(cells[count_index], kSite);
    if (!signal_count) {
      return refuse<std::vector<T14Bound>>(signal_count.error());
    }
    if (!is_canonical_digest_hex(cells[root_index])) {
      return refuse<std::vector<T14Bound>>(
          Refusal(RefusalCode::DECODE_FAILED, kSite,
                  "signal_sequence_root is not a canonical lowercase 64-hex digest",
                  static_cast<std::int64_t>(expected)));
    }
    T14Bound bound;
    bound.ordinal = ordinal.value();
    bound.day.assign(cells[1]);
    bound.signal_count = signal_count.value();
    bound.signal_sequence_root.assign(cells[root_index]);
    bounds.push_back(std::move(bound));
  }
  // The descriptor dies here: rows 918..1002 are never advanced to.
  source.close();
  return bounds;
}

// --- the prefix seal --------------------------------------------------------

Expected<PrefixSeal, Refusal> seal_prefix(PositionalSource& event,
                                          const std::vector<T14Bound>& bounds,
                                          const PrefixSealOptions& options,
                                          const SessionSink& sink) {
  constexpr const char* kSite = "qr_candidates::seal_prefix";
  if (options.stop_ordinal > kMaxPrefixOrdinal) {
    return refuse<PrefixSeal>(Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, kSite,
                                      "stop ordinal is past the 917 wall",
                                      static_cast<std::int64_t>(options.stop_ordinal)));
  }
  if (bounds.size() != static_cast<std::size_t>(options.stop_ordinal) + 1U) {
    return refuse<PrefixSeal>(Refusal(RefusalCode::CONFIG, kSite,
                                      "bounds do not cover exactly ordinals 0..stop",
                                      static_cast<std::int64_t>(bounds.size())));
  }
  if (options.require_pinned_event_bytes && event.size_bytes() != kEventSignalsBytes) {
    return refuse<PrefixSeal>(Refusal(RefusalCode::SOURCE_AUTHENTICATION_FAILED, kSite,
                                      "event_signals.tsv byte size is not the pinned size",
                                      event.size_bytes()));
  }

  PrefixSeal seal;
  seal.stop_ordinal = options.stop_ordinal;
  seal.io_before = read_io_accounting();
  Sha256 consumed;

  std::uint64_t expected_rows = 0;
  for (const T14Bound& bound : bounds) {
    if (expected_rows > UINT64_MAX - bound.signal_count) {
      return refuse<PrefixSeal>(
          Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kSite, "t14 row census overflows"));
    }
    expected_rows += bound.signal_count;
  }
  if (options.require_full_row_census && options.stop_ordinal == kMaxPrefixOrdinal &&
      expected_rows != kAdmittedRows0ToWall) {
    return refuse<PrefixSeal>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                      "t14 0..917 row census is not 13,115,504",
                                      static_cast<std::int64_t>(expected_rows)));
  }
  if (expected_rows == 0) {
    return refuse<PrefixSeal>(
        Refusal(RefusalCode::CONTENT_MISMATCH, kSite, "the prefix declares zero data rows"));
  }
  seal.expected_data_rows = expected_rows;
  seal.session_roots.reserve(bounds.size());

  // --- the header, one byte at a time --------------------------------------
  std::int64_t offset = 0;
  std::string header;
  if (const auto step = bytewise_line(event, offset, seal.event_stats, true, header, &consumed);
      !step) {
    return refuse<PrefixSeal>(step.error());
  }
  if (header != signal_header()) {
    return refuse<PrefixSeal>(Refusal(RefusalCode::SCHEMA_MISMATCH, kSite,
                                      "event_signals.tsv header is not the pinned header",
                                      static_cast<std::int64_t>(header.size())));
  }

  // --- per-row state --------------------------------------------------------
  std::size_t bound_index = 0;
  std::uint64_t session_rows = 0;
  bool have_previous_ordinal = false;
  std::uint32_t previous_ordinal = 0;
  Sha256 root;
  absorb_root_prologue(root, bounds[0].signal_count);
  SessionSignals retained;
  bool retaining = bounds[0].ordinal >= options.retain_from && bounds[0].ordinal <= options.retain_to;
  if (retaining) {
    retained.begin(bounds[0].ordinal);
  }
  std::array<std::string_view, kSignalFieldCount> cells{};
  std::array<std::uint8_t, kSignalImageCapacity> image{};
  Refusal pending_refusal(RefusalCode::CONFIG, kSite, "no refusal");
  bool refused = false;

  const auto handle_line = [&](std::string_view line) -> bool {
    if (bound_index >= bounds.size()) {
      pending_refusal = Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                "more event rows than the t14 census admits");
      return false;
    }
    const T14Bound& bound = bounds[bound_index];
    if (line.empty()) {
      pending_refusal = Refusal(RefusalCode::DECODE_FAILED, kSite, "blank data line");
      return false;
    }
    if (!split_tabs(line, cells.data(), kSignalFieldCount)) {
      pending_refusal = Refusal(RefusalCode::SCHEMA_MISMATCH, kSite,
                                "event row width is not the pinned 40 cells",
                                static_cast<std::int64_t>(bound.ordinal));
      return false;
    }
    const auto ordinal = parse_u32(cells[kFieldOrdinal], kSite);
    if (!ordinal) {
      pending_refusal = ordinal.error();
      return false;
    }
    // THE MONOTONICITY LAW, checked on its own so a permuted file that happens
    // to agree with a permuted census still refuses: an ordinal may repeat or
    // advance by exactly one, never move backwards and never pass 917.
    if (ordinal.value() > kMaxPrefixOrdinal) {
      pending_refusal = Refusal(RefusalCode::ORDINAL_OUTSIDE_SCOPE, kSite,
                                "decoded ordinal is past the 917 wall",
                                static_cast<std::int64_t>(ordinal.value()));
      return false;
    }
    if (have_previous_ordinal &&
        !(ordinal.value() == previous_ordinal || ordinal.value() == previous_ordinal + 1U)) {
      pending_refusal = Refusal(RefusalCode::OUT_OF_ORDER, kSite,
                                "decoded ordinals are not monotone 0..917",
                                static_cast<std::int64_t>(ordinal.value()));
      return false;
    }
    have_previous_ordinal = true;
    previous_ordinal = ordinal.value();
    if (ordinal.value() != bound.ordinal || cells[kFieldDay] != bound.day) {
      pending_refusal = Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                "event row session does not match the t14 row",
                                static_cast<std::int64_t>(ordinal.value()));
      return false;
    }
    const auto image_size = encode_signal_image(cells.data(), image.data());
    if (!image_size) {
      pending_refusal = image_size.error();
      return false;
    }
    root.update(image.data(), image_size.value());
    session_rows += 1;

    if (retaining) {
      SignalAuth row;
      row.ordinal = ordinal.value();
      row.signal_id.assign(cells[kFieldSignalId]);
      row.physical_event_id.assign(cells[kFieldPhysicalEventId]);
      row.policy_name.assign(cells[kFieldPolicyName]);
      const auto reversal = parse_u64(cells[kFieldReversalBps], kSite);
      if (!reversal) {
        pending_refusal = reversal.error();
        return false;
      }
      row.reversal_bps = reversal.value();
      row.extreme_side =
          cells[kFieldExtremeSide] == "LOW" ? ExtremeSide::LOW : ExtremeSide::HIGH;
      const auto visible = parse_i64(cells[kFieldCausalVisibleTsNs], kSite);
      if (!visible) {
        pending_refusal = visible.error();
        return false;
      }
      row.causal_visible_ts_ns = visible.value();
      if (!is_canonical_digest_hex(row.physical_event_id)) {
        pending_refusal = Refusal(RefusalCode::DECODE_FAILED, kSite,
                                  "physical_event_id is not a canonical digest",
                                  static_cast<std::int64_t>(ordinal.value()));
        return false;
      }
      retained.append(std::move(row));
    }

    if (session_rows == bound.signal_count) {
      const std::string observed = root.finish_hex();
      if (observed != bound.signal_sequence_root) {
        pending_refusal = Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                  "session signal_sequence_root does not match t14",
                                  static_cast<std::int64_t>(bound.ordinal));
        return false;
      }
      seal.session_roots.push_back(observed);
      seal.roots_verified += 1;
      if (retaining) {
        const auto sealed = retained.seal();
        if (!sealed) {
          pending_refusal = sealed.error();
          return false;
        }
        const auto accepted = sink(retained);
        if (!accepted) {
          pending_refusal = accepted.error();
          return false;
        }
        retained.clear();
      }
      bound_index += 1;
      session_rows = 0;
      if (bound_index < bounds.size()) {
        root.reset();
        absorb_root_prologue(root, bounds[bound_index].signal_count);
        retaining = bounds[bound_index].ordinal >= options.retain_from &&
                    bounds[bound_index].ordinal <= options.retain_to;
        if (retaining) {
          retained.begin(bounds[bound_index].ordinal);
        }
      } else {
        retaining = false;
      }
    }
    return true;
  };

  // --- the bounded block loop ----------------------------------------------
  std::vector<std::uint8_t> block(kBlockBytes);
  std::string carry;
  std::uint64_t remaining = expected_rows;
  while (remaining > 1) {
    // min(1MiB, R-1) — THE ARITHMETIC THAT IS THE WALL. A request of R-1 bytes
    // cannot contain R newlines, and row W+1 begins only after the R-th, so no
    // block can reach it. The guard below restates it as code.
    const std::size_t request =
        static_cast<std::size_t>(std::min<std::uint64_t>(kBlockBytes, remaining - 1U));
    if (static_cast<std::uint64_t>(request) >= remaining) {
      return refuse<PrefixSeal>(Refusal(RefusalCode::CLOCK_VIOLATION, kSite,
                                        "block request could contain the final newline",
                                        static_cast<std::int64_t>(request)));
    }
    {
      const auto step = event.read_at(block.data(), request, offset);
      if (!step) {
        return refuse<PrefixSeal>(step.error());
      }
      // One accounted call per REQUEST. `FileSource` retries a short kernel
      // read at the advanced offset inside itself, so this ledger counts
      // requests while /proc/self/io's `syscr` counts syscalls; both are
      // published so neither can hide a prefetch.
      seal.event_stats.pread_calls += 1;
      seal.event_stats.body_block_calls += 1;
      seal.event_stats.requested_bytes += static_cast<std::uint64_t>(request);
      seal.event_stats.max_request = std::max(seal.event_stats.max_request, request);
    }
    offset += static_cast<std::int64_t>(request);
    consumed.update(block.data(), request);

    // CR and NUL may not appear anywhere in the admitted region.
    if (std::memchr(block.data(), '\r', request) != nullptr ||
        std::memchr(block.data(), 0, request) != nullptr) {
      return refuse<PrefixSeal>(
          Refusal(RefusalCode::DECODE_FAILED, kSite, "forbidden CR or NUL byte in a data block"));
    }

    std::uint64_t newlines = 0;
    std::size_t cursor = 0;
    while (cursor < request) {
      const auto* found = static_cast<const std::uint8_t*>(
          std::memchr(block.data() + cursor, '\n', request - cursor));
      if (found == nullptr) {
        break;
      }
      const std::size_t end = static_cast<std::size_t>(found - block.data());
      std::string_view line;
      if (!carry.empty()) {
        carry.append(reinterpret_cast<const char*>(block.data() + cursor), end - cursor);
        line = carry;
      } else {
        line = std::string_view(reinterpret_cast<const char*>(block.data() + cursor), end - cursor);
      }
      if (!handle_line(line)) {
        refused = true;
        break;
      }
      carry.clear();
      newlines += 1;
      cursor = end + 1;
    }
    if (refused) {
      return refuse<PrefixSeal>(pending_refusal);
    }
    if (cursor < request) {
      carry.append(reinterpret_cast<const char*>(block.data() + cursor), request - cursor);
      if (carry.size() > kMaxLineBytes) {
        return refuse<PrefixSeal>(Refusal(RefusalCode::DECODE_FAILED, kSite,
                                          "event line exceeds the 2MB guard",
                                          static_cast<std::int64_t>(carry.size())));
      }
    }
    if (newlines >= remaining) {
      return refuse<PrefixSeal>(
          Refusal(RefusalCode::CLOCK_VIOLATION, kSite, "a block crossed the final newline",
                  static_cast<std::int64_t>(newlines)));
    }
    remaining -= newlines;
  }

  // --- the final row, one byte at a time ------------------------------------
  while (remaining == 1) {
    std::uint8_t byte = 0;
    const auto step = event.read_at(&byte, 1, offset);
    if (!step) {
      return refuse<PrefixSeal>(step.error());
    }
    offset += 1;
    seal.event_stats.pread_calls += 1;
    seal.event_stats.requested_bytes += 1;
    seal.event_stats.final_byte_calls += 1;
    seal.event_stats.max_request = std::max<std::size_t>(seal.event_stats.max_request, 1);
    consumed.update(&byte, 1);
    if (byte == '\n') {
      if (carry.empty()) {
        return refuse<PrefixSeal>(
            Refusal(RefusalCode::DECODE_FAILED, kSite, "blank final data line"));
      }
      if (!handle_line(carry)) {
        return refuse<PrefixSeal>(pending_refusal);
      }
      carry.clear();
      remaining = 0;
      break;
    }
    if (byte == '\r' || byte == 0) {
      return refuse<PrefixSeal>(
          Refusal(RefusalCode::DECODE_FAILED, kSite, "forbidden CR or NUL in the final line", byte));
    }
    carry.push_back(static_cast<char>(byte));
    if (carry.size() > kMaxLineBytes) {
      return refuse<PrefixSeal>(Refusal(RefusalCode::DECODE_FAILED, kSite,
                                        "final line exceeds the 2MB guard",
                                        static_cast<std::int64_t>(carry.size())));
    }
  }

  seal.event_stats.end_offset_exclusive = offset;
  // THE WALL CLOSES HERE, before any byte of row W+1 has been addressed.
  event.close();
  seal.io_after = read_io_accounting();

  if (!carry.empty() || bound_index != bounds.size() || session_rows != 0 ||
      seal.roots_verified != static_cast<std::uint32_t>(bounds.size())) {
    return refuse<PrefixSeal>(Refusal(RefusalCode::CONTENT_MISMATCH, kSite,
                                      "prefix did not end at the exact t14 boundary",
                                      static_cast<std::int64_t>(bound_index)));
  }
  seal.decoded_data_rows = expected_rows;
  seal.consumed_prefix_sha256 = consumed.finish_hex();
  return seal;
}

std::string render_safe_leaf(const SessionSignals& session) {
  std::string out =
      "ordinal\tsignal_id\tphysical_event_id\tpolicy_name\treversal_bps\textreme_side\t"
      "causal_visible_ts_ns\n";
  char scratch[64];
  for (const SignalAuth& row : session.rows()) {
    std::snprintf(scratch, sizeof(scratch), "%u", row.ordinal);
    out += scratch;
    out += '\t';
    out += row.signal_id;
    out += '\t';
    out += row.physical_event_id;
    out += '\t';
    out += row.policy_name;
    out += '\t';
    std::snprintf(scratch, sizeof(scratch), "%llu",
                  static_cast<unsigned long long>(row.reversal_bps));
    out += scratch;
    out += '\t';
    out += extreme_side_name(row.extreme_side);
    out += '\t';
    std::snprintf(scratch, sizeof(scratch), "%lld",
                  static_cast<long long>(row.causal_visible_ts_ns));
    out += scratch;
    out += '\n';
  }
  return out;
}

}  // namespace qr::candidates
