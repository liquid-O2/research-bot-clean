// qr_carriers/group_vector.hpp — THE REDUCED EQUAL-TIME GROUP VECTOR (69/65/89).
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 4,
// `NATIVE_ORDER`, verbatim):
//
//   "First, for each modality and timestamp group, identity token values plus
//    presence bits are reduced by finite mean and max over **all** equal-time
//    members, concatenate log group multiplicity, then project to a 64d base
//    group embedding once per `(session,side,modality)`."
//
// and section 5's arithmetic, which is the ONLY independent statement of the
// width:
//
//   "For stock print, equal-time mean+max over 17 values+17 masks plus log
//    multiplicity is 69 inputs; NBBO's 16-value analog is 65 and option's
//    22-value analog is 89."
//
// THE PROJECTION IS NOT HERE. The `69->32->64` (etc.) bias-free projections are
// the Python model's parameters; this module emits the REDUCED VECTORS, their
// timestamps and their phase labels, which is exactly what APPENDIX C4 stores
// (`groups_{mod} [G,69|65|89] f4`). Nothing in C++ ever multiplies a learned
// matrix.
//
// THE BLOCK ORDER IS A LANE RULING, REPORTED AS A STOP QUESTION. The card fixes
// the CONTENTS of the 69 and their count; it does not order them inside the
// vector. The order below is frozen here, once, and the projection that reads it
// is bias-free and learned, so the order is a labelling convention rather than a
// scientific claim — but it is still frozen and named so that two builds can
// never disagree:
//
//     [ 0*C, 1*C )  finite mean of each VALUE channel, declared channel order
//     [ 1*C, 2*C )  mean of each PRESENCE bit (the group's present fraction)
//     [ 2*C, 3*C )  finite max of each VALUE channel
//     [ 3*C, 4*C )  max of each PRESENCE bit (any member carried it)
//       4*C         log1p(group multiplicity)
//
// ABSENCE IS EXPRESSED, NOT LOST. The emitted leaf carries values only (C4:
// `[G,69] f4`, no parallel mask plane), and it does not need one: a value
// channel with no finite present member emits the card's "value0/presence0" as
// value 0 in the mean block AND 0 in BOTH mask blocks, so the model can read
// absence off the vector itself. The mask-mean channel is a fraction over the
// group's token count and is therefore always present (its denominator is a
// group multiplicity, which is >=1 by construction).
//
// SIDE-NEUTRAL STORAGE (orchestrator ruling, 2026-08-10). The two sides' reduced
// vectors are not independent data: `sigma = +1` for LONG, so the LONG vector IS
// the unoriented one, and the SHORT vector is a fixed function of it under the
// frozen per-channel orientation table (channels.hpp). The stored table is
// therefore ONE per `(session, modality)`:
//
//     [ 0, 4C+1 )        the unoriented (LONG) reduced vector, verbatim
//     [ 4C+1, 4C+1+S )   the finite MIN of each of the S channels that negate
//
// and the loader derives a side with `orient_group_vector`:
//
//   * INVARIANT channel  -> copied (counts, spreads, gamma, ages, masks, quality);
//   * SIGMA / SIGMA_RHO  -> mean negates, and the SHORT MAX is the NEGATED MIN,
//                           because max(-x) = -min(x) and a max does NOT commute
//                           with negation — that identity is the whole reason
//                           the min block exists;
//   * OWN_OPPOSITE_SWAP  -> the channel takes its declared partner's value AND
//                           its partner's mask, in both the mean and max blocks.
//
// An ABSENT channel stays exactly `+0.0` on both sides rather than becoming
// `-0.0`: the card's word is "value0", and negating a masked cell would emit a
// different bit pattern than the per-side reduction does.
//
// AND EVERY STORED ZERO IS `+0.0` (measured, not assumed). A PRESENT cell can
// also be exactly zero, and then the sign of that zero is NOT reproducible from
// the neutral table: `max` and `min` over a group containing both `+0.0` and
// `-0.0` return whichever the member order reached first (neither compares
// greater), so the per-side max and the negated neutral min can disagree in the
// sign bit alone. Session 125's option prints do exactly this — a CALL and a PUT
// with a zero print-minus-mid in one equal-time group. IEEE says the two are the
// same number and every downstream projection agrees; the emitted BYTES did not.
// `canonical_f4` therefore folds `-0.0` to `+0.0` once, in the one place every
// stored cell passes through, so the reduced tables carry one representation of
// zero and the orientation law is exact.
//
// The saving is measured, not assumed: `4C+1+S` against `2*(4C+1)` is 67/130 for
// NBBO (95.3% of session 125's cells), 74/138 stock print and 101/178 option —
// 51.7% of the per-side pair over the real session.
//
// TWO EXACT DOORS, NEVER ONE APPROXIMATE ONE. Stock prints and option prints
// reduce PER TOKEN, so their means are floating-point sums over the canonically
// ordered members (streams.hpp's permutation-invariance law). The sixteen NBBO
// channels are GROUP-level by the card's own construction ("NBBO prior/current
// midpoint and imbalance are derived only after those scalar means"), so every
// member of an NBBO group carries the same channel vector and its equal-time
// mean+max reduction IS that vector — `reduce_constant_group` writes it
// directly instead of summing k identical doubles and dividing by k, which is
// the same number in exact arithmetic but not always in IEEE-754.
#ifndef QR_CARRIERS_GROUP_VECTOR_HPP
#define QR_CARRIERS_GROUP_VECTOR_HPP

