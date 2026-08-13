// qr_futsess/dayrec.hpp — the per-(asset, UTC day) receipt of M0 spec §4.
//
// SPEC: design/PORT_M0_CENSUS_SPEC.md §4, reference engine/port_m0/s2_decode.py.
// Row order in every per-instrument array is `sorted(tracked ids)`, exactly as
// the reference's `.npz` receipts. This is the intermediate the session
// assembler stitches; it is NOT the differential target (the session receipts
// are), but it carries every field §5 consumes.
#ifndef QR_FUTSESS_DAYREC_HPP
#define QR_FUTSESS_DAYREC_HPP

#include <cstdint>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_futsess/calendar.hpp"
#include "qr_futsess/constants.hpp"

namespace qr::futsess {

/// One decoded UTC day. Grid arrays are row-major [n_tracked][86400].
struct DayReceipt {
  Date date;
  std::vector<std::int64_t> tracked_ids;  // sorted

  std::vector<std::int64_t> bid_px;       // UNDEF_PRICE where the §0 guard failed
  std::vector<std::int64_t> ask_px;
  std::vector<std::int64_t> bid_sz;
  std::vector<std::int64_t> ask_sz;
  std::vector<std::int8_t> state;         // §4 codes, forward-filled
  std::vector<std::int32_t> upd_count;    // records per second

  std::vector<std::int64_t> trades_iid;   // tracked instruments only
  std::vector<std::int64_t> trades_sec;
  std::vector<std::int64_t> trades_px;
  std::vector<std::int64_t> trades_size;
  std::vector<std::uint8_t> trades_side;  // ASCII 'B' / 'A' / 'N'

  std::vector<std::int64_t> tally_iid;    // ALL instruments, sorted
  std::vector<std::int64_t> tally_updates;
  std::vector<std::int64_t> tally_trades;
  std::vector<std::int64_t> tally_trade_size_sum;

  std::vector<std::int64_t> map_iid;      // ALL instruments, sorted
  std::vector<std::string> map_symbol;
  std::vector<std::uint8_t> map_outright;

  std::vector<std::int64_t> carry_iid;    // tracked instruments, sorted
  std::vector<std::int64_t> carry_bid;
  std::vector<std::int64_t> carry_ask;
  std::vector<std::int64_t> carry_bsz;
  std::vector<std::int64_t> carry_asz;
  std::vector<std::int8_t> carry_state;
  std::vector<std::int64_t> carry_last_sec;

  // Counters (M0 §4 integrity block).
  std::int64_t n_records = 0;
  std::int64_t n_dropped_sentinel = 0;
  std::int64_t n_no_flast_seconds = 0;
  std::int64_t tick_gcd_raw = 0;

  [[nodiscard]] std::size_t n_tracked() const { return tracked_ids.size(); }
  /// Row index of `iid` among the tracked ids, or -1 (M0 `_row_index`).
  [[nodiscard]] int row_index(std::int64_t iid) const;
  /// Row index of `iid` among the carry ids, or -1.
  [[nodiscard]] int carry_index(std::int64_t iid) const;
};

/// Write a day receipt to `path` (zstd-framed, deterministic byte-for-byte).
[[nodiscard]] Expected<std::monostate, Refusal> write_day_receipt(const std::string& path,
                                                                  const DayReceipt& rec);
/// Read a day receipt written by write_day_receipt().
[[nodiscard]] Expected<DayReceipt, Refusal> read_day_receipt(const std::string& path);

}  // namespace qr::futsess

#endif  // QR_FUTSESS_DAYREC_HPP
