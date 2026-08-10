// qr_clock/session_clock.cpp — the six fail-closed conditions, the totalized
// attachment classifier, and nothing else.
//
// Port reference (read-only, semantics-exact):
// /workspace/engine/crates/corpus/src/session_clock.rs
//
// EVERY arithmetic operation on this page goes through qr_core's checked
// helpers. No range-limiting helper appears here and no boundary value ever
// stands in for a true result: ci/check_banned_constructs.sh greps this module
// for exactly that, because twice in this rebuild such a helper turned the
// target defect into silence.
#include "qr_clock/session_clock.hpp"

#include <cstddef>
#include <string>
#include <utility>

#include "qr_core/checked.hpp"

namespace qr {
namespace {

// Greppable refusal sites — one per condition, so a refusal names the exact
// guard that fired without formatting a sentence.
constexpr const char* kSiteConstruct = "qr_clock::SessionClock::from_session";
constexpr const char* kSiteSameCivilDay = "qr_clock::SessionClock::to_frame_a_same_civil_day";
constexpr const char* kSiteCondition3 = "qr_clock::to_frame_a/condition3_frame_b_rth_window";
constexpr const char* kSiteCondition4 = "qr_clock::to_frame_a/condition4_frame_a_session_window";
constexpr const char* kSiteCondition5 = "qr_clock::to_frame_a/condition5_offset_equality";
constexpr const char* kSiteCondition1 = "qr_clock::convert_sequence/condition1_requested_day";
constexpr const char* kSiteCondition6a = "qr_clock::convert_sequence/condition6a_input_order";
constexpr const char* kSiteCondition6b = "qr_clock::convert_sequence/condition6b_row_count";
constexpr const char* kSiteCondition6c = "qr_clock::refuse_unless_non_decreasing";

template <class T>
Expected<T, Refusal> overflow(const char* site, const char* detail, std::int64_t context) noexcept {
  return Expected<T, Refusal>::refuse(
      Refusal(RefusalCode::ARITHMETIC_OVERFLOW, site, detail, context));
}

}  // namespace

const char* attach_kind_name(AttachKind kind) noexcept {
  switch (kind) {
    case AttachKind::MISSING:
      return "MISSING";
    case AttachKind::MALFORMED:
      return "MALFORMED";
    case AttachKind::WRONG_CIVIL_DAY:
      return "WRONG_CIVIL_DAY";
    case AttachKind::ON_DAY:
      return "ON_DAY";
  }
  return "UNKNOWN_ATTACH_KIND";
}

Expected<FrameB, Refusal> frame_b_from_naive_et_ms(std::int64_t ms) noexcept {
  const auto ns = checked_mul(ms, kNanosecondsPerMillisecond);
  if (!ns.has_value()) {
    return overflow<FrameB>("qr_clock::frame_b_from_naive_et_ms",
                            "naive-ET millisecond stamp does not fit i64 nanoseconds", ms);
  }
  return FrameB{ns.value()};
}

std::int64_t civil_day_of_naive_et_ns(std::int64_t ns) noexcept {
  // Exact floor division. kNanosecondsPerDay is a positive constant, so the
  // only i64 division trap (INT64_MIN / -1) cannot arise.
  const std::int64_t quotient = ns / kNanosecondsPerDay;
  const std::int64_t remainder = ns % kNanosecondsPerDay;
  return (remainder < 0) ? quotient - 1 : quotient;
}

Expected<std::size_t, Refusal> refuse_unless_non_decreasing(
    std::span<const FrameA> tape_a) noexcept {
  for (std::size_t index = 1; index < tape_a.size(); ++index) {
    if (tape_a[index - 1].ns() > tape_a[index].ns()) {
      return Expected<std::size_t, Refusal>::refuse(
          Refusal(RefusalCode::CLOCK_VIOLATION, kSiteCondition6c,
                  "converted frame-A tape is not non-decreasing",
                  static_cast<std::int64_t>(index)));
    }
  }
  return tape_a.size();
}

// ---------------------------------------------------------------------------
// Construction — boundary condition 2.
// ---------------------------------------------------------------------------

Expected<SessionClock, Refusal> SessionClock::from_session(const Session& session) {
  // Condition 2, at construction: the row's own span must be exactly
  // expected_bar_count bars. An early close that inherits a 390-bar window
  // admits 180 minutes of post-close tape as decision-time quotes.
  const auto span_ns = checked_sub(session.session_end_ns, session.session_start_ns);
  if (!span_ns.has_value()) {
    return overflow<SessionClock>(kSiteConstruct, "session_end_ns - session_start_ns overflowed",
                                  session.session_end_ns);
  }
  const auto expected_span_ns = checked_mul(session.expected_bar_count, kBarNs);
  if (!expected_span_ns.has_value()) {
    return overflow<SessionClock>(kSiteConstruct, "expected_bar_count * BAR_NS overflowed",
                                  session.expected_bar_count);
  }
  if (span_ns.value() != expected_span_ns.value()) {
    return Expected<SessionClock, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kSiteConstruct,
                "registry session span disagrees with its own expected_bar_count",
                span_ns.value()));
  }

  // The frame-B open, from the session's OWN civil date and the DST-free
  // 09:30 wall convention. There is no timezone table here and never will be.
  const auto midnight_ms = checked_mul(session.civil_date.days_since_epoch(), kMillisecondsPerDay);
  if (!midnight_ms.has_value()) {
    return overflow<SessionClock>(kSiteConstruct, "civil-day midnight in milliseconds overflowed",
                                  session.civil_date.days_since_epoch());
  }
  const auto open_ms = checked_add(midnight_ms.value(), kWallOpenOffsetMs);
  if (!open_ms.has_value()) {
    return overflow<SessionClock>(kSiteConstruct, "09:30 wall open in milliseconds overflowed",
                                  midnight_ms.value());
  }
  const auto open_b_ns = checked_mul(open_ms.value(), kNanosecondsPerMillisecond);
  if (!open_b_ns.has_value()) {
    return overflow<SessionClock>(kSiteConstruct, "09:30 wall open in nanoseconds overflowed",
                                  open_ms.value());
  }
  const auto close_b_ns = checked_add(open_b_ns.value(), expected_span_ns.value());
  if (!close_b_ns.has_value()) {
    return overflow<SessionClock>(kSiteConstruct, "frame-B close overflowed", open_b_ns.value());
  }
  // The registry's own DST image, derived once, checked.
  const auto offset_ns = checked_sub(session.session_start_ns, open_b_ns.value());
  if (!offset_ns.has_value()) {
    return overflow<SessionClock>(kSiteConstruct, "session_start_ns - open_b_ns overflowed",
                                  session.session_start_ns);
  }

  return SessionClock(session.day, session.civil_date, session.expected_bar_count,
                      session.session_start_ns, session.session_end_ns, open_b_ns.value(),
                      close_b_ns.value(), offset_ns.value());
}

