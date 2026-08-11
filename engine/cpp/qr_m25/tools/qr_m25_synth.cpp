// qr_m25_synth — publishes a SYNTHETIC DecisionTape corpus with a CONSTRUCTED
// reachability, for the M2.5 red-first suite.
//
// WHY A REAL PUBLISHED CORPUS AND NOT AN IN-MEMORY FIXTURE. The M2.5 gate has to
// be shown to FAIL on an object where the skill it needs cannot exist, and to
// PASS on one where it can. A fixture that hands the runner arrays in memory
// tests the arithmetic and nothing else; a fixture that PUBLISHES tapes through
// the real `qr::emit::ShardWriter`, and then runs the real loader, the real
// skill law, the real gate family and the real replay kernel over them, tests
// the machine that will be pointed at the corpus.
//
// THE TWO CONSTRUCTIONS.
//   --reachable    every carrier of `direct_raw` is the session's own signal g
//                  plus a small independent wobble, and the outcome is an affine
//                  function of g. Two actions with near-identical prefixes then
//                  have near-identical outcomes: the twin discordance goes to
//                  zero and Q_max goes to one, while perfect skill earns far
//                  more than the bar, so Q* lands well under Q_max. PASS.
//   --unreachable  `direct_raw` is independent noise and the outcome is
//                  independent noise: the prefix says NOTHING about the outcome,
//                  so twins are maximally discordant (Q_max -> 0) while any
//                  positive dollar bar still needs Q > 0 (at Q = 0 the sides are
//                  random and the 576c cost makes the expectation negative).
//                  Q* > Q_max by construction. FAIL.
//
// Nothing here is tuned to a result: both constructions are declared by their
// generating law, and the verdicts follow from the law, not from the numbers.
//
// usage: qr_m25_synth --base DIR --mode reachable|unreachable
//                     [--first 125] [--sessions 50] [--clocks 200]
//                     [--spacing-seconds 60] [--scale-cent 20000]
//                     [--wobble 0.02] [--card-sha HEX]
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <vector>

#include "qr_emit/shard_writer.hpp"
#include "qr_m25/skill.hpp"
#include "qr_replay/action.hpp"
#include "qr_replay/pcg64.hpp"

namespace {

using qr::emit::NpyDtype;
using qr::emit::Section;
using qr::emit::ShardSpec;
using qr::emit::ShardWriter;
using qr::replay::kHorizonCount;

constexpr std::int64_t kNs = 1000000000;
constexpr std::int64_t kSessionStartNs = 1657027800000000000;  // s125's 09:30 instant
constexpr std::int64_t kStopNetCent = 30000;
constexpr std::int64_t kCostCent = 576;
constexpr std::size_t kDirectChannels = 3;
constexpr std::size_t kDirectColumns = 60;

/// Per-horizon outcome weight: the same move is worth less at the two shortest
/// horizons. Declared here, fixed.
constexpr double kHorizonWeight[kHorizonCount] = {0.5, 0.8, 1.0, 1.0, 1.0, 1.0, 1.0};
constexpr std::int64_t kHorizonMinutes[kHorizonCount] = {2, 5, 15, 30, 60, 120, 390};

int fail(const qr::Refusal& refusal) {
  std::fprintf(stderr, "REFUSED: %s\n", refusal.message().c_str());
  return 1;
}

std::string pad4(std::int64_t value) {
  std::string digits = std::to_string(value);
  while (digits.size() < 4) {
    digits.insert(digits.begin(), '0');
  }
  return digits;
}

/// A plausible civil day whose YEAR is what the block bootstrap strata read.
std::string synth_day(std::int64_t index) {
  const std::int64_t year = 2022 + index / 25;
  const std::int64_t within = index % 25;
  const std::int64_t month = 1 + within / 3;
  const std::int64_t day = 1 + (within % 3) * 9;
  char buffer[64];
  std::snprintf(buffer, sizeof(buffer), "%04d-%02d-%02d", static_cast<int>(year),
                static_cast<int>(month), static_cast<int>(day));
  return buffer;
}

}  // namespace

