// qr_futsess/decode.hpp — PROGRAM MODE decode of one payload file into
// per-UTC-day receipts (M0 spec §4, reference engine/port_m0/s2_decode.py).
#ifndef QR_FUTSESS_DECODE_HPP
#define QR_FUTSESS_DECODE_HPP

#include <cstdint>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_futsess/constants.hpp"

namespace qr::futsess {

/// One row of `integrity_flags.tsv` (M0 §4: log, do not crash).
struct IntegrityFlag {
  std::string asset;
  std::string date;
  std::string flag;
  std::string detail;
};

struct DecodeResult {
  std::string file;
  std::int64_t n_records = 0;
  std::int64_t n_foreign = 0;
  std::vector<std::string> days_written;  // YYYYMMDD
  std::vector<IntegrityFlag> flags;
};

/// Decode one `.dbn.zst` payload into `out_dir/{YYYYMMDD}.qrday`.
///
/// Records whose `ts_event` UTC date falls outside the file's declared date
/// range are counted and dropped, never written — writing them would produce a
/// partial receipt for a day another file owns (s2_decode.py:293-301).
[[nodiscard]] Expected<DecodeResult, Refusal> decode_payload_file(Asset asset,
                                                                  const std::string& path,
                                                                  const std::string& out_dir);

}  // namespace qr::futsess

#endif  // QR_FUTSESS_DECODE_HPP
