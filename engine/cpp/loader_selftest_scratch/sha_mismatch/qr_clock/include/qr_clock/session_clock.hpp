// qr_clock/session_clock.hpp — THE ONE CLOCK BOUNDARY.
//
// SPEC: design/DESIGN_SUBSTRATE.md section 6 —
//   "`qr_clock` (six-condition SessionClock port; **WCD fix = totalize, don't
//    catch**: total classifier `classify_attach(ts_b, clock) → {MISSING,
//    MALFORMED, WRONG_CIVIL_DAY(delta_days), ON_DAY(FrameA)}` with no error
//    path; conversion only in ON_DAY; print retained; ... census carries
//    delta_days histogram; note the same latent `?`-abort shape exists in
//    production reader.rs:1173 — the port must not copy it)"
// SPEC: design/DESIGN_SUBSTRATE.md APPENDIX C2 —
//   "`SessionClock::for_day(registry, civil_date)`; `contains_b`;
//    `to_frame_a` (six conditions, offset re-derived from RESULT);
//    `classify_attach()` total (no error path; section 6);
//    `convert_sequence` (output re-checked monotone)."
// Port reference (read-only, semantics-exact):
//   /workspace/engine/crates/corpus/src/session_clock.rs
//
// WHY THIS TYPE EXISTS: every token corpus timestamp is naive-Eastern wall
// clock (frame B); the entry cutoffs are true UTC (frame A). Both are i64
// nanoseconds, so a bare-integer comparison type-checks and silently moves
// every fill 4-5 hours into the FUTURE of its own decision instant. This is
// the ONLY lawful producer of a frame-A instant from tape.
//
// THE REGISTRY IS THE SOLE CLOCK AUTHORITY. There is no DST table here and
// there never will be one: the authenticated registry row already carries the
// true-UTC image of the same 09:30 ET anchor (session_start_ns), so the whole
// conversion is
//
//     ts_A = session_start_ns + (ts_B - open_B)
//
// exact, checked, and incapable of disagreeing with the registry.
//
// expected_bar_count IS READ FROM THE SESSION'S OWN ROW, never from a caller:
// nine pinned sessions are 210-bar early closes and a 390-bar window on one of
// them admits 180 minutes of post-close tape as decision-time quotes.
//
// THE SIX FAIL-CLOSED CONDITIONS (session_clock.rs:41-57). Each one is a
// REFUSAL and never a range-limited substitute: ci/check_banned_constructs.sh
// greps this module for range-limiting helpers precisely because twice in this
// rebuild such a helper turned the target defect into silence:
//
//   1. the clock's day is the requested day            (convert_sequence)
//   2. session_end - session_start == expected_bar_count * BAR_NS
//                                                      (construction)
//   3. every retained ts_B is in the half-open frame-B session window
//                                                      (to_frame_a)
//   4. every converted ts_A is in [session_start, session_end)
//                                                      (to_frame_a)
//   5. ts_A - session_start == ts_B - open_B exactly, under CHECKED integer
//      arithmetic, RE-DERIVED FROM THE RESULT              (to_frame_a)
//   6. conversion preserves row count, input order, and OUTPUT order — the
//      output monotonicity re-checked on the output rather than inferred
//      from the input                                   (convert_sequence)
#ifndef QR_CLOCK_SESSION_CLOCK_HPP
#define QR_CLOCK_SESSION_CLOCK_HPP

#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "qr_core/frames.hpp"
#include "qr_core/refusal.hpp"
#include "qr_registry/registry.hpp"