Expected<SessionClock, Refusal> SessionClock::for_day(const Registry& registry,
                                                      CivilDate civil_date) {
  const std::string day = civil_date.to_ymd();
  const auto ordinal = registry.ordinal_of_day(day);
  if (!ordinal.has_value()) {
    return Expected<SessionClock, Refusal>::refuse(ordinal.error());
  }
  const auto row = registry.session_at(ordinal.value());
  if (!row.has_value()) {
    return Expected<SessionClock, Refusal>::refuse(row.error());
  }
  return from_session(*row.value());
}

SessionClock SessionClock::without_construction_gate(Fields fields) {
  return SessionClock(std::move(fields.day), fields.civil_date, fields.expected_bar_count,
                      fields.session_start_ns, fields.session_end_ns, fields.open_b_ns,
                      fields.close_b_ns, fields.offset_ns);
}

SessionClock::Fields SessionClock::fields() const {
  return Fields{day_,
                civil_date_,
                expected_bar_count_,
                session_start_ns_,
                session_end_ns_,
                open_b_ns_,
                close_b_ns_,
                offset_ns_};
}

// ---------------------------------------------------------------------------
// Conversion — boundary conditions 3, 4 and 5.
// ---------------------------------------------------------------------------

Expected<FrameA, Refusal> SessionClock::to_frame_a_same_civil_day(FrameB ts_b) const noexcept {
  const auto day_of_ts = civil_day_of_naive_et_ns(ts_b.ns());
  const auto delta_days = checked_sub(day_of_ts, civil_date_.days_since_epoch());
  if (!delta_days.has_value()) {
    return overflow<FrameA>(kSiteSameCivilDay, "civil-day difference overflowed", day_of_ts);
  }
  if (delta_days.value() != 0) {
    return Expected<FrameA, Refusal>::refuse(
        Refusal(RefusalCode::WRONG_CIVIL_DAY, kSiteSameCivilDay,
                "frame-B instant is not on this clock's civil day", delta_days.value()));
  }
  const auto ts_a_ns = checked_add(ts_b.ns(), offset_ns_);
  if (!ts_a_ns.has_value()) {
    return overflow<FrameA>(kSiteSameCivilDay, "ts_B + offset overflowed", ts_b.ns());
  }
  return FrameA::from_published_utc_epoch_ns(ts_a_ns.value());
}

