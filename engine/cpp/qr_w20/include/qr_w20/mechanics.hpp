// qr_w20/mechanics.hpp — W2.0 STREAM MECHANICS CENSUSES (option prints D3,
// option quotes D4).
//
// SPEC (FINAL_PLAN section 10, verbatim): "**W2.0 Stream Mechanics Dossiers**
// (5 dossiers, census-driven, ~1 session; idea seeds: NBBO queue decomposition
// executed-vs-cancelled, quote flicker/lifetime, inside-venue ownership, dealer
// requote latency after underlying moves, strike-ladder coverage thinning,
// bid/ask width as dealer risk appetite, term/skew demand shifts, round-number
// behavior)."
// SPEC (FINAL_PLAN section 10, derivation protocol, verbatim): "no family
// registers without a mechanism dossier: (1) who trades on this tape and how
// execution works ...; (2) what state each participant necessarily leaves in
// OUR columns (censuses first); (3) lawful strictly-prior construction; ..."
// SPEC (APPENDIX B3/B4): the projected columns and the HARD-REFUSED set. This
// module reads NOTHING the readers do not already project — it consumes
// `qr::sources::OptionPrintRow` / `OptionQuoteRow`, so a forbidden column is
// unreachable from here by construction, not by convention.
//
// THIS MODULE MEASURES. IT DOES NOT DESIGN.
// Every bin edge below is a DESCRIPTIVE census edge chosen to make a
// distribution readable at day/percent resolution. None of them is a feature
// bucket: A2's "5-moneyness x 3-DTE" edges are not stated in the cited spec,
// and inventing them here is exactly what the implementer stop rule forbids.
// The censuses exist so the orchestrator can choose those edges FROM MEASURED
// DEMAND rather than from habit.
//
// EXACTNESS. Every statistic is an exact integer count. Quantiles come from
// dense exact counters over a declared domain plus an explicitly reported
// overflow count, never from sampling, sorting or interpolation. Two runs of
// this module over the same bytes emit the same bytes: all iteration is over
// ordered containers and vectors, and no wall-clock value ever enters a census
// row.
//
// STRICTLY-PRIOR SPOT. The spot series is the program's own 1s midpoint grid
// (task card section 4 / APPENDIX C4 `grid_1s`), whose endpoint value is by
// construction the last eligible NBBO midpoint STRICTLY BEFORE that endpoint.
// A row at instant t is read against the endpoint `floor(t - open)` seconds,
// i.e. the last complete-second endpoint at or before t, so no census value
// ever sees a quote at or after its own row's instant.
#ifndef QR_W20_MECHANICS_HPP
#define QR_W20_MECHANICS_HPP

#include <cstdint>
#include <filesystem>
#include <map>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/option_quotes.hpp"

namespace qr::w20 {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;

// ---------------------------------------------------------------------------
// Exact counting.
// ---------------------------------------------------------------------------

/// An EXACT dense counter over the closed integer domain
/// `[base, base + span)`, plus separate under/over counts and the true
/// extremes. Quantiles are read off the dense counts, so they are exact
/// whenever the quantile falls inside the domain; when it falls outside, the
/// counter says so rather than inventing a value.
class DenseCounter {
 public:
  DenseCounter() = default;
  DenseCounter(std::int64_t base, std::int64_t span);

  void add(std::int64_t value) noexcept { add_weighted(value, 1); }
  /// Adds `weight` observations of `value` at once — the volume-weighted
  /// demand censuses need it and a per-contract loop would be the same number
  /// with a worse constant. A non-positive weight adds nothing.
  void add_weighted(std::int64_t value, std::int64_t weight) noexcept;

  [[nodiscard]] std::int64_t total() const noexcept { return total_; }
  /// True when some addition could not be represented in int64. NOTHING is
  /// wrapped or saturated when that happens: the offending weight is simply not
  /// counted and the census says so, because a wrapped count is a lie and a
  /// clamped count is a different lie.
  [[nodiscard]] bool counts_overflowed() const noexcept { return counts_overflowed_; }
  [[nodiscard]] std::int64_t under() const noexcept { return under_; }
  [[nodiscard]] std::int64_t over() const noexcept { return over_; }
  [[nodiscard]] std::int64_t min() const noexcept { return min_; }
  [[nodiscard]] std::int64_t max() const noexcept { return max_; }
  /// Exact sum of every added value (unclamped); refuses on i64 overflow.
  [[nodiscard]] Expected<std::int64_t, Refusal> sum() const noexcept;
  [[nodiscard]] std::int64_t count_at(std::int64_t value) const noexcept;
  /// Count of added values `<= value` (exact for every value; the under/over
  /// buckets are counted whole).
  [[nodiscard]] std::int64_t count_le(std::int64_t value) const noexcept;

