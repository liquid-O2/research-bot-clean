// qr_carriers/src/prior_state.cpp — the prior-state machines' arithmetic.
#include "qr_carriers/prior_state.hpp"

namespace qr::carriers {

// ---------------------------------------------------------------------------
// NbboScalars — the three DERIVED quantities, all computed AFTER the means.
// ---------------------------------------------------------------------------

Typed<std::int64_t> NbboScalars::mid() const noexcept {
  const Typed<std::int64_t> bid = bid_u6.mean();
  const Typed<std::int64_t> ask = ask_u6.mean();
  if (bid.v != Validity::VALID || ask.v != Validity::VALID) {
    return Typed<std::int64_t>{0, Validity::MISSING};
  }
  // `midpoint_u6` is WP4's overflow-free form of (bid+ask)/2.
  return Typed<std::int64_t>{qr::sources::midpoint_u6(bid.value, ask.value), Validity::VALID};
}

Typed<std::int64_t> NbboScalars::spread() const noexcept {
  const Typed<std::int64_t> bid = bid_u6.mean();
  const Typed<std::int64_t> ask = ask_u6.mean();
  if (bid.v != Validity::VALID || ask.v != Validity::VALID) {
    return Typed<std::int64_t>{0, Validity::MISSING};
  }
  return Typed<std::int64_t>{ask.value - bid.value, Validity::VALID};
}

Typed<double> NbboScalars::imbalance() const noexcept {
  const Typed<std::int64_t> bid = bid_shares.mean();
  const Typed<std::int64_t> ask = ask_shares.mean();
  if (bid.v != Validity::VALID || ask.v != Validity::VALID) {
    return masked(Validity::MISSING);
  }
  const std::int64_t total = bid.value + ask.value;
  if (total == 0) {
    return masked(Validity::MISSING);
  }
  return present(static_cast<double>(bid.value - ask.value) / static_cast<double>(total));
}

// ---------------------------------------------------------------------------
// OptionContractPrior.
// ---------------------------------------------------------------------------

bool OptionContractPrior::observe_eligible_price(const ContractKey& key, std::int64_t price_u6) {
  return pending_[key].add(price_u6);
}

void OptionContractPrior::commit_group() {
  for (const auto& entry : pending_) {
    const Typed<std::int64_t> mean = entry.second.mean();
    if (mean.v == Validity::VALID) {
      prior_[entry.first] = PriorScalar{true, pending_ts_ns_a_, mean.value};
    }
  }
  pending_.clear();
}

PriorScalar OptionContractPrior::prior(const ContractKey& key) const {
  const auto found = prior_.find(key);
  if (found == prior_.end()) {
    return PriorScalar{};
  }
  return found->second;
}

// ---------------------------------------------------------------------------
// UnderlyingPrior.
// ---------------------------------------------------------------------------

bool UnderlyingPrior::observe_valid(std::int64_t underlying_ts_ns_a,
                                    std::int64_t underlying_u6) noexcept {
  if (!have_best_ || underlying_ts_ns_a > best_ts_ns_a_) {
    have_best_ = true;
    best_ts_ns_a_ = underlying_ts_ns_a;
    pending_.reset();
    return pending_.add(underlying_u6);
  }
  if (underlying_ts_ns_a == best_ts_ns_a_) {
    return pending_.add(underlying_u6);
  }
  // An older attachment than the group's greatest one contributes nothing:
  // "the finite positive mean of only members sharing that timestamp".
  return true;
}

void UnderlyingPrior::commit_group() noexcept {
  const Typed<std::int64_t> mean = pending_.mean();
  if (have_best_ && mean.v == Validity::VALID) {
    prior_ = PriorScalar{true, best_ts_ns_a_, mean.value};
  }
  have_best_ = false;
  best_ts_ns_a_ = 0;
  pending_.reset();
}

// ---------------------------------------------------------------------------
// SequenceQuality.
// ---------------------------------------------------------------------------

Expected<SequenceVerdict, Refusal> SequenceQuality::verdict() const noexcept {
  SequenceVerdict out;
  out.group_sequence_valid = have_current_;
  if (!have_current_ || !previous_present_) {
    // "The first sequence-valid group and groups with no finite sequence have
    // all three missing."
    return out;
  }
  const auto gap = checked_sub(current_min_, previous_max_);
  if (!gap.has_value()) {
    return Expected<SequenceVerdict, Refusal>::refuse(gap.error());
  }
  out.pair_formed = true;
  out.gap = gap.value();
  out.monotone = gap.value() >= 0;
  out.inversion = gap.value() < 0;
  return out;
}

// ---------------------------------------------------------------------------
// GroupInterarrival.
// ---------------------------------------------------------------------------

Expected<std::optional<std::int64_t>, Refusal> GroupInterarrival::micros_before(
    std::int64_t group_ts_ns_a) const noexcept {
  if (!previous_present_) {
    return std::optional<std::int64_t>{};
  }
  const auto micros = duration_micros(previous_ts_ns_a_, group_ts_ns_a);
  if (!micros.has_value()) {
    return Expected<std::optional<std::int64_t>, Refusal>::refuse(micros.error());
  }
  return std::optional<std::int64_t>{micros.value()};
}

}  // namespace qr::carriers
