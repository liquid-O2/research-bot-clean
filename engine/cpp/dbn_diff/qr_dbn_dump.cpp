// qr_dbn_dump — differential-oracle DBN dumper built on OUR OWN hand-written
// decoder (/workspace/engine/cpp/qr_dbn). It is the third decoder of the
// three-way byte-agreement proof; decoder A is dbn_dump.cpp (official
// databento-cpp) and decoder B is the official databento_dbn Python library.
//
// Usage (identical to dbn_dump):
//   qr_dbn_dump <payload.dbn.zst> <instrument_id> <lo_ns> <hi_ns>
//
// Emits ONE TSV line per kept record to stdout (no header), columns and
// formatting byte-for-byte identical to dbn_dump.cpp:
//   ts_event sequence action side price size flags depth ts_recv ts_in_delta
//   bid_px ask_px bid_sz ask_sz bid_ct ask_ct
//
// The scan-stop rule mirrors dbn_dump.cpp exactly (one hour of slack past
// hi_ns) so the two programs visit the same prefix of the stream.
// Nothing but TSV rows goes to stdout; all diagnostics go to stderr.

#include <cerrno>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <string>

#include "qr_dbn/dbn.hpp"

namespace {

// Same slack as dbn_dump.cpp: records are time-ordered within a DBN file, so an
// hour past the requested window there can be no further matches.
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
                 argc > 0 ? argv[0] : "qr_dbn_dump");
    return 2;
  }

  const std::string path{argv[1]};
  std::uint64_t instrument_id_u = 0;
  std::uint64_t lo_ns = 0;
  std::uint64_t hi_ns = 0;
  if (!ParseU64(argv[2], &instrument_id_u) ||
      instrument_id_u > std::numeric_limits<std::uint32_t>::max()) {
    std::fprintf(stderr, "qr_dbn_dump: bad instrument_id '%s'\n", argv[2]);
    return 2;
  }
  if (!ParseU64(argv[3], &lo_ns)) {
    std::fprintf(stderr, "qr_dbn_dump: bad lo_ns '%s'\n", argv[3]);
    return 2;
  }
  if (!ParseU64(argv[4], &hi_ns)) {
    std::fprintf(stderr, "qr_dbn_dump: bad hi_ns '%s'\n", argv[4]);
    return 2;
  }
  const auto instrument_id = static_cast<std::uint32_t>(instrument_id_u);

  const std::uint64_t stop_ns =
      (hi_ns > std::numeric_limits<std::uint64_t>::max() - kScanSlackNs)
          ? std::numeric_limits<std::uint64_t>::max()
          : hi_ns + kScanSlackNs;

  qr::dbn::DbnStream stream;
  if (auto opened = stream.open(path); !opened) {
    std::fprintf(stderr, "qr_dbn_dump: open refused: %s\n",
                 opened.error().message().c_str());
    return 1;
  }

  std::uint64_t n_kept = 0;
  for (;;) {
    auto next = stream.next_mbp1();
    if (!next) {
      std::fflush(stdout);
      std::fprintf(stderr, "qr_dbn_dump: decode refused after %" PRIu64 " mbp1 records: %s\n",
                   stream.n_mbp1(), next.error().message().c_str());
      return 1;
    }
    const qr::dbn::Mbp1Msg* msg = next.value();
    if (msg == nullptr) {
      break;  // clean end of stream
    }
    const std::uint64_t ts_event = msg->hd.ts_event;
    if (ts_event >= stop_ns) {
      break;
    }
    if (msg->hd.instrument_id != instrument_id) {
      continue;
    }
    if (ts_event < lo_ns || ts_event >= hi_ns) {
      continue;
    }
    ++n_kept;

    const qr::dbn::BidAskPair& lvl = msg->levels[0];
    std::printf(
        "%" PRIu64 "\t%" PRIu32 "\t%c\t%c\t%" PRId64 "\t%" PRIu32 "\t%" PRIu32
        "\t%" PRIu32 "\t%" PRIu64 "\t%" PRId32 "\t%" PRId64 "\t%" PRId64 "\t%" PRIu32
        "\t%" PRIu32 "\t%" PRIu32 "\t%" PRIu32 "\n",
        ts_event, msg->sequence, static_cast<char>(msg->action),
        static_cast<char>(msg->side), msg->price, msg->size,
        static_cast<std::uint32_t>(msg->flags), static_cast<std::uint32_t>(msg->depth),
        msg->ts_recv, msg->ts_in_delta, lvl.bid_px, lvl.ask_px, lvl.bid_sz, lvl.ask_sz,
        lvl.bid_ct, lvl.ask_ct);
  }

  if (std::fflush(stdout) != 0) {
    std::fprintf(stderr, "qr_dbn_dump: failed to flush stdout\n");
    return 1;
  }
  std::fprintf(stderr,
               "qr_dbn_dump: mbp1=%" PRIu64 " skipped=%" PRIu64 " kept=%" PRIu64 "\n",
               stream.n_mbp1(), stream.n_skipped(), n_kept);
  return 0;
}
