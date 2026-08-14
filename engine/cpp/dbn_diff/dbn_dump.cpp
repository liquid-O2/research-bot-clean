// dbn_dump — differential-oracle DBN dumper built on the OFFICIAL databento-cpp
// library (vendored at /workspace/vendor/databento-cpp, v0.64.0).
//
// Usage:
//   dbn_dump <payload.dbn.zst> <instrument_id> <lo_ns> <hi_ns>
//
// Streams the DBN file with databento::DbnFileStore, keeps every Mbp1Msg whose
//   hd.instrument_id == instrument_id  AND  lo_ns <= hd.ts_event < hi_ns
// and writes ONE TSV line per kept record to stdout (no header), columns:
//   ts_event sequence action side price size flags depth ts_recv ts_in_delta
//   bid_px ask_px bid_sz ask_sz bid_ct ask_ct
//
// Conventions (deliberate, for byte-comparability against other decoders):
//   * ts_event / ts_recv printed as raw unsigned 64-bit nanosecond integers.
//   * action / side printed as the single ASCII character.
//   * price / bid_px / ask_px printed as the RAW int64 fixed-point value (unscaled).
//   * flags printed as the raw unsigned byte, depth as an unsigned integer.
//   * ts_in_delta printed as the raw signed 32-bit nanosecond count.
// Nothing but TSV rows goes to stdout; all diagnostics go to stderr.

#include <cerrno>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <limits>
#include <string>

#include "databento/dbn_file_store.hpp"
#include "databento/enums.hpp"
#include "databento/record.hpp"

namespace {

// Records are time-ordered within a DBN file, so once ts_event has run an hour
// past the requested window there can be no further matches. One hour of slack
// absorbs any residual out-of-order jitter.
constexpr std::uint64_t kScanSlackNs = 3600ULL * 1000000000ULL;

bool ParseU64(const char* text, std::uint64_t* out) {
  errno = 0;
  char* end = nullptr;
  const unsigned long long value = std::strtoull(text, &end, 10);
  if (errno != 0 || end == text || *end != '\0') {
    return false;
  }
  *out = static_cast<std::uint64_t>(value);
  return true;
}

}  // namespace

int main(int argc, char* argv[]) {
  if (argc != 5) {
    std::fprintf(stderr,
                 "usage: %s <payload.dbn.zst> <instrument_id> <lo_ns> <hi_ns>\n",
                 argc > 0 ? argv[0] : "dbn_dump");
    return 2;
  }

  const std::string path{argv[1]};
  std::uint64_t instrument_id_u = 0;
  std::uint64_t lo_ns = 0;
  std::uint64_t hi_ns = 0;
  if (!ParseU64(argv[2], &instrument_id_u) ||
      instrument_id_u > std::numeric_limits<std::uint32_t>::max()) {
    std::fprintf(stderr, "dbn_dump: bad instrument_id '%s'\n", argv[2]);
    return 2;
  }
  if (!ParseU64(argv[3], &lo_ns)) {
    std::fprintf(stderr, "dbn_dump: bad lo_ns '%s'\n", argv[3]);
    return 2;
  }
  if (!ParseU64(argv[4], &hi_ns)) {
    std::fprintf(stderr, "dbn_dump: bad hi_ns '%s'\n", argv[4]);
    return 2;
  }
  const auto instrument_id = static_cast<std::uint32_t>(instrument_id_u);

  // Saturating so a caller-supplied hi_ns near the top of the range cannot wrap.
  const std::uint64_t stop_ns =
      (hi_ns > std::numeric_limits<std::uint64_t>::max() - kScanSlackNs)
          ? std::numeric_limits<std::uint64_t>::max()
          : hi_ns + kScanSlackNs;

  std::uint64_t n_records = 0;
  std::uint64_t n_mbp1 = 0;
  std::uint64_t n_kept = 0;

  try {
    databento::DbnFileStore store{path};
    while (const databento::Record* rec = store.NextRecord()) {
      ++n_records;
      const std::uint64_t ts_event = rec->Header().ts_event.time_since_epoch().count();
      if (ts_event >= stop_ns) {
        break;
      }
      const auto* msg = rec->GetIf<databento::Mbp1Msg>();
      if (msg == nullptr) {
        continue;
      }
      ++n_mbp1;
      if (msg->hd.instrument_id != instrument_id) {
        continue;
      }
      if (ts_event < lo_ns || ts_event >= hi_ns) {
        continue;
      }
      ++n_kept;

      const databento::BidAskPair& lvl = msg->levels[0];
      std::printf(
          "%" PRIu64 "\t%" PRIu32 "\t%c\t%c\t%" PRId64 "\t%" PRIu32 "\t%" PRIu32
          "\t%" PRIu32 "\t%" PRIu64 "\t%" PRId32 "\t%" PRId64 "\t%" PRId64 "\t%" PRIu32
          "\t%" PRIu32 "\t%" PRIu32 "\t%" PRIu32 "\n",
          ts_event, msg->sequence, static_cast<char>(msg->action),
          static_cast<char>(msg->side), msg->price, msg->size,
          static_cast<std::uint32_t>(msg->flags.Raw()),
          static_cast<std::uint32_t>(msg->depth),
          msg->ts_recv.time_since_epoch().count(), msg->ts_in_delta.count(), lvl.bid_px,
          lvl.ask_px, lvl.bid_sz, lvl.ask_sz, lvl.bid_ct, lvl.ask_ct);
    }
  } catch (const std::exception& exc) {
    std::fflush(stdout);
    std::fprintf(stderr, "dbn_dump: decode error after %" PRIu64 " records: %s\n",
                 n_records, exc.what());
    return 1;
  }

  if (std::fflush(stdout) != 0) {
    std::fprintf(stderr, "dbn_dump: failed to flush stdout\n");
    return 1;
  }
  std::fprintf(stderr,
               "dbn_dump: scanned=%" PRIu64 " mbp1=%" PRIu64 " kept=%" PRIu64 "\n",
               n_records, n_mbp1, n_kept);
  return 0;
}
