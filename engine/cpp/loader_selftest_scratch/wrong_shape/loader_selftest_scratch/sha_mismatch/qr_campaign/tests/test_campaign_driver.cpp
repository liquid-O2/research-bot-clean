// test_campaign_driver.cpp — the campaign driver's red-first fixtures.
//
// Each of these was written before the code it covers and each has a committed
// mutation in tests/mutants that turns it red (tests/red_ledger.tsv maps them).
// They cover the four laws driver.hpp states — the spec gate, the ordinal wall,
// the publish/resume discipline and the ordinal-ordered merge — plus the
// handoff blob the APPENDIX C4 process separation is carried over.
#include <sys/wait.h>
#include <unistd.h>

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "qr_campaign/driver.hpp"
#include "qr_campaign/handoff.hpp"

namespace qr::campaign {
namespace {

using qr::emit::Side;

std::filesystem::path scratch(const std::string& name) {
  const std::filesystem::path root = std::filesystem::path(QR_TEST_SCRATCH_DIR) / "campaign" / name;
  std::error_code code;
  std::filesystem::remove_all(root, code);
  std::filesystem::create_directories(root, code);
  return root;
}

void write_file(const std::filesystem::path& path, const std::string& text) {
  std::error_code code;
  std::filesystem::create_directories(path.parent_path(), code);
  std::ofstream out(path, std::ios::binary | std::ios::trunc);
  out << text;
}

std::string read_file(const std::filesystem::path& path) {
  std::ifstream input(path, std::ios::binary);
  return std::string((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
}

/// A per-session receipt carrying exactly the rows the campaign ledger reads.
std::string session_receipt_text(std::int64_t ordinal) {
  Receipt receipt;
  receipt.add("session", "ordinal", ordinal);
  receipt.add("actions", "rows", ordinal * 2);
  receipt.add("label_state", "OK", ordinal);
  receipt.add_text("shard.L", "manifest_sha256", "L" + std::to_string(ordinal));
  receipt.add("shard.L", "leaves", 20);
  receipt.add("shard.L", "bytes", 1000 + ordinal);
  receipt.add_text("shard.S", "manifest_sha256", "S" + std::to_string(ordinal));
  receipt.add("shard.S", "leaves", 14);
  receipt.add("shard.S", "bytes", 2000 + ordinal);
  return receipt.render();
}

RunLayout layout_at(const std::filesystem::path& base) {
  auto layout = run_layout(base, 1);
  EXPECT_TRUE(layout.has_value());
  return layout.value();
}

/// Publishes a minimal but REAL shard through the driver's own emitter, so the
/// resume and no-replace fixtures stand on the production path.
void publish_minimal_shard(const RunLayout& layout, std::int64_t ordinal, Side side) {
  auto emitter = ShardEmitter::open(layout, ordinal, side, "test", {}, {});
  ASSERT_TRUE(emitter.has_value()) << emitter.error().message();
  const std::vector<std::int64_t> shape{2, 4};
  const std::vector<std::int64_t> keys{1, 2, 3, 4, 5, 6, 7, 8};
  ASSERT_TRUE(emitter.value()
                  ->writer()
                  .write_leaf<std::int64_t>(qr::emit::Section::FEATURES, "keys",
                                            qr::emit::NpyDtype::I8, shape, keys)
                  .has_value());
  ASSERT_TRUE(emitter.value()->publish().has_value());
}

// ---------------------------------------------------------------------------
// 1. the spec gate
// ---------------------------------------------------------------------------

TEST(CampaignSpecGate, TheFrozenCardPassesAndAnyEditedByteRefuses) {
  // The real card, at its frozen sha: the gate must pass on the bytes the
  // campaign is bound to.
  const std::filesystem::path card(kCardPath);
  ASSERT_TRUE(std::filesystem::is_regular_file(card))
      << "the frozen task card is not present at " << kCardPath;
  EXPECT_TRUE(verify_frozen_spec(card, kCardSha256).has_value());

  // One appended byte — a "harmless" edit — must stop the driver.
  const std::filesystem::path dirty = scratch("spec_gate") / "TASK_CARD_V4_DRAFT.md";
  write_file(dirty, read_file(card) + "\n");
  const Status refused = verify_frozen_spec(dirty, kCardSha256);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), RefusalCode::CONTENT_MISMATCH);

  // And a card that is not there at all is a refusal, never a silent pass.
  EXPECT_FALSE(verify_frozen_spec(scratch("spec_gate_missing") / "absent.md", kCardSha256)
                   .has_value());
}

// ---------------------------------------------------------------------------
// 2. the ordinal wall
// ---------------------------------------------------------------------------

TEST(CampaignOrdinalWall, TheWallRefusesOutsideTheScopeBeforeAnyPathIsFormed) {
  EXPECT_TRUE(refuse_unless_in_scope(125).has_value());
  EXPECT_TRUE(refuse_unless_in_scope(500).has_value());
  EXPECT_TRUE(refuse_unless_in_scope(749).has_value());
  for (const std::int64_t ordinal : {std::int64_t{-1}, std::int64_t{0}, std::int64_t{124},
                                     std::int64_t{750}, std::int64_t{962}, std::int64_t{1002}}) {
    const Status refused = refuse_unless_in_scope(ordinal);
    ASSERT_FALSE(refused.has_value()) << ordinal << " must not be admissible";
    EXPECT_EQ(refused.error().code(), RefusalCode::ORDINAL_OUTSIDE_SCOPE);
    // The wall fires before any path exists: `session_dir_name` is the first
    // path component and it refuses too.
    EXPECT_FALSE(session_dir_name(ordinal).has_value());
  }
  EXPECT_EQ(session_dir_name(125).value(), "s0125");
  EXPECT_EQ(session_dir_name(749).value(), "s0749");
}

TEST(CampaignOrdinalWall, TheSessionListParserRefusesAnyOutOfScopeElement) {
  auto probe = parse_session_list("125,500,625");
  ASSERT_TRUE(probe.has_value());
  EXPECT_EQ(probe.value(), (std::vector<std::int64_t>{125, 500, 625}));

  auto all = parse_session_list("all");
  ASSERT_TRUE(all.has_value());
  EXPECT_EQ(all.value().size(), 625U);
  EXPECT_EQ(all.value().front(), 125);
  EXPECT_EQ(all.value().back(), 749);

  auto range = parse_session_list("646-647,125");
  ASSERT_TRUE(range.has_value());
  EXPECT_EQ(range.value(), (std::vector<std::int64_t>{125, 646, 647}));

  for (const char* spec : {"124", "750", "700-800", "0", "", "12a", "200-100"}) {
    EXPECT_FALSE(parse_session_list(spec).has_value()) << spec << " must refuse";
  }
}

// ---------------------------------------------------------------------------
// 3. the publish discipline
// ---------------------------------------------------------------------------

TEST(CampaignPublish, AWorkerThatDiesMidSessionLeavesAStageAndNoPublishedShard) {
  const RunLayout layout = layout_at(scratch("crash"));
  const std::int64_t ordinal = 125;
  const auto shard = qr::emit::c4_shard_dir(layout.tapes(), ordinal, Side::LONG);
  ASSERT_TRUE(shard.has_value());

  const ::pid_t child = ::fork();
  ASSERT_GE(child, 0);
  if (child == 0) {
    auto emitter = ShardEmitter::open(layout, ordinal, Side::LONG, "test", {}, {});
    if (!emitter.has_value()) {
      ::_exit(2);
    }
    const std::vector<std::int64_t> shape{2, 4};
    const std::vector<std::int64_t> keys{1, 2, 3, 4, 5, 6, 7, 8};
    if (!emitter.value()
             ->writer()
             .write_leaf<std::int64_t>(qr::emit::Section::FEATURES, "keys",
                                       qr::emit::NpyDtype::I8, shape, keys)
             .has_value()) {
      ::_exit(3);
    }
    ::_exit(9);  // the crash: everything is staged, nothing is published
  }
  int status = 0;
  ASSERT_EQ(::waitpid(child, &status, 0), child);
  ASSERT_TRUE(WIFEXITED(status));
  ASSERT_EQ(WEXITSTATUS(status), 9);

  // NOTHING is published: not the manifest, not even the shard directory.
  EXPECT_FALSE(std::filesystem::exists(shard.value()))
      << "a dead worker published a shard directory";
  EXPECT_FALSE(std::filesystem::exists(shard.value() / qr::emit::kManifestName));

  // The stage it left is visible, and it is the ONLY thing under the session.
  std::int64_t stages = 0;
  std::error_code code;
  for (const std::filesystem::directory_entry& entry :
       std::filesystem::directory_iterator(shard.value().parent_path(), code)) {
    if (entry.path().filename().string().rfind(".L.stage-", 0) == 0) {
      ++stages;
    }
  }
  EXPECT_EQ(stages, 1) << "the crashed worker left no stage directory to find";

  // A retry clears exactly that stage and publishes normally.
  const auto cleared = clear_stale_stages(layout, ordinal, Side::LONG);
  ASSERT_TRUE(cleared.has_value());
  EXPECT_EQ(cleared.value(), 1);
  publish_minimal_shard(layout, ordinal, Side::LONG);
  EXPECT_TRUE(std::filesystem::is_regular_file(shard.value() / qr::emit::kManifestName));
}

TEST(CampaignPublish, ClearingStagesTouchesOnlyThisSideAndNeverAPublishedShard) {
  const RunLayout layout = layout_at(scratch("stages"));
  const std::int64_t ordinal = 500;
  publish_minimal_shard(layout, ordinal, Side::LONG);
  const auto long_shard = qr::emit::c4_shard_dir(layout.tapes(), ordinal, Side::LONG);
  ASSERT_TRUE(long_shard.has_value());
  const std::filesystem::path session_dir = long_shard.value().parent_path();
  write_file(session_dir / ".S.stage-4242" / "features" / "x.npy", "stale");
  write_file(session_dir / ".L.stage-4242" / "features" / "x.npy", "stale");

  const auto cleared = clear_stale_stages(layout, ordinal, Side::SHORT);
  ASSERT_TRUE(cleared.has_value());
  EXPECT_EQ(cleared.value(), 1) << "clearing SHORT must not touch the LONG stage";
  EXPECT_TRUE(std::filesystem::exists(session_dir / ".L.stage-4242"));
  EXPECT_FALSE(std::filesystem::exists(session_dir / ".S.stage-4242"));
  // The published shard is untouched by any amount of stage clearing.
  EXPECT_TRUE(std::filesystem::is_regular_file(long_shard.value() / qr::emit::kManifestName));
}

// ---------------------------------------------------------------------------
// 3b. resume
// ---------------------------------------------------------------------------

TEST(CampaignResume, AnAlreadyPublishedShardIsSkippedAndNeverPublishedTwice) {
  const RunLayout layout = layout_at(scratch("resume"));
  publish_minimal_shard(layout, 125, Side::LONG);
  EXPECT_TRUE(side_is_published(layout, 125, Side::LONG));
  EXPECT_FALSE(side_is_published(layout, 125, Side::SHORT));

  const std::vector<std::int64_t> requested{125, 500};
  auto resumed = plan_tasks(layout, requested, true);
  ASSERT_TRUE(resumed.has_value()) << resumed.error().message();
  ASSERT_EQ(resumed.value().size(), 2U);
  EXPECT_EQ(resumed.value()[0].ordinal, 125);
  EXPECT_FALSE(resumed.value()[0].build(Side::LONG)) << "a published shard must be SKIPPED";
  EXPECT_TRUE(resumed.value()[0].build(Side::SHORT));
  EXPECT_TRUE(resumed.value()[1].build(Side::LONG));
  EXPECT_TRUE(resumed.value()[1].build(Side::SHORT));

  // And the emitter itself refuses to republish: the no-replace rename is the
  // wall, not the plan.
  auto republish = ShardEmitter::open(layout, 125, Side::LONG, "test", {}, {});
  EXPECT_FALSE(republish.has_value()) << "a published shard was reopened for writing";
}

TEST(CampaignResume, WithoutResumeAnExistingShardIsARefusalNotAReplacement) {
  const RunLayout layout = layout_at(scratch("no_resume"));
  publish_minimal_shard(layout, 625, Side::SHORT);
  const std::vector<std::int64_t> requested{625};
  const auto refused = plan_tasks(layout, requested, false);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), RefusalCode::CONTENT_MISMATCH);
  // The published shard is still there, untouched.
  EXPECT_TRUE(side_is_published(layout, 625, Side::SHORT));
}

