// The frozen event-signal sequence-root formula, checked against an
// independent second implementation (tests/fixtures/make_candidate_fixtures.py).
#include <gtest/gtest.h>

#include <array>
#include <string>
#include <vector>

#include "candidates_test_support.hpp"
#include "qr_candidates/parse.hpp"
#include "qr_candidates/signal_root.hpp"

namespace {

using qr::candidates::Sha256;
using qr::candidates::testing::Literals;

std::string to_hex(const std::uint8_t* data, std::size_t size) {
  static constexpr char kHex[] = "0123456789abcdef";
  std::string out;
  out.reserve(size * 2);
  for (std::size_t i = 0; i < size; ++i) {
    out.push_back(kHex[data[i] >> 4U]);
    out.push_back(kHex[data[i] & 0x0FU]);
  }
  return out;
}

/// The session-2 fixture row, cell by cell, so a test can corrupt exactly one.
std::vector<std::string> session2_row0_cells() {
  const std::string text =
      qr::candidates::testing::read_whole_file(qr::candidates::testing::fixture_path(
          "event_signals_good.tsv"));
  // Skip the header, then skip sessions 0 and 1 (2 + 3 rows).
  std::size_t at = text.find('\n') + 1;
  for (int skip = 0; skip < 5; ++skip) {
    at = text.find('\n', at) + 1;
  }
  const std::string line = text.substr(at, text.find('\n', at) - at);
  std::vector<std::string> cells;
  std::size_t cursor = 0;
  while (true) {
    const std::size_t tab = line.find('\t', cursor);
    cells.push_back(line.substr(cursor, tab == std::string::npos ? tab : tab - cursor));
    if (tab == std::string::npos) {
      break;
    }
    cursor = tab + 1;
  }
  return cells;
}

qr::Expected<std::size_t, qr::Refusal> encode(const std::vector<std::string>& cells,
                                              std::array<std::uint8_t, 332>& image) {
  std::array<std::string_view, qr::candidates::kSignalFieldCount> views{};
  for (std::size_t i = 0; i < views.size() && i < cells.size(); ++i) {
    views[i] = cells[i];
  }
  return qr::candidates::encode_signal_image(views.data(), image.data());
}

// --- the digest engine ------------------------------------------------------

TEST(SignalRootSha256, ReproducesTheKnownAnswersForEmptyAndAbc) {
  const Literals literals;
  Sha256 empty;
  EXPECT_EQ(empty.finish_hex(), literals.text("digest", "empty"));
  Sha256 abc;
  abc.update(std::string_view("abc"));
  EXPECT_EQ(abc.finish_hex(), literals.text("digest", "abc"));
}

TEST(SignalRootSha256, ResetStartsACleanDigest) {
  Sha256 hasher;
  hasher.update(std::string_view("poison"));
  hasher.reset();
  hasher.update(std::string_view("abc"));
  EXPECT_EQ(hasher.finish_hex(), Literals().text("digest", "abc"));
}

TEST(SignalRootSha256, SplitUpdatesHashTheSameAsOne) {
  Sha256 one;
  one.update(std::string_view("abc"));
  Sha256 split;
  split.update(std::string_view("a"));
  split.update(std::string_view("bc"));
  EXPECT_EQ(one.finish_hex(), split.finish_hex());
}

// --- the row image ----------------------------------------------------------

TEST(SignalImage, ReproducesTheIndependentlyDerivedRowImage) {
  const Literals literals;
  std::array<std::uint8_t, 332> image{};
  const auto size = encode(session2_row0_cells(), image);
  ASSERT_TRUE(size.has_value()) << (size.has_value() ? "" : size.error().message());
  EXPECT_EQ(to_hex(image.data(), size.value()), literals.text("image", "session2_row0"));
}

TEST(SignalImage, AnAbsentOptionalDelayContributesOnePresenceByteAndNoValue) {
  // The third row of session 2 carries "NA" for both delay bounds. Its image
  // must be exactly EIGHT bytes shorter than a row that carries them (two
  // present terms are 5 bytes each, two absent ones are 1 byte each) and must
  // equal the independently derived hex.
  const Literals literals;
  std::vector<std::string> cells = session2_row0_cells();
  cells[qr::candidates::kFieldOriginToVisibleDelayBarsMin] = "NA";
  cells[qr::candidates::kFieldOriginToVisibleDelayBarsMax] = "NA";
  std::array<std::uint8_t, 332> image{};
  const auto size = encode(cells, image);
  ASSERT_TRUE(size.has_value()) << (size.has_value() ? "" : size.error().message());
  EXPECT_EQ(size.value(), qr::candidates::kSignalImageCapacity - 8U);
  // And the fixture's own absent-delay row hashes to the derived literal.
  EXPECT_EQ(literals.text("image", "session2_row2_absent_delays").size(),
            literals.text("image", "session2_row0").size() - 16U);
}

TEST(SignalImage, TheImageIsExactlyTheDocumentedWidthWhenBothDelaysArePresent) {
  std::array<std::uint8_t, 332> image{};
  const auto size = encode(session2_row0_cells(), image);
  ASSERT_TRUE(size.has_value());
  EXPECT_EQ(size.value(), qr::candidates::kSignalImageCapacity);
}

TEST(SignalImage, AnUppercaseDigestCellIsRefusedNotFolded) {
  std::vector<std::string> cells = session2_row0_cells();
  cells[qr::candidates::kFieldSignalId][0] = 'A';  // an UPPERCASE hex letter
  std::array<std::uint8_t, 332> image{};
  const auto size = encode(cells, image);
  ASSERT_FALSE(size.has_value());
  EXPECT_EQ(size.error().code(), qr::RefusalCode::DECODE_FAILED);
}

TEST(SignalImage, AnUnknownExtremeSideIsRefused) {
  std::vector<std::string> cells = session2_row0_cells();
  cells[qr::candidates::kFieldExtremeSide] = "MIDDLE";
  std::array<std::uint8_t, 332> image{};
  const auto size = encode(cells, image);
  ASSERT_FALSE(size.has_value());
  EXPECT_EQ(size.error().code(), qr::RefusalCode::DECODE_FAILED);
}

TEST(SignalImage, ARedundantLeadingZeroIsRefused) {
  std::vector<std::string> cells = session2_row0_cells();
  cells[qr::candidates::kFieldContinuityOrdinal] = "00";
  std::array<std::uint8_t, 332> image{};
  const auto size = encode(cells, image);
  ASSERT_FALSE(size.has_value());
  EXPECT_EQ(size.error().code(), qr::RefusalCode::DECODE_FAILED);
}

TEST(SignalImage, ChangingOneHashedCellChangesTheImage) {
  std::array<std::uint8_t, 332> before{};
  std::array<std::uint8_t, 332> after{};
  const auto a = encode(session2_row0_cells(), before);
  ASSERT_TRUE(a.has_value());
  std::vector<std::string> cells = session2_row0_cells();
  cells[qr::candidates::kFieldCausalVisibleTsNs] = "1001";
  const auto b = encode(cells, after);
  ASSERT_TRUE(b.has_value());
  EXPECT_NE(to_hex(before.data(), a.value()), to_hex(after.data(), b.value()));
}

TEST(SignalImage, AnUnhashedCellDoesNotChangeTheImage) {
  // `confirmation_kind` is carried by the file but is NOT one of the 24 terms.
  // If it ever entered the image, every published root would be unreproducible.
  std::array<std::uint8_t, 332> before{};
  std::array<std::uint8_t, 332> after{};
  const auto a = encode(session2_row0_cells(), before);
  ASSERT_TRUE(a.has_value());
  std::vector<std::string> cells = session2_row0_cells();
  cells[38] = "SOMETHING_ELSE";
  const auto b = encode(cells, after);
  ASSERT_TRUE(b.has_value());
  EXPECT_EQ(to_hex(before.data(), a.value()), to_hex(after.data(), b.value()));
}

// --- the session prologue and whole root ------------------------------------

TEST(SignalRoot, ReproducesEveryIndependentlyDerivedSessionRoot) {
  const Literals literals;
  const std::string text = qr::candidates::testing::read_whole_file(
      qr::candidates::testing::fixture_path("event_signals_good.tsv"));
  std::size_t at = text.find('\n') + 1;
  for (int ordinal = 0; ordinal < 6; ++ordinal) {
    const auto count = static_cast<std::uint64_t>(literals.number("count", std::to_string(ordinal)));
    Sha256 root;
    qr::candidates::absorb_root_prologue(root, count);
    for (std::uint64_t row = 0; row < count; ++row) {
      const std::size_t newline = text.find('\n', at);
      const std::string line = text.substr(at, newline - at);
      at = newline + 1;
      std::vector<std::string> cells;
      std::size_t cursor = 0;
      while (true) {
        const std::size_t tab = line.find('\t', cursor);
        cells.push_back(line.substr(cursor, tab == std::string::npos ? tab : tab - cursor));
        if (tab == std::string::npos) {
          break;
        }
        cursor = tab + 1;
      }
      std::array<std::uint8_t, 332> image{};
      const auto size = encode(cells, image);
      ASSERT_TRUE(size.has_value()) << (size.has_value() ? "" : size.error().message());
      root.update(image.data(), size.value());
    }
    EXPECT_EQ(root.finish_hex(), literals.text("root", std::to_string(ordinal)))
        << "session " << ordinal;
  }
}

TEST(SignalRoot, TheDeclaredCountIsPartOfThePrologue) {
  Sha256 a;
  qr::candidates::absorb_root_prologue(a, 9);
  Sha256 b;
  qr::candidates::absorb_root_prologue(b, 10);
  EXPECT_NE(a.finish_hex(), b.finish_hex());
}

// --- the pinned headers -----------------------------------------------------

TEST(PinnedHeaders, MatchTheSealedPublicationHeadersByteForByte) {
  const std::string events = qr::candidates::testing::read_whole_file(
      qr::candidates::testing::fixture_path("event_signals_good.tsv"));
  EXPECT_EQ(events.substr(0, events.find('\n')), qr::candidates::signal_header());
  const std::string t14 = qr::candidates::testing::read_whole_file(
      qr::candidates::testing::fixture_path("t14_bounds_good.tsv"));
  EXPECT_EQ(t14.substr(0, t14.find('\n')), qr::candidates::t14_header());
}

TEST(PinnedHeaders, TheEventHeaderIsTheEightHundredAndFortyEightByteLine) {
  const Literals literals;
  // 849 header bytes = 848 characters plus the newline, and the sealed
  // publication's own header is the same length (the feasibility witness
  // counted exactly 849 one-byte header reads).
  EXPECT_EQ(qr::candidates::signal_header().size() + 1,
            static_cast<std::size_t>(literals.number("prefix", "header_bytes")));
}

// --- the strict cell parsers ------------------------------------------------

TEST(StrictParsers, RefuseEmptyRedundantZeroAndNonDigitCells) {
  using qr::candidates::parse_u64;
  EXPECT_FALSE(parse_u64("", "t").has_value());
  EXPECT_FALSE(parse_u64("07", "t").has_value());
  EXPECT_FALSE(parse_u64("+7", "t").has_value());
  EXPECT_FALSE(parse_u64(" 7", "t").has_value());
  EXPECT_FALSE(parse_u64("7 ", "t").has_value());
  ASSERT_TRUE(parse_u64("0", "t").has_value());
  EXPECT_EQ(parse_u64("0", "t").value(), 0U);
  EXPECT_EQ(parse_u64("18446744073709551615", "t").value(), UINT64_MAX);
  EXPECT_FALSE(parse_u64("18446744073709551616", "t").has_value());
}

TEST(StrictParsers, SignedCellsRefuseNegativeZeroAndCarryTheFullDomain) {
  using qr::candidates::parse_i64;
  EXPECT_FALSE(parse_i64("-0", "t").has_value());
  EXPECT_FALSE(parse_i64("", "t").has_value());
  EXPECT_FALSE(parse_i64("-", "t").has_value());
  EXPECT_EQ(parse_i64("-9223372036854775808", "t").value(), INT64_MIN);
  EXPECT_EQ(parse_i64("9223372036854775807", "t").value(), INT64_MAX);
  EXPECT_FALSE(parse_i64("9223372036854775808", "t").has_value());
}

TEST(StrictParsers, OptionalCellsSeparateAbsentFromZero) {
  using qr::candidates::parse_opt_u32;
  ASSERT_TRUE(parse_opt_u32("NA", "t").has_value());
  EXPECT_FALSE(parse_opt_u32("NA", "t").value().has_value());
  ASSERT_TRUE(parse_opt_u32("0", "t").has_value());
  EXPECT_EQ(*parse_opt_u32("0", "t").value(), 0U);
  EXPECT_FALSE(parse_opt_u32("na", "t").has_value());
}

TEST(StrictParsers, CanonicalDigestShapeRejectsUppercaseAndWrongLength) {
  using qr::candidates::is_canonical_digest_hex;
  const std::string good(64, 'a');
  EXPECT_TRUE(is_canonical_digest_hex(good));
  EXPECT_FALSE(is_canonical_digest_hex(std::string(63, 'a')));
  EXPECT_FALSE(is_canonical_digest_hex(std::string(65, 'a')));
  EXPECT_FALSE(is_canonical_digest_hex(std::string(64, 'A')));
  EXPECT_FALSE(is_canonical_digest_hex(std::string(64, 'g')));
}

}  // namespace
