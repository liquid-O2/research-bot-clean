// The bounded, physically non-prefetching event-signal prefix reader.
//
// The load-bearing test in this file is
// `NeverAddressesAByteAtOrPastTheWall`: every byte the reader asks for goes
// through a shim that REFUSES anything at or past the stop byte. The fixture
// deliberately continues with two more sessions after the stop, so a reader
// that oversteps by a single byte cannot pass.
#include <gtest/gtest.h>

#include <string>
#include <vector>

#include "candidates_test_support.hpp"
#include "qr_candidates/prefix_reader.hpp"

namespace {

using namespace qr::candidates;          // NOLINT(build/namespaces)
using namespace qr::candidates::testing;  // NOLINT(build/namespaces)

constexpr std::uint32_t kStop = 3;

PrefixSealOptions fixture_options(std::uint32_t retain_from = 0,
                                  std::uint32_t retain_to = kStop) {
  PrefixSealOptions options;
  options.stop_ordinal = kStop;
  options.retain_from = retain_from;
  options.retain_to = retain_to;
  options.require_pinned_event_bytes = false;  // the fixture is not the 14GB file
  options.require_full_row_census = false;     // nor the 10,684,134-row census
  return options;
}

// --- the happy path ---------------------------------------------------------

TEST(PrefixSeal, ReproducesEverySessionRootAndCountThroughTheStop) {
  const Literals literals;
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  ASSERT_EQ(bounds.size(), kStop + 1U);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_TRUE(seal.has_value()) << (seal.has_value() ? "" : seal.error().message());
  EXPECT_EQ(seal.value().roots_verified, kStop + 1U);
  EXPECT_EQ(seal.value().decoded_data_rows,
            static_cast<std::uint64_t>(literals.number("prefix", "admitted_rows")));
  for (std::uint32_t ordinal = 0; ordinal <= kStop; ++ordinal) {
    EXPECT_EQ(seal.value().session_roots[ordinal], literals.text("root", std::to_string(ordinal)));
  }
}

TEST(PrefixSeal, StopsAtExactlyTheDeclaredBoundaryByteAndClosesTheDescriptor) {
  const Literals literals;
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_TRUE(seal.has_value()) << (seal.has_value() ? "" : seal.error().message());
  EXPECT_EQ(seal.value().event_stats.end_offset_exclusive,
            literals.number("prefix", "stop_byte_exclusive"));
  EXPECT_EQ(seal.value().event_stats.requested_bytes,
            static_cast<std::uint64_t>(literals.number("prefix", "stop_byte_exclusive")));
  // The file is much longer than the prefix: stopping is a real event.
  EXPECT_GT(literals.number("prefix", "file_bytes"),
            literals.number("prefix", "stop_byte_exclusive"));
  EXPECT_TRUE(source.closed());
}

TEST(PrefixSeal, NeverAddressesAByteAtOrPastTheWall) {
  const Literals literals;
  const auto stop_byte = literals.number("prefix", "stop_byte_exclusive");
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  WalledSource source(read_whole_file(fixture_path("event_signals_good.tsv")), stop_byte);
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_TRUE(seal.has_value()) << (seal.has_value() ? "" : seal.error().message());
  EXPECT_EQ(source.beyond_wall_calls(), 0U);
  EXPECT_EQ(source.highest_offset_touched(), stop_byte);
}

TEST(PrefixSeal, TheHeaderIsWalkedOneByteAtATime) {
  const Literals literals;
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_TRUE(seal.has_value());
  EXPECT_EQ(seal.value().event_stats.header_calls,
            static_cast<std::uint64_t>(literals.number("prefix", "header_bytes")));
}

TEST(PrefixSeal, TheFinalRowIsWalkedOneByteAtATimeThroughItsNewline) {
  const Literals literals;
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_TRUE(seal.has_value());
  EXPECT_EQ(seal.value().event_stats.final_byte_calls,
            static_cast<std::uint64_t>(literals.number("prefix", "final_row_bytes")));
}

TEST(PrefixSeal, BlockRequestsAreClampedToOneFewerThanTheRemainingRowCount) {
  // THE ARITHMETIC THAT IS THE WALL. With 19 admitted rows the very first
  // request is 18 BYTES, not 1MiB: the clamp is in units of remaining NEWLINES,
  // which is exactly why no block can contain the final one.
  const Literals literals;
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_TRUE(seal.has_value());
  EXPECT_EQ(seal.value().event_stats.max_request,
            static_cast<std::size_t>(literals.number("prefix", "admitted_rows") - 1));
  EXPECT_LE(seal.value().event_stats.max_request, kBlockBytes);
}

TEST(PrefixSeal, TwoIndependentExtractionsAreByteIdentical) {
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  std::vector<std::string> leaves[2];
  std::string prefix_digest[2];
  for (int run = 0; run < 2; ++run) {
    MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
    CollectingSink sink;
    const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
    ASSERT_TRUE(seal.has_value()) << (seal.has_value() ? "" : seal.error().message());
    prefix_digest[run] = seal.value().consumed_prefix_sha256;
    for (const SessionSignals& session : sink.sessions) {
      leaves[run].push_back(render_safe_leaf(session));
    }
  }
  EXPECT_EQ(prefix_digest[0], prefix_digest[1]);
  ASSERT_EQ(leaves[0].size(), leaves[1].size());
  for (std::size_t i = 0; i < leaves[0].size(); ++i) {
    EXPECT_EQ(leaves[0][i], leaves[1][i]) << "leaf " << i;
  }
}

TEST(PrefixSeal, TheRetainWindowKeepsExactlyTheRequestedSessions) {
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(2, 2), sink.sink());
  ASSERT_TRUE(seal.has_value()) << (seal.has_value() ? "" : seal.error().message());
  ASSERT_EQ(sink.sessions.size(), 1U);
  EXPECT_EQ(sink.sessions[0].ordinal(), 2U);
  // Every session is still DECODED and root-checked; only retention is scoped.
  EXPECT_EQ(seal.value().roots_verified, kStop + 1U);
}

