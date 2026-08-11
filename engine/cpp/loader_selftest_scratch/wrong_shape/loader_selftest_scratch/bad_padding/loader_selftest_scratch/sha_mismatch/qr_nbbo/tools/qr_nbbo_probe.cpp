// qr_nbbo_probe — the authorized session-125 full-day group-machine run.
//
// WP5 brief, REAL-FILE CHECK (payload read authorized for this work package on
// EXACTLY this file and no other):
//   /workspace/data/tokens/stock_quotes/IWM/2022/2022-07-05.parquet  (s125)
// "full-day group machine run; group count MUST equal registry
//  complete_group_count 2,810,589 ...; publish census TSV (all QuoteKind/flag
//  counts, printed in full) to tests/fixtures/; two-run identity."
//
// It is a binary rather than a ctest case for the reason WP3 and WP4
// established: 15.4M rows and 2.8M groups do not belong in every ctest
// invocation, twice, under ASan. ci/wp5_nbbo_realfile_gate.sh runs it against
// the release build.
//
// TWO PASSES, ON PURPOSE. The first drains the WP4 reader and throws the
// groups away; the second runs the group machine over the same stream. The
// difference is THIS work package's marginal cost, reported separately from
// the decode it sits on top of.
//
// usage:
//   qr_nbbo_probe --root DIR --label NAME [--ordinal N] [--tsv PATH]
//                 [--census PATH]
// The TSV and the census are deterministic: no timings inside either.
#include <chrono>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <utility>
#include <vector>

#include "qr_nbbo/group_machine.hpp"
#include "qr_sources/stock_quotes.hpp"