#include <array>
#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

#include "qr_carriers/channels.hpp"
#include "qr_carriers/transforms.hpp"

namespace qr::carriers {

// ---------------------------------------------------------------------------
// The three widths, derived from the three channel counts and static_asserted
// against section 5's own numbers.
// ---------------------------------------------------------------------------

/// `(C values + C masks) * 2 (mean and max) + 1 (log multiplicity)`.
[[nodiscard]] constexpr std::size_t group_vector_dim(std::size_t channels) noexcept {
  return 4 * channels + 1;
}

inline constexpr std::size_t kStockPrintGroupDim = group_vector_dim(kStockPrintChannelCount);
inline constexpr std::size_t kNbboGroupDim = group_vector_dim(kNbboChannelCount);
inline constexpr std::size_t kOptionPrintGroupDim = group_vector_dim(kOptionPrintChannelCount);
/// The widest of the three: the size of a stack scratch buffer that serves any
/// modality without a heap allocation inside the per-group loop.
inline constexpr std::size_t kMaxGroupDim = kOptionPrintGroupDim;

static_assert(kStockPrintGroupDim == 69, "section 5: stock-print group input is 69");
static_assert(kNbboGroupDim == 65, "section 5: NBBO group input is 65");
static_assert(kOptionPrintGroupDim == 89, "section 5: option-print group input is 89");

[[nodiscard]] std::size_t group_vector_dim_of(Modality modality) noexcept;

// ---------------------------------------------------------------------------
// The side-neutral widths and the frozen orientation table (the ruling above).
// ---------------------------------------------------------------------------

/// The declared orientation of one channel of one modality — channels.hpp's own
/// `kStockPrintOrientation` / `kNbboOrientation` / `kOptionPrintOrientation`,
/// reached by modality so the loader table has exactly one source.
[[nodiscard]] OrientKind group_channel_orientation(Modality modality,
                                                    std::size_t channel) noexcept;
/// The own/opposite partner of a channel; the channel itself when it does not
/// swap.
[[nodiscard]] std::size_t group_channel_swap_partner(Modality modality,
                                                      std::size_t channel) noexcept;
/// The channels whose oriented value NEGATES when the side flips (SIGMA and
/// SIGMA_RHO), in declared channel order: the min block's contents.
[[nodiscard]] std::span<const std::size_t> sigma_flip_channels(Modality modality) noexcept;
/// `channel`'s slot inside the min block, or `kNoSigmaSlot` when it does not
/// negate.
inline constexpr std::size_t kNoSigmaSlot = static_cast<std::size_t>(-1);
[[nodiscard]] std::size_t sigma_flip_slot(Modality modality, std::size_t channel) noexcept;

/// How many of a modality's channels negate under a side flip — computed from
/// the frozen orientation table itself, so a channel that changes kind moves
/// this width instead of silently mismatching it.
template <std::size_t N>
[[nodiscard]] constexpr std::size_t sigma_flip_count(
    const std::array<OrientKind, N>& orientation) noexcept {
  std::size_t count = 0;
  for (const OrientKind kind : orientation) {
    if (kind == OrientKind::SIGMA || kind == OrientKind::SIGMA_RHO) {
      ++count;
    }
  }
  return count;
}

inline constexpr std::size_t kStockPrintNeutralDim =
    kStockPrintGroupDim + sigma_flip_count(kStockPrintOrientation);
inline constexpr std::size_t kNbboNeutralDim = kNbboGroupDim + sigma_flip_count(kNbboOrientation);
inline constexpr std::size_t kOptionPrintNeutralDim =
    kOptionPrintGroupDim + sigma_flip_count(kOptionPrintOrientation);
inline constexpr std::size_t kMaxNeutralDim = kOptionPrintNeutralDim;

// The measured widths behind the ruling's arithmetic (74/138, 67/130, 101/178).
static_assert(kStockPrintNeutralDim == 74, "stock print: 69 + 5 negating channels");
static_assert(kNbboNeutralDim == 67, "NBBO: 65 + 2 negating channels");
static_assert(kOptionPrintNeutralDim == 101, "option print: 89 + 12 negating channels");
static_assert(kStockPrintNeutralDim < 2 * kStockPrintGroupDim);
static_assert(kNbboNeutralDim < 2 * kNbboGroupDim);
static_assert(kOptionPrintNeutralDim < 2 * kOptionPrintGroupDim);

/// `4C+1+S`: the unoriented vector plus one min per negating channel.
[[nodiscard]] std::size_t neutral_group_vector_dim_of(Modality modality) noexcept;
/// The first index of the min block — the unoriented vector's own width.
[[nodiscard]] constexpr std::size_t neutral_min_offset(std::size_t channels) noexcept {
  return group_vector_dim(channels);
}
[[nodiscard]] std::string neutral_vector_component_name(Modality modality, std::size_t index);

/// The one representation of zero (see the header note): `-0.0` folds to `+0.0`
/// as a value is narrowed to the emitted f4.
[[nodiscard]] inline float canonical_f4(double value) noexcept {
  return value == 0.0 ? 0.0F : static_cast<float>(value);
}
[[nodiscard]] inline float canonical_f4(float value) noexcept {
  return value == 0.0F ? 0.0F : value;
}

/// THE LOADER'S LAW, in C++ so a fixture can byte-compare it against the
/// per-side reduction rather than take it on trust. `out` receives the
/// `4C+1` reduced vector of `side`.
void orient_group_vector(Modality modality, std::span<const float> neutral, Side side,
                         std::span<float> out) noexcept;

/// The exported orientation leaf, one row per channel:
///   column 0 = `OrientKind`, column 1 = swap partner, column 2 = min slot
///              (`-1` when the channel does not negate).
inline constexpr std::size_t kOrientationLeafColumns = 3;
[[nodiscard]] std::vector<std::int32_t> orientation_leaf(Modality modality);

/// The four block offsets of a `C`-channel modality, in the frozen order above.
[[nodiscard]] constexpr std::size_t group_mean_value_offset(std::size_t) noexcept { return 0; }
[[nodiscard]] constexpr std::size_t group_mean_mask_offset(std::size_t channels) noexcept {
  return channels;
}
[[nodiscard]] constexpr std::size_t group_max_value_offset(std::size_t channels) noexcept {
  return 2 * channels;
}
[[nodiscard]] constexpr std::size_t group_max_mask_offset(std::size_t channels) noexcept {
  return 3 * channels;
}
[[nodiscard]] constexpr std::size_t group_log_multiplicity_offset(std::size_t channels) noexcept {
  return 4 * channels;
}

/// The frozen name of one component of a modality's reduced vector — censuses
/// print them, and a fixture reads them instead of re-deriving an index.
[[nodiscard]] std::string group_vector_component_name(Modality modality, std::size_t index);

// ---------------------------------------------------------------------------
// The two reduction doors.
// ---------------------------------------------------------------------------

/// The PER-TOKEN reducer: one instance per (group, side), fed every member of
/// the equal-timestamp group in the stream's canonical order.
///
/// "All token/group/bin means divide only by the number of finite present
/// members; zero such members emits value0/presence0. Max follows the same
/// eligibility." Both the mean and the max therefore count only VALID cells,
/// and the mask blocks count members rather than cells.
template <std::size_t C>
class GroupReducer {
 public:
  void observe(const ChannelRow<C>& row) noexcept {
    for (std::size_t channel = 0; channel < C; ++channel) {
      if (row.validity[channel] != Validity::VALID) {
        continue;
      }
      const double value = row.value[channel];
      sum_[channel] += value;
      if (present_[channel] == 0 || value > max_[channel]) {
        max_[channel] = value;
      }
      // The MIN is tracked for the side-neutral table only: the reflected side's
      // max is this min negated (see the header's ruling note).
      if (present_[channel] == 0 || value < min_[channel]) {
        min_[channel] = value;
      }
      ++present_[channel];
    }
    ++members_;
  }