TEST(PrefixSeal, TheSafeLeafCarriesOnlyTheSevenFieldsAndIsSortedBySignalId) {
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  ASSERT_TRUE(seal_prefix(source, bounds, fixture_options(2, 2), sink.sink()).has_value());
  ASSERT_EQ(sink.sessions.size(), 1U);
  const std::string leaf = render_safe_leaf(sink.sessions[0]);
  EXPECT_EQ(leaf.substr(0, leaf.find('\n')),
            "ordinal\tsignal_id\tphysical_event_id\tpolicy_name\treversal_bps\textreme_side\t"
            "causal_visible_ts_ns");
  const auto& rows = sink.sessions[0].rows();
  ASSERT_EQ(rows.size(), 9U);
  for (std::size_t i = 1; i < rows.size(); ++i) {
    EXPECT_LT(rows[i - 1].signal_id, rows[i].signal_id);
  }
}

TEST(PrefixSeal, ARetainedSessionResolvesItsOwnMemberIdsAndOnlyThose) {
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  ASSERT_TRUE(seal_prefix(source, bounds, fixture_options(2, 2), sink.sink()).has_value());
  ASSERT_EQ(sink.sessions.size(), 1U);
  const Literals literals;
  EXPECT_NE(sink.sessions[0].find(literals.text("signal_id", "A1")), nullptr);
  // G1 is a member id no signal carries: it must not resolve.
  EXPECT_EQ(sink.sessions[0].find(literals.text("signal_id", "G1")), nullptr);
}

// --- refusals ---------------------------------------------------------------