Expected<FrameA, Refusal> SessionClock::to_frame_a(FrameB ts_b) const noexcept {
  const auto converted = to_frame_a_same_civil_day(ts_b);
  if (!converted.has_value()) {
    return converted;
  }
  // Condition 3: the half-open frame-B RTH window, applied in FRAME B.
  if (!contains_b(ts_b)) {
    return Expected<FrameA, Refusal>::refuse(
        Refusal(RefusalCode::OUTSIDE_RTH, kSiteCondition3,
                "frame-B instant is outside the registered [open_b, close_b) window", ts_b.ns()));
  }
  // Condition 4: the frame-A image is inside the frame-A session.
  if (!contains_a(converted.value())) {
    return Expected<FrameA, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kSiteCondition4,
                "converted frame-A instant is outside [session_start, session_end)",
                converted.value().ns()));
  }
  // Condition 5: exact offset equality, RE-DERIVED FROM THE RESULT rather than
  // from the value just added — a transposition, a double conversion or a
  // corrupted cached offset is caught here.
  const auto back_offset_ns = checked_sub(converted.value().ns(), session_start_ns_);
  if (!back_offset_ns.has_value()) {
    return overflow<FrameA>(kSiteCondition5, "ts_A - session_start overflowed",
                            converted.value().ns());
  }
  const auto event_offset_ns = checked_sub(ts_b.ns(), open_b_ns_);
  if (!event_offset_ns.has_value()) {
    return overflow<FrameA>(kSiteCondition5, "ts_B - open_B overflowed", ts_b.ns());
  }
  if (back_offset_ns.value() != event_offset_ns.value()) {
    return Expected<FrameA, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kSiteCondition5,
                "offset equality violated: ts_A - session_start != ts_B - open_B",
                back_offset_ns.value() - event_offset_ns.value()));
  }
  return converted;
}

// ---------------------------------------------------------------------------
// Sequence conversion — boundary conditions 1 and 6.
// ---------------------------------------------------------------------------