  [[nodiscard]] std::int64_t members() const noexcept { return members_; }

  /// Writes the `4*C+1` reduced components. `token_count` is the group's own
  /// multiplicity (the mask-mean denominator) and `log1p_multiplicity` is the
  /// value `GroupRecord` already carries, so the two can never disagree.
  void write(std::int32_t token_count, double log1p_multiplicity,
             std::span<double> out) const noexcept {
    if (out.size() != group_vector_dim(C)) {
      detail::fail_fast("qr::carriers::GroupReducer::write: wrong output width");
    }
    const std::int64_t members = static_cast<std::int64_t>(token_count);
    for (std::size_t channel = 0; channel < C; ++channel) {
      const Typed<double> mean = finite_member_mean(sum_[channel], present_[channel]);
      out[group_mean_value_offset(C) + channel] = mean.v == Validity::VALID ? mean.value : 0.0;
      const Typed<double> mask_mean = fraction(present_[channel], members);
      out[group_mean_mask_offset(C) + channel] =
          mask_mean.v == Validity::VALID ? mask_mean.value : 0.0;
      out[group_max_value_offset(C) + channel] = present_[channel] > 0 ? max_[channel] : 0.0;
      out[group_max_mask_offset(C) + channel] = present_[channel] > 0 ? 1.0 : 0.0;
    }
    out[group_log_multiplicity_offset(C)] = log1p_multiplicity;
  }

