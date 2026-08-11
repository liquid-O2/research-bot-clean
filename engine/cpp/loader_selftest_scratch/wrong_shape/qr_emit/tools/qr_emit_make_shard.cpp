// qr_emit_make_shard — writes the synthetic reference DecisionTape.
//
// SPEC: FINAL_PLAN.md APPENDIX C4. The leaf NAMES and SHAPES are C4's; the
// VALUES are a deterministic arithmetic pattern owned by this tool, because
// WP10 is the container and WP8 owns the content. python/test_decision_tape_
// loader.py recomputes the identical formulas and compares element by element,
// which is the C++ -> numpy round trip.
//
// THE FORMULAS (duplicated verbatim in the Python self-test):
//   features/direct_raw    [N,3,60] f4  (n*180 + c*60 + k) % 4096 / 8
//   features/group_ts      [G]      i8  1600000000000000000 + g*1000000
//   features/recent128     [N,2]    i4  n*2 + j - 7
//   features/grid_1s       [S,4]    f4  (s*4 + j) / 4
//   features/keys          [N,4]    i8  n*4 + j + 1000
//   truth/menu_net_cent    [N,7]    i8  (n*7 + h)*13 - 30000
//   truth/stop_hit         [N,7]    u1  (n + h) % 2
//   truth/barrier          [N]      u1  n % 3
//   truth/keys             [N,4]    i8  n*4 + j + 1000   (the join key, shared)
//
// The shard path is the frozen APPENDIX C4 shape and is COMPOSED here, never
// spelled by the caller: <base>/s<0125>/<L|S> (orchestrator ruling 2026-08-10).
//
// usage: qr_emit_make_shard --base DIR [--ordinal N] [--side L|S] [--rows N]
//                           [--groups G] [--seconds S] [--features-only]
//                           [--build-id ID]
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>

#include "qr_emit/fd_census.hpp"
#include "qr_emit/shard_writer.hpp"

namespace {

using qr::emit::NpyDtype;
using qr::emit::Section;

int fail(const qr::Refusal& refusal) {
  std::fprintf(stderr, "REFUSED: %s\n", refusal.message().c_str());
  return 1;
}

}  // namespace

