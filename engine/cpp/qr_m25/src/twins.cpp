// qr_m25/src/twins.cpp — the twin-discordance observability ceiling.
#include "qr_m25/twins.hpp"

#include <algorithm>
#include <cmath>
#include <string>
#include <unordered_map>

namespace qr::m25 {
namespace {

using qr::replay::kHorizonCount;
using qr::replay::LabelState;
using qr::replay::Side;

constexpr std::int64_t kNanosPerSecond = 1000000000;

}  // namespace

void TwinAccumulator::add(const TwinAccumulator& other) noexcept {
  for (std::size_t k = 0; k < kTwinLadderDepth; ++k) {
    pair_count[k] += other.pair_count[k];
    distance_sum[k] += other.distance_sum[k];
    for (std::size_t h = 0; h < kHorizonCount; ++h) {
      gap_sq_sum[k][h] += other.gap_sq_sum[k][h];
      disjoint_pair_count[k][h] += other.disjoint_pair_count[k][h];
      disjoint_distance_sum[k][h] += other.disjoint_distance_sum[k][h];
      disjoint_gap_sq_sum[k][h] += other.disjoint_gap_sq_sum[k][h];
    }
  }
  all_pair_count += other.all_pair_count;
  for (std::size_t h = 0; h < kHorizonCount; ++h) {
    all_gap_sq_sum[h] += other.all_gap_sq_sum[h];
    all_disjoint_pair_count[h] += other.all_disjoint_pair_count[h];
    all_disjoint_gap_sq_sum[h] += other.all_disjoint_gap_sq_sum[h];
    z_centred_sq_sum[h] += other.z_centred_sq_sum[h];
  }
  z_row_count += other.z_row_count;
  cell_count += other.cell_count;
  rows_in_cells += other.rows_in_cells;
  exact_key_twin_pairs += other.exact_key_twin_pairs;
}

namespace {

/// The weighted affine fit D = D0 + beta*d over a ladder, and its intercept,
/// clamped into [0, D1]. Shared by the two ladders so they cannot drift apart.
struct LadderFit {
  double d1 = 0.0;
  double d0 = 0.0;
  std::int64_t pairs_k1 = 0;
  bool usable = false;
};

LadderFit fit_ladder(const std::array<std::int64_t, kTwinLadderDepth>& pairs,
                     const std::array<double, kTwinLadderDepth>& distance,
                     const std::array<double, kTwinLadderDepth>& gap_sq) {
  LadderFit out;
  if (pairs[0] <= 0) {
    return out;
  }
  out.usable = true;
  out.pairs_k1 = pairs[0];
  out.d1 = gap_sq[0] / static_cast<double>(pairs[0]);

  double w = 0.0;
  double sx = 0.0;
  double sy = 0.0;
  double sxx = 0.0;
  double sxy = 0.0;
  std::size_t usable = 0;
  for (std::size_t k = 0; k < kTwinLadderDepth; ++k) {
    if (pairs[k] <= 0) {
      continue;
    }
    const double weight = static_cast<double>(pairs[k]);
    const double x = distance[k] / weight;
    const double y = gap_sq[k] / weight;
    w += weight;
    sx += weight * x;
    sy += weight * y;
    sxx += weight * x * x;
    sxy += weight * x * y;
    ++usable;
  }
  double d0 = out.d1;
  if (usable >= 2) {
    const double denominator = w * sxx - sx * sx;
    if (std::fabs(denominator) > 0.0) {
      const double beta = (w * sxy - sx * sy) / denominator;
      d0 = (sy - beta * sx) / w;
    }
  }
  out.d0 = std::min(std::max(d0, 0.0), out.d1);
  return out;
}

double ceiling_from(double squared_gap, double variance) {
  return std::sqrt(std::max(0.0, 1.0 - squared_gap / (2.0 * variance)));
}

}  // namespace

TwinCeiling twin_ceiling(const TwinAccumulator& accumulator, std::size_t horizon_index) {
  TwinCeiling out;
  if (accumulator.z_row_count <= 1) {
    return out;
  }
  out.variance = accumulator.z_centred_sq_sum[horizon_index] /
                 static_cast<double>(accumulator.z_row_count);
  if (!(out.variance > 0.0)) {
    return out;
  }

  // The OVERLAP-PERMITTING ladder (reported, biased upwards — see the header).
  std::array<double, kTwinLadderDepth> gap_sq{};
  for (std::size_t k = 0; k < kTwinLadderDepth; ++k) {
    gap_sq[k] = accumulator.gap_sq_sum[k][horizon_index];
  }
  const LadderFit overlapping =
      fit_ladder(accumulator.pair_count, accumulator.distance_sum, gap_sq);
  if (overlapping.usable) {
    out.d1 = overlapping.d1;
    out.d0 = overlapping.d0;
    out.q_max_k1 = ceiling_from(out.d1, out.variance);
    out.q_max = ceiling_from(out.d0, out.variance);
  }

  // The DISJOINT ladder — the one the twin identity actually licenses.
  std::array<std::int64_t, kTwinLadderDepth> disjoint_pairs{};
  std::array<double, kTwinLadderDepth> disjoint_distance{};
  std::array<double, kTwinLadderDepth> disjoint_gap_sq{};
  for (std::size_t k = 0; k < kTwinLadderDepth; ++k) {
    disjoint_pairs[k] = accumulator.disjoint_pair_count[k][horizon_index];
    disjoint_distance[k] = accumulator.disjoint_distance_sum[k][horizon_index];
    disjoint_gap_sq[k] = accumulator.disjoint_gap_sq_sum[k][horizon_index];
  }
  const LadderFit disjoint = fit_ladder(disjoint_pairs, disjoint_distance, disjoint_gap_sq);
  if (disjoint.usable) {
    out.d1_disjoint = disjoint.d1;
    out.d0_disjoint = disjoint.d0;
    out.disjoint_pairs = disjoint.pairs_k1;
    out.q_max_disjoint_k1 = ceiling_from(out.d1_disjoint, out.variance);
    out.q_max_disjoint = ceiling_from(out.d0_disjoint, out.variance);
  }

  if (accumulator.all_pair_count > 0) {
    const double d_all = accumulator.all_gap_sq_sum[horizon_index] /
                         static_cast<double>(accumulator.all_pair_count);
    out.q_max_clock_only = ceiling_from(d_all, out.variance);
  }
  if (accumulator.all_disjoint_pair_count[horizon_index] > 0) {
    const double d_all = accumulator.all_disjoint_gap_sq_sum[horizon_index] /
                         static_cast<double>(accumulator.all_disjoint_pair_count[horizon_index]);
    out.q_max_disjoint_clock_only = ceiling_from(d_all, out.variance);
  }
  return out;
}

TwinAccumulator accumulate_twins(const SessionTape& tape, const SkillDraws& draws,
                                 const std::vector<float>& prefix, std::size_t prefix_width,
                                 std::int64_t bucket_seconds) {
  TwinAccumulator out;
  const std::size_t n = tape.rows.size();
  if (n == 0 || prefix_width == 0) {
    return out;
  }

  // The outcome variance denominator, over every row that carries an outcome.
  std::array<double, kHorizonCount> z_sum{};
  std::int64_t counted = 0;
  for (std::size_t i = 0; i < n; ++i) {
    if (tape.rows[i].label.state != LabelState::OK) {
      continue;
    }
    ++counted;
    for (std::size_t h = 0; h < kHorizonCount; ++h) {
      z_sum[h] += draws.net_z[h][i];
    }
  }
  out.z_row_count = counted;
  if (counted > 0) {
    std::array<double, kHorizonCount> z_mean{};
    for (std::size_t h = 0; h < kHorizonCount; ++h) {
      z_mean[h] = z_sum[h] / static_cast<double>(counted);
    }
    for (std::size_t i = 0; i < n; ++i) {
      if (tape.rows[i].label.state != LabelState::OK) {
        continue;
      }
      for (std::size_t h = 0; h < kHorizonCount; ++h) {
        const double centred = draws.net_z[h][i] - z_mean[h];
        out.z_centred_sq_sum[h] += centred * centred;
      }
    }
  }

  // Cells: (side, clock bucket). Rows arrive in (timestamp, side) order, so a
  // single pass groups them.
  const std::int64_t session_start = tape.rows.empty() ? 0 : tape.rows.front().key.decision_ts_ns;
  std::unordered_map<std::int64_t, std::vector<std::size_t>> cells;
  for (std::size_t i = 0; i < n; ++i) {
    if (tape.rows[i].label.state != LabelState::OK) {
      continue;
    }
    const std::int64_t elapsed_s = (tape.rows[i].key.decision_ts_ns - session_start) / kNanosPerSecond;
    const std::int64_t bucket = elapsed_s / bucket_seconds;
    const std::int64_t side_bit = tape.rows[i].key.side == Side::LONG ? 0 : 1;
    cells[bucket * 2 + side_bit].push_back(i);
  }

  // Two trades DO NOT OVERLAP at horizon h when neither is still open when the
  // other opens. Their outcomes are then separate trades over separate price
  // paths, which is exactly what the twin identity assumes.
  const auto disjoint_at = [&tape](std::size_t i, std::size_t j, std::size_t h) {
    const auto& a = tape.rows[i].label;
    const auto& b = tape.rows[j].label;
    return a.menu_exit_ts[h] < b.entry_ts_ns || b.menu_exit_ts[h] < a.entry_ts_ns;
  };

  std::vector<std::pair<float, std::size_t>> ranked;
  std::vector<std::size_t> sampled;
  for (const auto& entry : cells) {
    const std::vector<std::size_t>& all_members = entry.second;
    if (all_members.size() < 2) {
      continue;
    }
    // THE CELL CAP, by a deterministic stride: the widest buckets cost what the
    // narrow ones cost, and which members survive is a function of the cell
    // alone.
    const std::vector<std::size_t>* members = &all_members;
    if (all_members.size() > kTwinCellCap) {
      sampled.clear();
      const std::size_t stride = (all_members.size() + kTwinCellCap - 1) / kTwinCellCap;
      for (std::size_t at = 0; at < all_members.size(); at += stride) {
        sampled.push_back(all_members[at]);
      }
      members = &sampled;
    }
    const std::vector<std::size_t>& cell = *members;
    if (cell.size() < 2) {
      continue;
    }
    ++out.cell_count;
    out.rows_in_cells += static_cast<std::int64_t>(cell.size());

    // All-pairs reference (clock bucket + side only, no market information),
    // kept both overlap-permitting and disjoint.
    for (std::size_t a = 0; a + 1 < cell.size(); ++a) {
      for (std::size_t b = a + 1; b < cell.size(); ++b) {
        ++out.all_pair_count;
        for (std::size_t h = 0; h < kHorizonCount; ++h) {
          const double gap = draws.net_z[h][cell[a]] - draws.net_z[h][cell[b]];
          out.all_gap_sq_sum[h] += gap * gap;
          if (disjoint_at(cell[a], cell[b], h)) {
            ++out.all_disjoint_pair_count[h];
            out.all_disjoint_gap_sq_sum[h] += gap * gap;
          }
        }
      }
    }

    // The nearest-neighbour ladders. The prefix distance does not depend on the
    // horizon, so the ranking is computed ONCE and walked seven times: the
    // overlap-permitting ladder takes the first K neighbours outright, and each
    // horizon's disjoint ladder takes the first K neighbours that do not overlap
    // AT THAT HORIZON.
    for (const std::size_t i : cell) {
      ranked.clear();
      const float* xi = prefix.data() + i * prefix_width;
      for (const std::size_t j : cell) {
        if (j == i) {
          continue;
        }
        const float* xj = prefix.data() + j * prefix_width;
        float accumulated = 0.0F;
        for (std::size_t c = 0; c < prefix_width; ++c) {
          const float delta = xi[c] - xj[c];
          accumulated += delta * delta;
        }
        ranked.emplace_back(accumulated, j);
      }
      std::sort(ranked.begin(), ranked.end());

      const std::size_t depth = std::min(kTwinLadderDepth, ranked.size());
      for (std::size_t k = 0; k < depth; ++k) {
        const double distance = std::sqrt(static_cast<double>(ranked[k].first));
        ++out.pair_count[k];
        out.distance_sum[k] += distance;
        if (k == 0 && ranked[k].first == 0.0F) {
          ++out.exact_key_twin_pairs;
        }
        const std::size_t j = ranked[k].second;
        for (std::size_t h = 0; h < kHorizonCount; ++h) {
          const double gap = draws.net_z[h][i] - draws.net_z[h][j];
          out.gap_sq_sum[k][h] += gap * gap;
        }
      }

      for (std::size_t h = 0; h < kHorizonCount; ++h) {
        std::size_t taken = 0;
        for (const auto& candidate : ranked) {
          if (taken >= kTwinLadderDepth) {
            break;
          }
          const std::size_t j = candidate.second;
          if (!disjoint_at(i, j, h)) {
            continue;
          }
          const double gap = draws.net_z[h][i] - draws.net_z[h][j];
          out.disjoint_pair_count[taken][h] += 1;
          out.disjoint_distance_sum[taken][h] += std::sqrt(static_cast<double>(candidate.first));
          out.disjoint_gap_sq_sum[taken][h] += gap * gap;
          ++taken;
        }
      }
    }
  }
  return out;
}

Expected<std::vector<float>, Refusal> load_prefix_matrix(const TapeRoot& root,
                                                         const SessionTape& tape,
                                                         std::size_t* width_out) {
  const std::size_t n = tape.rows.size();
  std::size_t width = 0;
  std::vector<float> matrix;

  // Where each (decision_ordinal, side) lives in the merged tape.
  std::unordered_map<std::int64_t, std::size_t> position;
  position.reserve(n * 2);
  for (std::size_t i = 0; i < n; ++i) {
    position[tape.rows[i].key.decision_ordinal * 2 +
             (tape.rows[i].key.side == qr::replay::Side::LONG ? 0 : 1)] = i;
  }

  std::string digits = std::to_string(tape.session_ordinal);
  while (digits.size() < 4) {
    digits.insert(digits.begin(), '0');
  }

  std::int64_t placed = 0;
  for (const char* side_dir : {"L", "S"}) {
    const std::filesystem::path shard = root.tapes / ("s" + digits) / side_dir;
    Expected<TapeManifest, Refusal> manifest = read_manifest(shard);
    if (!manifest.has_value()) {
      return refuse<std::vector<float>>(manifest.error());
    }
    Expected<NpyArray, Refusal> keys = open_leaf(shard, manifest.value(), "features/keys.npy");
    if (!keys.has_value()) {
      return refuse<std::vector<float>>(keys.error());
    }
    Expected<NpyArray, Refusal> direct = open_leaf(shard, manifest.value(), "features/direct_raw.npy");
    if (!direct.has_value()) {
      return refuse<std::vector<float>>(direct.error());
    }
    const NpyArray& direct_raw = direct.value();
    if (direct_raw.shape().size() != 3) {
      return refuse<std::vector<float>>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                                "qr_m25::load_prefix_matrix",
                                                "direct_raw is not [N,3,60]", 0));
    }
    const std::size_t this_width =
        static_cast<std::size_t>(direct_raw.shape()[1] * direct_raw.shape()[2]);
    if (width == 0) {
      width = this_width;
      matrix.assign(n * width, 0.0F);
    } else if (width != this_width) {
      return refuse<std::vector<float>>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                                "qr_m25::load_prefix_matrix",
                                                "the two side shards disagree on prefix width", 0));
    }
    const std::span<const std::int64_t> key_values = keys.value().i8();
    const std::span<const float> values = direct_raw.f4();
    const std::int64_t rows = direct_raw.rows();
    for (std::int64_t r = 0; r < rows; ++r) {
      const std::size_t k = static_cast<std::size_t>(r) * 4;
      const std::int64_t member = key_values[k + 1] * 2 + (key_values[k + 3] == 1 ? 0 : 1);
      const auto at = position.find(member);
      if (at == position.end()) {
        return refuse<std::vector<float>>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                                  "qr_m25::load_prefix_matrix",
                                                  "a shard row has no matching tape row",
                                                  key_values[k + 1]));
      }
      std::copy(values.begin() + static_cast<std::ptrdiff_t>(static_cast<std::size_t>(r) * width),
                values.begin() + static_cast<std::ptrdiff_t>((static_cast<std::size_t>(r) + 1) * width),
                matrix.begin() + static_cast<std::ptrdiff_t>(at->second * width));
      ++placed;
    }
  }
  if (placed != static_cast<std::int64_t>(n)) {
    return refuse<std::vector<float>>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                              "qr_m25::load_prefix_matrix",
                                              "shard rows do not cover the tape", placed));
  }

  // Column-wise standardisation inside the session: the 180 carriers are on
  // different scales (log counts, returns, spreads), and an unstandardised
  // Euclidean metric would be a metric on whichever carrier happens to be
  // largest. Zero-variance columns carry no information and become zero.
  for (std::size_t c = 0; c < width; ++c) {
    double sum = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
      sum += matrix[i * width + c];
    }
    const double mean = sum / static_cast<double>(n);
    double variance = 0.0;
    for (std::size_t i = 0; i < n; ++i) {
      const double centred = matrix[i * width + c] - mean;
      variance += centred * centred;
    }
    variance /= static_cast<double>(n);
    const double scale = variance > 0.0 ? 1.0 / std::sqrt(variance) : 0.0;
    for (std::size_t i = 0; i < n; ++i) {
      matrix[i * width + c] = static_cast<float>((matrix[i * width + c] - mean) * scale);
    }
  }

  if (width_out != nullptr) {
    *width_out = width;
  }
  return matrix;
}

}  // namespace qr::m25