  /// The smallest domain value v with `count(<= v) >= ceil(q_num/q_den * n)`.
  /// `out_of_domain` is set when the quantile lies in the under/over tail, in
  /// which case the returned value is the domain edge it fell past.
  [[nodiscard]] std::int64_t quantile(std::int64_t q_num, std::int64_t q_den,
                                      bool& out_of_domain) const noexcept;

  [[nodiscard]] std::int64_t base() const noexcept { return base_; }
  [[nodiscard]] std::int64_t span() const noexcept { return static_cast<std::int64_t>(counts_.size()); }

 private:
  std::vector<std::int64_t> counts_;
  std::int64_t base_ = 0;
  std::int64_t total_ = 0;
  std::int64_t under_ = 0;
  std::int64_t over_ = 0;
  std::int64_t min_ = 0;
  std::int64_t max_ = 0;
  std::int64_t sum_ = 0;
  bool sum_overflowed_ = false;
  bool counts_overflowed_ = false;
  bool seen_ = false;
};

// ---------------------------------------------------------------------------
// The census report: an ordered, deterministic (scope, key, metric, value) TSV.
// ---------------------------------------------------------------------------

/// One census row. Emission order is INSERTION order, and every producer below
/// emits in a fixed program order, so two runs are byte-identical.
struct CensusRow {
  std::string scope;
  std::string key;
  std::string metric;
  std::int64_t value = 0;
  std::string text;
  bool is_text = false;
};

class CensusReport {
 public:
  void metric(std::string scope, std::string key, std::string metric_name, std::int64_t value);
  void text(std::string scope, std::string key, std::string metric_name, std::string value);
  /// Emits the standard distribution block of `counter`: n, min, max, sum,
  /// under, over and the deciles + p95/p99. A quantile that falls outside the
  /// dense domain is emitted with the `_out_of_domain` companion set to 1.
  void distribution(const std::string& scope, const std::string& key, const DenseCounter& counter);
  /// Emits every occupied dense cell of `counter` as its own row (the full
  /// histogram, for the small-domain counters the dossier reads directly).
  void histogram(const std::string& scope, const std::string& key, const DenseCounter& counter);

  [[nodiscard]] const std::vector<CensusRow>& rows() const noexcept { return rows_; }
  [[nodiscard]] Expected<std::monostate, Refusal> write(const std::filesystem::path& path) const;
  void print() const;

 private:
  std::vector<CensusRow> rows_;
};

// ---------------------------------------------------------------------------
// Coverage and dialect (footer-only).
// ---------------------------------------------------------------------------

/// How this corpus stores one registered session of one modality.
enum class Era : std::uint8_t {
  /// No payload at all: `Validity::MODALITY_ABSENT` for the whole session.
  ABSENT = 0,
  /// `<root>/<YYYY>/<day>.parquet`.
  FLAT = 1,
  /// `<root>/<YYYY>/<day>/exp<YYYY-MM-DD>.parquet`, one file per expiry.
  SHARD = 2,
};

[[nodiscard]] const char* era_name(Era era) noexcept;

struct CoverageRow {
  std::int64_t ordinal = 0;
  std::string day;
  Era era = Era::ABSENT;
  std::int64_t shard_count = 0;
  std::int64_t bytes = 0;
};

/// Coverage of ONE admitted session. The scope wall fires first: this function
/// takes a `DayScope`, which only `DayScope::admit` can produce, so no
/// out-of-scope ordinal ever reaches the filesystem.
[[nodiscard]] Expected<CoverageRow, Refusal> coverage_of(const DayScope& scope,
                                                         const std::filesystem::path& corpus_root);

/// The eight projected option-quote column forms of one file, read from the
/// FOOTER only (no page is decoded).
struct DialectRow {
  std::int64_t ordinal = 0;
  std::string day;
  std::string shard;
  std::int64_t file_rows = 0;
  std::int64_t row_groups = 0;
  std::array<std::uint8_t, 8> forms{};
};

[[nodiscard]] Expected<std::vector<DialectRow>, Refusal> option_quote_dialect(
    const DayScope& scope, const std::filesystem::path& corpus_root);

// ---------------------------------------------------------------------------
// The strictly-prior spot series.
// ---------------------------------------------------------------------------

/// The session's own emitted 1s midpoint grid, read back as the census spot
/// series. Column 0 of `features/grid_1s.npy` is the carried midpoint in u6
/// rounded to f4 once at emission; a missing endpoint carries 0, which no valid
/// midpoint can be (the card requires it finite and POSITIVE).
class SpotGrid {
 public:
  /// `tape_side_dir` is `<tapes>/sNNNN/L` (the grid leaf is BOTH_SHARDS scoped,
  /// so either side's copy is the same bytes).
  [[nodiscard]] static Expected<SpotGrid, Refusal> open(
      const std::filesystem::path& tape_side_dir, std::int64_t open_ms_b, std::int64_t bar_count);

