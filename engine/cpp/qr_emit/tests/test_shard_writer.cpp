// Fixtures SHARD-1..SHARD-12: the C4 directory layout, the manifest, the
// no-replace publish, and the two identity laws.
//
// SPEC: FINAL_PLAN.md APPENDIX C4 ("manifest.tsv (path,dtype,shape,rows,sha256
// + sources + census + build id)") + FINAL_PLAN section 6 Laws ("two-run byte
// identity inside EVERY WP acceptance ... sorted dir iteration").
#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <string>
#include <utility>
#include <vector>

#include "emit_test_support.hpp"
#include "gtest/gtest.h"
#include "qr_emit/shard_writer.hpp"

namespace {

using qr::emit::NpyDtype;
using qr::emit::Section;
using qr::emit::ShardSpec;
using qr::emit::ShardWriter;
using qr::emit::Side;
using qr_emit_test::read_file;
using qr_emit_test::scratch;

/// The C4 shard path for `base`: `<base>/s0125/L` (orchestrator ruling).
std::filesystem::path shard_dir(const std::filesystem::path& base, std::int64_t ordinal = 125,
                                Side side = Side::LONG) {
  auto composed = qr::emit::c4_shard_dir(base, ordinal, side);
  EXPECT_TRUE(composed.has_value());
  return composed.has_value() ? composed.value() : base;
}

ShardSpec spec_for(const std::filesystem::path& base, std::int64_t ordinal = 125,
                   Side side = Side::LONG) {
  ShardSpec spec;
  spec.publish_dir = shard_dir(base, ordinal, side);
  spec.session_ordinal = ordinal;
  spec.side = side;
  spec.build_id = "wp10-fixture-build";
  spec.sources = {
      {"stock_quotes", "aa11", "/workspace/data/tokens/stock_quotes/IWM/s125.parquet"},
      {"registry", "233dc10a", "engine/crates/corpus/registry/accepted_compact_sessions.tsv"},
  };
  spec.census = {{"dialect_census", "63557a43", "artifacts/cache/cpp/dialect_census.tsv"}};
  return spec;
}

/// The tiny C4-shaped tape used by most fixtures. `reversed` emits the same
/// leaf SET in the opposite order, which must not change a single published
/// byte.
void write_tape(ShardWriter& writer, bool reversed, bool with_truth = true) {
  const std::vector<float> direct_raw(3 * 2 * 60, 0.5F);
  const std::vector<std::int64_t> group_ts = {1, 2, 3, 4};
  const std::vector<std::int64_t> menu = std::vector<std::int64_t>(3 * 7, -42);
  const std::vector<std::uint8_t> barrier = {0, 1, 2};

  struct Step {
    Section section;
    const char* name;
  };
  std::vector<Step> steps = {{Section::FEATURES, "direct_raw"}, {Section::FEATURES, "group_ts"}};
  if (with_truth) {
    steps.push_back({Section::TRUTH, "menu_net_cent"});
    steps.push_back({Section::TRUTH, "barrier"});
  }
  if (reversed) {
    std::reverse(steps.begin(), steps.end());
  }
  for (const Step& step : steps) {
    const std::string name(step.name);
    if (name == "direct_raw") {
      const std::vector<std::int64_t> shape = {3, 2, 60};
      ASSERT_TRUE(writer.write_leaf<float>(step.section, name, NpyDtype::F4, shape, direct_raw)
                      .has_value());
    } else if (name == "group_ts") {
      const std::vector<std::int64_t> shape = {4};
      ASSERT_TRUE(
          writer.write_leaf<std::int64_t>(step.section, name, NpyDtype::I8, shape, group_ts)
              .has_value());
    } else if (name == "menu_net_cent") {
      const std::vector<std::int64_t> shape = {3, 7};
      ASSERT_TRUE(writer.write_leaf<std::int64_t>(step.section, name, NpyDtype::I8, shape, menu)
                      .has_value());
    } else {
      const std::vector<std::int64_t> shape = {3};
      ASSERT_TRUE(writer.write_leaf<std::uint8_t>(step.section, name, NpyDtype::U1, shape, barrier)
                      .has_value());
    }
  }
}

TEST(ShardLayout, PublishesTheAppendixC4DirectoryLayout) {
  const std::filesystem::path root = scratch("shard_layout");
  auto begun = ShardWriter::begin(spec_for(root));
  ASSERT_TRUE(begun.has_value()) << begun.error().message();
  std::unique_ptr<ShardWriter> writer = std::move(begun).value();
  write_tape(*writer, false);
  auto receipt = writer->publish();
  ASSERT_TRUE(receipt.has_value()) << receipt.error().message();

  const std::filesystem::path shard = shard_dir(root);
  EXPECT_TRUE(std::filesystem::is_directory(shard / "features"));
  EXPECT_TRUE(std::filesystem::is_directory(shard / "truth"));
  EXPECT_TRUE(std::filesystem::is_regular_file(shard / "manifest.tsv"));
  EXPECT_EQ(qr_emit_test::sorted_files(shard),
            (std::vector<std::string>{"features/direct_raw.npy", "features/group_ts.npy",
                                      "manifest.tsv", "truth/barrier.npy",
                                      "truth/menu_net_cent.npy"}));
  EXPECT_EQ(receipt.value().leaf_count, 4);
  // The stage directory is gone: the publish MOVED it, it did not copy it.
  int staged = 0;
  for (const auto& entry : std::filesystem::directory_iterator(shard.parent_path())) {
    if (entry.path().filename().string().rfind(".", 0) == 0) {
      ++staged;
    }
  }
  EXPECT_EQ(staged, 0);
}

TEST(ShardManifest, CarriesEveryC4FieldForEveryLeaf) {
  const std::filesystem::path root = scratch("shard_manifest");
  auto begun = ShardWriter::begin(spec_for(root));
  ASSERT_TRUE(begun.has_value());
  std::unique_ptr<ShardWriter> writer = std::move(begun).value();
  write_tape(*writer, false);
  auto receipt = writer->publish();
  ASSERT_TRUE(receipt.has_value());

  const std::string manifest = read_file(shard_dir(root) / "manifest.tsv");
  EXPECT_EQ(qr_emit_test::sha256_hex(manifest), receipt.value().manifest_sha256);
  EXPECT_NE(manifest.find("meta\tbuild_id\twp10-fixture-build\n"), std::string::npos);
  EXPECT_NE(manifest.find("meta\tsession_ordinal\t125\n"), std::string::npos);
  EXPECT_NE(manifest.find("meta\tside\tLONG\n"), std::string::npos);
  EXPECT_NE(manifest.find("meta\tleaf_count\t4\n"), std::string::npos);
  EXPECT_NE(manifest.find("source\tregistry\t233dc10a\t"), std::string::npos);
  EXPECT_NE(manifest.find("census\tdialect_census\t63557a43\t"), std::string::npos);

  // path, dtype, shape, rows, sha256 — the five C4 leaf columns, and the sha is
  // the sha of the file on disk.
  for (const qr::emit::NpyLeafReceipt& leaf : receipt.value().leaves) {
    const std::string row = std::string("leaf\t") + leaf.rel_path + "\t" +
                            qr::emit::npy_dtype_descr(leaf.dtype) + "\t";
    EXPECT_NE(manifest.find(row), std::string::npos) << leaf.rel_path;
    EXPECT_NE(manifest.find("\t" + leaf.sha256 + "\n"), std::string::npos) << leaf.rel_path;
    EXPECT_EQ(leaf.sha256, qr_emit_test::sha256_hex(read_file(shard_dir(root) / leaf.rel_path)));
  }
  EXPECT_NE(manifest.find("leaf\tfeatures/direct_raw.npy\t<f4\t3,2,60\t3\t"), std::string::npos);
  EXPECT_NE(manifest.find("leaf\ttruth/menu_net_cent.npy\t<i8\t3,7\t3\t"), std::string::npos);
}

TEST(ShardManifest, RowsAreSortedAndIndependentOfEmissionOrder) {
  const std::filesystem::path root = scratch("shard_order");
  std::vector<std::string> manifests;
  for (const bool reversed : {false, true}) {
    const std::filesystem::path base = root / (reversed ? "reversed" : "forward");
    auto begun = ShardWriter::begin(spec_for(base));
    ASSERT_TRUE(begun.has_value());
    std::unique_ptr<ShardWriter> writer = std::move(begun).value();
    write_tape(*writer, reversed);
    ASSERT_TRUE(writer->publish().has_value());
    manifests.push_back(read_file(shard_dir(base) / "manifest.tsv"));
  }
  EXPECT_EQ(manifests.at(0), manifests.at(1))
      << "published bytes must be a function of the leaf SET, not of emission order";

  // And the leaf rows really are in sorted path order.
  const std::string& manifest = manifests.at(0);
  const std::size_t direct = manifest.find("leaf\tfeatures/direct_raw.npy");
  const std::size_t group = manifest.find("leaf\tfeatures/group_ts.npy");
  const std::size_t barrier = manifest.find("leaf\ttruth/barrier.npy");
  const std::size_t menu = manifest.find("leaf\ttruth/menu_net_cent.npy");
  ASSERT_NE(direct, std::string::npos);
  EXPECT_LT(direct, group);
  EXPECT_LT(group, barrier);
  EXPECT_LT(barrier, menu);
}

TEST(ShardIdentity, TwoRunsAreByteIdenticalIncludingTheManifest) {
  const std::filesystem::path root = scratch("shard_identity");
  std::vector<std::filesystem::path> shards;
  for (const char* run : {"run_a", "run_b"}) {
    const std::filesystem::path base = root / run;
    auto begun = ShardWriter::begin(spec_for(base));
    ASSERT_TRUE(begun.has_value());
    std::unique_ptr<ShardWriter> writer = std::move(begun).value();
    write_tape(*writer, false);
    ASSERT_TRUE(writer->publish().has_value());
    shards.push_back(shard_dir(base));
  }
  const std::vector<std::string> files_a = qr_emit_test::sorted_files(shards.at(0));
  const std::vector<std::string> files_b = qr_emit_test::sorted_files(shards.at(1));
  ASSERT_EQ(files_a, files_b);
  ASSERT_FALSE(files_a.empty());
  for (const std::string& relative : files_a) {
    EXPECT_EQ(read_file(shards.at(0) / relative), read_file(shards.at(1) / relative)) << relative;
  }
}

TEST(ShardPublish, RefusesToReplaceAnAlreadyPublishedShard) {
  const std::filesystem::path root = scratch("shard_noreplace");
  const std::filesystem::path publish = shard_dir(root / "first");
  auto first = ShardWriter::begin(spec_for(root / "first"));
  ASSERT_TRUE(first.has_value());
  std::unique_ptr<ShardWriter> writer = std::move(first).value();
  write_tape(*writer, false);
  ASSERT_TRUE(writer->publish().has_value());
  const std::string manifest_before = read_file(publish / "manifest.tsv");

  // begin() refuses outright, which is the cheap wall...
  auto second = ShardWriter::begin(spec_for(root / "first"));
  ASSERT_FALSE(second.has_value());
  EXPECT_EQ(second.error().code(), qr::RefusalCode::IO);

  // ...and the rename is the real one: publish onto a path that appeared after
  // begin() must still refuse, and must leave the published bytes untouched.
  const std::filesystem::path racing = shard_dir(root / "racing");
  auto third = ShardWriter::begin(spec_for(root / "racing"));
  ASSERT_TRUE(third.has_value());
  std::unique_ptr<ShardWriter> racer = std::move(third).value();
  write_tape(*racer, false);
  std::filesystem::create_directories(racing);
  auto refused = racer->publish();
  ASSERT_FALSE(refused.has_value()) << "RENAME_NOREPLACE must refuse an occupied destination";
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::IO);
  EXPECT_TRUE(std::filesystem::is_directory(racer->stage_dir()))
      << "a refused publish leaves the stage directory intact for forensics";
  EXPECT_EQ(read_file(publish / "manifest.tsv"), manifest_before);
}