namespace {

constexpr std::uint64_t kFnvOffsetBasis = 0xCBF29CE484222325ULL;
constexpr std::uint64_t kFnvPrime = 0x100000001B3ULL;

std::uint64_t fnv1a(std::uint64_t digest, const std::vector<std::uint8_t>& data) {
  for (const std::uint8_t byte : data) {
    digest ^= static_cast<std::uint64_t>(byte);
    digest *= kFnvPrime;
  }
  return digest;
}

struct Row {
  std::string metric;
  std::string value;
};

const qr::Registry* registry_or_null() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  return loaded.has_value() ? &loaded.value() : nullptr;
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_nbbo_probe --root DIR --label NAME [--ordinal N] [--tsv PATH] "
               "[--census PATH]\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  std::string root;
  std::string label;
  std::string tsv;
  std::string census_path;
  std::int64_t ordinal = 125;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    const bool has_value = index + 1 < argc;
    if (flag == "--root" && has_value) {
      root = argv[++index];
    } else if (flag == "--label" && has_value) {
      label = argv[++index];
    } else if (flag == "--tsv" && has_value) {
      tsv = argv[++index];
    } else if (flag == "--census" && has_value) {
      census_path = argv[++index];
    } else if (flag == "--ordinal" && has_value) {
      ordinal = std::strtoll(argv[++index], nullptr, 10);
    } else {
      return usage();
    }
  }
  if (root.empty() || label.empty()) {
    return usage();
  }

  const qr::Registry* const registry = registry_or_null();
  if (registry == nullptr) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }
  const auto scope = qr::DayScope::admit(*registry, ordinal);
  if (!scope.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
    return 1;
  }
  const std::filesystem::path corpus_root(root);

  const auto open_reader = [&]() {
    return qr::sources::StockQuoteReader::open(scope.value(), corpus_root,
                                               scope.value().profile());
  };

  // --- pass 1: the WP4 decode alone (the denominator of the marginal cost) --
  double read_seconds = 0.0;
  {
    auto opened = open_reader();
    if (!opened.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", opened.error().message().c_str());
      return 1;
    }
    qr::sources::StockQuoteReader reader = std::move(opened).value();
    qr::sources::StockQuoteReader::Group group;
    const auto started = std::chrono::steady_clock::now();
    while (true) {
      const auto more = reader.next_group(group);
      if (!more.has_value()) {
        std::fprintf(stderr, "REFUSED: %s\n", more.error().message().c_str());
        return 1;
      }
      if (!more.value()) {
        break;
      }
    }
    read_seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
  }

  // --- pass 2: the group machine over the same stream ----------------------
  auto opened = open_reader();
  if (!opened.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", opened.error().message().c_str());
    return 1;
  }
  qr::sources::StockQuoteReader reader = std::move(opened).value();
  const auto started = std::chrono::steady_clock::now();
  auto ran = qr::nbbo::run_session(reader, scope.value());
  const double full_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
  if (!ran.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", ran.error().message().c_str());
    return 1;
  }
  const qr::nbbo::GroupMachine machine = std::move(ran).value();
  const qr::nbbo::FullDayQuoteCensus& census = machine.census();
  const std::uint64_t output_digest = fnv1a(kFnvOffsetBasis, machine.serialize());

  std::vector<Row> rows;
  const auto metric = [&rows](std::string name, std::int64_t value) {
    rows.push_back(Row{std::move(name), std::to_string(value)});
  };
  rows.push_back(Row{"path", reader.path().string()});
  rows.push_back(Row{"day", scope.value().day()});
  metric("ordinal", scope.value().ordinal());
  metric("registry_raw_rth_row_count", scope.value().session().raw_rth_row_count);
  metric("registry_complete_group_count", scope.value().session().complete_group_count);
  metric("machine_rth_rows", census.rth_rows);
  metric("machine_group_count", census.group_count);
  metric("registry_rth_rows_match",
         census.rth_rows == scope.value().session().raw_rth_row_count ? 1 : 0);
  metric("registry_group_count_match",
         census.group_count == scope.value().session().complete_group_count ? 1 : 0);
  metric("sealed", machine.sealed() ? 1 : 0);
  metric("output_digest_i64", static_cast<std::int64_t>(output_digest));
  metric("scientific_midpoint_offsets_len",
         static_cast<std::int64_t>(machine.groups().scientific_midpoint_offsets.size()));
  metric("wide_midpoint_offsets_len",
         static_cast<std::int64_t>(machine.groups().wide_midpoint_offsets.size()));

  std::printf("label\tmetric\tvalue\n");
  for (const Row& row : rows) {
    std::printf("%s\t%s\t%s\n", label.c_str(), row.metric.c_str(), row.value.c_str());
  }
  const std::string census_tsv = census.to_tsv(label);
  std::fputs(census_tsv.c_str(), stdout);
  std::printf("read_seconds %.6f\n", read_seconds);
  std::printf("full_seconds %.6f\n", full_seconds);
  std::printf("machine_seconds %.6f\n", full_seconds - read_seconds);
  std::printf("groups_per_second %" PRId64 "\n",
              full_seconds > 0.0
                  ? static_cast<std::int64_t>(static_cast<double>(census.group_count) /
                                              full_seconds)
                  : 0);

  if (!tsv.empty()) {
    std::FILE* out = std::fopen(tsv.c_str(), "wb");
    if (out == nullptr) {
      std::fprintf(stderr, "cannot write %s\n", tsv.c_str());
      return 1;
    }
    std::fprintf(out, "label\tmetric\tvalue\n");
    for (const Row& row : rows) {
      std::fprintf(out, "%s\t%s\t%s\n", label.c_str(), row.metric.c_str(), row.value.c_str());
    }
    if (std::fclose(out) != 0) {
      return 1;
    }
  }
  if (!census_path.empty()) {
    std::FILE* out = std::fopen(census_path.c_str(), "wb");
    if (out == nullptr) {
      std::fprintf(stderr, "cannot write %s\n", census_path.c_str());
      return 1;
    }
    std::fputs(census_tsv.c_str(), out);
    if (std::fclose(out) != 0) {
      return 1;
    }
  }
  return 0;
}