namespace qr {

/// Nanoseconds per millisecond — the raw tape is stamped in ms
/// (session_clock.rs:65).
inline constexpr std::int64_t kNanosecondsPerMillisecond = 1'000'000;
/// Nanoseconds per microsecond (session_clock.rs:67).
inline constexpr std::int64_t kNanosecondsPerMicrosecond = 1'000;
/// Milliseconds in one civil day (session_clock.rs:69).
inline constexpr std::int64_t kMillisecondsPerDay = 86'400'000;
/// Nanoseconds in one civil day (session_clock.rs:71).
inline constexpr std::int64_t kNanosecondsPerDay = kMillisecondsPerDay * kNanosecondsPerMillisecond;
/// 09:30 local ET as an offset from local midnight, in milliseconds. The
/// source timestamps are wall-clock milliseconds in that same local
/// convention, so this offset is DST-free BY CONSTRUCTION — which is exactly
/// why frame B needs no timezone table (session_clock.rs:72-76).
inline constexpr std::int64_t kWallOpenOffsetMs = 9 * 3'600'000 + 30 * 60'000;

// ---------------------------------------------------------------------------
// The totalized attachment classifier's result type.
// ---------------------------------------------------------------------------

/// The FOUR — and only four — outcomes of `classify_attach`. There is no
/// error variant by design: "WCD fix = totalize, don't catch". A wrong-civil-
/// day attachment is a TYPED STATE that the run carries forward, never a `?`
/// that aborts a 12-hour pass (the latent shape at reader.rs:1173, which this
/// port does not copy).
enum class AttachKind : std::uint8_t {
  /// The source carried no attachment timestamp at all (a null def-level).
  MISSING = 0,
  /// The attachment timestamp cannot be made into a lawful frame-B instant:
  /// its own arithmetic refuses (i64 overflow). The totalized image of the
  /// reference port's ArithmeticOverflow branch.
  MALFORMED = 1,
  /// A well-formed instant on a DIFFERENT civil day than this clock's, and by
  /// exactly how many days (signed; census carries the delta_days histogram).
  WRONG_CIVIL_DAY = 2,
  /// On this clock's civil day. THE ONLY BRANCH THAT CONVERTS.
  ON_DAY = 3,
};

/// Stable screaming-snake name of an attach kind (never a sentence).
[[nodiscard]] const char* attach_kind_name(AttachKind kind) noexcept;

/// WP8 MASKING MAP (orchestrator ruling, 2026-08-10) — the carriers mask their
/// 14 quote-dependent channels from this classification:
///
///   MISSING          -> Validity::MISSING
///   MALFORMED        -> Validity::MALFORMED   (the fifteenth state; a
///                       malformed datum is its own census category and never
///                       collapses into MISSING or CLOCK_UNAVAILABLE)
///   WRONG_CIVIL_DAY  -> Validity::WRONG_CIVIL_DAY  (delta_days to the census)
///   ON_DAY           -> Validity::VALID
///
/// The map itself lands with the carriers in WP8, not here: this module types
/// the attachment and converts it, and masks nothing.

/// The classifier's total result: a kind plus exactly the payload that kind
/// carries. Reading a payload the kind does not carry is a programmer-contract
/// violation and fails fast; it is not a silent zero.
class AttachClass {
 public:
  AttachClass() = delete;

  [[nodiscard]] static constexpr AttachClass missing() noexcept {
    return AttachClass(AttachKind::MISSING, 0, std::nullopt);
  }
  [[nodiscard]] static constexpr AttachClass malformed() noexcept {
    return AttachClass(AttachKind::MALFORMED, 0, std::nullopt);
  }
  [[nodiscard]] static constexpr AttachClass wrong_civil_day(std::int64_t delta_days) noexcept {
    return AttachClass(AttachKind::WRONG_CIVIL_DAY, delta_days, std::nullopt);
  }
  [[nodiscard]] static constexpr AttachClass on_day(FrameA ts_a) noexcept {
    return AttachClass(AttachKind::ON_DAY, 0, ts_a);
  }

  [[nodiscard]] constexpr AttachKind kind() const noexcept { return kind_; }
  [[nodiscard]] constexpr bool is_on_day() const noexcept { return kind_ == AttachKind::ON_DAY; }

  /// Signed civil-day difference (attachment day - clock day). Only
  /// WRONG_CIVIL_DAY carries one.
  [[nodiscard]] constexpr std::int64_t delta_days() const {
    if (kind_ != AttachKind::WRONG_CIVIL_DAY) {
      detail::fail_fast("qr::AttachClass::delta_days() on a non-WRONG_CIVIL_DAY class");
    }
    return delta_days_;
  }

  /// The converted frame-A instant. Only ON_DAY carries one.
  [[nodiscard]] constexpr FrameA frame_a() const {
    if (kind_ != AttachKind::ON_DAY || !ts_a_.has_value()) {
      detail::fail_fast("qr::AttachClass::frame_a() on a non-ON_DAY class");
    }
    return *ts_a_;
  }

  friend constexpr bool operator==(const AttachClass& lhs, const AttachClass& rhs) noexcept {
    return lhs.kind_ == rhs.kind_ && lhs.delta_days_ == rhs.delta_days_ && lhs.ts_a_ == rhs.ts_a_;
  }

