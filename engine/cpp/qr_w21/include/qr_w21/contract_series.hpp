// qr_w21/contract_series.hpp — PER-CONTRACT OPTION-QUOTE EMISSION.
//
// SPEC: design/D020_SCALE_PROTOCOL.md §ORCH-6.3 ("Per-contract option-quote
// emission mode on qr_w21_dump: second named item, same shape as the residual
// block") and D-037's DATA COMPLETENESS LAW ("the decision sheet must carry ALL
// owned lawful fields at event grain — ... contract-level option quotes ...").
// SPEC (the columns): FINAL_PLAN APPENDIX B4 — "expiration(1), strike(2),
// right(3), ts(4), bid_size(5), bid(7), ask_size(9), ask(11)".
//
// WHY THIS IS NOT A SURFACE READ. `SurfaceBuilder` reduces the option-quote
// tape into 20 moneyness x DTE x right BUCKETS: by construction it holds no
// contract-level price, and Q4 says so as a type ("THERE IS NO PRICE FIELD IN
// THIS STRUCT"). A case pack that wants what ONE named contract's NBBO did
// cannot get it from the surface at any resolution, so this block reads the
// same B4 stream a second, contract-keyed way. Nothing here is a channel and
// nothing here is a feature: it is an EMISSION of retained values.
//
// TWO MODES, ONE PASS.
//   * NAMED CONTRACT — the caller says (expiry, strike_u6, right) and gets that
//     contract's quote series over a closed second range.
//   * DISCOVERY — the caller does not yet know which contract to name, so the
//     top-K most ACTIVE contracts of the window are reported, with the exact
//     `strike_u6` a subsequent named run must pass. Discovery is what makes the
//     named mode usable without guessing a strike.
//
// STRIKES ARE PASSED AS u6 INTEGERS, NEVER AS DECIMAL TEXT. The strike is the
// contract's identity, and a decimal string that has to be parsed back into a
// price is a rounding decision hiding in an interface. Discovery prints the u6
// value; the named mode takes it back unchanged.
//
// CENSUS-STYLE, LIKE THE RESIDUAL BLOCK IT SITS BESIDE: read-only, no
// wall-clock value anywhere in the output, ordered containers only, and every
// ordering total — so two runs of the same arguments are byte-identical.
#ifndef QR_W21_CONTRACT_SERIES_HPP
#define QR_W21_CONTRACT_SERIES_HPP

#include <cstdint>
#include <map>
#include <string>
#include <string_view>
#include <vector>

#include "qr_core/frames.hpp"
#include "qr_core/refusal.hpp"
#include "qr_sources/option_quotes.hpp"

namespace qr::w21 {

using qr::Expected;
using qr::Refusal;

/// The contract identity B4 names: (expiry, strike, right).
struct ContractId {
  /// Expiration as days since the Unix epoch, exactly as the reader emits it.
  std::int32_t expiration_day = 0;
  std::int64_t strike_u6 = 0;
  qr::sources::Right right = qr::sources::Right::Other;

  friend bool operator==(const ContractId& left, const ContractId& right) noexcept {
    return left.expiration_day == right.expiration_day && left.strike_u6 == right.strike_u6 &&
           left.right == right.right;
  }
  /// A TOTAL order, so a `std::map` keyed on it iterates deterministically.
  friend auto operator<=>(const ContractId& left, const ContractId& right) noexcept {
    if (auto cmp = left.expiration_day <=> right.expiration_day; cmp != 0) return cmp;
    if (auto cmp = left.strike_u6 <=> right.strike_u6; cmp != 0) return cmp;
    return static_cast<std::uint8_t>(left.right) <=> static_cast<std::uint8_t>(right.right);
  }
};

/// The identity of the contract a quote row belongs to.
[[nodiscard]] ContractId contract_of(const qr::sources::OptionQuoteRow& row) noexcept;

/// `<YYYY-MM-DD>:<strike_u6>:<C|CALL|P|PUT>`, the one accepted spelling.
///
/// EVERY REJECTION IS TYPED, because a mistyped contract must not silently
/// become a different contract: a malformed day is MALFORMED_CIVIL_DATE, a
/// non-integer or non-positive strike is CONFIG, and a right the frozen token
/// set does not name is CONFIG rather than `Right::Other` (an unnamed right is
/// a caller error here, unlike on the tape where it is a datum).
[[nodiscard]] Expected<ContractId, Refusal> parse_contract_id(std::string_view text);

/// `<YYYY-MM-DD>:<strike_u6>:<CALL|PUT>` — round-trips `parse_contract_id`.
[[nodiscard]] std::string format_contract_id(const ContractId& id);

/// One retained quote of one contract.
struct ContractQuote {
  /// The session second and the millisecond into the session, both from the
  /// session's own frame-B open — the SAME arithmetic the surface uses
  /// (`second = (ts_ms_b - open_ms_b) / 1000`), never a second clock.
  std::int64_t second = 0;
  std::int64_t ms = 0;
  std::int64_t bid_u6 = 0;
  std::int64_t ask_u6 = 0;
  std::int64_t bid_size = 0;
  std::int64_t ask_size = 0;
  /// The reader's own null mask, carried through: an absent side is a mask bit
  /// and the field holds 0, never a sentinel price.
  std::uint16_t null_mask = 0;

