// Fixtures CENSUS-1..CENSUS-9: the process separation of APPENDIX C4.
//
// SPEC: FINAL_PLAN.md APPENDIX C4, "Separation BY PROCESS (review F4): the
// feature BUILDER's fd census proves it never opens truth/; the TRAINER opens
// an explicit truth allowlist for loss computation only".
#include <fcntl.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

#include "emit_test_support.hpp"
#include "gtest/gtest.h"
#include "qr_emit/fd_census.hpp"
#include "qr_emit/shard_writer.hpp"

namespace {

using qr::emit::FdCensus;
using qr::emit::NpyDtype;
using qr::emit::OpenRecord;
using qr::emit::ProcessRole;
using qr::emit::Section;
using qr::emit::ShardSpec;
using qr::emit::ShardWriter;
using qr::emit::Side;
using qr_emit_test::read_file;
using qr_emit_test::scratch;

/// The census is process-wide by nature, so every fixture resets it.
class FdCensusTest : public ::testing::Test {
 protected:
  void SetUp() override { FdCensus::instance().reset_for_test(); }
  void TearDown() override { FdCensus::instance().reset_for_test(); }

  static bool recorded(const std::string& needle) {
    for (const OpenRecord& record : FdCensus::instance().records()) {
      if (record.path == needle) {
        return true;
      }
    }
    return false;
  }

  static bool recorded_refused_truth(const std::string& needle) {
    for (const OpenRecord& record : FdCensus::instance().records()) {
      if (record.path == needle && record.truth && record.refused) {
        return true;
      }
    }
    return false;
  }
};

TEST_F(FdCensusTest, TheInterposingDoorIsLinkedIntoThisBinary) {
  EXPECT_TRUE(qr::emit::fd_census_interposition_installed())
      << "without the interposing object the census sees only its own opens, which proves nothing";
}

TEST_F(FdCensusTest, ATruthComponentIsRecognisedWhereverItSits) {
  EXPECT_TRUE(qr::emit::path_has_truth_component("truth/menu_net_cent.npy"));
  EXPECT_TRUE(qr::emit::path_has_truth_component("/a/b/truth/menu_net_cent.npy"));
  EXPECT_TRUE(qr::emit::path_has_truth_component("features/../truth/x.npy"));
  EXPECT_TRUE(qr::emit::path_has_truth_component("/a/truth"));
  EXPECT_TRUE(qr::emit::path_has_truth_component("truth"));
  // Not truth: a component that merely CONTAINS the word.
  EXPECT_FALSE(qr::emit::path_has_truth_component("features/truthy.npy"));
  EXPECT_FALSE(qr::emit::path_has_truth_component("/a/untruth/x.npy"));
  EXPECT_FALSE(qr::emit::path_has_truth_component("/a/truth_v2/x.npy"));
  EXPECT_EQ(qr::emit::path_basename("/a/truth/menu.npy"), "menu.npy");
  EXPECT_EQ(qr::emit::path_basename("menu.npy"), "menu.npy");
}

TEST_F(FdCensusTest, RecordsPathsOpenedThroughStreamsStdioAndPosixAlike) {
  const std::filesystem::path dir = scratch("census_records");
  const std::string via_ofstream = (dir / "a.txt").string();
  const std::string via_ifstream = (dir / "b.txt").string();
  const std::string via_fopen = (dir / "c.txt").string();
  const std::string via_open = (dir / "d.txt").string();
  { std::ofstream seed(via_ifstream); seed << "seed\n"; }

  FdCensus::instance().begin(ProcessRole::UNSET);
  { std::ofstream stream(via_ofstream); stream << "x\n"; }
  { std::ifstream stream(via_ifstream); std::string line; std::getline(stream, line); }
  FILE* handle = std::fopen(via_fopen.c_str(), "wb");
  ASSERT_NE(handle, nullptr);
  std::fclose(handle);
  const int fd = ::open(via_open.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0644);
  ASSERT_GE(fd, 0);
  ::close(fd);

  EXPECT_TRUE(recorded(via_ofstream)) << "std::ofstream escaped the census";
  EXPECT_TRUE(recorded(via_ifstream)) << "std::ifstream escaped the census";
  EXPECT_TRUE(recorded(via_fopen)) << "fopen escaped the census";
  EXPECT_TRUE(recorded(via_open)) << "::open escaped the census";
  EXPECT_GE(FdCensus::instance().opens_seen(), 4U);
}

TEST_F(FdCensusTest, NothingIsRecordedBeforeTheRoleIsDeclared) {
  const std::filesystem::path dir = scratch("census_before_begin");
  const std::string early = (dir / "early.txt").string();
  { std::ofstream stream(early); stream << "x\n"; }
  EXPECT_TRUE(FdCensus::instance().records().empty());
  FdCensus::instance().begin(ProcessRole::UNSET);
  EXPECT_FALSE(recorded(early));
}

TEST_F(FdCensusTest, AFeatureBuilderIsRefusedAtTheDoorAndItsCensusFails) {
  const std::filesystem::path dir = scratch("census_builder_truth");
  std::filesystem::create_directories(dir / "truth");
  const std::string truth_leaf = (dir / "truth" / "menu_net_cent.npy").string();
  { std::ofstream seed(truth_leaf); seed << "not really a leaf\n"; }

  FdCensus::instance().begin(ProcessRole::FEATURE_BUILDER);
  ASSERT_TRUE(FdCensus::instance().verify_no_truth_opened().has_value())
      << "a builder that has touched nothing starts clean";

  errno = 0;
  const int fd = ::open(truth_leaf.c_str(), O_RDONLY);
  EXPECT_LT(fd, 0) << "a feature builder must be refused AT THE DOOR, not merely recorded";
  EXPECT_EQ(errno, EACCES);
  if (fd >= 0) {
    ::close(fd);
  }
  // std::ifstream is refused by the same door.
  std::ifstream stream(truth_leaf);
  EXPECT_FALSE(stream.is_open());

  EXPECT_TRUE(recorded_refused_truth(truth_leaf));
  auto refused = FdCensus::instance().verify_no_truth_opened();
  ASSERT_FALSE(refused.has_value()) << "the census must fail after a truth path is touched";
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::SOURCE_AUTHENTICATION_FAILED);
  EXPECT_EQ(FdCensus::instance().truth_records().size(), 2U);
}

