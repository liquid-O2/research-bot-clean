// qr_gen/families.hpp — the S1.2 DISCOVERY-FAMILY detectors (CC-M1-7.1/7.2).
//
// The four adopted generator families and the one adopted FLAG all reduce to
// four causal detectors over a session, and each is a law with a mutant:
//
//   WINDOWS        NEWS-WINDOW / MICRO-OPENS fire on a confirmation landing in
//                  [trigger, trigger + width) — half-open, merged, so two
//                  triggers 60s apart are ONE window and not two overlapping
//                  ones that double-count.
//   SHOCK          POST-SHOCK's episode detector is CAUSAL: a second is in
//                  shock when the mid range over the TRAILING (t - 150, t]
//                  wall-seconds reaches $1,000 — a quantity known at t. The
//                  window is in WALL seconds, so a gap of insane seconds
//                  SHORTENS it instead of reaching further back.
//   INSANE         the second POST-SHOCK trigger: a run of >= 10 seconds that
//                  are TWO_SIDED but not MID-SANE (D-054 wide books — the
//                  pathological book, never a book outage).
//   OR-EXTENSION   the F-D6 flag reads a LIVE, SAME-SEGMENT opening-range
//                  extension at k >= 1.5. A Tokyo opening range says nothing
//                  about a New York price, and a level does not exist before
//                  its own range has closed.
//
// The same opening-range construction feeds the CC-M1-6.1 OR_EXT LEDGER family
// (levels.hpp) — one definition, two consumers, which is why it lives here and
// not inside either.
#ifndef QR_GEN_FAMILIES_HPP
#define QR_GEN_FAMILIES_HPP

// Every detector here takes PLAIN ARRAYS, never a session object: they are the
// laws, and a law that can only be exercised through a corpus receipt is a law
// nobody can put a mutant against.
#include <cstdint>
#include <vector>

namespace qr::gen {

// --- CC-M1-7.1 window / shock constants -------------------------------------
inline constexpr std::int32_t kNewsWindow = 600;   ///< F-D3 "first 10 min"
inline constexpr std::int32_t kNewsDelay = 15;     ///< CC-M1-7.1 "single 15s delay"
inline constexpr std::int32_t kMicroWindow = 300;  ///< F-D2 = the FAST-OPEN construction
inline constexpr std::int32_t kMicroDelay = 15;
inline constexpr std::int32_t kShockSpan = 150;    ///< = NEWS_SPAN (CC-M1-4.3)
inline constexpr double kShockUsd = 1000.0;        ///< the $1k leg class
inline constexpr std::int32_t kInsaneMinSec = 10;  ///< §6 G3 "sustained >= 10s"
inline constexpr double kOrExtKMin = 1.5;          ///< F-D6 "beyond an OR_EXT k >= 1.5"

/// The censused opening-range ladder (= hl_census.P3_K) and its minute grid.
inline constexpr std::size_t kOrExtKCount = 4;
inline constexpr double kOrExtK[kOrExtKCount] = {0.5, 1.0, 1.5, 2.0};
inline constexpr std::size_t kOrMinutesCount = 2;
inline constexpr int kOrMinutes[kOrMinutesCount] = {30, 60};

/// An INCLUSIVE second interval [a, b].
struct Interval {
  std::int32_t a = 0;
  std::int32_t b = -1;
};

/// Sorted, non-overlapping, inclusive intervals; abutting intervals merge.
[[nodiscard]] std::vector<Interval> merge_intervals(std::vector<Interval> iv);

/// [t, t + width) for every trigger second t, merged (F-D2 / F-D3).
[[nodiscard]] std::vector<Interval> open_windows(const std::vector<std::int32_t>& secs,
                                                 std::int32_t width);

/// TRUE iff `sec` lies inside one of the merged inclusive intervals.
[[nodiscard]] bool in_intervals(std::int32_t sec, const std::vector<Interval>& iv);

/// out[i] = max(a[max(0, i - w + 1) .. i]) — the trailing sliding maximum.
[[nodiscard]] std::vector<double> sliding_max(const std::vector<double>& a, std::int32_t w);

/// Trailing-`span`-WALL-second SANE mid range in dollars at each observed
/// second (same order/length as `vt`).
[[nodiscard]] std::vector<double> rolling_range_usd(const std::vector<std::int32_t>& vt,
                                                    const std::vector<double>& vm, double mult,
                                                    std::int32_t span);

/// Maximal runs of in-shock OBSERVED seconds, as (first_sec, last_sec). A run
/// is contiguous in OBSERVATION index, so a gap of insane seconds does not
/// split an episode.
[[nodiscard]] std::vector<Interval> shock_episodes(const std::vector<std::int32_t>& vt,
                                                   const std::vector<double>& vm, double mult);

/// D-054 wide-book episodes: runs of >= 10 seconds that are TWO_SIDED but not
/// MID-SANE, as (first_sec, last_sec). `state` and `sane` are per SESSION
/// SECOND: a book OUTAGE is not a wide book and must never become one.
[[nodiscard]] std::vector<Interval> insane_episodes(const std::vector<std::int8_t>& state,
                                                    const std::vector<std::uint8_t>& sane);

/// Indices of the EARLIEST confirmation strictly after `end_sec`. All entries
/// sharing that second are returned (both sides can confirm on one second).
[[nodiscard]] std::vector<std::size_t> first_confirmations_after(
    const std::vector<std::int32_t>& conf_secs, std::int32_t end_sec);

/// One segment's opening range on the SANE mids: [first sane second of the
/// segment, + minutes x 60). `valid` is false whenever either the range side or
/// the rest-of-window side is empty (typed exclusion, never a substituted 0).
struct OpeningRange {
  double hi = 0.0;
  double lo = 0.0;
  std::int32_t t1 = -1;  ///< the second the range CLOSES (levels exist from it)
  std::int8_t phase = -1;
  bool valid = false;
};
/// `vt`/`vm` are the MID-SANE seconds and their mids; `phase_at_vt` is the
/// phase tag at those same seconds (so the SANE mask is applied by
/// construction, never re-derived).
[[nodiscard]] OpeningRange opening_range(const std::vector<std::int32_t>& vt,
                                         const std::vector<double>& vm,
                                         const std::vector<std::int8_t>& phase_at_vt, int phase,
                                         int minutes);

/// One live OR-extension price for the F-D6 flag.
struct OrExtLevel {
  std::int32_t t1 = -1;
  double price = 0.0;
  std::int8_t side = 0;   ///< +1 = the UP extension, -1 = the DOWN extension
  std::int8_t phase = -1; ///< the segment the level is scoped to
};

/// The F-D6 extension prices of one opening range: the k >= 1.5 rungs ONLY,
/// both sides. An invalid range builds nothing.
[[nodiscard]] std::vector<OrExtLevel> orext_flag_levels(const OpeningRange& r);

/// TRUE iff `mid` sits beyond a LIVE, SAME-SEGMENT extension.
[[nodiscard]] bool beyond_extension(double mid, std::int32_t sec, std::int8_t phase,
                                    const std::vector<OrExtLevel>& cells);

}  // namespace qr::gen

#endif  // QR_GEN_FAMILIES_HPP