Expected<std::vector<FrameA>, Refusal> SessionClock::convert_sequence(
    CivilDate requested_day, std::span<const FrameB> tape_b) const {
  // Condition 1: this clock is the requested day's clock.
  if (requested_day != civil_date_) {
    return Expected<std::vector<FrameA>, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kSiteCondition1,
                "this clock is not the requested day's clock",
                requested_day.delta_days(civil_date_)));
  }
  std::vector<FrameA> out;
  out.reserve(tape_b.size());
  for (std::size_t index = 0; index < tape_b.size(); ++index) {
    // Condition 6a: the frame-B tape must already be non-decreasing. The
    // conversion is monotone, so a violation here is an INPUT defect and
    // refuses rather than being sorted into silence.
    if (index > 0 && tape_b[index - 1].ns() > tape_b[index].ns()) {
      return Expected<std::vector<FrameA>, Refusal>::refuse(
          Refusal(RefusalCode::CLOCK_VIOLATION, kSiteCondition6a,
                  "frame-B tape is not non-decreasing", static_cast<std::int64_t>(index)));
    }
    const auto converted = to_frame_a(tape_b[index]);
    if (!converted.has_value()) {
      return Expected<std::vector<FrameA>, Refusal>::refuse(converted.error());
    }
    out.push_back(converted.value());
  }
  // Condition 6b: row count preserved.
  if (out.size() != tape_b.size()) {
    return Expected<std::vector<FrameA>, Refusal>::refuse(
        Refusal(RefusalCode::CLOCK_VIOLATION, kSiteCondition6b, "conversion changed the row count",
                static_cast<std::int64_t>(out.size())));
  }
  // Condition 6c: order preserved in the CONVERTED tape, re-checked on the
  // output rather than inferred from the input's monotonicity.
  const auto ordered = refuse_unless_non_decreasing(out);
  if (!ordered.has_value()) {
    return Expected<std::vector<FrameA>, Refusal>::refuse(ordered.error());
  }
  return out;
}

// ---------------------------------------------------------------------------
// THE TOTAL CLASSIFIER — "WCD fix = totalize, don't catch".
//
// Four outcomes, no error path, no abort. A wrong-civil-day attachment is a
// typed state the run carries forward and the census counts by delta_days; it
// is NOT a `?` that ends a twelve-hour pass (reader.rs:1173's latent shape,
// deliberately not copied here).
// ---------------------------------------------------------------------------

AttachClass SessionClock::classify_attach(std::optional<FrameB> ts_b) const noexcept {
  if (!ts_b.has_value()) {
    return AttachClass::missing();
  }
  const std::int64_t raw_ns = ts_b->ns();
  const std::int64_t day_of_ts = civil_day_of_naive_et_ns(raw_ns);
  const auto delta_days = checked_sub(day_of_ts, civil_date_.days_since_epoch());
  if (!delta_days.has_value()) {
    return AttachClass::malformed();
  }
  if (delta_days.value() != 0) {
    return AttachClass::wrong_civil_day(delta_days.value());
  }

  // CONVERSION ONLY IN ON_DAY.
  const auto ts_a_ns = checked_add(raw_ns, offset_ns_);
  if (!ts_a_ns.has_value()) {
    return AttachClass::malformed();
  }
  // The offset-equality post-condition, re-derived from the RESULT. Its two
  // arithmetic refusals are data (MALFORMED); an actual INEQUALITY is not
  // reachable from data under exact arithmetic — it means this code is wrong
  // (a transposition or a double conversion), which is a programmer-contract
  // violation and fails closed. It is code, never assert(): it does not
  // disappear under NDEBUG.
  const auto back_offset_ns = checked_sub(ts_a_ns.value(), session_start_ns_);
  const auto event_offset_ns = checked_sub(raw_ns, open_b_ns_);
  if (!back_offset_ns.has_value() || !event_offset_ns.has_value()) {
    return AttachClass::malformed();
  }
  if (back_offset_ns.value() != event_offset_ns.value()) {
    detail::fail_fast("qr_clock::classify_attach offset-equality post-condition violated");
  }
  return AttachClass::on_day(FrameA::from_published_utc_epoch_ns(ts_a_ns.value()));
}

AttachClass SessionClock::classify_attach_ms(std::optional<std::int64_t> ts_ms) const noexcept {
  if (!ts_ms.has_value()) {
    return AttachClass::missing();
  }
  const auto ts_b = frame_b_from_naive_et_ms(*ts_ms);
  if (!ts_b.has_value()) {
    return AttachClass::malformed();
  }
  return classify_attach(ts_b.value());
}

}  // namespace qr