TEST_F(FdCensusTest, AFeatureBuilderShardBuildNeverTouchesTruth) {
  const std::filesystem::path root = scratch("census_builder_shard");
  FdCensus::instance().begin(ProcessRole::FEATURE_BUILDER);

  ShardSpec spec;
  auto composed = qr::emit::c4_shard_dir(root, 125, Side::LONG);
  ASSERT_TRUE(composed.has_value());
  spec.publish_dir = composed.value();
  spec.session_ordinal = 125;
  spec.side = Side::LONG;
  spec.build_id = "wp10-builder-census";
  auto begun = ShardWriter::begin(spec);
  ASSERT_TRUE(begun.has_value()) << begun.error().message();
  std::unique_ptr<ShardWriter> writer = std::move(begun).value();
  const std::vector<std::int64_t> shape = {3, 2, 60};
  const std::vector<float> values(3 * 2 * 60, 0.25F);
  ASSERT_TRUE(
      writer->write_leaf<float>(Section::FEATURES, "direct_raw", NpyDtype::F4, shape, values)
          .has_value());
  ASSERT_TRUE(writer->publish().has_value());

  EXPECT_TRUE(FdCensus::instance().verify_no_truth_opened().has_value())
      << "the whole feature build must be truth-free";
  EXPECT_TRUE(FdCensus::instance().verify_open_fds_are_censused().has_value());
  EXPECT_GE(FdCensus::instance().opens_seen(), 2U);

  const std::filesystem::path receipt = root / "fd_census.tsv";
  ASSERT_TRUE(FdCensus::instance().write_census_tsv(receipt).has_value());
  const std::string text = read_file(receipt);
  EXPECT_NE(text.find("# qr_emit_fd_census_v1\trole\tFEATURE_BUILDER"), std::string::npos);
  EXPECT_NE(text.find("path\tfirst_sequence\topen_count\ttruth\trefused_count\n"),
            std::string::npos);
  EXPECT_EQ(text.find("\t1\t0\n"), std::string::npos) << "no row may be flagged truth";
}

