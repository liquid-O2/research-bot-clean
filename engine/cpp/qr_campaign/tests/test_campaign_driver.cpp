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

/// A stand-in for a verified card sha (64 lowercase hex), so a test layout is
/// bound exactly the way the spec gate binds the real one.
std::string test_card_sha(char fill = 'a') { return std::string(64, fill); }

RunLayout layout_at(const std::filesystem::path& base) {
  auto layout = run_layout(base, 1);
  EXPECT_TRUE(layout.has_value());
  RunLayout bound = layout.value();
  bound.card_sha256 = test_card_sha();
  return bound;
}

/// A synthetic CARD_LINEAGE.tsv: the preamble comments and the header the
/// parser insists on, then the rows the fixture is about.
std::string lineage_text(const std::vector<std::string>& rows) {
  std::string text =
      "# synthetic lineage\nsha256\tdate\tamendment\tscope\tconsumers_invariant\n";
  for (const std::string& row : rows) {
    text += row + "\n";
  }
  return text;
}

std::string lineage_row(char fill, std::string_view scope, std::string_view amendment) {
  return test_card_sha(fill) + "\t2026-08-11\t" + std::string(amendment) + "\t" +
         std::string(scope) + "\tconsumer note";
}

/// Writes `text` as a lineage file and loads it.
Expected<CardLineage, Refusal> load_lineage(const std::string& name, const std::string& text) {
  const std::filesystem::path path = scratch(name) / "CARD_LINEAGE.tsv";
  write_file(path, text);
  return CardLineage::load(path);
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
  // The real card, at the sha the real lineage names as its head: a BUILD binds
  // to the head and to nothing else.
  auto lineage = CardLineage::load(kCardLineagePath);
  ASSERT_TRUE(lineage.has_value()) << lineage.error().message();
  const std::filesystem::path card(kCardPath);
  ASSERT_TRUE(std::filesystem::is_regular_file(card))
      << "the frozen task card is not present at " << kCardPath;
  EXPECT_TRUE(lineage.value().verify_head_card(card).has_value())
      << "the card on disk is not the lineage head";

  // One appended byte — a "harmless" edit — must stop the driver.
  const std::filesystem::path dirty = scratch("spec_gate") / "TASK_CARD_V4_DRAFT.md";
  write_file(dirty, read_file(card) + "\n");
  const Status refused = lineage.value().verify_head_card(dirty);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), RefusalCode::CONTENT_MISMATCH);

  // And a card that is not there at all is a refusal, never a silent pass.
  EXPECT_FALSE(verify_frozen_spec(scratch("spec_gate_missing") / "absent.md", test_card_sha())
                   .has_value());
}

// ---------------------------------------------------------------------------
// 1b. the card lineage
// ---------------------------------------------------------------------------

TEST(CampaignCardLineage, TheRealLineageCarriesTheFrozenAncestryAndItsHeadIsTheCardOnDisk) {
  auto lineage = CardLineage::load(kCardLineagePath);
  ASSERT_TRUE(lineage.has_value()) << lineage.error().message();
  ASSERT_GE(lineage.value().rows().size(), 2U)
      << "the lineage must carry the M2 freeze AND the amendment that followed it";

  // The first row is the M2-close freeze the published 625-session corpus was
  // built under; the head is the card the next build must bind to.
  const CardLineageRow& root = lineage.value().rows().front();
  EXPECT_EQ(root.sha256, "5c26438b12dd90e15b005375829d976fa46a1710c78041ff20ffc587dc092792");
  ASSERT_EQ(root.scope.size(), 1U);
  EXPECT_EQ(root.scope.front(), "ROOT");
  EXPECT_EQ(lineage.value().head().sha256,
            "23b9151095e847f6a9c0f80b2fb39820e5359c0eaeb33f1889cab09772862a9a");  // CC-010 head

  // The head is a real file's sha, not a hope: it is the card on disk.
  EXPECT_TRUE(lineage.value().verify_head_card(kCardPath).has_value());

  // THE RULING, fixtured: the published corpus names the M2 freeze, every
  // amendment since is declared outside the tape read scope, so the corpus
  // stands without a rebuild.
  EXPECT_TRUE(lineage.value()
                  .verify_corpus_card_sha(
                      "5c26438b12dd90e15b005375829d976fa46a1710c78041ff20ffc587dc092792")
                  .has_value());
  for (std::size_t index = 1; index < lineage.value().rows().size(); ++index) {
    EXPECT_FALSE(lineage.value().rows()[index].touches_tape_read_scope())
        << "row " << index << " declares a tape-read section: the corpus is retired, not valid";
  }
}

