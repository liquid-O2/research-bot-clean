// qr_carriers/src/normalization.cpp — the TRAIN-only equal-session fit.
#include "qr_carriers/normalization.hpp"

#include <cmath>
#include <cstdio>

#include <openssl/evp.h>

namespace qr::carriers {
namespace {

[[nodiscard]] std::string sha256_hex(std::string_view bytes) {
  unsigned char digest[EVP_MAX_MD_SIZE];
  unsigned int digest_len = 0;
  if (EVP_Digest(bytes.data(), bytes.size(), digest, &digest_len, EVP_sha256(), nullptr) != 1) {
    detail::fail_fast("qr::carriers: OpenSSL EVP_Digest(sha256) failed");
  }
  static constexpr char kHex[] = "0123456789abcdef";
  std::string out;
  out.reserve(static_cast<std::size_t>(digest_len) * 2U);
  for (unsigned int index = 0; index < digest_len; ++index) {
    out.push_back(kHex[digest[index] >> 4U]);
    out.push_back(kHex[digest[index] & 0x0FU]);
  }
  return out;
}

}  // namespace

void SessionMoments::observe(double value) noexcept {
  if (!std::isfinite(value)) {
    return;  // "use only finite present values"
  }
  sum += value;
  sum_squares += value * value;
  ++count;
}

void SessionMoments::observe_typed(double value, Validity validity) noexcept {
  if (validity != Validity::VALID) {
    return;
  }
  observe(value);
}

double SessionMoments::first_moment() const noexcept {
  if (count <= 0) {
    return 0.0;
  }
  return sum / static_cast<double>(count);
}

double SessionMoments::second_moment() const noexcept {
  if (count <= 0) {
    return 0.0;
  }
  return sum_squares / static_cast<double>(count);
}

double FeatureNormalization::apply(double value) const noexcept {
  if (!centered) {
    return value;
  }
  const double standardized = (value - mu) / scale;
  if (standardized < -kNormalizationClip) {
    return -kNormalizationClip;
  }
  if (standardized > kNormalizationClip) {
    return kNormalizationClip;
  }
  return standardized;
}

NormalizationFitter::NormalizationFitter(std::size_t feature_count,
                                         std::span<const std::uint8_t> continuous)
    : feature_count_(feature_count),
      continuous_(continuous.begin(), continuous.end()),
      sum_first_(feature_count, 0.0),
      sum_second_(feature_count, 0.0),
      sessions_(feature_count, 0) {
  if (continuous_.size() != feature_count_) {
    detail::fail_fast("qr::carriers::NormalizationFitter: continuous mask has the wrong width");
  }
}

Expected<bool, Refusal> NormalizationFitter::observe_session(
    std::span<const SessionMoments> moments) {
  if (moments.size() != feature_count_) {
    return Expected<bool, Refusal>::refuse(
        Refusal(RefusalCode::CONTENT_MISMATCH, "qr_carriers::NormalizationFitter::observe_session",
                "a session's moment vector has the wrong width",
                static_cast<std::int64_t>(moments.size())));
  }
  ++sessions_observed_;
  for (std::size_t index = 0; index < feature_count_; ++index) {
    if (continuous_[index] == 0 || !moments[index].present()) {
      continue;
    }
    // EQUAL SESSION WEIGHT: the session's own MEAN enters the outer mean, not
    // its values.
    sum_first_[index] += moments[index].first_moment();
    sum_second_[index] += moments[index].second_moment();
    ++sessions_[index];
  }
  return true;
}

std::vector<FeatureNormalization> NormalizationFitter::freeze() const {
  std::vector<FeatureNormalization> table(feature_count_);
  for (std::size_t index = 0; index < feature_count_; ++index) {
    FeatureNormalization& entry = table[index];
    entry.centered = continuous_[index] != 0;
    if (!entry.centered) {
      entry.sessions = 0;
      entry.mu = 0.0;
      entry.scale = 1.0;
      continue;
    }
    entry.sessions = sessions_[index];
    if (entry.sessions == 0) {
      entry.mu = 0.0;   // "S=0 gives (mu,scale)=(0,1)"
      entry.scale = 1.0;
      continue;
    }
    const double sessions = static_cast<double>(entry.sessions);
    entry.mu = sum_first_[index] / sessions;
    const double mean_second = sum_second_[index] / sessions;
    const double variance = mean_second - entry.mu * entry.mu;
    entry.scale = std::sqrt(variance > 0.0 ? variance : 0.0);
    if (entry.scale < kScaleFloor) {
      entry.scale = 1.0;  // "scale<1e-6 becomes 1"
    }
  }
  return table;
}

std::string render_normalization(std::span<const FeatureNormalization> table) {
  std::string out = "feature\tsessions\tmu\tscale\tcentered\n";
  char buffer[128];
  for (std::size_t index = 0; index < table.size(); ++index) {
    const FeatureNormalization& entry = table[index];
    const int written =
        std::snprintf(buffer, sizeof(buffer), "%zu\t%lld\t%.17g\t%.17g\t%d\n", index,
                      static_cast<long long>(entry.sessions), entry.mu, entry.scale,
                      entry.centered ? 1 : 0);
    if (written <= 0 || static_cast<std::size_t>(written) >= sizeof(buffer)) {
      detail::fail_fast("qr::carriers::render_normalization: row did not fit");
    }
    out.append(buffer, static_cast<std::size_t>(written));
  }
  return out;
}

std::string normalization_sha256(std::span<const FeatureNormalization> table) {
  return sha256_hex(render_normalization(table));
}

}  // namespace qr::carriers