TEST_F(FdCensusTest, ATrainerOpensItsExplicitAllowlistAndNothingElseUnderTruth) {
  const std::filesystem::path dir = scratch("census_trainer") / "s0125" / "L";
  std::filesystem::create_directories(dir / "truth");
  const std::string allowed = (dir / "truth" / "menu_net_cent.npy").string();
  const std::string denied = (dir / "truth" / "cert_net.npy").string();
  { std::ofstream seed(allowed); seed << "a\n"; }
  { std::ofstream seed(denied); seed << "b\n"; }

  FdCensus::instance().begin(ProcessRole::TRAINER);
  FdCensus::instance().set_truth_allowlist({"s0125/L/truth/menu_net_cent.npy"});
  EXPECT_EQ(FdCensus::instance().truth_allowlist().size(), 1U);

  const int good = ::open(allowed.c_str(), O_RDONLY);
  EXPECT_GE(good, 0) << "the allowlisted truth leaf is exactly what a trainer may read";
  if (good >= 0) {
    ::close(good);
  }
  EXPECT_TRUE(FdCensus::instance().verify_truth_allowlist_respected().has_value());

  errno = 0;
  const int bad = ::open(denied.c_str(), O_RDONLY);
  EXPECT_LT(bad, 0);
  EXPECT_EQ(errno, EACCES);
  if (bad >= 0) {
    ::close(bad);
  }
  auto refused = FdCensus::instance().verify_truth_allowlist_respected();
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::SOURCE_AUTHENTICATION_FAILED);
  // A trainer reading FEATURES is never restricted.
  const std::string feature = (dir / "direct_raw.npy").string();
  { std::ofstream seed(feature); seed << "f\n"; }
  const int fd = ::open(feature.c_str(), O_RDONLY);
  EXPECT_GE(fd, 0);
  if (fd >= 0) {
    ::close(fd);
  }
}

// ---------------------------------------------------------------------------
// THE FOLD WALL (card section 7(p), review F4/F5): "the trainer's truth
// allowlist matches SESSION-QUALIFIED paths (basename matching cannot bind the
// fold wall) and a per-session truth-open receipt is published".
// ---------------------------------------------------------------------------

TEST_F(FdCensusTest, TheSameLeafInAnotherSessionIsNotAdmittedByAQualifiedAllowlist) {
  // THE WHOLE POINT. `menu_net_cent.npy` is the same NAME in every session of
  // every fold, so a basename allowlist that lets a trainer read F4-TRAIN's copy
  // lets it read F4-TEST's copy too — the fold wall is a statement about
  // SESSIONS and a basename cannot make one.
  const std::filesystem::path base = scratch("census_fold_wall");
  const std::filesystem::path train = base / "s0125" / "L" / "truth";
  const std::filesystem::path test = base / "s0500" / "L" / "truth";
  std::filesystem::create_directories(train);
  std::filesystem::create_directories(test);
  const std::string in_fold = (train / "menu_net_cent.npy").string();
  const std::string across_the_wall = (test / "menu_net_cent.npy").string();
  { std::ofstream seed(in_fold); seed << "train\n"; }
  { std::ofstream seed(across_the_wall); seed << "test\n"; }

  FdCensus::instance().begin(ProcessRole::TRAINER);
  FdCensus::instance().set_truth_allowlist({"s0125/L/truth/menu_net_cent.npy"});

  const int allowed = ::open(in_fold.c_str(), O_RDONLY);
  EXPECT_GE(allowed, 0) << "the trainer's own fold's leaf must open";
  if (allowed >= 0) {
    ::close(allowed);
  }
  errno = 0;
  const int walled = ::open(across_the_wall.c_str(), O_RDONLY);
  EXPECT_LT(walled, 0) << "the SAME leaf name in a TEST session was admitted: the allowlist is "
                          "matching basenames, and a basename cannot bind the fold wall";
  EXPECT_EQ(errno, EACCES);
  if (walled >= 0) {
    ::close(walled);
  }
  const auto verdict = FdCensus::instance().verify_truth_allowlist_respected();
  ASSERT_FALSE(verdict.has_value());
  EXPECT_EQ(verdict.error().code(), qr::RefusalCode::SOURCE_AUTHENTICATION_FAILED);

  // The side is part of the scope too: the SHORT tape of the very same session
  // is a different shard and is not on the list.
  const std::filesystem::path other_side = base / "s0125" / "S" / "truth";
  std::filesystem::create_directories(other_side);
  const std::string short_leaf = (other_side / "menu_net_cent.npy").string();
  { std::ofstream seed(short_leaf); seed << "short\n"; }
  errno = 0;
  const int short_fd = ::open(short_leaf.c_str(), O_RDONLY);
  EXPECT_LT(short_fd, 0);
  if (short_fd >= 0) {
    ::close(short_fd);
  }
}