TEST(CampaignCardLineage, AnAncestorIsValidOnlyWhileEveryLaterAmendmentIsOutsideTheTapeScope) {
  // Two amendments, both model-only: the ancestor's tapes stay valid.
  auto model_only = load_lineage("lineage_model_only",
                                 lineage_text({lineage_row('a', "ROOT", "M2_FREEZE"),
                                               lineage_row('b', "S5", "CC-009"),
                                               lineage_row('c', "S6,S7", "CC-010")}));
  ASSERT_TRUE(model_only.has_value()) << model_only.error().message();
  EXPECT_TRUE(model_only.value().verify_corpus_card_sha(test_card_sha('a')).has_value());
  EXPECT_TRUE(model_only.value().verify_corpus_card_sha(test_card_sha('b')).has_value());
  EXPECT_TRUE(model_only.value().verify_corpus_card_sha(test_card_sha('c')).has_value());

  // The same ancestry with ONE amendment that declares §4 — the native inputs
  // the tape constructors read. Every corpus older than it is retired, and the
  // gate says so instead of quietly accepting the tapes.
  auto touches_tape = load_lineage("lineage_touches_tape",
                                   lineage_text({lineage_row('a', "ROOT", "M2_FREEZE"),
                                                 lineage_row('b', "S5", "CC-009"),
                                                 lineage_row('c', "S4,S5", "CC-011")}));
  ASSERT_TRUE(touches_tape.has_value()) << touches_tape.error().message();
  const Status ancestor = touches_tape.value().verify_corpus_card_sha(test_card_sha('a'));
  ASSERT_FALSE(ancestor.has_value()) << "a §4 amendment must retire every earlier corpus";
  EXPECT_EQ(ancestor.error().code(), RefusalCode::CONTENT_MISMATCH);
  EXPECT_FALSE(touches_tape.value().verify_corpus_card_sha(test_card_sha('b')).has_value());
  // The amendment's OWN card is still the head, so a corpus built under it is
  // exactly as valid as the amendment.
  EXPECT_TRUE(touches_tape.value().verify_corpus_card_sha(test_card_sha('c')).has_value());

  // The leaf layout counts as read scope for the same reason §§1-4 do.
  auto touches_layout = load_lineage("lineage_touches_layout",
                                     lineage_text({lineage_row('a', "ROOT", "M2_FREEZE"),
                                                   lineage_row('b', "C4", "CC-012")}));
  ASSERT_TRUE(touches_layout.has_value()) << touches_layout.error().message();
  EXPECT_FALSE(touches_layout.value().verify_corpus_card_sha(test_card_sha('a')).has_value());
}

TEST(CampaignCardLineage, ACardShaOutsideTheLineageIsRefused) {
  auto lineage = load_lineage("lineage_stranger",
                              lineage_text({lineage_row('a', "ROOT", "M2_FREEZE"),
                                            lineage_row('b', "S5", "CC-009")}));
  ASSERT_TRUE(lineage.has_value()) << lineage.error().message();
  // An unknown ancestor is not an ancestor: nothing at all can be concluded
  // about a corpus whose card never appears in the lineage.
  const Status stranger = lineage.value().verify_corpus_card_sha(test_card_sha('f'));
  ASSERT_FALSE(stranger.has_value());
  EXPECT_EQ(stranger.error().code(), RefusalCode::CONTENT_MISMATCH);
  EXPECT_FALSE(lineage.value().verify_corpus_card_sha("").has_value());
  EXPECT_FALSE(lineage.value().verify_corpus_card_sha("not-a-sha").has_value());
}

