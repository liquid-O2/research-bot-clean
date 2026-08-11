// qr_m25/tests/m25_test_support.cpp — the published-shard half of the support.
#include "m25_test_support.hpp"

#include <cstdio>
#include <map>

namespace qr::m25::test {
namespace {

using qr::emit::NpyDtype;
using qr::emit::Section;
using qr::replay::kHorizonCount;

constexpr std::size_t kPrefixWidth = 3 * 60;

std::string pad4(std::int64_t value) {
  std::string digits = std::to_string(value);
  while (digits.size() < 4) {
    digits.insert(digits.begin(), '0');
  }
  return digits;
}

}  // namespace

Status publish_specs(const std::filesystem::path& run_dir, std::int64_t ordinal,
                     const std::string& day, const std::vector<Spec>& specs,
                     std::int64_t spacing_seconds, const std::vector<float>* prefix_long,
                     const std::vector<float>* prefix_short) {
  std::filesystem::create_directories(run_dir / "tapes");
  std::filesystem::create_directories(run_dir / "receipts" / "sessions");
  {
    const std::filesystem::path receipt =
        run_dir / "receipts" / "sessions" / ("s" + pad4(ordinal) + ".tsv");
    std::FILE* file = std::fopen(receipt.c_str(), "wb");
    if (file == nullptr) {
      return Status::refuse(Refusal(RefusalCode::IO, "publish_specs", "cannot write receipt", 0));
    }
    std::fprintf(file, "section\tmetric\tvalue\nsession\tday\t%s\n", day.c_str());
    std::fclose(file);
  }

  for (int side_index = 0; side_index < 2; ++side_index) {
    const bool want_long = side_index == 0;
    std::vector<Spec> side_specs;
    for (const Spec& spec : specs) {
      if (spec.is_long == want_long) {
        side_specs.push_back(spec);
      }
    }
    const std::int64_t n = static_cast<std::int64_t>(side_specs.size());
    std::vector<std::int64_t> keys(static_cast<std::size_t>(n) * 4, 0);
    std::vector<std::int64_t> entry(static_cast<std::size_t>(n), 0);
    std::vector<std::uint8_t> label_state(static_cast<std::size_t>(n), 0);
    std::vector<std::int64_t> gap(static_cast<std::size_t>(n), 0);
    std::vector<std::int64_t> cost(static_cast<std::size_t>(n), qr::replay::kTradeCostCent);
    std::vector<std::int64_t> menu_net(static_cast<std::size_t>(n) * kHorizonCount, 0);
    std::vector<std::int64_t> menu_mae(static_cast<std::size_t>(n) * kHorizonCount, 0);
    std::vector<std::int64_t> menu_exit(static_cast<std::size_t>(n) * kHorizonCount, 0);
    std::vector<std::uint8_t> stop_hit(static_cast<std::size_t>(n) * kHorizonCount, 0);
    std::vector<float> prefix(static_cast<std::size_t>(n) * kPrefixWidth, 0.0F);
    const std::vector<float>* supplied = want_long ? prefix_long : prefix_short;
    if (supplied != nullptr) {
      prefix = *supplied;
    } else {
      for (std::int64_t r = 0; r < n; ++r) {
        for (std::size_t c = 0; c < kPrefixWidth; ++c) {
          prefix[static_cast<std::size_t>(r) * kPrefixWidth + c] =
              static_cast<float>(side_specs[static_cast<std::size_t>(r)].clock) + 0.001F * static_cast<float>(c);
        }
      }
    }

    for (std::int64_t r = 0; r < n; ++r) {
      const Spec& spec = side_specs[static_cast<std::size_t>(r)];
      const std::size_t at = static_cast<std::size_t>(r);
      const std::int64_t decision_ts = kStart + spec.clock * spacing_seconds * kNs;
      keys[at * 4 + 0] = ordinal;
      keys[at * 4 + 1] = spec.clock;
      keys[at * 4 + 2] = decision_ts;
      keys[at * 4 + 3] = spec.is_long ? 1 : -1;
      entry[at] = decision_ts + kNs;
      label_state[at] = spec.available ? 0 : 1;
      gap[at] = spec.gap_through_cent;
      for (std::size_t h = 0; h < kHorizonCount; ++h) {
        const std::size_t cell = at * kHorizonCount + h;
        menu_net[cell] = spec.net_cent;
        menu_mae[cell] = spec.net_cent < 0 ? -spec.net_cent + 6 : 6;
        menu_exit[cell] = entry[at] + spec.hold_seconds * kNs;
        stop_hit[cell] = spec.stopped ? 1 : 0;
      }
    }

    qr::emit::ShardSpec shard_spec;
    shard_spec.session_ordinal = ordinal;
    shard_spec.side = want_long ? qr::emit::Side::LONG : qr::emit::Side::SHORT;
    shard_spec.build_id = "qr_m25_test";
    shard_spec.census.push_back(qr::emit::CensusRow{"task_card_v4", std::string(64, 'a'), "test"});
    auto dir = qr::emit::c4_shard_dir(run_dir / "tapes", ordinal, shard_spec.side);
    if (!dir.has_value()) {
      return Status::refuse(dir.error());
    }
    shard_spec.publish_dir = dir.value();
    auto writer = qr::emit::ShardWriter::begin(shard_spec);
    if (!writer.has_value()) {
      return Status::refuse(writer.error());
    }
    qr::emit::ShardWriter& shard = *writer.value();
    const std::vector<std::int64_t> key_shape{n, 4};
    const std::vector<std::int64_t> row_shape{n};
    const std::vector<std::int64_t> menu_shape{n, static_cast<std::int64_t>(kHorizonCount)};
    const std::vector<std::int64_t> direct_shape{n, 3, 60};

    Status last = ok();
    auto guard = [&last](qr::emit::Status status) {
      if (!status.has_value() && last.has_value()) {
        last = Status::refuse(status.error());
      }
    };
    guard(shard.write_leaf<std::int64_t>(Section::FEATURES, "keys", NpyDtype::I8, key_shape, keys));
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
    guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "menu_net_cent", NpyDtype::I8, menu_shape,
                                         menu_net));
    guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "menu_mae_cent", NpyDtype::I8, menu_shape,
                                         menu_mae));
    guard(shard.write_leaf<std::int64_t>(Section::TRUTH, "menu_exit_ts", NpyDtype::I8, menu_shape,
                                         menu_exit));
    guard(shard.write_leaf<std::uint8_t>(Section::TRUTH, "stop_hit", NpyDtype::U1, menu_shape,
                                         stop_hit));
    if (!last.has_value()) {
      return last;
    }
    auto published = shard.publish();
    if (!published.has_value()) {
      return Status::refuse(published.error());
    }
  }
  return ok();
}

}  // namespace qr::m25::test