TEST(ShardPublish, NothingIsVisibleAtThePublishPathBeforePublish) {
  const std::filesystem::path root = scratch("shard_staged");
  const std::filesystem::path publish = shard_dir(root);
  auto begun = ShardWriter::begin(spec_for(root));
  ASSERT_TRUE(begun.has_value());
  std::unique_ptr<ShardWriter> writer = std::move(begun).value();
  write_tape(*writer, false);
  EXPECT_FALSE(std::filesystem::exists(publish));
  EXPECT_TRUE(std::filesystem::is_directory(writer->stage_dir()));
  EXPECT_TRUE(std::filesystem::is_regular_file(writer->stage_dir() / "features" /
                                               "direct_raw.npy"));
  EXPECT_FALSE(std::filesystem::exists(writer->stage_dir() / "manifest.tsv"))
      << "the manifest is written last, at publish";
  ASSERT_TRUE(writer->publish().has_value());
  EXPECT_TRUE(std::filesystem::exists(publish));
}

TEST(ShardPublish, AProcessKilledMidStageLeavesNoPublishedShard) {
  const std::filesystem::path root = scratch("shard_killed");
  const std::filesystem::path publish = shard_dir(root);
  const pid_t child = ::fork();
  ASSERT_GE(child, 0);
  if (child == 0) {
    auto begun = ShardWriter::begin(spec_for(root));
    if (!begun) {
      ::_exit(2);
    }
    std::unique_ptr<ShardWriter> writer = std::move(begun).value();
    const std::vector<float> direct_raw(3 * 2 * 60, 0.5F);
    const std::vector<std::int64_t> shape = {3, 2, 60};
    if (!writer->write_leaf<float>(Section::FEATURES, "direct_raw", NpyDtype::F4, shape,
                                   direct_raw)) {
      ::_exit(3);
    }
    // Killed here: mid-shard, after a leaf is durable, before the manifest and
    // before the rename. This is a real SIGKILL, not a destructor.
    ::kill(::getpid(), SIGKILL);
    ::_exit(4);
  }
  int status = 0;
  ASSERT_EQ(::waitpid(child, &status, 0), child);
  EXPECT_TRUE(WIFSIGNALED(status)) << "the child must have been killed, not have exited";
  EXPECT_EQ(WTERMSIG(status), SIGKILL);

  EXPECT_FALSE(std::filesystem::exists(publish))
      << "a killed builder must publish nothing at all";
  int stage_dirs = 0;
  for (const auto& entry : std::filesystem::directory_iterator(publish.parent_path())) {
    if (entry.path().filename().string().rfind(".L.stage-", 0) == 0) {
      ++stage_dirs;
      EXPECT_TRUE(std::filesystem::is_regular_file(entry.path() / "features" / "direct_raw.npy"));
      EXPECT_FALSE(std::filesystem::exists(entry.path() / "manifest.tsv"));
    }
  }
  EXPECT_EQ(stage_dirs, 1) << "the partial work survives, in the stage directory, and only there";
}