  /// The SIDE-NEUTRAL vector: the unoriented (LONG) `4C+1` prefix, then the
  /// finite min of each negating channel, in declared channel order.
  void write_neutral(Modality modality, std::int32_t token_count, double log1p_multiplicity,
                     std::span<double> out) const noexcept {
    const std::span<const std::size_t> flips = sigma_flip_channels(modality);
    if (out.size() != group_vector_dim(C) + flips.size()) {
      detail::fail_fast("qr::carriers::GroupReducer::write_neutral: wrong output width");
    }
    write(token_count, log1p_multiplicity, out.subspan(0, group_vector_dim(C)));
    for (std::size_t slot = 0; slot < flips.size(); ++slot) {
      const std::size_t channel = flips[slot];
      out[neutral_min_offset(C) + slot] = present_[channel] > 0 ? min_[channel] : 0.0;
    }
  }

 private:
  std::array<double, C> sum_{};
  std::array<double, C> max_{};
  std::array<double, C> min_{};
  std::array<std::int64_t, C> present_{};
  std::int64_t members_ = 0;
};

/// The GROUP-LEVEL door (NBBO): every one of the group's `token_count` members
/// carries `row`, so mean == max == the row's own value and the two mask blocks
/// are its presence bit. See the header comment: this is the exact reduction,
/// not an approximation of the per-token one.
template <std::size_t C>
void reduce_constant_group(const ChannelRow<C>& row, double log1p_multiplicity,
                           std::span<double> out) noexcept {
  if (out.size() != group_vector_dim(C)) {
    detail::fail_fast("qr::carriers::reduce_constant_group: wrong output width");
  }
  for (std::size_t channel = 0; channel < C; ++channel) {
    const bool present_bit = row.validity[channel] == Validity::VALID;
    const double value = present_bit ? row.value[channel] : 0.0;
    out[group_mean_value_offset(C) + channel] = value;
    out[group_mean_mask_offset(C) + channel] = present_bit ? 1.0 : 0.0;
    out[group_max_value_offset(C) + channel] = value;
    out[group_max_mask_offset(C) + channel] = present_bit ? 1.0 : 0.0;
  }
  out[group_log_multiplicity_offset(C)] = log1p_multiplicity;
}

/// The group-level door's SIDE-NEUTRAL form: a constant group's min is its own
/// value, exactly as its max is.
template <std::size_t C>
void reduce_constant_group_neutral(Modality modality, const ChannelRow<C>& row,
                                   double log1p_multiplicity, std::span<double> out) noexcept {
  const std::span<const std::size_t> flips = sigma_flip_channels(modality);
  if (out.size() != group_vector_dim(C) + flips.size()) {
    detail::fail_fast("qr::carriers::reduce_constant_group_neutral: wrong output width");
  }
  reduce_constant_group(row, log1p_multiplicity, out.subspan(0, group_vector_dim(C)));
  for (std::size_t slot = 0; slot < flips.size(); ++slot) {
    const std::size_t channel = flips[slot];
    const bool present_bit = row.validity[channel] == Validity::VALID;
    out[neutral_min_offset(C) + slot] = present_bit ? row.value[channel] : 0.0;
  }
}

// ---------------------------------------------------------------------------
// The per-(session, modality) table — APPENDIX C4's `groups_{mod} [G,D]`, now
// stored once for both sides (the ruling in the header).
// ---------------------------------------------------------------------------

/// The reduced vectors of one modality of one session, in group order — either
/// the SIDE-NEUTRAL table (the stored and emitted form) or one side's reduced
/// vectors (the reference form the equivalence fixture compares against).
///
/// STORED AS f4 BECAUSE THAT IS WHAT IS EMITTED (C4: `groups_{mod} [G,69|65|89]
/// f4`). Rounding happens exactly once, here, so the bytes a fixture asserts and
/// the bytes the trainer reads are the same bytes; a double-precision table
/// would additionally cost 731MB per side on session 125's 2.81M NBBO groups.
class GroupVectorTable {
 public:
  /// Which reduction a table holds. NEUTRAL is the stored and emitted form;
  /// LONG/SHORT tables exist so the equivalence fixture and the real-file spot
  /// check have an INDEPENDENTLY built reference to byte-compare against.
  enum class Form : std::uint8_t { NEUTRAL, ORIENTED };

