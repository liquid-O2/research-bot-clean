// Fixture REG-1..REG-7: the frozen registry, its digest gate, and the
// single-byte-flip refusal named in the WP1 brief.
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <string_view>
#include <vector>

#include "gtest/gtest.h"
#include "qr_registry/registry.hpp"

namespace {

std::filesystem::path scratch_dir() {
  const std::filesystem::path dir = std::filesystem::path(QR_TEST_SCRATCH_DIR) / "registry";
  std::filesystem::create_directories(dir);
  return dir;
}

std::string read_file(const std::filesystem::path& path) {
  std::ifstream stream(path, std::ios::binary);
  return std::string(std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>());
}

TEST(RegistryDigestGate, EmbeddedTextHashesToThePinnedDigest) {
  const std::string_view text = qr::embedded_registry_text();
  EXPECT_EQ(text.size(), 575296U) << "embedded blob is not the pinned 575,296-byte TSV";
  EXPECT_EQ(qr::sha256_hex(text), qr::kExpectedRegistrySha256);
  EXPECT_EQ(qr::kExpectedRegistrySha256,
            "233dc10ab4c0973a8caa92792757a322bbff102296f0e7ffb71c6d78810bcaed")
      << "the pinned digest must stay the corpus authority value";
}

TEST(RegistryDigestGate, EmbeddedBytesAreTheOnDiskRegistryBytes) {
  const std::string on_disk = read_file(QR_REGISTRY_TSV_PATH);
  const std::string embedded(qr::embedded_registry_text());
  ASSERT_FALSE(on_disk.empty());
  // Compared by size, digest and equality rather than by value, so a failure
  // reports three short facts instead of dumping 575KB twice.
  EXPECT_EQ(on_disk.size(), embedded.size());
  EXPECT_EQ(qr::sha256_hex(on_disk), qr::sha256_hex(embedded));
  EXPECT_TRUE(on_disk == embedded) << "configure-time embedding mangled the registry bytes";
}

TEST(RegistryDigestGate, SingleFlippedByteIsRefusedWithATypedError) {
  const std::string original = read_file(QR_REGISTRY_TSV_PATH);
  ASSERT_GT(original.size(), 1000U);

  // Flip exactly one byte, in the middle of a data row, in a copy.
  const std::size_t victim = original.size() / 2;
  std::string flipped = original;
  flipped[victim] = static_cast<char>(flipped[victim] ^ 0x01);
  ASSERT_NE(flipped, original);

  const std::filesystem::path path = scratch_dir() / "registry_one_byte_flipped.tsv";
  {
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    out.write(flipped.data(), static_cast<std::streamsize>(flipped.size()));
  }

  const auto loaded = qr::Registry::load_from_file(path);
  ASSERT_FALSE(loaded.has_value()) << "a flipped byte must never authenticate";
  EXPECT_EQ(loaded.error().code(), qr::RefusalCode::REGISTRY_DIGEST_MISMATCH);
  EXPECT_NE(loaded.error().message().find("REGISTRY_DIGEST_MISMATCH"), std::string::npos);

  // The unflipped copy through the same code path still authenticates, so the
  // refusal is caused by the flip and not by the file-loading path itself.
  const std::filesystem::path clean_path = scratch_dir() / "registry_clean_copy.tsv";
  {
    std::ofstream out(clean_path, std::ios::binary | std::ios::trunc);
    out.write(original.data(), static_cast<std::streamsize>(original.size()));
  }
  const auto clean = qr::Registry::load_from_file(clean_path);
  ASSERT_TRUE(clean.has_value()) << "byte-identical copy must authenticate";
  EXPECT_EQ(clean.value().size(), qr::kRegistrySessionCount);
}

TEST(RegistryDigestGate, MissingFileIsAnIoRefusalNotACrash) {
  const auto loaded = qr::Registry::load_from_file(scratch_dir() / "does_not_exist.tsv");
  ASSERT_FALSE(loaded.has_value());
  EXPECT_EQ(loaded.error().code(), qr::RefusalCode::IO);
}

TEST(RegistryParse, EmbeddedRegistryIsTheFrozenOneThousandAndThreeSessions) {
  const auto loaded = qr::Registry::load_embedded();
  ASSERT_TRUE(loaded.has_value()) << loaded.error().message();
  const qr::Registry& registry = loaded.value();

  ASSERT_EQ(registry.size(), 1003U);
  EXPECT_EQ(registry.receipt().session_count, 1003U);
  EXPECT_EQ(registry.receipt().sha256, qr::kExpectedRegistrySha256);
  EXPECT_EQ(registry.sessions().front().day, "2022-01-03");
  EXPECT_EQ(registry.sessions().back().day, "2025-12-31");
}

TEST(RegistryParse, EveryRowCarriesTheTenExposedFieldsAndItsInvariants) {
  const auto loaded = qr::Registry::load_embedded();
  ASSERT_TRUE(loaded.has_value());
  const qr::Registry& registry = loaded.value();

  std::size_t cent = 0;
  std::size_t dollar = 0;
  for (std::size_t i = 0; i < registry.size(); ++i) {
    const qr::Session& session = registry.sessions()[i];
    EXPECT_EQ(session.day.size(), 10U);
    EXPECT_EQ(session.civil_date.to_ymd(), session.day);
    EXPECT_EQ(session.session_end_ns - session.session_start_ns,
              session.expected_bar_count * qr::kBarNs)
        << session.day;
    EXPECT_TRUE(session.expected_bar_count == 390 || session.expected_bar_count == 210)
        << session.day << " has bar count " << session.expected_bar_count;
    EXPECT_EQ(session.source_sha256.size(), 64U) << session.day;
    EXPECT_GT(session.source_size_bytes, 0) << session.day;
    EXPECT_GT(session.raw_rth_row_count, 0) << session.day;
    EXPECT_GT(session.complete_group_count, 0) << session.day;
    EXPECT_LE(session.complete_group_count, session.raw_rth_row_count) << session.day;
    EXPECT_EQ(session.source_relative_path, session.day.substr(0, 4) + "/" + session.day + ".parquet")
        << session.day;
    if (i > 0) {
      EXPECT_LT(registry.sessions()[i - 1].day, session.day) << "registry is not strictly sorted";
    }
    if (session.source_profile == qr::SourceProfile::CentInt32) {
      ++cent;
    } else {
      ++dollar;
    }
  }

  // FINAL_PLAN section 1, measured data truth: cent_int32 x 364 /
  // dollar_float64 x 639, interleaved (the registry row decides, never
  // chronology).
  EXPECT_EQ(cent, 364U);
  EXPECT_EQ(dollar, 639U);
  EXPECT_EQ(cent + dollar, qr::kRegistrySessionCount);
  EXPECT_STREQ(qr::source_profile_name(qr::SourceProfile::CentInt32), "cent_int32");
  EXPECT_STREQ(qr::source_profile_name(qr::SourceProfile::DollarFloat64), "dollar_float64");
}

TEST(RegistryParse, LookupByOrdinalAndDayAgreeAndRefuseOutOfRange) {
  const auto loaded = qr::Registry::load_embedded();
  ASSERT_TRUE(loaded.has_value());
  const qr::Registry& registry = loaded.value();

  const auto first_scoped = registry.session_at(125);
  ASSERT_TRUE(first_scoped.has_value());
  EXPECT_EQ(first_scoped.value()->day, "2022-07-05");
  EXPECT_EQ(first_scoped.value()->source_profile, qr::SourceProfile::CentInt32);

  const auto last_scoped = registry.session_at(749);
  ASSERT_TRUE(last_scoped.has_value());
  EXPECT_EQ(last_scoped.value()->day, "2024-12-26");

  const auto ordinal = registry.ordinal_of_day("2022-07-05");
  ASSERT_TRUE(ordinal.has_value());
  EXPECT_EQ(ordinal.value(), 125);
  const auto last = registry.ordinal_of_day("2025-12-31");
  ASSERT_TRUE(last.has_value());
  EXPECT_EQ(last.value(), 1002);

  EXPECT_FALSE(registry.session_at(-1).has_value());
  const auto past_end = registry.session_at(1003);
  ASSERT_FALSE(past_end.has_value());
  EXPECT_EQ(past_end.error().code(), qr::RefusalCode::DAY_OUTSIDE_CALENDAR);
  const auto in_2026 = registry.ordinal_of_day("2026-01-02");
  ASSERT_FALSE(in_2026.has_value());
  EXPECT_EQ(in_2026.error().code(), qr::RefusalCode::UNKNOWN_SESSION);
  EXPECT_FALSE(registry.ordinal_of_day("2021-12-31").has_value());
}

TEST(RegistryParse, MalformedTextIsRefusedWithATypedRegistryError) {
  const std::string header = std::string(qr::kRegistryHeader);
  struct Case {
    const char* name;
    std::string text;
  };
  const std::vector<Case> cases = {
      {"empty", ""},
      {"header only", header + "\n"},
      {"drifted header", std::string("day\tnope\n")},
      {"short row", header + "\n2022-01-03\t1\t2\n"},
      {"bad day", header +
                      "\n2022-13-40\t1641220200000000000\t1641243600000000000\t390\t"
                      "2022/x.parquet\ta\t" +
                      std::string(64, 'a') +
                      "\t1\tcent_int32\t1\t1\tb\tc\td\te\tf\n"},
      {"unknown profile", header +
                              "\n2022-01-03\t1641220200000000000\t1641243600000000000\t390\t"
                              "2022/x.parquet\ta\t" +
                              std::string(64, 'a') +
                              "\t1\tfurlongs\t1\t1\tb\tc\td\te\tf\n"},
      {"span disagrees", header +
                             "\n2022-01-03\t1641220200000000000\t1641243600000000001\t390\t"
                             "2022/x.parquet\ta\t" +
                             std::string(64, 'a') +
                             "\t1\tcent_int32\t1\t1\tb\tc\td\te\tf\n"},
  };

  for (const Case& item : cases) {
    const auto parsed = qr::Registry::parse_without_digest_gate(item.text);
    ASSERT_FALSE(parsed.has_value()) << "accepted malformed registry: " << item.name;
    EXPECT_EQ(parsed.error().code(), qr::RefusalCode::REGISTRY_MALFORMED) << item.name;
  }
}

TEST(RegistryBudget, FullParseAndDigestGateUnderFiveSeconds) {
  // WP1 budget: qr_registry full parse + hash gate <= 5s (the hash is of the
  // 575KB TSV itself; per-payload-file digests are a later work package).
  const auto started = std::chrono::steady_clock::now();
  const auto loaded = qr::Registry::load_embedded();
  const auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - started);
  ASSERT_TRUE(loaded.has_value());
  EXPECT_EQ(loaded.value().size(), qr::kRegistrySessionCount);
  EXPECT_LT(elapsed.count(), 5.0) << "registry parse+gate budget blown: " << elapsed.count() << "s";
  std::printf("[budget] registry parse+digest-gate: %.4f s\n", elapsed.count());
}

}  // namespace