TEST_F(FdCensusTest, TheQualifiedLeafShapeAndItsSuffixMatchAreBothExact) {
  EXPECT_TRUE(qr::emit::is_session_qualified_truth_leaf("s0125/L/truth/menu_net_cent.npy"));
  EXPECT_TRUE(qr::emit::is_session_qualified_truth_leaf("s0749/S/truth/keys.npy"));
  // Everything a basename allowlist would have accepted:
  EXPECT_FALSE(qr::emit::is_session_qualified_truth_leaf("menu_net_cent.npy"));
  EXPECT_FALSE(qr::emit::is_session_qualified_truth_leaf("truth/menu_net_cent.npy"));
  EXPECT_FALSE(qr::emit::is_session_qualified_truth_leaf("s125/L/truth/x.npy"));
  EXPECT_FALSE(qr::emit::is_session_qualified_truth_leaf("s0125/X/truth/x.npy"));
  EXPECT_FALSE(qr::emit::is_session_qualified_truth_leaf("s0125/L/features/x.npy"));
  EXPECT_FALSE(qr::emit::is_session_qualified_truth_leaf("/s0125/L/truth/x.npy"));
  EXPECT_FALSE(qr::emit::is_session_qualified_truth_leaf("s0125/L/truth/sub/x.npy"));
  EXPECT_FALSE(qr::emit::is_session_qualified_truth_leaf("s0125/L/truth/"));

  const std::string entry = "s0125/L/truth/menu_net_cent.npy";
  EXPECT_TRUE(qr::emit::path_ends_with_qualified_leaf("/tapes/s0125/L/truth/menu_net_cent.npy",
                                                      entry));
  EXPECT_TRUE(qr::emit::path_ends_with_qualified_leaf(entry, entry));
  EXPECT_FALSE(qr::emit::path_ends_with_qualified_leaf("/tapes/s0500/L/truth/menu_net_cent.npy",
                                                       entry));
  // A component boundary, not a substring: `xs0125` is a different directory.
  EXPECT_FALSE(qr::emit::path_ends_with_qualified_leaf("/tapes/xs0125/L/truth/menu_net_cent.npy",
                                                       entry));
}

TEST_F(FdCensusTest, ThePerSessionTruthOpenReceiptIsPublishedAndKeepsTheSessionsApart) {
  const std::filesystem::path base = scratch("census_receipt");
  const std::filesystem::path train = base / "s0125" / "L" / "truth";
  const std::filesystem::path test = base / "s0500" / "L" / "truth";
  std::filesystem::create_directories(train);
  std::filesystem::create_directories(test);
  const std::string net = (train / "menu_net_cent.npy").string();
  const std::string mae = (train / "menu_mae_cent.npy").string();
  const std::string walled = (test / "menu_net_cent.npy").string();
  for (const std::string& path : {net, mae, walled}) {
    std::ofstream seed(path);
    seed << "x\n";
  }

  FdCensus::instance().begin(ProcessRole::TRAINER);
  FdCensus::instance().set_truth_allowlist(
      {"s0125/L/truth/menu_net_cent.npy", "s0125/L/truth/menu_mae_cent.npy"});
  for (const std::string& path : {net, net, mae, walled}) {
    const int fd = ::open(path.c_str(), O_RDONLY);
    if (fd >= 0) {
      ::close(fd);
    }
  }

  const std::vector<FdCensus::TruthOpenRow> rows = FdCensus::instance().truth_open_receipt();
  ASSERT_EQ(rows.size(), 3U);
  EXPECT_EQ(rows[0].session_scope, "s0125/L");
  EXPECT_EQ(rows[0].leaf, "menu_mae_cent.npy");
  EXPECT_EQ(rows[0].opens, 1);
  EXPECT_EQ(rows[0].refused, 0);
  EXPECT_EQ(rows[1].session_scope, "s0125/L");
  EXPECT_EQ(rows[1].leaf, "menu_net_cent.npy");
  EXPECT_EQ(rows[1].opens, 2) << "repeats are counted, not collapsed";
  EXPECT_EQ(rows[2].session_scope, "s0500/L");
  EXPECT_EQ(rows[2].leaf, "menu_net_cent.npy");
  EXPECT_EQ(rows[2].refused, 1) << "the walled session's open is in the receipt AND refused";

  const std::filesystem::path receipt = base / "truth_open_receipt.tsv";
  ASSERT_TRUE(FdCensus::instance().write_truth_open_receipt_tsv(receipt).has_value());
  const std::string text = read_file(receipt);
  EXPECT_NE(text.find("# qr_emit_truth_open_receipt_v1\trole\tTRAINER\ttruth_opens\t4\n"),
            std::string::npos);
  EXPECT_NE(text.find("session_scope\tleaf\topens\trefused\n"), std::string::npos);
  EXPECT_NE(text.find("s0125/L\tmenu_net_cent.npy\t2\t0\n"), std::string::npos);
  EXPECT_NE(text.find("s0500/L\tmenu_net_cent.npy\t1\t1\n"), std::string::npos);
  // A second write onto the same path never replaces a published receipt.
  EXPECT_FALSE(FdCensus::instance().write_truth_open_receipt_tsv(receipt).has_value());
}