TEST(ShardPublish, RefusesWhileALeafIsStillOpen) {
  const std::filesystem::path root = scratch("shard_open_leaf");
  auto begun = ShardWriter::begin(spec_for(root));
  ASSERT_TRUE(begun.has_value());
  std::unique_ptr<ShardWriter> writer = std::move(begun).value();
  const std::vector<std::int64_t> shape = {4};
  auto leaf = writer->open_leaf(Section::FEATURES, "group_ts", NpyDtype::I8, shape);
  ASSERT_TRUE(leaf.has_value());
  auto refused = writer->publish();
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONFIG);
  // A second leaf may not be opened while the first is unfinished either.
  EXPECT_FALSE(writer->open_leaf(Section::FEATURES, "other", NpyDtype::I8, shape).has_value());
}

TEST(ShardPublish, RefusesAnEmptyShardAndADuplicateLeaf) {
  const std::filesystem::path root = scratch("shard_degenerate");
  auto begun = ShardWriter::begin(spec_for(root / "empty"));
  ASSERT_TRUE(begun.has_value());
  std::unique_ptr<ShardWriter> writer = std::move(begun).value();
  EXPECT_FALSE(writer->publish().has_value()) << "a shard with no leaves is not a tape";

  auto second = ShardWriter::begin(spec_for(root / "dup"));
  ASSERT_TRUE(second.has_value());
  std::unique_ptr<ShardWriter> dup = std::move(second).value();
  const std::vector<std::int64_t> shape = {4};
  const std::vector<std::int64_t> values = {1, 2, 3, 4};
  ASSERT_TRUE(
      dup->write_leaf<std::int64_t>(Section::FEATURES, "group_ts", NpyDtype::I8, shape, values)
          .has_value());
  EXPECT_FALSE(dup->open_leaf(Section::FEATURES, "group_ts", NpyDtype::I8, shape).has_value());
  // The same NAME in the other section is a different leaf and is allowed:
  // `keys` legitimately exists in both C4 sections.
  EXPECT_TRUE(dup->open_leaf(Section::TRUTH, "group_ts", NpyDtype::I8, shape).has_value());
}