  GroupVectorTable() = default;
  /// A side's reduced-vector table (`4C+1` wide).
  GroupVectorTable(Modality modality, Side side);
  /// The side-neutral table (`4C+1+S` wide).
  explicit GroupVectorTable(Modality modality);

  [[nodiscard]] Modality modality() const noexcept { return modality_; }
  [[nodiscard]] Form form() const noexcept { return form_; }
  /// Meaningful only for an ORIENTED table.
  [[nodiscard]] Side side() const noexcept { return side_; }
  [[nodiscard]] std::size_t dim() const noexcept { return dim_; }
  [[nodiscard]] std::size_t groups() const noexcept {
    return dim_ == 0 ? 0 : values_.size() / dim_;
  }
  /// The whole row-major `[G, D]` buffer — the emitted leaf, verbatim.
  [[nodiscard]] std::span<const float> values() const noexcept { return values_; }
  [[nodiscard]] std::span<const float> row(std::size_t group) const noexcept;

  /// Appends one reduced vector, rounding to f4 exactly once.
  void append(std::span<const double> reduced);
  void reserve(std::size_t groups);

 private:
  std::vector<float> values_;
  std::size_t dim_ = 0;
  Modality modality_ = Modality::STOCK_PRINT;
  Side side_ = Side::LONG;
  Form form_ = Form::ORIENTED;
};

}  // namespace qr::carriers

#endif  // QR_CARRIERS_GROUP_VECTOR_HPP