  [[nodiscard]] bool is_null(std::size_t slot) const noexcept {
    return (null_mask & static_cast<std::uint16_t>(1U << slot)) != 0;
  }
  /// The true midpoint — computed, never the walled vendor `mid`. Typed absent
  /// (returned as `false`) unless BOTH sides are present.
  [[nodiscard]] bool mid_u6(std::int64_t& out) const noexcept;
};

/// The quote series of ONE named contract over a closed second range.
class ContractSeries {
 public:
  ContractSeries(ContractId id, std::int64_t from_second, std::int64_t to_second) noexcept
      : id_(id), from_second_(from_second), to_second_(to_second) {}

  /// Offers one quote row. It is retained iff it belongs to this contract AND
  /// its second is inside `[from_second, to_second]`. Both tests are counted
  /// separately, so a caller can tell "the contract never quoted in the window"
  /// from "the contract does not exist in this session".
  void observe(std::int64_t second, std::int64_t ms, const qr::sources::OptionQuoteRow& row);

  [[nodiscard]] const ContractId& id() const noexcept { return id_; }
  [[nodiscard]] const std::vector<ContractQuote>& quotes() const noexcept { return quotes_; }
  /// Rows of this contract seen anywhere in the session, window or not.
  [[nodiscard]] std::int64_t session_rows() const noexcept { return session_rows_; }

 private:
  ContractId id_;
  std::int64_t from_second_ = 0;
  std::int64_t to_second_ = 0;
  std::int64_t session_rows_ = 0;
  std::vector<ContractQuote> quotes_;
};

/// One row of the discovery report.
struct ContractActivity {
  ContractId id;
  /// Quote rows of this contract inside the window.
  std::int64_t rows = 0;
  /// Distinct session seconds this contract quoted in, inside the window.
  ///
  /// COUNTED AS SECOND CHANGES, which is exact here and nowhere else: a
  /// contract lives in exactly one shard (shards are per-expiry) and a shard's
  /// tape is non-decreasing in time or the reader refuses it (OUT_OF_ORDER), so
  /// this contract's seconds arrive non-decreasing and a change of second is a
  /// new second. No per-contract second set is kept, because a full-session
  /// window would then cost seconds x contracts of memory.
  std::int64_t seconds_present = 0;
  std::int64_t first_ms = 0;
  std::int64_t last_ms = 0;
};

/// The top-K-most-active discovery census over a closed second range.
class ActivityCensus {
 public:
  ActivityCensus(std::int64_t from_second, std::int64_t to_second) noexcept
      : from_second_(from_second), to_second_(to_second) {}

  void observe(std::int64_t second, std::int64_t ms, const qr::sources::OptionQuoteRow& row);

  /// The `k` most active contracts, ordered by row count DESCENDING and, on a
  /// tie, by contract identity ASCENDING. The tie-break is the identity and
  /// never arrival order, so the report does not depend on how the tape
  /// happened to interleave two equally busy contracts.
  [[nodiscard]] std::vector<ContractActivity> top(std::size_t k) const;

  /// Distinct contracts that quoted inside the window.
  [[nodiscard]] std::int64_t contracts() const noexcept {
    return static_cast<std::int64_t>(seen_.size());
  }
  /// Quote rows inside the window, across all contracts.
  [[nodiscard]] std::int64_t rows() const noexcept { return rows_; }

 private:
  struct Tally {
    ContractActivity activity;
    std::int64_t last_second = 0;
    bool started = false;
  };

  std::int64_t from_second_ = 0;
  std::int64_t to_second_ = 0;
  std::int64_t rows_ = 0;
  std::map<ContractId, Tally> seen_;
};

}  // namespace qr::w21

#endif  // QR_W21_CONTRACT_SERIES_HPP