  /// The midpoint at the last complete-second endpoint at or before `ts_ms_b`,
  /// in u6. Zero means absent (before the session's first eligible quote, or a
  /// timestamp outside the grid).
  [[nodiscard]] std::int64_t mid_u6_at(std::int64_t ts_ms_b) const noexcept;
  /// Endpoint `index`'s midpoint in u6; zero means absent.
  [[nodiscard]] std::int64_t mid_u6_endpoint(std::int64_t index) const noexcept;
  [[nodiscard]] std::int64_t endpoints() const noexcept {
    return static_cast<std::int64_t>(mid_u6_.size());
  }
  [[nodiscard]] std::int64_t present_endpoints() const noexcept { return present_; }
  /// Endpoint indices where the grid moved by at least half a basis point —
  /// A2's spot-move event ("spot-move event = |Delta mid| >= 0.5bps").
  [[nodiscard]] const std::vector<std::int64_t>& move_endpoints() const noexcept {
    return move_endpoints_;
  }

 private:
  std::vector<std::int64_t> mid_u6_;
  std::vector<std::int64_t> move_endpoints_;
  std::int64_t open_ms_b_ = 0;
  std::int64_t present_ = 0;
};

// ---------------------------------------------------------------------------
// D4 — option-quote mechanics.
// ---------------------------------------------------------------------------

/// A contract identity as the option-quote tape carries it.
struct ContractKey {
  std::int32_t expiration_day = 0;
  std::int64_t strike_u6 = 0;
  std::uint8_t right = 0;

  friend bool operator<(const ContractKey& left, const ContractKey& right) noexcept {
    if (left.expiration_day != right.expiration_day) {
      return left.expiration_day < right.expiration_day;
    }
    if (left.strike_u6 != right.strike_u6) return left.strike_u6 < right.strike_u6;
    return left.right < right.right;
  }
};

/// How many concurrent spot-move events the requote tracker follows. Events sit
/// on the 1s grid and are followed for at most 5s (A2's "no-requote-5s
/// fraction"), so at most six can ever be open at once; the eighth slot exists
/// so that "dropped" is provably always zero rather than assumed.
inline constexpr std::size_t kRequoteSlots = 8;
inline constexpr std::int64_t kRequoteHorizonMs = 5000;
/// A contract counts as LIVE for an event if it quoted inside the 60s strictly
/// before the event. (Census definition; A2's channel is bucket-scoped and its
/// bucket edges are not in the cited spec.)
inline constexpr std::int64_t kLiveWindowMs = 60000;

struct OptionQuoteMechanicsCensus {
  std::int64_t ordinal = 0;
  std::string day;
  Era era = Era::ABSENT;
  std::int64_t shard_count = 0;

  // --- stream shape ---
  std::int64_t rth_rows = 0;
  std::int64_t groups = 0;
  std::int64_t skipped_null_rows = 0;
  std::int64_t decoded_values = 0;
  std::int64_t contracts = 0;
  std::int64_t expirations = 0;
  std::int64_t calls = 0;
  std::int64_t puts = 0;
  std::int64_t other_right = 0;
  std::int64_t null_field_rows = 0;

  // --- two-sidedness and width (dealer risk appetite) ---
  std::int64_t two_sided_positive = 0;
  std::int64_t zero_bid = 0;
  std::int64_t zero_ask = 0;
  std::int64_t crossed = 0;
  std::int64_t locked = 0;
  std::int64_t spot_absent_rows = 0;

  // --- distributions ---
  DenseCounter bid_size;
  DenseCounter ask_size;
  DenseCounter spread_cents;
  DenseCounter spread_bps_of_mid;
  /// (ask_size - bid_size) / (ask_size + bid_size) in bp — the displayed-depth
  /// asymmetry of the two sides, which is what this tape can say about
  /// dealer-side willingness. (A2's own width asymmetry is the STRADDLE width
  /// change, which needs the blocked bucket construction.)
  DenseCounter size_imbalance_bp;
  DenseCounter dte_rows;
  DenseCounter dte_contracts;
  DenseCounter moneyness_bps_rows;
  DenseCounter moneyness_bps_contracts;
  DenseCounter group_size;
  DenseCounter updates_per_second;
  DenseCounter contract_updates;
  DenseCounter contract_gap_ms;