 private:
  constexpr AttachClass(AttachKind kind, std::int64_t delta_days,
                        std::optional<FrameA> ts_a) noexcept
      : kind_(kind), delta_days_(delta_days), ts_a_(ts_a) {}

  AttachKind kind_;
  std::int64_t delta_days_;
  std::optional<FrameA> ts_a_;
};

// ---------------------------------------------------------------------------
// The clock.
// ---------------------------------------------------------------------------

/// The typed clock of ONE authenticated registry session.
class SessionClock {
 public:
  SessionClock() = delete;

  /// APPENDIX C2 entry point: builds the clock for one civil day from the
  /// frozen registry. UNKNOWN_SESSION if the day has no row; CLOCK_VIOLATION
  /// if that row's own span disagrees with its expected_bar_count (condition
  /// 2); ARITHMETIC_OVERFLOW if the frame-B window does not fit i64.
  [[nodiscard]] static Expected<SessionClock, Refusal> for_day(const Registry& registry,
                                                               CivilDate civil_date);

  /// Builds the clock from an already-looked-up registry row (the port of
  /// `SessionClock::from_entry`). Condition 2 is enforced HERE, so a caller
  /// holding a hand-corrupted row cannot build a clock from it.
  [[nodiscard]] static Expected<SessionClock, Refusal> from_session(const Session& session);

  /// The internal state of a clock, exposed for ONE purpose: see
  /// `without_construction_gate` below.
  struct Fields {
    std::string day;
    CivilDate civil_date;
    std::int64_t expected_bar_count;
    std::int64_t session_start_ns;
    std::int64_t session_end_ns;
    std::int64_t open_b_ns;
    std::int64_t close_b_ns;
    std::int64_t offset_ns;
  };

  /// TEST-ONLY escape hatch, mirroring `Registry::parse_without_digest_gate`:
  /// builds a clock from raw fields WITHOUT the construction gate, so that
  /// boundary conditions 4 and 5 — which exact arithmetic makes unreachable
  /// from any valid registry row — can be fired by a counterfixture instead of
  /// only by a source mutant. No production entry point calls this; every
  /// other constructor gates first.
  [[nodiscard]] static SessionClock without_construction_gate(Fields fields);

  /// This clock's own fields (the inverse of `without_construction_gate`).
  [[nodiscard]] Fields fields() const;

  [[nodiscard]] std::string_view day() const noexcept { return day_; }
  [[nodiscard]] CivilDate civil_date() const noexcept { return civil_date_; }

  /// The session's bar count, read from ITS OWN registry row — 390 on 994
  /// sessions, 210 on the nine early closes.
  [[nodiscard]] std::int64_t expected_bar_count() const noexcept { return expected_bar_count_; }

  /// Frame-B 09:30 ET open.
  [[nodiscard]] FrameB open_b() const noexcept { return FrameB{open_b_ns_}; }
  /// Frame-B official close: open_b + expected_bar_count * BAR_NS.
  [[nodiscard]] FrameB close_b() const noexcept { return FrameB{close_b_ns_}; }
  /// Frame-A session start (the registry's true-UTC image of open_b).
  [[nodiscard]] FrameA session_start_a() const noexcept {
    return FrameA::from_published_utc_epoch_ns(session_start_ns_);
  }
  /// Frame-A session end (exclusive).
  [[nodiscard]] FrameA session_end_a() const noexcept {
    return FrameA::from_published_utc_epoch_ns(session_end_ns_);
  }
  /// session_start_a - open_b, derived once under checked arithmetic at
  /// construction. This is the registry's DST image, not a computed offset.
  [[nodiscard]] std::int64_t offset_ns() const noexcept { return offset_ns_; }

  /// Whether ts_b is inside the half-open frame-B RTH window — the
  /// premarket/postmarket filter, applied in FRAME B before any conversion.
  [[nodiscard]] bool contains_b(FrameB ts_b) const noexcept {
    return ts_b.ns() >= open_b_ns_ && ts_b.ns() < close_b_ns_;
  }
  /// Whether ts_a is inside [session_start, session_end).
  [[nodiscard]] bool contains_a(FrameA ts_a) const noexcept {
    return ts_a.ns() >= session_start_ns_ && ts_a.ns() < session_end_ns_;
  }

