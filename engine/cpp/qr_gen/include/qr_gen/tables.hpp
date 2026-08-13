// qr_gen/tables.hpp — the frozen TSV inputs the generation engine stands on.
//
// SPEC: design/PORT_M1B_SPEC.md §1 S2; PORT_M1_SPEC.md §3/§4 + CC-M1-1.
//
// NOTHING here is a model. These are the receipts other, already-gated stages
// wrote, read back verbatim:
//
//   bars_{ASSET}.tsv               ATR14_prev_usd, the causal ATR the rung
//                                  ladder and the level tolerance are scaled by
//   census_a_cost_rollup.tsv       pooled per-(year, phase) median spread, the
//                                  §1 rung floor
//   m1/fvol/v1_realized.tsv        per-(session, segment) O/H/L/C + range, the
//                                  history PRIOR_DAY / NDAY / PHASE_HL levels
//                                  are built from
//   m1/fvol/fvol_forecasts.tsv     the FROZEN fvol coefficients' output:
//                                  sigma_hat($) and the CC-M1-1 calibrated
//                                  expected-move multipliers per quantile
//
// A missing file is a refusal. A missing CELL is NaN and is handled by the
// caller exactly as the Python oracle handles it (skip the level, drop the
// floor term) — never by substitution.
#ifndef QR_GEN_TABLES_HPP
#define QR_GEN_TABLES_HPP

#include <cstdint>
#include <map>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"

namespace qr::gen {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;

/// The five v1_realized segments. SESSION and OVERNIGHT are NOT phases: the
/// frozen m0 table has three phases (CC-M1-3.6) and OVERNIGHT is the additional
/// §4(c) segment m1_common defines.
enum class Segment : std::uint8_t { SESSION = 0, OVERNIGHT = 1, TOKYO = 2, LONDON = 3, NY = 4 };
inline constexpr std::size_t kSegmentCount = 5;
[[nodiscard]] const char* segment_name(Segment s);

/// CC-M1-1(A): the calibrated expected-move ladder quantiles.
inline constexpr std::size_t kLadderQCount = 5;
inline constexpr int kLadderQ[kLadderQCount] = {10, 25, 50, 75, 90};

struct SegmentBar {
  double open_px = 0.0;
  double high_px = 0.0;
  double low_px = 0.0;
  double close_px = 0.0;
  double range_usd = 0.0;
  bool present = false;
};

/// One trade date's segment bars.
struct DayBars {
  SegmentBar seg[kSegmentCount];
};

/// §3 V1 history. A session whose SESSION range is not strictly positive is a
/// FROZEN QUOTE, not a session (b2_fvol.series_for), and is dropped here — it
/// must never supply a prior-day / N-day / per-phase level.
class V1History {
 public:
  [[nodiscard]] static Expected<V1History, Refusal> load(const std::string& path,
                                                         const std::string& asset);

  /// Ascending trade dates (stale-book sessions already removed).
  [[nodiscard]] const std::vector<std::int32_t>& dates() const { return dates_; }
  /// Position of date8 in dates(), or -1 when the date is not a session here.
  [[nodiscard]] std::int64_t index_of(std::int32_t date8) const;
  /// Bars of dates()[i].
  [[nodiscard]] const DayBars& at(std::int64_t i) const { return bars_[static_cast<std::size_t>(i)]; }

 private:
  std::vector<std::int32_t> dates_;
  std::vector<DayBars> bars_;
};

/// §3/CC-M1-1 forecast row for one (trade date, segment).
struct FvolRow {
  double sigma_hat_usd = 0.0;
  /// Multipliers ON sigma_hat_usd (the table's own header says so).
  double move_q[kLadderQCount] = {0.0, 0.0, 0.0, 0.0, 0.0};
  bool present = false;
};

class FvolForecasts {
 public:
  [[nodiscard]] static Expected<FvolForecasts, Refusal> load(const std::string& path,
                                                             const std::string& asset);
  /// nullptr when the (date, segment) pair has no forecast row at all.
  [[nodiscard]] const FvolRow* find(std::int32_t date8, Segment seg) const;

 private:
  std::map<std::pair<std::int32_t, std::uint8_t>, FvolRow> rows_;
};

/// bars_{ASSET}.tsv -> ATR14_prev_usd. The roster carries the value at the
/// PRINTED precision of that file, which is what the Python oracle parses too.
class BarsTable {
 public:
  [[nodiscard]] static Expected<BarsTable, Refusal> load(const std::string& path);
  /// NaN when the date is absent or the cell is empty (m0 "NO_ATR14").
  [[nodiscard]] double atr14_prev_usd(std::int32_t date8) const;

 private:
  std::map<std::int32_t, double> atr_;
};

/// census_a_cost_rollup.tsv -> pooled median two-sided spread ($) per
/// (year, phase), split == "all" and a numeric era only (c_a_cost.py:236).
class PhaseMedianSpreads {
 public:
  [[nodiscard]] static Expected<PhaseMedianSpreads, Refusal> load(const std::string& path,
                                                                  const std::string& asset);
  /// NaN when absent — the caller then drops the spread floor term entirely.
  [[nodiscard]] double median_usd(std::int32_t year, std::size_t phase) const;

 private:
  std::map<std::pair<std::int32_t, std::uint8_t>, double> med_;
};

/// Shared TSV reader: '#' comment lines skipped, first surviving line is the
/// header, fields split on TAB. Empty cell -> NaN for numeric access.
class Tsv {
 public:
  [[nodiscard]] static Expected<Tsv, Refusal> load(const std::string& path);
  [[nodiscard]] std::size_t rows() const { return rows_.size(); }
  /// Column index by name, or -1.
  [[nodiscard]] std::int64_t column(const std::string& name) const;
  [[nodiscard]] const std::string& cell(std::size_t row, std::int64_t col) const;
  /// strtod of the cell; NaN on an empty or unparseable cell.
  [[nodiscard]] double number(std::size_t row, std::int64_t col) const;

 private:
  std::vector<std::string> header_;
  std::vector<std::vector<std::string>> rows_;
  std::string empty_;
};

/// "YYYY-MM-DD" -> YYYYMMDD; 0 when the text is not a date.
[[nodiscard]] std::int32_t date8_of_iso(const std::string& iso);

}  // namespace qr::gen

#endif  // QR_GEN_TABLES_HPP
