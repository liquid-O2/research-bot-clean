// qr_gen/calendar.hpp — the S1.2 NEWS/MICRO-OPEN calendar joins (CC-M1-7.1).
//
// The adopted NEWS-WINDOW and MICRO-OPENS families are anchored on LOCAL WALL
// CLOCK times, not on UTC offsets:
//
//   NEWS   the fixed 08:30 and 10:00 America/New_York slots (the calendar-lite
//          proxy that subsumes every banked BLS release — the whole
//          bls_calendar/bls_release_dates.csv corpus lands at 08:30 ET, so the
//          fixed slot is a superset of it, which is why the frozen oracle reads
//          no BLS file), plus the FOMC statement at 14:00 ET on the meeting's
//          LAST day, joined on the ET CALENDAR DAY OF THE RELEASE SECOND.
//   MICRO  12:30 Asia/Tokyo (the lunch reopen) and 09:30 America/New_York (the
//          US cash open).
//
// TWO LAWS LIVE HERE, both of them bug-shaped:
//
//   (1) DST. A frozen UTC offset silently moves every ET slot by an hour for
//       eight months of the year. The offsets are materialised through the IANA
//       tz database (std::chrono::time_zone), and a wall time that does not
//       exist on a spring-forward date is DROPPED by a round-trip check rather
//       than silently shifted.
//   (2) THE THREE-DAY SCAN. A Globex session opens the previous evening ET, so
//       up to three ET calendar days' slots can fall inside one session; the
//       scan runs over {yesterday, today, tomorrow} of the session open's own
//       local date. Joining on the session's trade_date alone is the
//       off-by-one-day bug this header exists to prevent (V3-3).
#ifndef QR_GEN_CALENDAR_HPP
#define QR_GEN_CALENDAR_HPP

#include <cstdint>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"

namespace qr::gen {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;

/// The IANA zones the S1.2 calendars are expressed in.
inline constexpr const char* kTzNewYork = "America/New_York";
inline constexpr const char* kTzTokyo = "Asia/Tokyo";

/// One local-wall-clock slot: a zone and an hh:mm on it.
struct LocalSlot {
  const char* tz;
  int hh;
  int mm;
};

/// CC-M1-7.1 fixed release slots (BOJ deferred — FD-2: the banked calendar
/// starts 2026, so its leg would be all-warm-up).
inline constexpr std::size_t kNewsSlotCount = 2;
inline constexpr LocalSlot kNewsSlots[kNewsSlotCount] = {{kTzNewYork, 8, 30},
                                                         {kTzNewYork, 10, 0}};
inline constexpr int kFomcHour = 14;
inline constexpr int kFomcMin = 0;

/// CC-M1-7.1 micro-opens: the Tokyo lunch reopen and the US cash open.
inline constexpr std::size_t kMicroOpenCount = 2;
inline constexpr LocalSlot kMicroOpens[kMicroOpenCount] = {{kTzTokyo, 12, 30},
                                                           {kTzNewYork, 9, 30}};

/// Session-second offsets inside [open_utc, open_utc + n) whose LOCAL clock in
/// `tz` reads hh:mm, scanning the local day BEFORE, the local day OF the open
/// and the local day AFTER. Ascending, deduplicated.
[[nodiscard]] std::vector<std::int32_t> local_epoch_offsets(std::int64_t open_utc, std::int32_t n,
                                                            const char* tz, int hh, int mm);

/// YYYYMMDD of `epoch` on the LOCAL calendar of `tz` (the V3-3 join key).
[[nodiscard]] std::int32_t local_date8(std::int64_t epoch, const char* tz);

/// The LAST day of every banked FOMC meeting, as YYYYMMDD, ascending and
/// deduplicated. calendar_fomc.csv rows are (year, month, days) with the month
/// possibly a two-month span ("Jan/Feb") and the days a range ("31-1"): the
/// statement lands on the meeting's last (month, day) pair, and a span that
/// wraps into January belongs to the NEXT year.
[[nodiscard]] Expected<std::vector<std::int32_t>, Refusal> fomc_release_dates(
    const std::string& csv_path);

}  // namespace qr::gen

#endif  // QR_GEN_CALENDAR_HPP