TEST(ShardManifest, RefusesFieldsThatCouldForgeAColumnOrARow) {
  const std::filesystem::path root = scratch("shard_injection");
  ShardSpec tabbed = spec_for(root / "a");
  tabbed.build_id = "build\tid";
  EXPECT_FALSE(ShardWriter::begin(tabbed).has_value());

  ShardSpec newline = spec_for(root / "b");
  newline.sources.at(0).path = "/data/x\nleaf\tfeatures/fake.npy\t<i8\t1\t1\tdead";
  EXPECT_FALSE(ShardWriter::begin(newline).has_value());

  ShardSpec fine = spec_for(root / "c");
  auto begun = ShardWriter::begin(fine);
  ASSERT_TRUE(begun.has_value());
  std::unique_ptr<ShardWriter> writer = std::move(begun).value();
  const std::vector<std::int64_t> shape = {1};
  EXPECT_FALSE(writer->open_leaf(Section::FEATURES, "a/b", NpyDtype::I8, shape).has_value());
  EXPECT_FALSE(writer->open_leaf(Section::FEATURES, "../escape", NpyDtype::I8, shape).has_value());
  EXPECT_FALSE(writer->open_leaf(Section::FEATURES, "", NpyDtype::I8, shape).has_value());
  EXPECT_FALSE(writer->open_leaf(Section::FEATURES, ".hidden", NpyDtype::I8, shape).has_value());
}