int main(int argc, char** argv) {
  std::string base;
  std::string mode = "reachable";
  std::int64_t first = 125;
  std::int64_t sessions = 50;
  std::int64_t clocks = 200;
  std::int64_t spacing_seconds = 60;
  double scale_cent = 20000.0;
  double wobble = 0.02;
  std::string card_sha = "synthetic_no_card";

  for (int index = 1; index < argc; ++index) {
    const std::string argument = argv[index];
    const bool has_next = index + 1 < argc;
    if (argument == "--base" && has_next) {
      base = argv[++index];
    } else if (argument == "--mode" && has_next) {
      mode = argv[++index];
    } else if (argument == "--first" && has_next) {
      first = std::atoll(argv[++index]);
    } else if (argument == "--sessions" && has_next) {
      sessions = std::atoll(argv[++index]);
    } else if (argument == "--clocks" && has_next) {
      clocks = std::atoll(argv[++index]);
    } else if (argument == "--spacing-seconds" && has_next) {
      spacing_seconds = std::atoll(argv[++index]);
    } else if (argument == "--scale-cent" && has_next) {
      scale_cent = std::atof(argv[++index]);
    } else if (argument == "--wobble" && has_next) {
      wobble = std::atof(argv[++index]);
    } else if (argument == "--card-sha" && has_next) {
      card_sha = argv[++index];
    } else {
      std::fprintf(stderr, "unknown argument: %s\n", argument.c_str());
      return 2;
    }
  }
  if (base.empty() || (mode != "reachable" && mode != "unreachable")) {
    std::fprintf(stderr, "usage: qr_m25_synth --base DIR --mode reachable|unreachable\n");
    return 2;
  }
  const bool reachable = mode == "reachable";

  const std::filesystem::path root(base);
  std::filesystem::create_directories(root / "tapes");
  std::filesystem::create_directories(root / "receipts" / "sessions");

  const std::size_t prefix_width = kDirectChannels * kDirectColumns;

  for (std::int64_t s = 0; s < sessions; ++s) {
    const std::int64_t ordinal = first + s;

    // One stream per session drives BOTH the signal and every wobble, so the
    // corpus is a pure function of (mode, ordinal) and nothing else.
    qr::replay::Pcg64 generator(qr::replay::SeedSequence::from_entropy(
        std::vector<std::uint64_t>{qr::replay::kProgramSeed, qr::m25::kM25Tag, 7,
                                   static_cast<std::uint64_t>(ordinal),
                                   static_cast<std::uint64_t>(reachable ? 1 : 0)}));
    auto uniform = [&generator]() {
      return static_cast<double>(generator.next_uint64() >> 11) * (1.0 / 9007199254740992.0);
    };

    std::vector<double> signal(static_cast<std::size_t>(clocks));
    std::vector<double> outcome(static_cast<std::size_t>(clocks));
    std::vector<float> prefix(static_cast<std::size_t>(clocks) * prefix_width, 0.0F);
    for (std::int64_t c = 0; c < clocks; ++c) {
      const std::size_t at = static_cast<std::size_t>(c);
      signal[at] = qr::m25::ndtri(uniform());
      const double independent = qr::m25::ndtri(uniform());
      outcome[at] = reachable ? signal[at] : independent;
      for (std::size_t w = 0; w < prefix_width; ++w) {
        const double carrier = reachable ? signal[at] + wobble * qr::m25::ndtri(uniform())
                                         : qr::m25::ndtri(uniform());
        prefix[at * prefix_width + w] = static_cast<float>(carrier);
      }
    }

    const std::string day = synth_day(s);
    {
      const std::filesystem::path receipt =
          root / "receipts" / "sessions" / ("s" + pad4(ordinal) + ".tsv");
      std::FILE* file = std::fopen(receipt.c_str(), "wb");
      if (file == nullptr) {
        std::fprintf(stderr, "cannot write %s\n", receipt.c_str());
        return 1;
      }
      std::fprintf(file, "section\tmetric\tvalue\n");
      std::fprintf(file, "session\tschema\tqr_campaign_session_v1\n");
      std::fprintf(file, "session\tordinal\t%lld\n", static_cast<long long>(ordinal));
      std::fprintf(file, "session\tday\t%s\n", day.c_str());
      std::fclose(file);
    }

    for (int side_index = 0; side_index < 2; ++side_index) {
      const qr::emit::Side side = side_index == 0 ? qr::emit::Side::LONG : qr::emit::Side::SHORT;
      const double sign = side_index == 0 ? 1.0 : -1.0;

      std::vector<std::int64_t> keys(static_cast<std::size_t>(clocks) * 4, 0);
      std::vector<std::int64_t> entry(static_cast<std::size_t>(clocks), 0);
      std::vector<std::uint8_t> label_state(static_cast<std::size_t>(clocks), 0);
      std::vector<std::int64_t> gap(static_cast<std::size_t>(clocks), 0);
      std::vector<std::int64_t> cost(static_cast<std::size_t>(clocks), kCostCent);
      std::vector<std::int64_t> menu_net(static_cast<std::size_t>(clocks) * kHorizonCount, 0);
      std::vector<std::int64_t> menu_mae(static_cast<std::size_t>(clocks) * kHorizonCount, 0);
      std::vector<std::int64_t> menu_exit(static_cast<std::size_t>(clocks) * kHorizonCount, 0);
      std::vector<std::uint8_t> stop_hit(static_cast<std::size_t>(clocks) * kHorizonCount, 0);

      for (std::int64_t c = 0; c < clocks; ++c) {
        const std::size_t at = static_cast<std::size_t>(c);
        const std::int64_t decision_ts = kSessionStartNs + c * spacing_seconds * kNs;
        keys[at * 4 + 0] = ordinal;
        keys[at * 4 + 1] = c;
        keys[at * 4 + 2] = decision_ts;
        keys[at * 4 + 3] = side_index == 0 ? 1 : -1;
        entry[at] = decision_ts + kNs;
        // A sprinkle of unavailable labels, so NO_FRESH_FILL is exercised.
        label_state[at] = (c % 97 == 96) ? 1 : 0;

        const double move = sign * outcome[at] * scale_cent;
        for (std::size_t h = 0; h < kHorizonCount; ++h) {
          const std::size_t cell = at * kHorizonCount + h;
          double gross = move * kHorizonWeight[h];
          std::int64_t net = static_cast<std::int64_t>(std::llround(gross)) - kCostCent;
          if (net < -kStopNetCent) {
            net = -kStopNetCent;
            stop_hit[cell] = 1;
          }
          menu_net[cell] = net;
          menu_mae[cell] = net < 0 ? -net + 6 : 6;
          menu_exit[cell] = entry[at] + kHorizonMinutes[h] * 60 * kNs;
        }
      }

      ShardSpec spec;
      spec.session_ordinal = ordinal;
      spec.side = side;
      spec.build_id = std::string("qr_m25_synth_") + mode;
      spec.census.push_back(qr::emit::CensusRow{"task_card_v4", card_sha, "synthetic"});
      qr::Expected<std::filesystem::path, qr::Refusal> dir =
          qr::emit::c4_shard_dir(root / "tapes", ordinal, side);
      if (!dir.has_value()) {
        return fail(dir.error());
      }
      spec.publish_dir = dir.value();

      auto writer = ShardWriter::begin(spec);
      if (!writer.has_value()) {
        return fail(writer.error());
      }
      ShardWriter& shard = *writer.value();

      const std::int64_t n = clocks;
      const std::vector<std::int64_t> key_shape{n, 4};
      const std::vector<std::int64_t> row_shape{n};
      const std::vector<std::int64_t> menu_shape{n, static_cast<std::int64_t>(kHorizonCount)};
      const std::vector<std::int64_t> direct_shape{n, static_cast<std::int64_t>(kDirectChannels),
                                                   static_cast<std::int64_t>(kDirectColumns)};

      qr::m25::Status last = qr::m25::ok();
      auto guard = [&](qr::emit::Status status) {
        if (!status.has_value()) {
          last = qr::m25::Status::refuse(status.error());
        }
      };
      guard(shard.write_leaf<std::int64_t>(Section::FEATURES, "keys", NpyDtype::I8, key_shape,
                                           keys));
      guard(shard.write_leaf<float>(Section::FEATURES, "direct_raw", NpyDtype::F4, direct_shape,
                                    prefix));
      guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "keys", NpyDtype::I8, key_shape, keys));
      guard(shard.write_leaf<std::uint8_t>(Section::TRUTH, "label_state", NpyDtype::U1, row_shape,
                                           label_state));
      guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "entry_ts_ns", NpyDtype::I8, row_shape,
                                           entry));
      guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "gap_through_cent", NpyDtype::I8,
                                           row_shape, gap));
      guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "cost_charged_cent", NpyDtype::I8,
                                           row_shape, cost));
      guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "menu_net_cent", NpyDtype::I8,
                                           menu_shape, menu_net));
      guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "menu_mae_cent", NpyDtype::I8,
                                           menu_shape, menu_mae));
      guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "menu_exit_ts", NpyDtype::I8,
                                           menu_shape, menu_exit));
      guard(shard.write_leaf<std::uint8_t>(Section::TRUTH, "stop_hit", NpyDtype::U1, menu_shape,
                                           stop_hit));
      if (!last.has_value()) {
        return fail(last.error());
      }
      auto published = shard.publish();
      if (!published.has_value()) {
        return fail(published.error());
      }
    }
  }

  std::fprintf(stdout, "qr_m25_synth: mode=%s sessions=%lld clocks=%lld base=%s\n", mode.c_str(),
               static_cast<long long>(sessions), static_cast<long long>(clocks), base.c_str());
  return 0;
}