  /// Converts a frame-B instant on this clock's authenticated civil day.
  /// WRONG_CIVIL_DAY off-day; ARITHMETIC_OVERFLOW if the sum does not fit.
  /// Deliberately has no RTH filter.
  [[nodiscard]] Expected<FrameA, Refusal> to_frame_a_same_civil_day(FrameB ts_b) const noexcept;

  /// **THE SOLE RTH CONVERSION**: same-civil-day conversion (WRONG_CIVIL_DAY),
  /// then boundary conditions 3, 4 and 5 in that order.
  [[nodiscard]] Expected<FrameA, Refusal> to_frame_a(FrameB ts_b) const noexcept;

  /// Converts a whole retained tape, enforcing ALL SIX conditions: 1 against
  /// `requested_day`, 2 already at construction, 3-5 per row, and 6 as row
  /// count + input order + OUTPUT order re-checked on the output.
  [[nodiscard]] Expected<std::vector<FrameA>, Refusal> convert_sequence(
      CivilDate requested_day, std::span<const FrameB> tape_b) const;

  /// **THE TOTAL CLASSIFIER** (section 6). Four outcomes, no error path, no
  /// abort: an absent attachment is MISSING, an attachment whose own
  /// arithmetic refuses is MALFORMED, an off-day attachment is
  /// WRONG_CIVIL_DAY(delta_days), and ONLY an on-day attachment converts.
  /// The offset-equality post-condition is checked on the ON_DAY result.
  [[nodiscard]] AttachClass classify_attach(std::optional<FrameB> ts_b) const noexcept;

  /// The raw-tape door: the corpora stamp attachment timestamps in
  /// milliseconds, and the ms->ns widening is itself checked. An overflowing
  /// stamp is MALFORMED — the totalized image of `FrameB::from_naive_et_ms`'s
  /// ArithmeticOverflow (session_clock.rs:309-313).
  [[nodiscard]] AttachClass classify_attach_ms(std::optional<std::int64_t> ts_ms) const noexcept;

 private:
  SessionClock(std::string day, CivilDate civil_date, std::int64_t expected_bar_count,
               std::int64_t session_start_ns, std::int64_t session_end_ns, std::int64_t open_b_ns,
               std::int64_t close_b_ns, std::int64_t offset_ns)
      : day_(std::move(day)),
        civil_date_(civil_date),
        expected_bar_count_(expected_bar_count),
        session_start_ns_(session_start_ns),
        session_end_ns_(session_end_ns),
        open_b_ns_(open_b_ns),
        close_b_ns_(close_b_ns),
        offset_ns_(offset_ns) {}

  std::string day_;
  CivilDate civil_date_;
  std::int64_t expected_bar_count_;
  std::int64_t session_start_ns_;
  std::int64_t session_end_ns_;
  std::int64_t open_b_ns_;
  std::int64_t close_b_ns_;
  std::int64_t offset_ns_;
};

/// APPENDIX C2 spells the classifier as a free function over (ts_b, clock);
/// it is the member above, named exactly as the design names it.
[[nodiscard]] inline AttachClass classify_attach(std::optional<FrameB> ts_b,
                                                 const SessionClock& clock) noexcept {
  return clock.classify_attach(ts_b);
}

/// Frame-B nanoseconds of a naive-ET millisecond stamp, or ARITHMETIC_OVERFLOW
/// (the port of `FrameB::from_naive_et_ms`). The refusing form; the totalizing
/// form is `SessionClock::classify_attach_ms`.
[[nodiscard]] Expected<FrameB, Refusal> frame_b_from_naive_et_ms(std::int64_t ms) noexcept;

/// Days since 1970-01-01 of the civil day a naive-ET instant falls on. Exact
/// floor division: a pre-epoch instant lands on the day it is actually on, not
/// on the one truncation-toward-zero would name.
[[nodiscard]] std::int64_t civil_day_of_naive_et_ns(std::int64_t ns) noexcept;

/// Boundary condition 6c as a NAMED PRIMITIVE, so the guard is directly
/// testable on a hand-built tape: `convert_sequence` calls exactly this on its
/// OUTPUT rather than inferring order from the input's monotonicity. Returns
/// the row count, or CLOCK_VIOLATION carrying the index of the first descent.
[[nodiscard]] Expected<std::size_t, Refusal> refuse_unless_non_decreasing(
    std::span<const FrameA> tape_a) noexcept;

}  // namespace qr

#endif  // QR_CLOCK_SESSION_CLOCK_HPP
