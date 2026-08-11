// Fixture CENSUS-1..CENSUS-3: the WP0 dialect census tool.
//
// CENSUS-1 is the truncated-footer fixture named in the WP1 brief: an
// unreadable file must get its OWN census row carrying its reason, the tool
// must make that loud through a nonzero exit status, and it must not crash.
// CENSUS-2 proves a readable file in the SAME run still censuses correctly
// (so "unreadable" is not a blanket failure), and CENSUS-3 proves the output
// is byte-identical across two runs.
#include <sys/wait.h>

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "gtest/gtest.h"

namespace {

namespace fs = std::filesystem;

struct RunResult {
  int exit_status;
  bool exited_normally;
};

RunResult run_census(const fs::path& root_spec, const fs::path& out_dir) {
  std::ostringstream command;
  command << QR_PYTHON3 << " " << QR_CENSUS_TOOL << " --root '" << root_spec.string() << "'"
          << " --out-dir '" << out_dir.string() << "' --workers 1 > '"
          << (out_dir / "stdout.log").string() << "' 2>&1";
  const int raw = std::system(command.str().c_str());
  if (raw == -1) {
    return RunResult{-1, false};
  }
  const bool normal = WIFEXITED(raw);
  return RunResult{normal ? WEXITSTATUS(raw) : -1, normal};
}

std::string read_file(const fs::path& path) {
  std::ifstream stream(path, std::ios::binary);
  return std::string(std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>());
}

/// A census root laid out the way the corpora are: <root>/<year>/<file>.
fs::path build_fixture_root(const std::string& name, bool include_readable) {
  const fs::path root = fs::path(QR_TEST_SCRATCH_DIR) / "census" / name;
  fs::remove_all(root);
  fs::create_directories(root / "2022");
  for (const char* bad :
       {"truncated_footer.parquet", "missing_magic.parquet", "garbage_footer.parquet"}) {
    fs::copy_file(fs::path(QR_FIXTURE_DIR) / "parquet" / bad, root / "2022" / bad,
                  fs::copy_options::overwrite_existing);
  }
  if (include_readable) {
    // A real, readable corpus file, linked (never copied) next to the broken
    // ones. Only its footer is ever read.
    const fs::path real = "/workspace/data/tokens/stock_quotes/IWM/2022/2022-07-05.parquet";
    if (fs::is_regular_file(real)) {
      fs::create_symlink(real, root / "2022" / "readable.parquet");
    }
  }
  return root;
}

TEST(DialectCensusTool, UnreadableFileGetsItsOwnRowWithAReasonAndNeverCrashes) {
  const fs::path root = build_fixture_root("unreadable_only", false);
  const fs::path out_dir = fs::path(QR_TEST_SCRATCH_DIR) / "census" / "out_unreadable";
  fs::remove_all(out_dir);
  fs::create_directories(out_dir);

  const RunResult result = run_census("fixture=" + root.string(), out_dir);
  ASSERT_TRUE(result.exited_normally) << "the census tool crashed instead of reporting";
  EXPECT_EQ(result.exit_status, 2) << "unreadable files must be loud (exit status 2)";

  const std::string census = read_file(out_dir / "dialect_census.tsv");
  const std::string unreadable = read_file(out_dir / "dialect_census_unreadable.tsv");
  ASSERT_FALSE(census.empty());

  for (const char* reason : {"footer length exceeds file size", "missing trailing PAR1 magic",
                             "unknown thrift type"}) {
    EXPECT_NE(census.find(reason), std::string::npos)
        << "census row is missing the reason: " << reason;
  }
  for (const char* name :
       {"truncated_footer.parquet", "missing_magic.parquet", "garbage_footer.parquet"}) {
    EXPECT_NE(unreadable.find(name), std::string::npos)
        << "unreadable companion file never named " << name;
  }
  // Three distinct unreadable rows, one per file, none of them silently merged
  // into a readable dialect row.
  std::size_t rows = 0;
  std::istringstream lines(census);
  std::string line;
  while (std::getline(lines, line)) {
    if (line.find("__UNREADABLE__") != std::string::npos) {
      ++rows;
    }
  }
  EXPECT_EQ(rows, 3U);
}

TEST(DialectCensusTool, ReadableFileInTheSameRunStillCensusesItsDialect) {
  const fs::path root = build_fixture_root("mixed", true);
  ASSERT_TRUE(fs::exists(root / "2022" / "readable.parquet"))
      << "pinned corpus file for the positive control is missing";
  const fs::path out_dir = fs::path(QR_TEST_SCRATCH_DIR) / "census" / "out_mixed";
  fs::remove_all(out_dir);
  fs::create_directories(out_dir);

  const RunResult result = run_census("fixture=" + root.string(), out_dir);
  ASSERT_TRUE(result.exited_normally);
  EXPECT_EQ(result.exit_status, 2);

  const std::string census = read_file(out_dir / "dialect_census.tsv");
  EXPECT_NE(census.find("ZSTD"), std::string::npos) << "the readable file's codec is missing";
  EXPECT_NE(census.find("__UNREADABLE__"), std::string::npos)
      << "the broken files vanished from the census";
  EXPECT_EQ(census.find("UNCOMPRESSED"), std::string::npos);
}

TEST(DialectCensusTool, TwoRunsAreByteIdentical) {
  const fs::path root = build_fixture_root("identity", true);
  const fs::path out_a = fs::path(QR_TEST_SCRATCH_DIR) / "census" / "identity_a";
  const fs::path out_b = fs::path(QR_TEST_SCRATCH_DIR) / "census" / "identity_b";
  for (const fs::path& dir : {out_a, out_b}) {
    fs::remove_all(dir);
    fs::create_directories(dir);
  }

  ASSERT_TRUE(run_census("fixture=" + root.string(), out_a).exited_normally);
  ASSERT_TRUE(run_census("fixture=" + root.string(), out_b).exited_normally);

  EXPECT_EQ(read_file(out_a / "dialect_census.tsv"), read_file(out_b / "dialect_census.tsv"));
  EXPECT_EQ(read_file(out_a / "dialect_census_unreadable.tsv"),
            read_file(out_b / "dialect_census_unreadable.tsv"));
  EXPECT_FALSE(read_file(out_a / "dialect_census.tsv").empty());
}

}  // namespace