TEST(CampaignCardLineage, AMalformedLineageRefusesRatherThanDefaultingOpen) {
  const std::string good_root = lineage_row('a', "ROOT", "M2_FREEZE");
  const std::string good_next = lineage_row('b', "S5", "CC-009");

  // No header at all.
  EXPECT_FALSE(load_lineage("lineage_no_header", good_root + "\n").has_value());
  // A row that is not five fields.
  EXPECT_FALSE(load_lineage("lineage_four_fields",
                            lineage_text({std::string(64, 'a') + "\t2026-08-11\tX\tROOT"}))
                   .has_value());
  // A sha that is not 64 lowercase hex.
  EXPECT_FALSE(load_lineage("lineage_short_sha",
                            lineage_text({"abc\t2026-08-11\tX\tROOT\tnote"}))
                   .has_value());
  EXPECT_FALSE(load_lineage("lineage_upper_sha",
                            lineage_text({std::string(64, 'A') + "\t2026-08-11\tX\tROOT\tnote"}))
                   .has_value());
  // A date that is not YYYY-MM-DD.
  EXPECT_FALSE(load_lineage("lineage_bad_date",
                            lineage_text({std::string(64, 'a') + "\t11/08/2026\tX\tROOT\tnote"}))
                   .has_value());
  // A scope token the gate cannot reason about is a REFUSAL, not a pass: this
  // is the difference between an honest gate and a rubber stamp.
  EXPECT_FALSE(load_lineage("lineage_unknown_scope",
                            lineage_text({good_root, lineage_row('b', "MODEL", "CC-009")}))
                   .has_value());
  EXPECT_FALSE(load_lineage("lineage_empty_scope",
                            lineage_text({good_root, lineage_row('b', "", "CC-009")}))
                   .has_value());
  // ROOT belongs to the first row and to no other; and no row may be both.
  EXPECT_FALSE(load_lineage("lineage_late_root",
                            lineage_text({good_root, lineage_row('b', "ROOT", "CC-009")}))
                   .has_value());
  EXPECT_FALSE(
      load_lineage("lineage_root_and_scope", lineage_text({lineage_row('a', "ROOT,S5", "X")}))
          .has_value());
  EXPECT_FALSE(load_lineage("lineage_headless_first",
                            lineage_text({lineage_row('a', "S5", "X"), good_next}))
                   .has_value());
  // The same card twice is an ambiguous ancestry.
  EXPECT_FALSE(load_lineage("lineage_duplicate", lineage_text({good_root, good_root}))
                   .has_value());
  // No rows at all, and no file at all.
  EXPECT_FALSE(load_lineage("lineage_empty", lineage_text({})).has_value());
  EXPECT_FALSE(CardLineage::load(scratch("lineage_absent") / "CARD_LINEAGE.tsv").has_value());

  // And the shape that must pass, so the refusals above are about the defect
  // and not about the parser refusing everything.
  EXPECT_TRUE(load_lineage("lineage_good", lineage_text({good_root, good_next})).has_value());
}

TEST(CampaignCorpusCard, EveryManifestNamesItsCardAndAManifestWithoutOneRefuses) {
  const std::filesystem::path root = scratch("corpus_card");
  const auto manifest = [&root](const char* session, const char* side, const std::string& body) {
    write_file(root / "tapes" / session / side / "manifest.tsv", body);
  };
  const std::string card = test_card_sha('a');
  const std::string with_card = "schema\tqr_shard_v1\ncensus\ttask_card_v4\t" + card +
                                "\t/workspace/evidence/claims/native_state/TASK_CARD_V4_DRAFT.md\n";
  manifest("s0125", "L", with_card);
  manifest("s0125", "S", with_card);
  manifest("s0500", "L", with_card);

  auto tally = corpus_card_shas(root);
  ASSERT_TRUE(tally.has_value()) << tally.error().message();
  ASSERT_EQ(tally.value().size(), 1U);
  EXPECT_EQ(tally.value().front().first, card);
  EXPECT_EQ(tally.value().front().second, 3);

  // A second card in the same corpus is REPORTED, not averaged away.
  manifest("s0500", "S", "census\ttask_card_v4\t" + test_card_sha('b') + "\tpath\n");
  auto mixed = corpus_card_shas(root);
  ASSERT_TRUE(mixed.has_value());
  EXPECT_EQ(mixed.value().size(), 2U);

  // A manifest that names no card is a refusal: an unnamed card is not an
  // absent constraint, it is an unknown one.
  manifest("s0625", "L", "schema\tqr_shard_v1\nleaf\tfeatures/keys.npy\ti8\t2,4\t2\tdeadbeef\n");
  EXPECT_FALSE(corpus_card_shas(root).has_value());

  // A root with no tapes at all refuses rather than reporting a clean corpus.
  EXPECT_FALSE(corpus_card_shas(scratch("corpus_card_empty")).has_value());
}

TEST(CampaignReceipt, AnUnboundCardShaRefusesInsteadOfNamingAnUncheckedCard) {
  // Everything the campaign receipt needs is on disk...
  const std::vector<std::int64_t> ordinals{125, 500};
  RunLayout layout = layout_at(scratch("unbound_card"));
  for (const std::int64_t ordinal : ordinals) {
    write_file(layout.session_receipt(ordinal), session_receipt_text(ordinal));
  }
  ASSERT_TRUE(render_campaign_receipt(layout, ordinals).has_value());

  // ...so the ONLY thing missing in the refusal below is the verified card sha.
  // A layout the spec gate never bound must not publish a receipt that names a
  // card nobody checked.
  layout.card_sha256.clear();
  const auto unbound = render_campaign_receipt(layout, ordinals);
  ASSERT_FALSE(unbound.has_value());
  EXPECT_EQ(unbound.error().code(), RefusalCode::CONFIG);
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