TEST(PrefixSeal, ASessionCountThatDisagreesWithTheCensusRefuses) {
  const auto bounds = load_fixture_bounds("t14_bounds_bad_count.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(PrefixSeal, ASessionRootThatDisagreesWithTheCensusRefuses) {
  const auto bounds = load_fixture_bounds("t14_bounds_bad_root.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(PrefixSeal, NonMonotoneOrdinalsRefuseEvenWhenTheCensusAgreesWithThem) {
  // The fixture file goes 0,1,0,2,3,... AND its census is permuted the same
  // way, so the session-agreement check passes row by row. Only the
  // monotonicity law can catch this.
  MemorySource census(read_whole_file(fixture_path("t14_bounds_nonmonotone.tsv")));
  ReadStats stats;
  const auto bounds = load_t14_bounds(census, 2, stats);
  // The permuted census is not the dense 0..stop ladder, so the loader refuses
  // it first; feed the reader a hand-built permuted census to reach the row
  // check itself.
  EXPECT_FALSE(bounds.has_value());

  std::vector<T14Bound> permuted;
  const Literals literals;
  for (const std::uint32_t ordinal : {0U, 1U, 0U}) {
    T14Bound bound;
    bound.ordinal = ordinal;
    bound.day = literals.text("day", std::to_string(ordinal));
    bound.signal_count = static_cast<std::uint64_t>(literals.number("count", std::to_string(ordinal)));
    bound.signal_sequence_root = literals.text("root", std::to_string(ordinal));
    permuted.push_back(bound);
  }
  MemorySource source(read_whole_file(fixture_path("event_signals_nonmonotone.tsv")));
  CollectingSink sink;
  PrefixSealOptions options = fixture_options();
  options.stop_ordinal = 2;
  const auto seal = seal_prefix(source, permuted, options, sink.sink());
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::OUT_OF_ORDER);
}

TEST(PrefixSeal, ACarriageReturnInsideAnAdmittedRowRefuses) {
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_carriage_return.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::DECODE_FAILED);
}