int main(int argc, char** argv) {
  std::string base;
  std::int64_t ordinal = 125;
  qr::emit::Side side = qr::emit::Side::LONG;
  std::string build_id = "qr_emit_make_shard_v1";
  std::int64_t rows = 17;
  std::int64_t groups = 23;
  std::int64_t seconds = 11;
  bool features_only = false;
  for (int index = 1; index < argc; ++index) {
    const std::string argument = argv[index];
    const bool has_next = index + 1 < argc;
    if (argument == "--base" && has_next) {
      base = argv[++index];
    } else if (argument == "--ordinal" && has_next) {
      ordinal = std::atoll(argv[++index]);
    } else if (argument == "--side" && has_next) {
      const std::string letter = argv[++index];
      if (letter == "L") {
        side = qr::emit::Side::LONG;
      } else if (letter == "S") {
        side = qr::emit::Side::SHORT;
      } else {
        std::fprintf(stderr, "--side is L or S, not %s\n", letter.c_str());
        return 2;
      }
    } else if (argument == "--build-id" && has_next) {
      build_id = argv[++index];
    } else if (argument == "--rows" && has_next) {
      rows = std::atoll(argv[++index]);
    } else if (argument == "--groups" && has_next) {
      groups = std::atoll(argv[++index]);
    } else if (argument == "--seconds" && has_next) {
      seconds = std::atoll(argv[++index]);
    } else if (argument == "--features-only") {
      features_only = true;
    } else {
      std::fprintf(stderr,
                   "usage: %s --base DIR [--ordinal N] [--side L|S] [--rows N] [--groups G]"
                   " [--seconds S] [--features-only] [--build-id ID]\n",
                   argv[0]);
      return 2;
    }
  }
  if (base.empty()) {
    std::fprintf(stderr, "--base is required\n");
    return 2;
  }
  auto shard_dir = qr::emit::c4_shard_dir(base, ordinal, side);
  if (!shard_dir) {
    return fail(shard_dir.error());
  }
  if (features_only) {
    // A feature-only build declares itself a feature builder, so the census
    // enforces (not merely observes) the C4 separation for this whole process.
    qr::emit::FdCensus::instance().begin(qr::emit::ProcessRole::FEATURE_BUILDER);
  }

  qr::emit::ShardSpec spec;
  spec.publish_dir = shard_dir.value();
  spec.session_ordinal = ordinal;
  spec.side = side;
  spec.build_id = build_id;
  spec.sources = {{"stock_quotes_s125", "0000000000000000000000000000000000000000000000000000000000000000",
                   "synthetic://stock_quotes/s125"}};
  spec.census = {{"dialect_census", "0000000000000000000000000000000000000000000000000000000000000000",
                  "synthetic://dialect_census"}};

  auto begun = qr::emit::ShardWriter::begin(spec);
  if (!begun) {
    return fail(begun.error());
  }
  std::unique_ptr<qr::emit::ShardWriter> writer = std::move(begun).value();

  const std::size_t n = static_cast<std::size_t>(rows);
  const std::size_t g = static_cast<std::size_t>(groups);
  const std::size_t s = static_cast<std::size_t>(seconds);

  std::vector<float> direct_raw(n * 3 * 60);
  for (std::size_t row = 0; row < n; ++row) {
    for (std::size_t channel = 0; channel < 3; ++channel) {
      for (std::size_t column = 0; column < 60; ++column) {
        const std::size_t index = (row * 3 + channel) * 60 + column;
        const std::int64_t raw =
            static_cast<std::int64_t>(row * 180 + channel * 60 + column) % 4096;
        direct_raw[index] = static_cast<float>(raw) / 8.0F;
      }
    }
  }
  std::vector<std::int64_t> group_ts(g);
  for (std::size_t index = 0; index < g; ++index) {
    group_ts[index] = 1600000000000000000LL + static_cast<std::int64_t>(index) * 1000000LL;
  }
  std::vector<std::int32_t> recent128(n * 2);
  for (std::size_t row = 0; row < n; ++row) {
    for (std::size_t column = 0; column < 2; ++column) {
      recent128[row * 2 + column] = static_cast<std::int32_t>(row * 2 + column) - 7;
    }
  }
  std::vector<float> grid_1s(s * 4);
  for (std::size_t second = 0; second < s; ++second) {
    for (std::size_t column = 0; column < 4; ++column) {
      grid_1s[second * 4 + column] = static_cast<float>(second * 4 + column) / 4.0F;
    }
  }
  std::vector<std::int64_t> keys(n * 4);
  for (std::size_t row = 0; row < n; ++row) {
    for (std::size_t column = 0; column < 4; ++column) {
      keys[row * 4 + column] = static_cast<std::int64_t>(row * 4 + column) + 1000;
    }
  }
  std::vector<std::int64_t> menu_net_cent(n * 7);
  std::vector<std::uint8_t> stop_hit(n * 7);
  for (std::size_t row = 0; row < n; ++row) {
    for (std::size_t horizon = 0; horizon < 7; ++horizon) {
      menu_net_cent[row * 7 + horizon] =
          static_cast<std::int64_t>(row * 7 + horizon) * 13 - 30000;
      stop_hit[row * 7 + horizon] = static_cast<std::uint8_t>((row + horizon) % 2);
    }
  }
  std::vector<std::uint8_t> barrier(n);
  for (std::size_t row = 0; row < n; ++row) {
    barrier[row] = static_cast<std::uint8_t>(row % 3);
  }

  const std::vector<std::int64_t> direct_shape = {rows, 3, 60};
  const std::vector<std::int64_t> group_shape = {groups};
  const std::vector<std::int64_t> recent_shape = {rows, 2};
  const std::vector<std::int64_t> grid_shape = {seconds, 4};
  const std::vector<std::int64_t> keys_shape = {rows, 4};
  const std::vector<std::int64_t> menu_shape = {rows, 7};
  const std::vector<std::int64_t> barrier_shape = {rows};

  struct Step {
    Section section;
    const char* name;
    NpyDtype dtype;
    const std::vector<std::int64_t>* shape;
  };
  const std::vector<Step> feature_steps = {
      {Section::FEATURES, "direct_raw", NpyDtype::F4, &direct_shape},
      {Section::FEATURES, "group_ts", NpyDtype::I8, &group_shape},
      {Section::FEATURES, "recent128", NpyDtype::I4, &recent_shape},
      {Section::FEATURES, "grid_1s", NpyDtype::F4, &grid_shape},
      {Section::FEATURES, "keys", NpyDtype::I8, &keys_shape},
  };
  for (const Step& step : feature_steps) {
    qr::emit::Status status = qr::emit::ok_status();
    const std::string name(step.name);
    if (name == "direct_raw") {
      status = writer->write_leaf<float>(step.section, name, step.dtype, *step.shape, direct_raw);
    } else if (name == "group_ts") {
      status = writer->write_leaf<std::int64_t>(step.section, name, step.dtype, *step.shape,
                                                group_ts);
    } else if (name == "recent128") {
      status = writer->write_leaf<std::int32_t>(step.section, name, step.dtype, *step.shape,
                                                recent128);
    } else if (name == "grid_1s") {
      status = writer->write_leaf<float>(step.section, name, step.dtype, *step.shape, grid_1s);
    } else {
      status = writer->write_leaf<std::int64_t>(step.section, name, step.dtype, *step.shape, keys);
    }
    if (!status) {
      return fail(status.error());
    }
  }
  if (!features_only) {
    qr::emit::Status status = writer->write_leaf<std::int64_t>(
        Section::TRUTH, "menu_net_cent", NpyDtype::I8, menu_shape, menu_net_cent);
    if (!status) {
      return fail(status.error());
    }
    status = writer->write_leaf<std::uint8_t>(Section::TRUTH, "stop_hit", NpyDtype::U1, menu_shape,
                                              stop_hit);
    if (!status) {
      return fail(status.error());
    }
    status = writer->write_leaf<std::uint8_t>(Section::TRUTH, "barrier", NpyDtype::U1,
                                              barrier_shape, barrier);
    if (!status) {
      return fail(status.error());
    }
    status = writer->write_leaf<std::int64_t>(Section::TRUTH, "keys", NpyDtype::I8, keys_shape,
                                              keys);
    if (!status) {
      return fail(status.error());
    }
  }

  auto receipt = writer->publish();
  if (!receipt) {
    return fail(receipt.error());
  }
  std::printf("published\t%s\nleaves\t%lld\nbytes\t%lld\nmanifest_sha256\t%s\n",
              receipt.value().publish_dir.c_str(),
              static_cast<long long>(receipt.value().leaf_count),
              static_cast<long long>(receipt.value().total_leaf_bytes),
              receipt.value().manifest_sha256.c_str());
  if (features_only) {
    qr::emit::Status clean = qr::emit::FdCensus::instance().verify_no_truth_opened();
    if (!clean) {
      return fail(clean.error());
    }
    clean = qr::emit::FdCensus::instance().verify_open_fds_are_censused();
    if (!clean) {
      return fail(clean.error());
    }
    std::printf("fd_census\tCLEAN\topens_seen\t%llu\n",
                static_cast<unsigned long long>(qr::emit::FdCensus::instance().opens_seen()));
  }
  return 0;
}
