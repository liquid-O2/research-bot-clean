// qr_census_compare — the WP9 comparator.
//
// SPEC (WP9 brief): "(e) comparator emits verdict.tsv (field, oracle_value,
//   cpp_value, verdict PASS/FAIL/WAIVED, waiver_id) — sole legal waiver WCD-1;
//   any other delta = FAIL nonzero exit".
//
// usage: qr_census_compare --cpp PATH --rust PATH --out PATH [--max-print N]
#include <cstdio>
#include <cstdlib>
#include <string>

#include "qr_census/verdict.hpp"

namespace {

int usage() {
  std::fprintf(stderr,
               "usage: qr_census_compare --cpp PATH --rust PATH --out PATH [--max-print N]\n"
               "       qr_census_compare --verify PATH --sha HEX\n"
               "       qr_census_compare --sha-of PATH\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  std::string cpp_path;
  std::string rust_path;
  std::string out_path;
  std::string verify_path;
  std::string sha_of_path;
  std::string expected_sha;
  long max_print = 50;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    const bool has_value = index + 1 < argc;
    if (flag == "--cpp" && has_value) {
      cpp_path = argv[++index];
    } else if (flag == "--rust" && has_value) {
      rust_path = argv[++index];
    } else if (flag == "--out" && has_value) {
      out_path = argv[++index];
    } else if (flag == "--verify" && has_value) {
      verify_path = argv[++index];
    } else if (flag == "--sha" && has_value) {
      expected_sha = argv[++index];
    } else if (flag == "--sha-of" && has_value) {
      sha_of_path = argv[++index];
    } else if (flag == "--max-print" && has_value) {
      max_print = std::strtol(argv[++index], nullptr, 10);
    } else {
      return usage();
    }
  }

  // --- the archive re-check the merge gate runs -----------------------------
  if (!sha_of_path.empty()) {
    auto sha = qr::census::file_sha256(sha_of_path);
    if (!sha.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", sha.error().message().c_str());
      return 1;
    }
    std::printf("%s\n", sha.value().c_str());
    return 0;
  }
  if (!verify_path.empty()) {
    if (expected_sha.empty()) {
      return usage();
    }
    auto summary = qr::census::verify_archive(verify_path, expected_sha);
    if (!summary.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", summary.error().message().c_str());
      return 1;
    }
    std::printf("archive_sha256 %s\nverdict_rows %lld\npass %lld\nfail %lld\nwaived %lld\n"
                "census %lld\nnot_compared %lld\n",
                summary.value().sha256.c_str(), static_cast<long long>(summary.value().rows),
                static_cast<long long>(summary.value().pass),
                static_cast<long long>(summary.value().fail),
                static_cast<long long>(summary.value().waived),
                static_cast<long long>(summary.value().census),
                static_cast<long long>(summary.value().not_compared));
    return summary.value().fail == 0 ? 0 : 1;
  }

  if (cpp_path.empty() || rust_path.empty() || out_path.empty()) {
    return usage();
  }

  auto cpp_dump = qr::census::load_dump(cpp_path);
  if (!cpp_dump.has_value()) {
    std::fprintf(stderr, "REFUSED (cpp dump): %s\n", cpp_dump.error().message().c_str());
    return 1;
  }
  auto rust_dump = qr::census::load_dump(rust_path);
  if (!rust_dump.has_value()) {
    std::fprintf(stderr, "REFUSED (rust dump): %s\n", rust_dump.error().message().c_str());
    return 1;
  }

  const qr::census::VerdictReport report =
      qr::census::compare_dumps(cpp_dump.value(), rust_dump.value());
  const std::string tsv = report.to_tsv();
  std::FILE* out = std::fopen(out_path.c_str(), "wb");
  if (out == nullptr) {
    std::fprintf(stderr, "cannot write %s\n", out_path.c_str());
    return 1;
  }
  std::fwrite(tsv.data(), 1, tsv.size(), out);
  const bool write_failed = std::ferror(out) != 0;
  if (std::fclose(out) != 0 || write_failed) {
    std::fprintf(stderr, "the verdict could not be written to the end\n");
    return 1;
  }

  long printed = 0;
  for (const qr::census::VerdictRow& row : report.rows) {
    if (row.verdict != qr::census::Verdict::FAIL) {
      continue;
    }
    if (printed < max_print) {
      std::fprintf(stderr, "FAIL\t%s\toracle=%s\tcpp=%s\n", row.field.c_str(),
                   row.oracle_value.c_str(), row.cpp_value.c_str());
    }
    ++printed;
  }
  if (printed > max_print) {
    std::fprintf(stderr, "... %ld further FAIL rows, all in %s\n", printed - max_print,
                 out_path.c_str());
  }

  std::printf("verdict_rows %zu\npass %lld\nfail %lld\nwaived %lld\ncensus %lld\nnot_compared %lld\n",
              report.rows.size(), static_cast<long long>(report.pass),
              static_cast<long long>(report.fail), static_cast<long long>(report.waived),
              static_cast<long long>(report.census), static_cast<long long>(report.not_compared));
  return report.green() ? 0 : 1;
}