TEST(PrefixSeal, ADuplicateSignalIdInsideOneSessionRefuses) {
  const auto bounds = load_fixture_bounds("t14_bounds_duplicate_id.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_duplicate_id.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(PrefixSeal, AHeaderThatIsNotThePinnedHeaderRefuses) {
  std::string text = read_whole_file(fixture_path("event_signals_good.tsv"));
  text[0] = 'O';  // "ordinal" -> "Ordinal"
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(text);
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

TEST(PrefixSeal, AStopOrdinalPastTheWallIsRefusedBeforeAnyByteIsRead) {
  MemorySource source(read_whole_file(fixture_path("t14_bounds_good.tsv")));
  ReadStats stats;
  const auto bounds = load_t14_bounds(source, 750, stats);
  ASSERT_FALSE(bounds.has_value());
  EXPECT_EQ(bounds.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  EXPECT_EQ(stats.pread_calls, 0U);
}

TEST(PrefixSeal, BoundsThatDoNotCoverTheStopRefuse) {
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", 2);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  const auto seal = seal_prefix(source, bounds, fixture_options(), sink.sink());
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::CONFIG);
}

TEST(PrefixSeal, TheProductionByteSizeGateRefusesAFileThatIsNotThePinnedSize) {
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  PrefixSealOptions options = fixture_options();
  options.require_pinned_event_bytes = true;
  const auto seal = seal_prefix(source, bounds, options, sink.sink());
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::SOURCE_AUTHENTICATION_FAILED);
}

TEST(PrefixSeal, TheFullScopeCensusGateRequiresTheDeclaredTenPointSevenMillionRows) {
  auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  ASSERT_FALSE(bounds.empty());
  // Present the fixture census as if it were the full 0..749 seal.
  bounds.resize(kMaxPrefixOrdinal + 1U, bounds.back());
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  CollectingSink sink;
  PrefixSealOptions options = fixture_options();
  options.stop_ordinal = kMaxPrefixOrdinal;
  options.require_full_row_census = true;
  const auto seal = seal_prefix(source, bounds, options, sink.sink());
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(PrefixSeal, ASinkRefusalStopsTheSealRatherThanBeingIgnored) {
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  MemorySource source(read_whole_file(fixture_path("event_signals_good.tsv")));
  const auto seal = seal_prefix(source, bounds, fixture_options(), [](SessionSignals&) {
    return qr::refuse<bool>(qr::Refusal(qr::RefusalCode::CONFIG, "test", "the sink refuses"));
  });
  ASSERT_FALSE(seal.has_value());
  EXPECT_EQ(seal.error().code(), qr::RefusalCode::CONFIG);
}

// --- the t14 census loader --------------------------------------------------

TEST(T14Bounds, ReadsTheCensusOneByteAtATimeAndClosesAtTheStop) {
  MemorySource source(read_whole_file(fixture_path("t14_bounds_good.tsv")));
  ReadStats stats;
  const auto bounds = load_t14_bounds(source, kStop, stats);
  ASSERT_TRUE(bounds.has_value()) << (bounds.has_value() ? "" : bounds.error().message());
  EXPECT_EQ(stats.max_request, 1U);
  EXPECT_EQ(stats.pread_calls, stats.requested_bytes);
  EXPECT_TRUE(source.closed());
  EXPECT_EQ(bounds.value().size(), kStop + 1U);
  const Literals literals;
  for (std::uint32_t ordinal = 0; ordinal <= kStop; ++ordinal) {
    EXPECT_EQ(bounds.value()[ordinal].signal_sequence_root,
              literals.text("root", std::to_string(ordinal)));
    EXPECT_EQ(bounds.value()[ordinal].day, literals.text("day", std::to_string(ordinal)));
  }
}

TEST(T14Bounds, ANonDenseOrdinalLadderRefuses) {
  MemorySource source(read_whole_file(fixture_path("t14_bounds_nonmonotone.tsv")));
  ReadStats stats;
  const auto bounds = load_t14_bounds(source, kStop, stats);
  ASSERT_FALSE(bounds.has_value());
  EXPECT_EQ(bounds.error().code(), qr::RefusalCode::OUT_OF_ORDER);
}

TEST(T14Bounds, AHeaderThatIsNotThePinnedHeaderRefuses) {
  std::string text = read_whole_file(fixture_path("t14_bounds_good.tsv"));
  text[0] = 'O';
  MemorySource source(text);
  ReadStats stats;
  const auto bounds = load_t14_bounds(source, kStop, stats);
  ASSERT_FALSE(bounds.has_value());
  EXPECT_EQ(bounds.error().code(), qr::RefusalCode::SCHEMA_MISMATCH);
}

// --- kernel-level accounting -------------------------------------------------

TEST(PrefixSeal, TheKernelIsNeverAskedForMoreBytesThanTheLedgerRecords) {
  // /proc/self/io's `rchar` counts bytes THIS PROCESS asked the kernel for. A
  // buffered reader, a readline, or a library prefetch would show up here as
  // bytes the ledger never requested.
  const auto bounds = load_fixture_bounds("t14_bounds_good.tsv", kStop);
  auto source = FileSource::open(fixture_path("event_signals_good.tsv"));
  ASSERT_TRUE(source.has_value());
  CollectingSink sink;
  const auto seal = seal_prefix(*source.value(), bounds, fixture_options(), sink.sink());
  ASSERT_TRUE(seal.has_value()) << (seal.has_value() ? "" : seal.error().message());
  ASSERT_TRUE(seal.value().io_before.available);
  ASSERT_TRUE(seal.value().io_after.available);
  const std::uint64_t rchar = seal.value().io_after.rchar - seal.value().io_before.rchar;
  // The only slack is /proc/self/io itself, read once at each end.
  EXPECT_LE(rchar, seal.value().event_stats.requested_bytes + 8192U);
  EXPECT_GE(rchar, seal.value().event_stats.requested_bytes);
}

TEST(PrefixSeal, TheProductionSourceRefusesAReadAfterClose) {
  auto source = FileSource::open(fixture_path("event_signals_good.tsv"));
  ASSERT_TRUE(source.has_value());
  source.value()->close();
  std::uint8_t byte = 0;
  const auto step = source.value()->read_at(&byte, 1, 0);
  ASSERT_FALSE(step.has_value());
  EXPECT_EQ(step.error().code(), qr::RefusalCode::IO);
}

}  // namespace