TEST(ShardLayout, TheTruthDirectoryExistsOnlyWhenATruthLeafWasWritten) {
  const std::filesystem::path root = scratch("shard_features_only");
  auto begun = ShardWriter::begin(spec_for(root));
  ASSERT_TRUE(begun.has_value());
  std::unique_ptr<ShardWriter> writer = std::move(begun).value();
  write_tape(*writer, false, /*with_truth=*/false);
  ASSERT_TRUE(writer->publish().has_value());
  EXPECT_TRUE(std::filesystem::is_directory(shard_dir(root) / "features"));
  EXPECT_FALSE(std::filesystem::exists(shard_dir(root) / "truth"))
      << "a feature-only build may not so much as create the truth directory";
}

TEST(ShardPublish, RefusesAShardDirectoryNameOutsideTheC4Shape) {
  // The frozen shape is `<base>/s<four digits>/<L|S>` and nothing looser
  // (orchestrator ruling, 2026-08-10). The validator is the same call the
  // writer makes at begin() and again immediately before the rename.
  const std::filesystem::path root = scratch("shard_naming");
  EXPECT_TRUE(qr::emit::validate_c4_shard_dir(root / "s0125" / "L", 125, Side::LONG).has_value());
  EXPECT_TRUE(qr::emit::validate_c4_shard_dir(root / "s0749" / "S", 749, Side::SHORT).has_value());
  EXPECT_TRUE(qr::emit::validate_c4_shard_dir(root / "s0000" / "L", 0, Side::LONG).has_value());

  const std::vector<std::pair<std::filesystem::path, const char*>> malformed = {
      {root / "s125" / "L", "unpadded ordinal"},
      {root / "s00125" / "L", "over-padded ordinal"},
      {root / "S0125" / "L", "capital s"},
      {root / "0125" / "L", "no s prefix"},
      {root / "s012x" / "L", "non-digit in the ordinal"},
      {root / "s0125" / "LONG", "side spelled out"},
      {root / "s0125" / "l", "lowercase side letter"},
      {root / "s0125" / "S", "the other side"},
      {root / "s0126" / "L", "a different session than the shard carries"},
      {root / "s0125", "no side component at all"},
      {std::filesystem::path("s0125/L/"), "trailing slash"},
  };
  for (const auto& [path, why] : malformed) {
    EXPECT_FALSE(qr::emit::validate_c4_shard_dir(path, 125, Side::LONG).has_value()) << why;
    ShardSpec spec = spec_for(root / "unused");
    spec.publish_dir = path;
    EXPECT_FALSE(ShardWriter::begin(spec).has_value())
        << why << ": begin() must refuse before a single byte is staged";
  }
  // A malformed name never leaves a stage directory behind either.
  std::error_code code;
  EXPECT_TRUE(std::filesystem::is_empty(root, code)) << "a refused begin() staged something";

  // c4_shard_dir composes exactly that shape, and refuses an ordinal that does
  // not fit the four-digit field rather than truncating it.
  auto composed = qr::emit::c4_shard_dir("/base", 125, Side::LONG);
  ASSERT_TRUE(composed.has_value());
  EXPECT_EQ(composed.value().string(), "/base/s0125/L");
  auto short_side = qr::emit::c4_shard_dir("/base", 749, Side::SHORT);
  ASSERT_TRUE(short_side.has_value());
  EXPECT_EQ(short_side.value().string(), "/base/s0749/S");
  EXPECT_FALSE(qr::emit::c4_shard_dir("/base", 10000, Side::LONG).has_value());
  EXPECT_FALSE(qr::emit::c4_shard_dir("/base", -1, Side::LONG).has_value());
}

}  // namespace