// ---------------------------------------------------------------------------
// 4. the ordinal-ordered merge
// ---------------------------------------------------------------------------

TEST(CampaignLedger, IsOrdinalOrderedWhateverTheCompletionOrder) {
  const std::vector<std::int64_t> ordinals{125, 500, 625};

  const RunLayout ascending = layout_at(scratch("ledger_ascending"));
  for (const std::int64_t ordinal : ordinals) {
    write_file(ascending.session_receipt(ordinal), session_receipt_text(ordinal));
  }
  auto first = render_campaign_receipt(ascending, ordinals);
  ASSERT_TRUE(first.has_value()) << first.error().message();

  // The SAME sessions, finished in the reverse order and handed to the ledger
  // in that order: a 12-worker run against a 2-worker run.
  const RunLayout descending = layout_at(scratch("ledger_descending"));
  for (auto ordinal = ordinals.rbegin(); ordinal != ordinals.rend(); ++ordinal) {
    write_file(descending.session_receipt(*ordinal), session_receipt_text(*ordinal));
  }
  const std::vector<std::int64_t> shuffled{625, 125, 500};
  auto second = render_campaign_receipt(descending, shuffled);
  ASSERT_TRUE(second.has_value()) << second.error().message();

  EXPECT_EQ(first.value(), second.value())
      << "the campaign receipt moved with the completion order";
  EXPECT_NE(first.value().find("manifest_root_sha256"), std::string::npos);
  // The root hash is over the ordinal-ordered shard list, so it is stable and
  // it CHANGES when a shard's manifest changes.
  write_file(descending.session_receipt(500),
             session_receipt_text(500) + "shard.L\tmanifest_sha256\tDRIFT\n");
  auto drifted = render_campaign_receipt(descending, shuffled);
  ASSERT_TRUE(drifted.has_value());
  EXPECT_EQ(drifted.value(), second.value())
      << "the ledger must read the FIRST row of a metric, not the last";
}