TEST_F(FdCensusTest, AFeatureBuildersTruthOpenReceiptIsEmptyWhichIsItsWholeClaim) {
  const std::filesystem::path base = scratch("census_receipt_builder");
  std::filesystem::create_directories(base);
  FdCensus::instance().begin(ProcessRole::FEATURE_BUILDER);
  const std::string feature = (base / "direct_raw.npy").string();
  { std::ofstream seed(feature); seed << "f\n"; }
  const int fd = ::open(feature.c_str(), O_RDONLY);
  if (fd >= 0) {
    ::close(fd);
  }
  EXPECT_TRUE(FdCensus::instance().truth_open_receipt().empty());
  const std::filesystem::path receipt = base / "truth_open_receipt.tsv";
  ASSERT_TRUE(FdCensus::instance().write_truth_open_receipt_tsv(receipt).has_value());
  const std::string text = read_file(receipt);
  EXPECT_NE(text.find("truth_opens\t0\n"), std::string::npos);
}

TEST_F(FdCensusTest, TheProcSweepCatchesADescriptorTheDoorNeverSaw) {
  const std::filesystem::path dir = scratch("census_sweep");
  const std::string path = (dir / "smuggled.bin").string();
  { std::ofstream seed(path); seed << "smuggled\n"; }

  FdCensus::instance().begin(ProcessRole::FEATURE_BUILDER);
  ASSERT_TRUE(FdCensus::instance().verify_open_fds_are_censused().has_value());

  // Straight to the kernel: no PLT, no door, no record.
  const int smuggled = static_cast<int>(::syscall(SYS_openat, AT_FDCWD, path.c_str(), O_RDONLY, 0));
  ASSERT_GE(smuggled, 0);
  auto refused = FdCensus::instance().verify_open_fds_are_censused();
  ASSERT_FALSE(refused.has_value()) << "an uncensused open descriptor must fail the sweep";
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::SOURCE_AUTHENTICATION_FAILED);
  EXPECT_EQ(refused.error().context(), smuggled) << "the refusal names the descriptor";

  ::close(smuggled);
  EXPECT_TRUE(FdCensus::instance().verify_open_fds_are_censused().has_value());
}

