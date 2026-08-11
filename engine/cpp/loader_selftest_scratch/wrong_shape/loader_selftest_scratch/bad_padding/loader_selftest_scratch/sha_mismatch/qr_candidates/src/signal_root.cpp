#include "qr_candidates/signal_root.hpp"

#include <openssl/evp.h>

#include <array>
#include <cstdio>
#include <cstring>
#include <vector>

#include "qr_candidates/parse.hpp"

namespace qr::candidates {
namespace {

constexpr const char* kSite = "qr_candidates::encode_signal_image";

/// Big-endian fixed-width writers. Big-endian because the sealing authority
/// used Rust's `to_be_bytes`; little-endian would change every root.
void put_be(std::uint8_t* out, std::uint64_t value, std::size_t width) noexcept {
  for (std::size_t i = 0; i < width; ++i) {
    out[i] = static_cast<std::uint8_t>((value >> (8U * (width - 1U - i))) & 0xFFU);
  }
}

/// Lowercase-hex nibble table; 0xFF marks "not a lowercase hex digit".
constexpr std::array<std::uint8_t, 256> make_nibbles() {
  std::array<std::uint8_t, 256> table{};
  for (std::size_t i = 0; i < table.size(); ++i) {
    table[i] = 0xFFU;
  }
  for (std::size_t i = 0; i < 10; ++i) {
    table[static_cast<std::size_t>('0') + i] = static_cast<std::uint8_t>(i);
  }
  for (std::size_t i = 0; i < 6; ++i) {
    table[static_cast<std::size_t>('a') + i] = static_cast<std::uint8_t>(10U + i);
  }
  return table;
}
constexpr std::array<std::uint8_t, 256> kNibble = make_nibbles();

/// Decodes a canonical lowercase 64-hex digest into 32 raw bytes.
[[nodiscard]] bool put_digest(std::string_view cell, std::uint8_t* out) noexcept {
  if (cell.size() != 64) {
    return false;
  }
  for (std::size_t i = 0; i < 32; ++i) {
    const std::uint8_t hi = kNibble[static_cast<unsigned char>(cell[2 * i])];
    const std::uint8_t lo = kNibble[static_cast<unsigned char>(cell[2 * i + 1])];
    if (hi == 0xFFU || lo == 0xFFU) {
      return false;
    }
    out[i] = static_cast<std::uint8_t>((hi << 4U) | lo);
  }
  return true;
}

/// One length-prefixed text term of the prologue: be64(len) || bytes.
void absorb_text(Sha256& hasher, std::string_view text) {
  std::array<std::uint8_t, 8> length{};
  put_be(length.data(), static_cast<std::uint64_t>(text.size()), 8);
  hasher.update(length.data(), length.size());
  hasher.update(text);
}

constexpr std::string_view kSignalHeader =
    "ordinal\tday\tsignal_id\tphysical_event_id\tpolicy_id\tpolicy_name\treversal_bps\t"
    "causal_run_prefix_root\tcontinuity_ordinal\textreme_side\tpivot_price_u6\t"
    "pivot_evidence_root\tpivot_fragment_count\tpivot_fragments\tpivot_first_ts_ns\t"
    "pivot_last_ts_ns\tpivot_last_bar_ordinal\tconfirmation_state_position\t"
    "confirmation_group_ordinal\tconfirmation_ts_ns\tcausal_visible_ts_ns\t"
    "confirmation_bar_ordinal\tcausal_visible_bar_ordinal\tpivot_retouch_order_uncertain\t"
    "origin_to_visible_delay_bars_min\torigin_to_visible_delay_bars_max\t"
    "latency_from_pivot_ns_min\tlatency_from_pivot_ns_max\tlatency_from_pivot_groups_min\t"
    "latency_from_pivot_groups_max\tthreshold_level_u6\tconfirmation_price_low_u6\t"
    "confirmation_price_high_u6\tconfirmation_crossing_count\tconfirmation_crossing_set_root\t"
    "confirmation_group_root\tovershoot_low_u6\tovershoot_high_u6\tconfirmation_kind\t"
    "confirmation_quality_mask";

constexpr std::string_view kT14Header =
    "ordinal\tday\tsource_authority_root\tevent_input_root\tadapter_receipt_id\t"
    "source_retained_bytes\tscientific_group_count\trun_count\tbreaker_count\tbar_count\t"
    "causal_session_id\tscientific_path_book_id\twide_breaker_root\tepisode_book_id\t"
    "episode_sequence_root\tscale_link_sequence_root\tepisode_count\tconfirmed_episode_count\t"
    "scale_link_count\tplateau_fragment_count\tunresolved_fragment_count\tepisode_retained_bytes\t"
    "truth_20_count\ttruth_20_fragment_count\ttruth_20_retained_bytes\ttruth_40_count\t"
    "truth_40_fragment_count\ttruth_40_retained_bytes\tevent_book_id\tsignal_sequence_root\t"
    "ambiguity_sequence_root\tsummary_sequence_root\tsignal_count\tambiguity_count\t"
    "summary_count\tpivot_fragment_count\tevent_retained_bytes\t"
    "scoring_signal_views_retained_bytes\tscoring_ambiguity_views_retained_bytes\t"
    "max_stream_signal_count\tmax_stream_ambiguity_count\tmax_stream_truth_count\t"
    "max_stream_workspace_bytes\tepisode_transient_bytes\tevent_transient_bytes\t"
    "episode_phase_bytes\tevent_phase_bytes\tscoring_phase_bytes\tcharge_bytes\tadmission_class";

}  // namespace

// --- Sha256 -----------------------------------------------------------------

Sha256::Sha256() {
  auto* context = EVP_MD_CTX_new();
  if (context == nullptr || EVP_DigestInit_ex(context, EVP_sha256(), nullptr) != 1) {
    detail::fail_fast("OpenSSL EVP_DigestInit_ex(sha256) failed");
  }
  context_ = context;
}

Sha256::~Sha256() {
  if (context_ != nullptr) {
    EVP_MD_CTX_free(static_cast<EVP_MD_CTX*>(context_));
    context_ = nullptr;
  }
}

Sha256::Sha256(Sha256&& other) noexcept : context_(other.context_) { other.context_ = nullptr; }

Sha256& Sha256::operator=(Sha256&& other) noexcept {
  if (this != &other) {
    if (context_ != nullptr) {
      EVP_MD_CTX_free(static_cast<EVP_MD_CTX*>(context_));
    }
    context_ = other.context_;
    other.context_ = nullptr;
  }
  return *this;
}

void Sha256::update(const void* data, std::size_t size) noexcept {
  if (size == 0) {
    return;
  }
  if (context_ == nullptr ||
      EVP_DigestUpdate(static_cast<EVP_MD_CTX*>(context_), data, size) != 1) {
    detail::fail_fast("OpenSSL EVP_DigestUpdate(sha256) failed");
  }
}

std::string Sha256::finish_hex() {
  std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
  unsigned int digest_len = 0;
  if (context_ == nullptr ||
      EVP_DigestFinal_ex(static_cast<EVP_MD_CTX*>(context_), digest.data(), &digest_len) != 1) {
    detail::fail_fast("OpenSSL EVP_DigestFinal_ex(sha256) failed");
  }
  std::string hex;
  hex.resize(static_cast<std::size_t>(digest_len) * 2U);
  static constexpr char kHex[] = "0123456789abcdef";
  for (unsigned int i = 0; i < digest_len; ++i) {
    hex[2U * i] = kHex[digest[i] >> 4U];
    hex[2U * i + 1U] = kHex[digest[i] & 0x0FU];
  }
  return hex;
}

void Sha256::reset() {
  if (context_ == nullptr) {
    context_ = EVP_MD_CTX_new();
  }
  if (context_ == nullptr ||
      EVP_DigestInit_ex(static_cast<EVP_MD_CTX*>(context_), EVP_sha256(), nullptr) != 1) {
    detail::fail_fast("OpenSSL EVP_DigestInit_ex(sha256) failed");
  }
}

Expected<std::string, Refusal> sha256_file_hex(const std::string& path) {
  std::FILE* file = std::fopen(path.c_str(), "rb");
  if (file == nullptr) {
    return refuse<std::string>(
        Refusal(RefusalCode::IO, "qr_candidates::sha256_file_hex", "cannot open the file"));
  }
  Sha256 hasher;
  std::vector<std::uint8_t> block(8U << 20U);
  while (true) {
    const std::size_t got = std::fread(block.data(), 1, block.size(), file);
    if (got > 0) {
      hasher.update(block.data(), got);
    }
    if (got < block.size()) {
      const bool failed = std::ferror(file) != 0;
      std::fclose(file);
      if (failed) {
        return refuse<std::string>(
            Refusal(RefusalCode::IO, "qr_candidates::sha256_file_hex", "read error"));
      }
      break;
    }
  }
  return hasher.finish_hex();
}

// --- the formula ------------------------------------------------------------

std::string_view signal_header() noexcept { return kSignalHeader; }
std::string_view t14_header() noexcept { return kT14Header; }

void absorb_root_prologue(Sha256& hasher, std::uint64_t session_signal_count) {
  absorb_text(hasher, kFramingSemantic);
  absorb_text(hasher, kFramingCode);
  absorb_text(hasher, kSignalDomain);
  absorb_text(hasher, kKernelSemantic);
  absorb_text(hasher, kKernelCode);
  std::array<std::uint8_t, 8> count{};
  put_be(count.data(), session_signal_count, 8);
  hasher.update(count.data(), count.size());
}

Expected<std::size_t, Refusal> encode_signal_image(
    const std::string_view fields[kSignalFieldCount], std::uint8_t out[kSignalImageCapacity]) {
  std::size_t at = 0;

  /// Every writer goes through this: a term that would not fit refuses instead
  /// of overrunning, so the capacity constant is enforced rather than trusted.
  const auto room = [&](std::size_t width) noexcept -> bool {
    return at + width <= kSignalImageCapacity;
  };
  const auto digest_term = [&](std::size_t index) noexcept -> bool {
    if (!room(32) || !put_digest(fields[index], out + at)) {
      return false;
    }
    at += 32;
    return true;
  };
  // Terms 1-4: signal id, physical event id, policy id, causal run prefix root.
  for (const std::size_t index : {static_cast<std::size_t>(kFieldSignalId),
                                  static_cast<std::size_t>(kFieldPhysicalEventId),
                                  static_cast<std::size_t>(kFieldPolicyId),
                                  static_cast<std::size_t>(kFieldCausalRunPrefixRoot)}) {
    if (!digest_term(index)) {
      return refuse<std::size_t>(Refusal(RefusalCode::DECODE_FAILED, kSite,
                                         "cell is not a canonical lowercase 64-hex digest",
                                         static_cast<std::int64_t>(index)));
    }
  }

  const auto overrun = [&]() {
    return refuse<bool>(
        Refusal(RefusalCode::ARITHMETIC_OVERFLOW, kSite, "signal image would overrun its capacity",
                static_cast<std::int64_t>(at)));
  };
  const auto u32_term = [&](std::size_t index) -> Expected<bool, Refusal> {
    const auto value = parse_u32(fields[index], kSite);
    if (!value) {
      return refuse<bool>(value.error());
    }
    if (!room(4)) {
      return overrun();
    }
    put_be(out + at, value.value(), 4);
    at += 4;
    return true;
  };
  const auto u64_term = [&](std::size_t index) -> Expected<bool, Refusal> {
    const auto value = parse_u64(fields[index], kSite);
    if (!value) {
      return refuse<bool>(value.error());
    }
    if (!room(8)) {
      return overrun();
    }
    put_be(out + at, value.value(), 8);
    at += 8;
    return true;
  };
  const auto i64_term = [&](std::size_t index) -> Expected<bool, Refusal> {
    const auto value = parse_i64(fields[index], kSite);
    if (!value) {
      return refuse<bool>(value.error());
    }
    if (!room(8)) {
      return overrun();
    }
    put_be(out + at, static_cast<std::uint64_t>(value.value()), 8);
    at += 8;
    return true;
  };
  const auto byte_term = [&](std::uint8_t value) -> bool {
    if (!room(1)) {
      return false;
    }
    out[at++] = value;
    return true;
  };

  // Term 5: continuity ordinal.
  if (const auto step = u32_term(kFieldContinuityOrdinal); !step) {
    return refuse<std::size_t>(step.error());
  }
  // Term 6: the extreme side, as one byte. LOW=0, HIGH=1, nothing else exists.
  if (fields[kFieldExtremeSide] == "LOW") {
    if (!byte_term(0)) {
      return refuse<std::size_t>(overrun().error());
    }
  } else if (fields[kFieldExtremeSide] == "HIGH") {
    if (!byte_term(1)) {
      return refuse<std::size_t>(overrun().error());
    }
  } else {
    return refuse<std::size_t>(Refusal(RefusalCode::DECODE_FAILED, kSite,
                                       "extreme_side is neither LOW nor HIGH",
                                       static_cast<std::int64_t>(kFieldExtremeSide)));
  }
  // Term 7: pivot price.
  if (const auto step = i64_term(kFieldPivotPriceU6); !step) {
    return refuse<std::size_t>(step.error());
  }
  // Term 8: pivot evidence root.
  if (!digest_term(kFieldPivotEvidenceRoot)) {
    return refuse<std::size_t>(Refusal(RefusalCode::DECODE_FAILED, kSite,
                                       "pivot_evidence_root is not a canonical digest",
                                       static_cast<std::int64_t>(kFieldPivotEvidenceRoot)));
  }
  // Terms 9-12: confirmation state position, group ordinal, ts, visible ts.
  if (const auto step = u64_term(kFieldConfirmationStatePosition); !step) {
    return refuse<std::size_t>(step.error());
  }
  if (const auto step = u64_term(kFieldConfirmationGroupOrdinal); !step) {
    return refuse<std::size_t>(step.error());
  }
  if (const auto step = i64_term(kFieldConfirmationTsNs); !step) {
    return refuse<std::size_t>(step.error());
  }
  if (const auto step = i64_term(kFieldCausalVisibleTsNs); !step) {
    return refuse<std::size_t>(step.error());
  }
  // Term 13: the retouch-order flag.
  {
    const auto flag = parse_bool(fields[kFieldPivotRetouchOrderUncertain], kSite);
    if (!flag) {
      return refuse<std::size_t>(flag.error());
    }
    if (!byte_term(flag.value() ? 1U : 0U)) {
      return refuse<std::size_t>(overrun().error());
    }
  }
  // Terms 14-15: the two optional delay bounds — presence byte, then the value
  // only when present. An absent bound contributes ONE byte, not five.
  for (const std::size_t index : {static_cast<std::size_t>(kFieldOriginToVisibleDelayBarsMin),
                                  static_cast<std::size_t>(kFieldOriginToVisibleDelayBarsMax)}) {
    const auto value = parse_opt_u32(fields[index], kSite);
    if (!value) {
      return refuse<std::size_t>(value.error());
    }
    if (!byte_term(value.value().has_value() ? 1U : 0U)) {
      return refuse<std::size_t>(overrun().error());
    }
    if (value.value().has_value()) {
      if (!room(4)) {
        return refuse<std::size_t>(overrun().error());
      }
      put_be(out + at, *value.value(), 4);
      at += 4;
    }
  }
  // Terms 16-19: the latency bounds.
  if (const auto step = i64_term(kFieldLatencyFromPivotNsMin); !step) {
    return refuse<std::size_t>(step.error());
  }
  if (const auto step = i64_term(kFieldLatencyFromPivotNsMax); !step) {
    return refuse<std::size_t>(step.error());
  }
  if (const auto step = u64_term(kFieldLatencyFromPivotGroupsMin); !step) {
    return refuse<std::size_t>(step.error());
  }
  if (const auto step = u64_term(kFieldLatencyFromPivotGroupsMax); !step) {
    return refuse<std::size_t>(step.error());
  }
  // Terms 20-22: the confirmation price band and crossing count.
  if (const auto step = i64_term(kFieldConfirmationPriceLowU6); !step) {
    return refuse<std::size_t>(step.error());
  }
  if (const auto step = i64_term(kFieldConfirmationPriceHighU6); !step) {
    return refuse<std::size_t>(step.error());
  }
  if (const auto step = u32_term(kFieldConfirmationCrossingCount); !step) {
    return refuse<std::size_t>(step.error());
  }
  // Terms 23-24: the crossing-set and group roots.
  if (!digest_term(kFieldConfirmationCrossingSetRoot)) {
    return refuse<std::size_t>(Refusal(RefusalCode::DECODE_FAILED, kSite,
                                       "confirmation_crossing_set_root is not a canonical digest",
                                       static_cast<std::int64_t>(kFieldConfirmationCrossingSetRoot)));
  }
  if (!digest_term(kFieldConfirmationGroupRoot)) {
    return refuse<std::size_t>(Refusal(RefusalCode::DECODE_FAILED, kSite,
                                       "confirmation_group_root is not a canonical digest",
                                       static_cast<std::int64_t>(kFieldConfirmationGroupRoot)));
  }

  if (at > kSignalImageCapacity) {
    detail::fail_fast("qr_candidates: signal image overran its capacity");
  }
  return at;
}

}  // namespace qr::candidates