  // --- requote latency after an underlying move ---
  std::int64_t move_events = 0;
  std::int64_t move_events_tracked = 0;
  std::int64_t move_events_dropped = 0;
  std::int64_t move_events_no_live_contract = 0;
  std::int64_t no_requote_5s_half = 0;
  std::int64_t no_requote_5s_any = 0;
  DenseCounter first_requote_ms;
  DenseCounter half_requote_ms;
  DenseCounter live_contracts_at_event;

  // --- coverage thinning (60s samples) ---
  DenseCounter live_two_sided_60s;
  DenseCounter one_sided_fraction_bp;
  DenseCounter median_spread_bps_60s;
  DenseCounter thinning_ratio_bp;
};

/// Runs the D4 census over ONE admitted session. `tape_side_dir` may be empty,
/// in which case every spot-dependent statistic is typed absent rather than
/// computed from a substitute (no proxy spot, ever).
[[nodiscard]] Expected<OptionQuoteMechanicsCensus, Refusal> census_option_quotes(
    const DayScope& scope, const std::filesystem::path& corpus_root,
    const std::filesystem::path& tape_side_dir);

void emit(CensusReport& report, const OptionQuoteMechanicsCensus& census);

// ---------------------------------------------------------------------------
// D3 — option-print mechanics.
// ---------------------------------------------------------------------------

/// The B3 single-leg condition set, exposed for the census's own split.
inline constexpr std::array<std::int64_t, 4> kSingleLegConditions{18, 95, 125, 126};

struct OptionPrintMechanicsCensus {
  std::int64_t ordinal = 0;
  std::string day;

  std::int64_t rth_rows = 0;
  std::int64_t groups = 0;
  std::int64_t skipped_null_rows = 0;
  std::int64_t decoded_values = 0;
  std::int64_t contracts = 0;
  std::int64_t expirations = 0;
  std::int64_t calls = 0;
  std::int64_t puts = 0;
  std::int64_t other_right = 0;

  // --- condition codes (B3: "condition(10) [single-leg in {18,95,125,126}]") ---
  std::map<std::int64_t, std::int64_t> condition_prints;
  std::map<std::int64_t, std::int64_t> condition_volume;
  std::int64_t single_leg_prints = 0;
  std::int64_t single_leg_volume = 0;
  std::int64_t total_volume = 0;
  std::int64_t call_volume = 0;
  std::int64_t put_volume = 0;

  // --- greek / IV availability (B3: "IV/Greeks need BOTH strict-prior attachments") ---
  std::int64_t delta_present = 0;
  std::int64_t gamma_present = 0;
  std::int64_t vanna_present = 0;
  std::int64_t charm_present = 0;
  std::int64_t iv_present = 0;
  std::int64_t delta_finite = 0;
  std::int64_t gamma_finite = 0;
  std::int64_t iv_finite = 0;
  std::int64_t underlying_px_present = 0;
  std::int64_t underlying_ts_present = 0;

  // --- attachment clocks (the ATTACHMENT_FUTURE census) ---
  std::int64_t quote_ts_present = 0;
  std::int64_t quote_ts_strictly_prior = 0;
  std::int64_t quote_ts_equal = 0;
  std::int64_t quote_ts_future = 0;
  DenseCounter quote_attach_age_ms;

  // --- the attached quote block: option-quote state that survives where the
  //     option-quote TAPE is MODALITY_ABSENT ---
  std::int64_t attached_two_sided_positive = 0;
  std::int64_t attached_zero_bid = 0;
  std::int64_t attached_crossed = 0;
  std::int64_t attached_locked = 0;
  DenseCounter attached_spread_cents;
  DenseCounter attached_spread_bps_of_mid;
  DenseCounter attached_bid_size;
  DenseCounter attached_ask_size;

  // --- demand structure ---
  DenseCounter size_prints;
  DenseCounter dte_prints;
  DenseCounter dte_volume;
  DenseCounter moneyness_bps_prints;
  DenseCounter moneyness_bps_volume;
  DenseCounter group_size;
  DenseCounter prints_per_second;
  DenseCounter contract_gap_ms;
  std::int64_t spot_absent_rows = 0;
  std::int64_t aggressor_at_or_above_ask = 0;
  std::int64_t aggressor_at_or_below_bid = 0;
  std::int64_t aggressor_inside = 0;
  std::int64_t aggressor_undecidable = 0;
};

[[nodiscard]] Expected<OptionPrintMechanicsCensus, Refusal> census_option_prints(
    const DayScope& scope, const std::filesystem::path& corpus_root,
    const std::filesystem::path& tape_side_dir);

void emit(CensusReport& report, const OptionPrintMechanicsCensus& census);

}  // namespace qr::w20

#endif  // QR_W20_MECHANICS_HPP