TEST_F(FdCensusTest, TheCensusReceiptIsSortedDeterministicAndCountsRepeats) {
  const std::filesystem::path dir = scratch("census_receipt");
  const std::string a = (dir / "a.bin").string();
  const std::string b = (dir / "b.bin").string();
  { std::ofstream seed(a); seed << "a\n"; }
  { std::ofstream seed(b); seed << "b\n"; }

  FdCensus::instance().begin(ProcessRole::UNSET);
  for (int repeat = 0; repeat < 3; ++repeat) {
    const int fd = ::open(b.c_str(), O_RDONLY);
    ASSERT_GE(fd, 0);
    ::close(fd);
  }
  const int fd = ::open(a.c_str(), O_RDONLY);
  ASSERT_GE(fd, 0);
  ::close(fd);

  ASSERT_TRUE(FdCensus::instance().write_census_tsv(dir / "one.tsv").has_value());
  ASSERT_TRUE(FdCensus::instance().write_census_tsv(dir / "two.tsv").has_value());
  const std::string first = read_file(dir / "one.tsv");
  EXPECT_EQ(first, read_file(dir / "two.tsv")) << "two receipts of one census must be identical";
  const std::size_t position_a = first.find(a + "\t");
  const std::size_t position_b = first.find(b + "\t");
  ASSERT_NE(position_a, std::string::npos);
  ASSERT_NE(position_b, std::string::npos);
  EXPECT_LT(position_a, position_b) << "receipt rows are sorted by path";
  EXPECT_NE(first.find(b + "\t1\t3\t0\t0\n"), std::string::npos)
      << "three opens of one path are one row with an open_count of 3";
  // Writing the receipt may not census itself.
  EXPECT_EQ(first.find((dir / "one.tsv").string()), std::string::npos);
}

TEST_F(FdCensusTest, RefusingAnOpenNeverCreatesTheFile) {
  const std::filesystem::path dir = scratch("census_no_create");
  std::filesystem::create_directories(dir / "truth");
  const std::string leaf = (dir / "truth" / "new_leaf.npy").string();
  FdCensus::instance().begin(ProcessRole::FEATURE_BUILDER);
  errno = 0;
  const int fd = ::open(leaf.c_str(), O_WRONLY | O_CREAT | O_EXCL, 0644);
  EXPECT_LT(fd, 0);
  EXPECT_EQ(errno, EACCES);
  if (fd >= 0) {
    ::close(fd);
  }
  EXPECT_FALSE(std::filesystem::exists(leaf))
      << "a refused create must not leave a file behind";
}