TEST(CampaignLedger, AMissingSessionReceiptRefusesRatherThanShorteningTheCampaign) {
  const RunLayout layout = layout_at(scratch("ledger_missing"));
  write_file(layout.session_receipt(125), session_receipt_text(125));
  const std::vector<std::int64_t> ordinals{125, 500};
  EXPECT_FALSE(render_campaign_receipt(layout, ordinals).has_value());
}

// ---------------------------------------------------------------------------
// The handoff blob
// ---------------------------------------------------------------------------

TEST(CampaignHandoff, RoundTripsEveryDtypeAcrossAForkAndRefusesAnUnfinishedBlob) {
  auto fd = create_handoff_fd();
  ASSERT_TRUE(fd.has_value()) << fd.error().message();

  const std::vector<float> values{1.5F, -2.5F, 3.25F, 0.0F};
  const std::vector<std::int64_t> stamps{7, 8, 9};
  const std::vector<std::int32_t> offsets{0, 2, 4};
  const std::vector<std::uint8_t> masks{1, 0, 1};

  // An unfinished blob is not readable: the header is written LAST.
  {
    HandoffWriter writer(fd.value());
    const std::array<std::int64_t, 2> shape{2, 2};
    ASSERT_TRUE(writer.append_values<float>("direct_raw", LeafScope::LONG_SHARD, NpyDtype::F4,
                                            shape, values)
                    .has_value());
    EXPECT_FALSE(HandoffReader::map(fd.value()).has_value())
        << "a half-written handoff must never look like a whole one";
  }
  {
    HandoffWriter writer(fd.value());
    const std::array<std::int64_t, 2> shape{2, 2};
    ASSERT_TRUE(writer.append_values<float>("direct_raw", LeafScope::LONG_SHARD, NpyDtype::F4,
                                            shape, values)
                    .has_value());
    const std::array<std::int64_t, 1> stamp_shape{3};
    ASSERT_TRUE(writer.append_values<std::int64_t>("group_ts_stock_nbbo",
                                                   LeafScope::SESSION_LONG_SHARD, NpyDtype::I8,
                                                   stamp_shape, stamps)
                    .has_value());
    ASSERT_TRUE(writer.append_values<std::int32_t>("candset_offsets", LeafScope::SHORT_SHARD,
                                                   NpyDtype::I4, stamp_shape, offsets)
                    .has_value());
    ASSERT_TRUE(writer.append_values<std::uint8_t>("masks", LeafScope::BOTH_SHARDS, NpyDtype::U1,
                                                   stamp_shape, masks)
                    .has_value());
    // A shape that disagrees with the byte count is refused at the door.
    const std::array<std::int64_t, 1> wrong{99};
    EXPECT_FALSE(writer
                     .append_values<std::uint8_t>("bad", LeafScope::BOTH_SHARDS, NpyDtype::U1,
                                                  wrong, masks)
                     .has_value());
    ASSERT_TRUE(writer.finish().has_value());
  }

  auto blob = HandoffReader::map(fd.value());
  ASSERT_TRUE(blob.has_value()) << blob.error().message();
  ASSERT_EQ(blob.value().leaves().size(), 4U);
  const HandoffLeaf& first = blob.value().leaves()[0];
  EXPECT_EQ(first.name, "direct_raw");
  EXPECT_EQ(first.scope, LeafScope::LONG_SHARD);
  EXPECT_EQ(first.shape, (std::vector<std::int64_t>{2, 2}));
  ASSERT_TRUE(blob.value().elements(first).has_value());
  EXPECT_EQ(blob.value().elements(first).value(), 4U);
  const auto* floats = static_cast<const float*>(blob.value().payload(first));
  for (std::size_t index = 0; index < values.size(); ++index) {
    EXPECT_EQ(floats[index], values[index]);
  }
  const HandoffLeaf& second = blob.value().leaves()[1];
  EXPECT_EQ(second.scope, LeafScope::SESSION_LONG_SHARD);
  const auto* longs = static_cast<const std::int64_t*>(blob.value().payload(second));
  for (std::size_t index = 0; index < stamps.size(); ++index) {
    EXPECT_EQ(longs[index], stamps[index]);
  }
  const auto* ints = static_cast<const std::int32_t*>(blob.value().payload(
      blob.value().leaves()[2]));
  for (std::size_t index = 0; index < offsets.size(); ++index) {
    EXPECT_EQ(ints[index], offsets[index]);
  }
  const auto* bytes = static_cast<const std::uint8_t*>(blob.value().payload(
      blob.value().leaves()[3]));
  for (std::size_t index = 0; index < masks.size(); ++index) {
    EXPECT_EQ(bytes[index], masks[index]);
  }
  ::close(fd.value());
}

TEST(CampaignReceipt, RendersAndParsesItsOwnRowsAndRefusesAForeignHeader) {
  const std::filesystem::path root = scratch("receipt");
  Receipt receipt;
  receipt.add("session", "ordinal", 125);
  receipt.add_text("shard.L", "manifest_sha256", "abc");
  ASSERT_TRUE(receipt.write(root / "r.tsv").has_value());
  auto rows = parse_receipt(root / "r.tsv");
  ASSERT_TRUE(rows.has_value());
  ASSERT_EQ(rows.value().size(), 2U);
  EXPECT_EQ(receipt_value(rows.value(), "session", "ordinal").value(), "125");
  EXPECT_EQ(receipt_value(rows.value(), "shard.L", "manifest_sha256").value(), "abc");
  EXPECT_FALSE(receipt_value(rows.value(), "shard.S", "manifest_sha256").has_value());

  write_file(root / "foreign.tsv", "a\tb\tc\n1\t2\t3\n");
  EXPECT_FALSE(parse_receipt(root / "foreign.tsv").has_value());
}

}  // namespace
}  // namespace qr::campaign