TEST_F(FdCensusTest, TheBuilderPhaseIsTaggedAndTheEmitStepWritesBothSections) {
  // THE TOPOLOGY (orchestrator ruling, 2026-08-10): feature CONSTRUCTION runs
  // in a FEATURE_BUILDER-tagged process that provably never opens truth/, and
  // hands its arrays to ONE untagged emit step that writes both sections in a
  // single publish — one manifest, one no-replace rename.
  const std::filesystem::path root = scratch("topology");
  const std::filesystem::path handoff = root / "constructed_direct_raw.bin";
  const std::filesystem::path receipt_path = root / "builder_fd_census.tsv";
  constexpr std::size_t kRows = 4;
  constexpr std::size_t kElements = kRows * 3 * 60;

  // --- phase 1: the tagged constructor, in its own process -----------------
  const pid_t child = ::fork();
  ASSERT_GE(child, 0);
  if (child == 0) {
    FdCensus::instance().begin(ProcessRole::FEATURE_BUILDER);
    std::vector<float> constructed(kElements);
    for (std::size_t index = 0; index < kElements; ++index) {
      constructed[index] = static_cast<float>(index % 4096) / 8.0F;
    }
    {
      std::ofstream out(handoff, std::ios::binary);
      out.write(reinterpret_cast<const char*>(constructed.data()),
                static_cast<std::streamsize>(constructed.size() * sizeof(float)));
      if (!out) {
        ::_exit(2);
      }
    }
    if (!FdCensus::instance().verify_no_truth_opened()) {
      ::_exit(3);
    }
    if (!FdCensus::instance().verify_open_fds_are_censused()) {
      ::_exit(4);
    }
    if (!FdCensus::instance().write_census_tsv(receipt_path)) {
      ::_exit(5);
    }
    ::_exit(0);
  }
  int status = 0;
  ASSERT_EQ(::waitpid(child, &status, 0), child);
  ASSERT_TRUE(WIFEXITED(status));
  ASSERT_EQ(WEXITSTATUS(status), 0) << "the tagged construction phase did not finish clean";

  // Its census receipt is the proof, and it is a file the emit step can keep.
  const std::string receipt = read_file(receipt_path);
  ASSERT_NE(receipt.find("# qr_emit_fd_census_v1\trole\tFEATURE_BUILDER"), std::string::npos);
  std::size_t data_rows = 0;
  std::size_t line_start = receipt.find("path\tfirst_sequence");
  ASSERT_NE(line_start, std::string::npos);
  line_start = receipt.find('\n', line_start) + 1;
  while (line_start < receipt.size()) {
    const std::size_t line_end = receipt.find('\n', line_start);
    if (line_end == std::string::npos) {
      break;
    }
    const std::string line = receipt.substr(line_start, line_end - line_start);
    std::vector<std::string> fields;
    std::size_t field_start = 0;
    while (true) {
      const std::size_t tab = line.find('\t', field_start);
      fields.push_back(line.substr(field_start, tab - field_start));
      if (tab == std::string::npos) {
        break;
      }
      field_start = tab + 1;
    }
    ASSERT_EQ(fields.size(), 5U) << line;
    EXPECT_EQ(fields.at(3), "0") << "the construction phase touched a truth path: " << line;
    ++data_rows;
    line_start = line_end + 1;
  }
  EXPECT_GT(data_rows, 0U) << "the builder's census recorded nothing at all";

  // --- phase 2: ONE untagged emit step, BOTH sections, one publish ---------
  EXPECT_EQ(FdCensus::instance().role(), ProcessRole::UNSET)
      << "the emit step is untagged; only the construction phase is tagged";
  std::vector<float> handed(kElements);
  {
    std::ifstream in(handoff, std::ios::binary);
    in.read(reinterpret_cast<char*>(handed.data()),
            static_cast<std::streamsize>(handed.size() * sizeof(float)));
    ASSERT_TRUE(in.good() || in.eof());
  }

  ShardSpec spec;
  auto composed = qr::emit::c4_shard_dir(root / "tapes", 125, Side::LONG);
  ASSERT_TRUE(composed.has_value());
  spec.publish_dir = composed.value();
  spec.session_ordinal = 125;
  spec.side = Side::LONG;
  spec.build_id = "wp10-topology";
  auto begun = ShardWriter::begin(spec);
  ASSERT_TRUE(begun.has_value()) << begun.error().message();
  std::unique_ptr<ShardWriter> writer = std::move(begun).value();

  const std::vector<std::int64_t> feature_shape = {static_cast<std::int64_t>(kRows), 3, 60};
  ASSERT_TRUE(writer
                  ->write_leaf<float>(Section::FEATURES, "direct_raw", NpyDtype::F4,
                                      feature_shape, handed)
                  .has_value());
  const std::vector<std::int64_t> menu_shape = {static_cast<std::int64_t>(kRows), 7};
  const std::vector<std::int64_t> menu(kRows * 7, -30000);
  ASSERT_TRUE(writer
                  ->write_leaf<std::int64_t>(Section::TRUTH, "menu_net_cent", NpyDtype::I8,
                                             menu_shape, menu)
                  .has_value());
  auto published = writer->publish();
  ASSERT_TRUE(published.has_value()) << published.error().message();

  const std::filesystem::path shard = composed.value();
  EXPECT_EQ(shard.filename().string(), "L");
  EXPECT_EQ(shard.parent_path().filename().string(), "s0125");
  EXPECT_TRUE(std::filesystem::is_regular_file(shard / "features" / "direct_raw.npy"));
  EXPECT_TRUE(std::filesystem::is_regular_file(shard / "truth" / "menu_net_cent.npy"));
  EXPECT_EQ(qr_emit_test::sorted_files(shard),
            (std::vector<std::string>{"features/direct_raw.npy", "manifest.tsv",
                                      "truth/menu_net_cent.npy"}))
      << "one publish, one manifest, both sections";
  int stage_dirs = 0;
  for (const auto& entry : std::filesystem::directory_iterator(shard.parent_path())) {
    if (entry.path().filename().string().rfind(".", 0) == 0) {
      ++stage_dirs;
    }
  }
  EXPECT_EQ(stage_dirs, 0) << "the single rename moved the stage directory";
  // The emit step wrote truth/ and is untagged, so its own census is silent
  // about roles — the proof for the phase that matters is the builder receipt.
  EXPECT_TRUE(FdCensus::instance().records().empty());
}

}  // namespace
