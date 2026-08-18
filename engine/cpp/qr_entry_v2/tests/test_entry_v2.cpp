#include <zstd.h>
#include <openssl/evp.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include "gtest/gtest.h"
#include "qr_dbn/dbn.hpp"
#include "qr_entry_v2/forecast.hpp"
#include "qr_entry_v2/g1.hpp"
#include "qr_entry_v2/substrate.hpp"
#include "qr_futsess/calendar.hpp"

namespace {

namespace fs = std::filesystem;
using qr::dbn::BidAskPair;
using qr::dbn::Mbp1Msg;
using qr::entry_v2::Config;
using qr::entry_v2::EventRow;
using qr::entry_v2::LockStatus;
using qr::entry_v2::PhaseSource;
using qr::entry_v2::TallyRow;

constexpr std::size_t kSymbolWidth = qr::dbn::kSymbolCstrLenV1;
constexpr std::uint64_t kPreH2EndNs = 1'751'320'800'000'000'000ULL;

template <class T>
void put_le(std::vector<std::uint8_t>* out, T value) {
  const auto* bytes = reinterpret_cast<const std::uint8_t*>(&value);
  out->insert(out->end(), bytes, bytes + sizeof(T));
}

void put_cstr(std::vector<std::uint8_t>* out, const std::string& text, std::size_t width) {
  for (std::size_t i = 0; i < width; ++i) {
    out->push_back(i < text.size() ? static_cast<std::uint8_t>(text[i]) : 0u);
  }
}

struct Mapping {
  std::string raw;
  std::string iid;
  std::uint32_t start_d8 = 20230101;
  std::uint32_t end_d8_exclusive = 20260101;
};

std::vector<std::uint8_t> metadata_body(
    const std::vector<Mapping>& mappings,
    std::uint64_t end_ts_recv_ns = kPreH2EndNs) {
  std::vector<std::uint8_t> out;
  put_cstr(&out, "GLBX.MDP3", 16);
  put_le<std::uint16_t>(&out, qr::dbn::kSchemaMbp1);
  put_le<std::uint64_t>(&out, 1'609'459'200'000'000'000ULL);
  put_le<std::uint64_t>(&out, end_ts_recv_ns);
  put_le<std::uint64_t>(&out, 0);
  put_le<std::uint64_t>(&out, ~std::uint64_t{0});
  out.push_back(3);
  out.push_back(0);
  out.push_back(0);
  out.insert(out.end(), 47, 0u);
  put_le<std::uint32_t>(&out, 0);
  put_le<std::uint32_t>(&out, static_cast<std::uint32_t>(mappings.size()));
  for (const Mapping& mapping : mappings) {
    put_cstr(&out, mapping.raw, kSymbolWidth);
  }
  put_le<std::uint32_t>(&out, 0);  // partial
  put_le<std::uint32_t>(&out, 0);  // not found
  put_le<std::uint32_t>(&out, static_cast<std::uint32_t>(mappings.size()));
  for (const Mapping& mapping : mappings) {
    put_cstr(&out, mapping.raw, kSymbolWidth);
    put_le<std::uint32_t>(&out, 1);
    put_le<std::uint32_t>(&out, mapping.start_d8);
    put_le<std::uint32_t>(&out, mapping.end_d8_exclusive);
    put_cstr(&out, mapping.iid, kSymbolWidth);
  }
  return out;
}

Mbp1Msg record(std::uint32_t iid, std::uint64_t ts_ns, std::uint32_t sequence) {
  Mbp1Msg row{};
  row.hd.length = static_cast<std::uint8_t>(sizeof(Mbp1Msg) / qr::dbn::kLengthUnit);
  row.hd.rtype = qr::dbn::kRTypeMbp1;
  row.hd.publisher_id = 1;
  row.hd.instrument_id = iid;
  row.hd.ts_event = ts_ns;
  row.price = 25'005'000'000LL + static_cast<std::int64_t>(iid);
  row.size = 2;
  row.action = 'A';
  row.side = 'B';
  row.flags = 0x80u;
  row.depth = 0;
  row.ts_recv = ts_ns + 10u;
  row.ts_in_delta = 7;
  row.sequence = sequence;
  row.levels[0] = BidAskPair{25'000'000'000LL, 25'010'000'000LL, 4, 5, 2, 3};
  return row;
}

std::string write_stream(const fs::path& path, const std::vector<Mapping>& mappings,
                         std::vector<Mbp1Msg> records,
                         std::uint64_t end_ts_recv_ns = kPreH2EndNs) {
  std::stable_sort(records.begin(), records.end(), [](const Mbp1Msg& lhs, const Mbp1Msg& rhs) {
    return lhs.hd.ts_event < rhs.hd.ts_event;
  });
  const std::vector<std::uint8_t> body = metadata_body(mappings, end_ts_recv_ns);
  std::vector<std::uint8_t> raw;
  raw.push_back('D');
  raw.push_back('B');
  raw.push_back('N');
  raw.push_back(1);
  put_le<std::uint32_t>(&raw, static_cast<std::uint32_t>(body.size()));
  raw.insert(raw.end(), body.begin(), body.end());
  for (const Mbp1Msg& row : records) {
    const auto* bytes = reinterpret_cast<const std::uint8_t*>(&row);
    raw.insert(raw.end(), bytes, bytes + sizeof(row));
  }
  std::vector<std::uint8_t> compressed(ZSTD_compressBound(raw.size()));
  const std::size_t n =
      ZSTD_compress(compressed.data(), compressed.size(), raw.data(), raw.size(), 3);
  EXPECT_EQ(ZSTD_isError(n), 0u);
  fs::create_directories(path.parent_path());
  std::FILE* file = std::fopen(path.c_str(), "wb");
  EXPECT_NE(file, nullptr);
  if (file != nullptr) {
    EXPECT_EQ(std::fwrite(compressed.data(), 1, n, file), n);
    std::fclose(file);
  }
  return path.string();
}

std::string write_fixture(const fs::path& path, int n_sessions) {
  EXPECT_TRUE(qr::futsess::init_globex_timezone().has_value());
  const std::vector<Mapping> mappings = {
      {"SIH4", "10"}, {"SIK4", "20"}, {"SIH4-SIK4", "99"}};
  std::vector<Mbp1Msg> records;
  std::uint32_t sequence = 1;
  const std::int64_t first_day = qr::futsess::date_to_day({2023, 12, 1});
  for (int day = 0; day < n_sessions; ++day) {
    const qr::futsess::Date date = qr::futsess::day_to_date(first_day + day);
    const auto [open, close] = qr::futsess::session_bounds(date);
    (void)close;
    // Six clean profile observations for each outright. Day zero is an exact
    // tie; the lower-iid law must lock iid=10 on day one.
    for (int k = 0; k < 6; ++k) {
      const std::uint64_t base = static_cast<std::uint64_t>(open + 60 + k * 3600) *
                                 1'000'000'000ull;
      records.push_back(record(10, base + 10u, sequence++));
      records.push_back(record(20, base + 20u, sequence++));
    }
    // A spread dominates every session by raw update count but is ineligible
    // for the outright-only lock.
    for (int k = 0; k < 12; ++k) {
      const std::uint64_t ts = static_cast<std::uint64_t>(open + 100 + k) * 1'000'000'000ull;
      records.push_back(record(99, ts, sequence++));
    }
    // Day one has an enormous current-session iid=20 majority. Its own lock
    // must nevertheless remain iid=10 from completed day zero.
    if (day == 1) {
      for (int k = 0; k < 20; ++k) {
        const std::uint64_t ts = static_cast<std::uint64_t>(open + 20'000 + k) *
                                 1'000'000'000ull;
        records.push_back(record(20, ts, sequence++));
      }
    } else if (day > 1 && day % 2 == 0) {
      const std::uint64_t ts = static_cast<std::uint64_t>(open + 25'000) * 1'000'000'000ull;
      records.push_back(record(10, ts, sequence++));
    } else if (day > 1) {
      const std::uint64_t ts = static_cast<std::uint64_t>(open + 25'000) * 1'000'000'000ull;
      records.push_back(record(20, ts, sequence++));
    }
  }
  return write_stream(path, mappings, std::move(records));
}

std::string write_mixed_2025_fixture(const fs::path& path) {
  EXPECT_TRUE(qr::futsess::init_globex_timezone().has_value());
  const std::vector<Mapping> mappings = {{"SIU5", "10"}, {"SIZ5", "20"}};
  std::vector<Mbp1Msg> records;
  std::uint32_t sequence = 1;
  for (const qr::futsess::Date date : {qr::futsess::Date{2025, 6, 29},
                                      qr::futsess::Date{2025, 6, 30},
                                      qr::futsess::Date{2025, 7, 1}}) {
    const auto [open, close] = qr::futsess::session_bounds(date);
    (void)close;
    for (int k = 0; k < 3; ++k) {
      const std::uint64_t ts = static_cast<std::uint64_t>(open + 60 + k * 60) *
                               1'000'000'000ull;
      records.push_back(record(10, ts + 10u, sequence++));
    }
    const std::uint64_t other = static_cast<std::uint64_t>(open + 300) * 1'000'000'000ull;
    records.push_back(record(20, other + 20u, sequence++));
  }
  return write_stream(path, mappings, std::move(records),
                      1'767'225'600'000'000'000ULL);
}

std::string text(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  std::ostringstream out;
  out << in.rdbuf();
  return out.str();
}

std::string sha256(const fs::path& path) {
  const std::string bytes = text(path);
  unsigned char digest[EVP_MAX_MD_SIZE]{};
  unsigned int length = 0;
  EXPECT_EQ(EVP_Digest(bytes.data(), bytes.size(), digest, &length,
                       EVP_sha256(), nullptr), 1);
  static constexpr char hex[] = "0123456789abcdef";
  std::string out(length * 2u, '0');
  for (unsigned int i = 0; i < length; ++i) {
    out[2u * i] = hex[digest[i] >> 4u];
    out[2u * i + 1u] = hex[digest[i] & 0x0fu];
  }
  return out;
}

void write_bytes(const fs::path& path, std::string_view bytes) {
  fs::create_directories(path.parent_path());
  std::FILE* file = std::fopen(path.c_str(), "wb");
  ASSERT_NE(file, nullptr);
  if (file != nullptr) {
    EXPECT_EQ(std::fwrite(bytes.data(), 1, bytes.size(), file), bytes.size());
    EXPECT_EQ(std::fclose(file), 0);
  }
}

template <class T>
void overwrite_le(std::string* bytes, std::size_t offset, T value) {
  ASSERT_NE(bytes, nullptr);
  ASSERT_LE(offset + sizeof(T), bytes->size());
  std::memcpy(bytes->data() + offset, &value, sizeof(value));
}

const qr::entry_v2::LockRow* lock_for(const std::vector<qr::entry_v2::LockRow>& rows,
                                      std::int32_t d8) {
  const auto found = std::find_if(rows.begin(), rows.end(), [d8](const auto& row) {
    return row.d8 == d8;
  });
  return found == rows.end() ? nullptr : &*found;
}

const qr::entry_v2::PhaseRow* phase_for(const std::vector<qr::entry_v2::PhaseRow>& rows,
                                        std::int32_t month) {
  const auto found = std::find_if(rows.begin(), rows.end(), [month](const auto& row) {
    return row.month == month;
  });
  return found == rows.end() ? nullptr : &*found;
}

class EntryV2Fixture : public ::testing::Test {
 protected:
  void SetUp() override {
    scratch_ = fs::path(QR_TEST_SCRATCH_DIR) / "qr_entry_v2_fixture";
    std::error_code ec;
    fs::remove_all(scratch_, ec);
    fs::create_directories(scratch_);
    input_ = write_fixture(
        scratch_ / "glbx-mdp3-20231201-20240203.mbp-1.dbn.zst", 65);
  }

  Config config(const char* root) const {
    Config out;
    out.asset = qr::futsess::Asset::SI;
    out.inputs = {input_};
    out.development_input_sha256[input_] = sha256(input_);
    out.output_root = (scratch_ / root).string();
    return out;
  }

  fs::path scratch_;
  std::string input_;
};

TEST_F(EntryV2Fixture, BoundedRawFixtureRunsAllFourProductionStages) {
  const Config cfg = config("run_a");
  auto result = qr::entry_v2::run(cfg, qr::entry_v2::Stage::ALL);
  ASSERT_TRUE(result.has_value()) << result.error().message();

  auto tallies = qr::entry_v2::read_tallies(cfg);
  auto locks = qr::entry_v2::read_locks(cfg);
  auto phases = qr::entry_v2::read_phases(cfg);
  ASSERT_TRUE(tallies.has_value()) << tallies.error().message();
  ASSERT_TRUE(locks.has_value()) << locks.error().message();
  ASSERT_TRUE(phases.has_value()) << phases.error().message();
  EXPECT_EQ(tallies.value().size(), 65u * 3u);
  ASSERT_EQ(locks.value().size(), 65u);
  EXPECT_EQ(locks.value()[0].status, LockStatus::WARMUP_NO_PREVIOUS);
  EXPECT_EQ(locks.value()[1].status, LockStatus::LOCKED);
  EXPECT_EQ(locks.value()[1].locked_iid, 10);  // lower-iid tie, not spread 99
  EXPECT_EQ(locks.value()[1].selection_basis_d8, 20231201);

  const auto* december = phase_for(phases.value(), 202312);
  const auto* february = phase_for(phases.value(), 202402);
  ASSERT_NE(december, nullptr);
  ASSERT_NE(february, nullptr);
  EXPECT_EQ(december->source, PhaseSource::FIXED_MIN60);
  EXPECT_EQ(february->source, PhaseSource::TRAILING_252_PRIOR);
  EXPECT_EQ(february->n_fit, 61u);  // Dec 2..Jan 31; warmup is never fitted

  const fs::path pack_path = fs::path(cfg.output_root) / "events" / "SI" /
                             "20231202.qre2";
  auto pack = qr::entry_v2::read_event_pack(pack_path.string());
  ASSERT_TRUE(pack.has_value()) << pack.error().message();
  EXPECT_EQ(pack.value().header.locked_iid, 10);
  ASSERT_FALSE(pack.value().rows.empty());
  const std::uint64_t decision =
      static_cast<std::uint64_t>(pack.value().header.open_utc + 3 * 3600) * 1'000'000'000ull;
  const std::size_t cut = qr::entry_v2::event_cutoff(pack.value().rows, decision);
  ASSERT_GT(cut, 0u);
  EXPECT_LT(pack.value().rows[cut - 1u].ts_recv_ns, decision);
  if (cut < pack.value().rows.size()) {
    EXPECT_GE(pack.value().rows[cut].ts_recv_ns, decision);
  }
  const std::string sidecar = text(fs::path(cfg.output_root) / "events" / "SI" /
                                   "20231202.qre2.json");
  EXPECT_NE(sidecar.find("\"ts_recv_ns\""), std::string::npos);
  EXPECT_NE(sidecar.find("\"selection_basis_d8\":20231201"), std::string::npos);
  EXPECT_NE(sidecar.find("phase_schedule_sha256"), std::string::npos);
  EXPECT_NE(sidecar.find("lower_bound(ts_recv_ns,decision_ts_ns)"), std::string::npos);

  auto forecast = qr::entry_v2::build_forecast_artifact(cfg);
  ASSERT_TRUE(forecast.has_value()) << forecast.error().message();
  EXPECT_EQ(forecast.value().sessions, 65u);
  EXPECT_EQ(forecast.value().rows,
            65u * qr::entry_v2::kForecastSegmentCount);
  EXPECT_EQ(forecast.value().ready, 0u);
  EXPECT_EQ(forecast.value().missing,
            65u * qr::entry_v2::kForecastSegmentCount);
  auto frozen = qr::entry_v2::read_forecast_artifact(
      cfg, forecast.value().output_sha256);
  ASSERT_TRUE(frozen.has_value()) << frozen.error().message();
  ASSERT_EQ(frozen.value().rows.size(),
            65u * qr::entry_v2::kForecastSegmentCount);
  const auto& first_forecast = frozen.value().rows.front();
  auto equal_availability = qr::entry_v2::join_forecast(
      frozen.value(), first_forecast.d8, first_forecast.segment,
      first_forecast.availability_ts_ns, forecast.value().output_sha256);
  EXPECT_FALSE(equal_availability.has_value());
  EXPECT_EQ(equal_availability.error().code(), qr::RefusalCode::CLOCK_VIOLATION);
  auto causal_availability = qr::entry_v2::join_forecast(
      frozen.value(), first_forecast.d8, first_forecast.segment,
      first_forecast.availability_ts_ns + 1u,
      forecast.value().output_sha256);
  ASSERT_TRUE(causal_availability.has_value())
      << causal_availability.error().message();
  EXPECT_TRUE(fs::is_regular_file(fs::path(cfg.output_root) / "forecast" /
                                  "SI.qrf2.json"));
}

TEST_F(EntryV2Fixture, BoundedFixtureWritesSeparatedCandidateTeacherAndCeilingPlanes) {
  const Config cfg = config("g1_artifacts");
  auto substrate = qr::entry_v2::run(cfg, qr::entry_v2::Stage::ALL);
  ASSERT_TRUE(substrate.has_value()) << substrate.error().message();

  // No calendar is supplied on purpose. Mechanics still run, while any
  // emitted row would be COMPLIANCE_UNKNOWN and therefore not deployable.
  auto candidates = qr::entry_v2::build_g1_candidate_artifacts(cfg, nullptr);
  ASSERT_TRUE(candidates.has_value()) << candidates.error().message();
  EXPECT_EQ(candidates.value().sessions, 65u);
  EXPECT_EQ(candidates.value().no_candidate_sessions, 65u);
  EXPECT_EQ(candidates.value().candidates, 0u);
  EXPECT_EQ(candidates.value().manifest_sha256.size(), 64u);
  EXPECT_EQ(candidates.value().receipt_sha256.size(), 64u);

  const fs::path g1 = fs::path(cfg.output_root) / "g1";
  const std::string candidate_file = text(g1 / "candidates" / "SI" /
                                          "20231202.tsv");
  EXPECT_NE(candidate_file.find("# QRE2G1CAND2"), std::string::npos);
  // The deployable plane is causal-only; teacher/oracle/schedule fields are
  // structurally forbidden even when a session has no rows.
  for (const std::string_view forbidden : {
           "cert_close_usd", "mfe_usd", "mae_usd", "time_to_peak_sec",
           "wall_hit", "payer", "take_target", "exit_ts_ns", "selected"}) {
    EXPECT_EQ(candidate_file.find(forbidden), std::string::npos) << forbidden;
  }
  const std::string candidate_receipt = text(
      g1 / "receipts" / "SI" / "20231202.candidates.json");
  EXPECT_NE(candidate_receipt.find("\"schema\":\"QRE2G1CANDRECEIPT2\""),
            std::string::npos);
  EXPECT_NE(candidate_receipt.find("\"compliance_artifact_sha256\":null"),
            std::string::npos);
  EXPECT_NE(candidate_receipt.find("equal receive-time batch is future"),
            std::string::npos);

  auto teacher = qr::entry_v2::build_g1_teacher_artifacts(cfg);
  ASSERT_TRUE(teacher.has_value()) << teacher.error().message();
  EXPECT_EQ(teacher.value().sessions, 65u);
  EXPECT_EQ(teacher.value().teacher_ready, 0u);
  EXPECT_TRUE(fs::is_regular_file(g1 / "teacher" / "SI" / "manifest.tsv"));

  auto deployable = qr::entry_v2::build_g1_schedule_artifact(
      {cfg}, false,
      qr::entry_v2::ScheduleUniverse::DEPLOYABLE_CLEAR_ONLY, nullptr);
  auto mechanical = qr::entry_v2::build_g1_schedule_artifact(
      {cfg}, false, qr::entry_v2::ScheduleUniverse::MECHANICAL_ALL, nullptr);
  ASSERT_TRUE(deployable.has_value()) << deployable.error().message();
  ASSERT_TRUE(mechanical.has_value()) << mechanical.error().message();
  // The first raw session is a typed WARMUP_NO_PREVIOUS/NO_LOCK. It is
  // integrity-checked through the empty teacher plane, but is not a deployable
  // opportunity and therefore cannot inflate the ceiling denominator.
  EXPECT_EQ(deployable.value().sessions, 64u);
  EXPECT_EQ(mechanical.value().sessions, 64u);
  EXPECT_EQ(deployable.value().teacher_ready, 0u);
  const std::string ceiling_receipt = text(
      g1 / "receipts" / "SI.deployable_ceiling.json");
  EXPECT_NE(ceiling_receipt.find(
                "\"law\":\"DEPLOYABLE_EXACT_WEIGHTED_INTERVAL_CEILING\""),
            std::string::npos);
  EXPECT_NE(ceiling_receipt.find("\"expected_sessions\":64"),
            std::string::npos);
  EXPECT_NE(ceiling_receipt.find("\"zero_sessions\":64"),
            std::string::npos);
}

TEST_F(EntryV2Fixture, CurrentSessionTotalsCannotChangeItsAlreadyLockedInstrument) {
  const Config cfg = config("causal_lock");
  ASSERT_TRUE(qr::entry_v2::run_tally(cfg).has_value());
  auto tallies = qr::entry_v2::read_tallies(cfg);
  ASSERT_TRUE(tallies.has_value());
  const auto before = qr::entry_v2::derive_locks(tallies.value());
  const auto* before_day = lock_for(before, 20231202);
  ASSERT_NE(before_day, nullptr);
  ASSERT_EQ(before_day->locked_iid, 10);

  std::vector<TallyRow> mutated = tallies.value();
  for (TallyRow& row : mutated) {
    if (row.d8 == 20231202 && row.iid == 20u) {
      row.updates += 1'000'000u;
    }
  }
  const auto after = qr::entry_v2::derive_locks(mutated);
  const auto* after_day = lock_for(after, 20231202);
  ASSERT_NE(after_day, nullptr);
  EXPECT_EQ(after_day->locked_iid, before_day->locked_iid);
  EXPECT_EQ(after_day->selection_basis_d8, before_day->selection_basis_d8);
}

TEST_F(EntryV2Fixture, MonthlyPhaseIsFrozenAgainstSameMonthAndFutureMutations) {
  const Config cfg = config("causal_phase");
  ASSERT_TRUE(qr::entry_v2::run_tally(cfg).has_value());
  ASSERT_TRUE(qr::entry_v2::run_lock(cfg).has_value());
  auto tallies = qr::entry_v2::read_tallies(cfg);
  auto locks = qr::entry_v2::read_locks(cfg);
  ASSERT_TRUE(tallies.has_value());
  ASSERT_TRUE(locks.has_value());
  const auto before = qr::entry_v2::derive_phase_schedule(tallies.value(), locks.value());
  const auto* feb_before = phase_for(before, 202402);
  ASSERT_NE(feb_before, nullptr);

  std::vector<TallyRow> mutated = tallies.value();
  for (TallyRow& row : mutated) {
    if (row.d8 >= 20240201) {
      row.phase_updates.fill(9'999'999u);
    }
  }
  const auto after = qr::entry_v2::derive_phase_schedule(mutated, locks.value());
  const auto* feb_after = phase_for(after, 202402);
  ASSERT_NE(feb_after, nullptr);
  EXPECT_EQ(feb_after->source, feb_before->source);
  EXPECT_EQ(feb_after->n_fit, feb_before->n_fit);
  EXPECT_EQ(feb_after->fit_end_d8, feb_before->fit_end_d8);
  EXPECT_EQ(feb_after->boundaries, feb_before->boundaries);
  EXPECT_EQ(feb_after->profile_sha256, feb_before->profile_sha256);
}

TEST(PhaseSchedule, NeverFitsMoreThanTheLast252StrictlyPriorSessions) {
  ASSERT_TRUE(qr::futsess::init_globex_timezone().has_value());
  std::vector<TallyRow> tallies;
  std::vector<qr::entry_v2::LockRow> locks;
  const std::int64_t start = qr::futsess::date_to_day({2023, 1, 1});
  for (int i = 0; i < 340; ++i) {
    const auto date = qr::futsess::day_to_date(start + i);
    TallyRow tally;
    tally.d8 = date.yyyymmdd();
    tally.iid = 10;
    tally.outright = true;
    tally.updates = 1;
    tally.phase_updates[static_cast<std::size_t>(i) % qr::entry_v2::kPhaseBins] = 1;
    tallies.push_back(tally);
    qr::entry_v2::LockRow lock;
    lock.d8 = tally.d8;
    lock.status = i == 0 ? LockStatus::WARMUP_NO_PREVIOUS : LockStatus::LOCKED;
    lock.locked_iid = i == 0 ? -1 : 10;
    const auto [open, close] = qr::futsess::session_bounds(date);
    lock.open_utc = open;
    lock.close_utc = close;
    locks.push_back(lock);
  }
  const auto phases = qr::entry_v2::derive_phase_schedule(tallies, locks);
  ASSERT_FALSE(phases.empty());
  const auto max_fit = std::max_element(phases.begin(), phases.end(), [](const auto& lhs,
                                                                        const auto& rhs) {
    return lhs.n_fit < rhs.n_fit;
  });
  EXPECT_EQ(max_fit->n_fit, qr::entry_v2::kPhaseLookback);
  for (const auto& phase : phases) {
    EXPECT_LE(phase.n_fit, qr::entry_v2::kPhaseLookback);
    EXPECT_LT(phase.fit_end_d8, phase.month * 100 + 1);
  }
}

TEST_F(EntryV2Fixture, TwoIndependentBuildRootsAreByteIdentical) {
  const Config first = config("det_a");
  const Config second = config("det_b");
  ASSERT_TRUE(qr::entry_v2::run(first, qr::entry_v2::Stage::ALL).has_value());
  ASSERT_TRUE(qr::entry_v2::run(second, qr::entry_v2::Stage::ALL).has_value());
  for (const fs::path& rel : {fs::path("tallies/SI.tsv"), fs::path("locks/SI.tsv"),
                             fs::path("phases/SI.tsv"), fs::path("events/SI/manifest.tsv"),
                             fs::path("events/SI/20231202.qre2"),
                             fs::path("events/SI/20231202.qre2.json")}) {
    EXPECT_EQ(text(fs::path(first.output_root) / rel), text(fs::path(second.output_root) / rel))
        << rel;
  }
}

TEST_F(EntryV2Fixture, FilenameSealFiresBeforeA2026PayloadCanBeOpened) {
  const fs::path sealed = scratch_ / "glbx-mdp3-20260101.mbp-1.dbn.zst";
  fs::copy_file(input_, sealed, fs::copy_options::overwrite_existing);
  Config cfg = config("sealed");
  cfg.inputs = {sealed.string()};
  cfg.development_input_sha256.clear();
  cfg.development_input_sha256[sealed.string()] = std::string(64, 'a');
  cfg.development_prefix_inputs.insert(sealed.string());
  auto result = qr::entry_v2::run_tally(cfg);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), qr::RefusalCode::DAY_OUTSIDE_CALENDAR);
  EXPECT_FALSE(fs::exists(fs::path(cfg.output_root) / "tallies" / "SI.tsv"));
}

TEST_F(EntryV2Fixture, Mixed2025PrefixStopsBeforeAnyH2EntryStateOrArtifact) {
  const std::string mixed = write_mixed_2025_fixture(
      scratch_ / "glbx-mdp3-20250101-20251231.mbp-1.dbn.zst");
  Config cfg = config("mixed_2025");
  cfg.inputs = {mixed};
  cfg.development_input_sha256.clear();
  cfg.development_input_sha256[mixed] = sha256(mixed);
  cfg.development_prefix_inputs.insert(mixed);

  auto built = qr::entry_v2::run(cfg, qr::entry_v2::Stage::ALL);
  ASSERT_TRUE(built.has_value()) << built.error().message();
  EXPECT_EQ(built.value().raw_records, 8u);
  const std::string inputs = text(fs::path(cfg.output_root) / "manifests" /
                                  "SI.inputs.tsv");
  EXPECT_NE(inputs.find("\tDEVELOPMENT_PREFIX\n"), std::string::npos);
  for (const fs::path& rel : {fs::path("tallies/SI.tsv"),
                             fs::path("locks/SI.tsv"),
                             fs::path("events/SI/manifest.tsv")}) {
    EXPECT_EQ(text(fs::path(cfg.output_root) / rel).find("\n20250701\t"),
              std::string::npos) << rel;
  }
}

TEST_F(EntryV2Fixture, UtcDailyJune30IsAnAdmissibleBoundedPrefix) {
  const std::string boundary = write_mixed_2025_fixture(
      scratch_ / "glbx-mdp3-20250630.mbp-1.dbn.zst");
  Config cfg = config("utc_daily_boundary");
  cfg.inputs = {boundary};
  cfg.development_input_sha256.clear();
  cfg.development_input_sha256[boundary] = sha256(boundary);
  cfg.development_prefix_inputs.insert(boundary);

  auto built = qr::entry_v2::run(cfg, qr::entry_v2::Stage::ALL);
  ASSERT_TRUE(built.has_value()) << built.error().message();
  EXPECT_EQ(built.value().raw_records, 8u);
  EXPECT_EQ(text(fs::path(cfg.output_root) / "events" / "SI" /
                 "manifest.tsv").find("\n20250701\t"),
            std::string::npos);
}

TEST_F(EntryV2Fixture, MixedContainerWithoutProviderHashIsRefusedBeforeHashing) {
  const std::string mixed = write_mixed_2025_fixture(
      scratch_ / "glbx-mdp3-20250101-20251231.mbp-1.dbn.zst");
  Config cfg = config("mixed_missing_hash");
  cfg.inputs = {mixed};
  cfg.development_input_sha256.clear();
  auto result = qr::entry_v2::run_tally(cfg);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), qr::RefusalCode::CONFIG);
  EXPECT_FALSE(fs::exists(fs::path(cfg.output_root) / "manifests" / "SI.inputs.tsv"));
  EXPECT_FALSE(fs::exists(fs::path(cfg.output_root) / "tallies" / "SI.tsv"));
}

TEST_F(EntryV2Fixture, RenamedKnownMixedProviderHashIsBlockedBeforeAnyOpen) {
  const fs::path renamed =
      scratch_ / "glbx-mdp3-20240101-20240131.mbp-1.dbn.zst";
  ASSERT_FALSE(fs::exists(renamed));
  Config cfg = config("renamed_known_mixed");
  cfg.inputs = {renamed.string()};
  cfg.development_input_sha256.clear();
  cfg.development_input_sha256[renamed.string()] =
      "30a9e8f81d46e3213b2d2324cfd8d957cf70aa2ef1aab256e2c618a513ab884a";
  auto result = qr::entry_v2::run_tally(cfg);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), qr::RefusalCode::DAY_OUTSIDE_CALENDAR);
  EXPECT_FALSE(fs::exists(fs::path(cfg.output_root) / "manifests" / "SI.inputs.tsv"));
}

TEST_F(EntryV2Fixture, ProviderHashMismatchCannotAuthorizeCurrentBytes) {
  Config cfg = config("provider_hash_mismatch");
  cfg.development_input_sha256[input_] = std::string(64, '0');
  auto result = qr::entry_v2::run_tally(cfg);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
  EXPECT_FALSE(fs::exists(fs::path(cfg.output_root) / "manifests" / "SI.inputs.tsv"));
}

TEST_F(EntryV2Fixture, EventPackReaderRejectsEveryPinnedClockAndLayoutMutation) {
  const Config cfg = config("event_pack_corruption");
  auto built = qr::entry_v2::run(cfg, qr::entry_v2::Stage::ALL);
  ASSERT_TRUE(built.has_value()) << built.error().message();
  const fs::path source = fs::path(cfg.output_root) / "events" / "SI" /
                          "20231202.qre2";
  const std::string pristine = text(source);
  ASSERT_GT(pristine.size(), qr::entry_v2::kEventPackHeaderBytes +
                                 qr::entry_v2::kEventRowBytes);
  auto valid = qr::entry_v2::read_event_pack(source.string());
  ASSERT_TRUE(valid.has_value()) << valid.error().message();

  const fs::path bad_name = scratch_ / "event_pack_bad_name" /
                            "20231202-copy.qre2";
  write_bytes(bad_name, pristine);
  auto named = qr::entry_v2::read_event_pack(bad_name.string());
  ASSERT_FALSE(named.has_value());
  EXPECT_EQ(named.error().code(), qr::RefusalCode::DAY_OUTSIDE_CALENDAR);

  const auto rejects_content = [&](std::string name, std::string bytes) {
    const fs::path path = scratch_ / std::move(name) / "20231202.qre2";
    write_bytes(path, bytes);
    auto result = qr::entry_v2::read_event_pack(path.string());
    EXPECT_FALSE(result.has_value());
    if (!result.has_value()) {
      EXPECT_EQ(result.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
    }
  };

  std::string bad_d8 = pristine;
  overwrite_le<std::int32_t>(&bad_d8, 16u, 20231203);
  rejects_content("event_pack_bad_d8", std::move(bad_d8));

  std::string bad_reserved = pristine;
  overwrite_le<std::uint32_t>(&bad_reserved, 56u, 1u);
  rejects_content("event_pack_bad_reserved", std::move(bad_reserved));

  std::string bad_receive_sec = pristine;
  overwrite_le<std::int32_t>(&bad_receive_sec,
                             qr::entry_v2::kEventPackHeaderBytes + 68u,
                             123456);
  rejects_content("event_pack_bad_receive_sec", std::move(bad_receive_sec));

  std::string bad_bounds = pristine;
  overwrite_le<std::int64_t>(&bad_bounds, 28u,
                             valid.value().header.open_utc + 1);
  rejects_content("event_pack_bad_bounds", std::move(bad_bounds));
}

TEST(EntryV2Symbology, UsesFloorUtcDateInsideTheNextGlobexTradeDate) {
  ASSERT_TRUE(qr::futsess::init_globex_timezone().has_value());
  const fs::path scratch = fs::path(QR_TEST_SCRATCH_DIR) /
                           "qr_entry_v2_symbol_utc";
  std::error_code ec;
  fs::remove_all(scratch, ec);
  const auto [open, close] =
      qr::futsess::session_bounds(qr::futsess::Date{2023, 12, 2});
  (void)close;
  const std::uint64_t ts = static_cast<std::uint64_t>(open + 60) *
                           1'000'000'000ull;
  const std::string input = write_stream(
      scratch / "glbx-mdp3-20231202.mbp-1.dbn.zst",
      {{"SIZ3", "10", 20230101, 20231202},
       {"SIH4", "10", 20231202, 20260101}},
      {record(10, ts, 1)});
  Config cfg;
  cfg.asset = qr::futsess::Asset::SI;
  cfg.inputs = {input};
  cfg.development_input_sha256[input] = sha256(input);
  cfg.output_root = (scratch / "out").string();
  auto tally = qr::entry_v2::run_tally(cfg);
  ASSERT_TRUE(tally.has_value()) << tally.error().message();
  auto rows = qr::entry_v2::read_tallies(cfg);
  ASSERT_TRUE(rows.has_value()) << rows.error().message();
  ASSERT_EQ(rows.value().size(), 1u);
  EXPECT_EQ(rows.value()[0].d8, 20231202);
  EXPECT_EQ(rows.value()[0].symbol, "SIZ3");
}

TEST(EntryV2Symbology, MissingExactFloorUtcSymbolIsAContentRefusal) {
  ASSERT_TRUE(qr::futsess::init_globex_timezone().has_value());
  const fs::path scratch = fs::path(QR_TEST_SCRATCH_DIR) /
                           "qr_entry_v2_symbol_missing";
  std::error_code ec;
  fs::remove_all(scratch, ec);
  const auto [open, close] =
      qr::futsess::session_bounds(qr::futsess::Date{2023, 12, 2});
  (void)close;
  const std::uint64_t ts = static_cast<std::uint64_t>(open + 60) *
                           1'000'000'000ull;
  const std::string input = write_stream(
      scratch / "glbx-mdp3-20231202.mbp-1.dbn.zst",
      {{"SIH4", "10", 20240101, 20260101}}, {record(10, ts, 1)});
  Config cfg;
  cfg.asset = qr::futsess::Asset::SI;
  cfg.inputs = {input};
  cfg.development_input_sha256[input] = sha256(input);
  cfg.output_root = (scratch / "out").string();
  auto tally = qr::entry_v2::run_tally(cfg);
  ASSERT_FALSE(tally.has_value());
  EXPECT_EQ(tally.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
  EXPECT_FALSE(fs::exists(fs::path(cfg.output_root) / "tallies" / "SI.tsv"));
}

TEST(EntryV2Tally, LateUnresolvedBookTaintErasesWholeInstrumentSessionEconomics) {
  ASSERT_TRUE(qr::futsess::init_globex_timezone().has_value());
  const fs::path scratch = fs::path(QR_TEST_SCRATCH_DIR) /
                           "qr_entry_v2_tally_taint";
  std::error_code ec;
  fs::remove_all(scratch, ec);
  const auto [open, close] =
      qr::futsess::session_bounds(qr::futsess::Date{2023, 12, 2});
  (void)close;
  const std::uint64_t base = static_cast<std::uint64_t>(open) * 1'000'000'000ull;
  std::vector<Mbp1Msg> records = {
      record(10, base + 60u * 1'000'000'000ull, 1),
      record(10, base + 120u * 1'000'000'000ull, 2),
      record(10, base + 180u * 1'000'000'000ull, 3)};
  records.back().flags = static_cast<std::uint8_t>(
      records.back().flags | qr::entry_v2::kFlagMaybeBadBook);
  const std::string input = write_stream(
      scratch / "glbx-mdp3-20231202.mbp-1.dbn.zst",
      {{"SIH4", "10"}}, std::move(records));
  Config cfg;
  cfg.asset = qr::futsess::Asset::SI;
  cfg.inputs = {input};
  cfg.development_input_sha256[input] = sha256(input);
  cfg.output_root = (scratch / "out").string();
  auto tally = qr::entry_v2::run_tally(cfg);
  ASSERT_TRUE(tally.has_value()) << tally.error().message();
  auto rows = qr::entry_v2::read_tallies(cfg);
  ASSERT_TRUE(rows.has_value()) << rows.error().message();
  ASSERT_EQ(rows.value().size(), 1u);
  const TallyRow& row = rows.value()[0];
  EXPECT_EQ(row.raw_records, 3u);
  EXPECT_EQ(row.maybe_bad_book_records, 1u);
  EXPECT_EQ(row.updates, 0u);
  EXPECT_EQ(row.trusted_economic_records, 0u);
  EXPECT_TRUE(std::all_of(row.phase_updates.begin(), row.phase_updates.end(),
                          [](std::uint64_t value) { return value == 0u; }));
}

TEST(EntryV2ClockLaw, HgShapedStandaloneBadBurstTaintsLockedSessionWithoutPack) {
  ASSERT_TRUE(qr::futsess::init_globex_timezone().has_value());
  const fs::path scratch = fs::path(QR_TEST_SCRATCH_DIR) /
                           "qr_entry_v2_hg_bad_ts_recv_burst";
  std::error_code ec;
  fs::remove_all(scratch, ec);

  std::vector<Mbp1Msg> records;
  std::uint32_t sequence = 35'633'380u;
  const auto [prior_open, prior_close] =
      qr::futsess::session_bounds(qr::futsess::Date{2023, 12, 1});
  const auto [open, close] =
      qr::futsess::session_bounds(qr::futsess::Date{2023, 12, 2});
  (void)prior_close;
  (void)close;
  records.push_back(record(
      225412u, static_cast<std::uint64_t>(prior_open + 60) * 1'000'000'000ull,
      sequence++));
  const std::uint64_t base =
      static_cast<std::uint64_t>(open + 100) * 1'000'000'000ull;
  records.push_back(record(225412u, base, sequence++));
  const std::uint64_t first_bad_event = base + 1'000'000'000ull;
  const std::uint64_t frozen_bad_recv = first_bad_event - 181'839'894ull;
  for (std::uint32_t i = 0; i < 23u; ++i) {
    Mbp1Msg bad = record(225412u, first_bad_event + i * 50'000'000ull,
                         sequence++);
    bad.ts_recv = frozen_bad_recv;
    bad.ts_in_delta = -182'077'785 - static_cast<std::int32_t>(i * 50'000'000u);
    bad.action = 'T';
    bad.side = 'A';
    bad.flags = i < 3u ? 0x08u : 0x8au;
    bad.price = 4'413'000'000LL + static_cast<std::int64_t>(i) * 25'000LL;
    bad.levels[0] = BidAskPair{bad.price, bad.price + 500'000LL, 8, 7, 3, 2};
    records.push_back(bad);
  }
  records.push_back(record(225412u, base + 4'000'000'000ull, sequence++));
  records.push_back(record(225412u, base + 5'000'000'000ull, sequence++));

  const std::string input = write_stream(
      scratch / "glbx-mdp3-20231201-20231202.mbp-1.dbn.zst",
      {{"HGH4", "225412"}}, std::move(records));
  Config cfg;
  cfg.asset = qr::futsess::Asset::HG;
  cfg.inputs = {input};
  cfg.development_input_sha256[input] = sha256(input);
  cfg.output_root = (scratch / "out").string();

  auto tally = qr::entry_v2::run_tally(cfg);
  ASSERT_TRUE(tally.has_value()) << tally.error().message();
  auto rows = qr::entry_v2::read_tallies(cfg);
  ASSERT_TRUE(rows.has_value()) << rows.error().message();
  const auto day = std::find_if(rows.value().begin(), rows.value().end(),
                                [](const TallyRow& row) {
                                  return row.d8 == 20231202 && row.iid == 225412u;
                                });
  ASSERT_NE(day, rows.value().end());
  EXPECT_EQ(day->raw_records, 26u);
  EXPECT_EQ(day->standalone_bad_ts_recv_records, 23u);
  EXPECT_EQ(day->updates, 2u);  // recovery F_LAST is a quarantined clock seed

  ASSERT_TRUE(qr::entry_v2::run_lock(cfg).has_value());
  ASSERT_TRUE(qr::entry_v2::run_phase(cfg).has_value());
  const fs::path stale_pack = fs::path(cfg.output_root) / "events" / "HG" /
                              "20231202.qre2";
  write_bytes(stale_pack, "stale-pack-must-not-survive");
  auto events = qr::entry_v2::run_events(cfg);
  ASSERT_TRUE(events.has_value()) << events.error().message();
  EXPECT_EQ(events.value().standalone_bad_ts_recv_records, 23u);
  EXPECT_FALSE(fs::exists(stale_pack));

  const std::string manifest = text(fs::path(cfg.output_root) / "events" / "HG" /
                                    "manifest.tsv");
  EXPECT_NE(manifest.find("HG\t20231202\tBAD_TS_RECV_CLOCK_TAINT\t225412"),
            std::string::npos);
  const std::string sidecar = text(fs::path(cfg.output_root) / "events" / "HG" /
                                   "20231202.qre2.json");
  EXPECT_NE(sidecar.find("\"status\":\"BAD_TS_RECV_CLOCK_TAINT\""),
            std::string::npos);
  EXPECT_NE(sidecar.find("\"standalone_bad_ts_recv_records\":23"),
            std::string::npos);
  EXPECT_NE(sidecar.find("\"binary_file\":null"), std::string::npos);
}

TEST_F(EntryV2Fixture, OrdinaryConfigCannotExpandIntoTheFinalExamWindow) {
  Config cfg = config("bad_window");
  cfg.end_d8_exclusive = 20250702;
  auto result = qr::entry_v2::run_tally(cfg);
  ASSERT_FALSE(result.has_value());
  EXPECT_EQ(result.error().code(), qr::RefusalCode::DAY_OUTSIDE_CALENDAR);
  EXPECT_FALSE(fs::exists(fs::path(cfg.output_root) / "manifests" / "SI.inputs.tsv"));
}

TEST(EventCutoff, EqualTimestampEventsAreNeverIncludedInThePrefix) {
  std::vector<EventRow> rows(4);
  rows[0].ts_recv_ns = 10;
  rows[1].ts_recv_ns = 20;
  rows[2].ts_recv_ns = 20;
  rows[3].ts_recv_ns = 30;
  EXPECT_EQ(qr::entry_v2::event_cutoff(rows, 20), 1u);
  EXPECT_EQ(qr::entry_v2::event_cutoff(rows, 21), 3u);
}

TEST(BookQuality, SnapshotResetAndBadFlagsAreFailClosed) {
  qr::entry_v2::BookQualityState state;
  auto ordinary = state.observe(10, 0, true);
  ASSERT_TRUE(ordinary.has_value());
  EXPECT_TRUE(ordinary.value().trusted_economic);

  auto snapshot = state.observe(
      20, qr::entry_v2::kFlagSnapshot | qr::entry_v2::kFlagBadTsRecv, true);
  ASSERT_TRUE(snapshot.has_value());
  EXPECT_TRUE(snapshot.value().snapshot_row);
  EXPECT_TRUE(snapshot.value().reset_derived_state);
  EXPECT_FALSE(snapshot.value().trusted_economic);

  auto establishes = state.observe(21, 0, true);
  ASSERT_TRUE(establishes.has_value());
  EXPECT_FALSE(establishes.value().trusted_economic);
  auto trusted = state.observe(22, 0, true);
  ASSERT_TRUE(trusted.has_value());
  EXPECT_TRUE(trusted.value().trusted_economic);

  qr::entry_v2::BookQualityState bad;
  auto refused = bad.observe(30, qr::entry_v2::kFlagBadTsRecv, true);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::CONTENT_MISMATCH);
}

TEST(BookQuality, ExactFortyFiveRowSnapshotBlockIsOneAtomicReset) {
  qr::entry_v2::BookQualityState state;
  ASSERT_TRUE(state.observe(10, 0, true).value().trusted_economic);
  std::uint64_t generation = 0;
  std::size_t resets = 0;
  for (std::size_t i = 0; i < 45u; ++i) {
    auto row = state.observe(
        20, qr::entry_v2::kFlagSnapshot | qr::entry_v2::kFlagBadTsRecv,
        true);
    ASSERT_TRUE(row.has_value()) << row.error().message();
    EXPECT_TRUE(row.value().snapshot_row);
    EXPECT_FALSE(row.value().trusted_economic);
    resets += row.value().reset_derived_state ? 1u : 0u;
    if (i == 0u) generation = row.value().generation;
    EXPECT_EQ(row.value().generation, generation);
  }
  EXPECT_EQ(resets, 1u);
  EXPECT_FALSE(state.unresolved_taint());
  auto seed = state.observe(21, 0, true);
  ASSERT_TRUE(seed.has_value());
  EXPECT_FALSE(seed.value().trusted_economic);
  auto trusted = state.observe(22, 0, true);
  ASSERT_TRUE(trusted.has_value());
  EXPECT_TRUE(trusted.value().trusted_economic);
  EXPECT_EQ(trusted.value().generation, generation);
}

TEST(BookQuality, MaybeBadBookRemainsTaintedUntilCleanSnapshot) {
  qr::entry_v2::BookQualityState state;
  auto taint = state.observe(10, qr::entry_v2::kFlagMaybeBadBook, true);
  ASSERT_TRUE(taint.has_value());
  EXPECT_TRUE(taint.value().reset_derived_state);
  EXPECT_FALSE(state.observe(11, 0, true).value().trusted_economic);
  ASSERT_TRUE(state.observe(
      12, qr::entry_v2::kFlagSnapshot | qr::entry_v2::kFlagBadTsRecv, true).has_value());
  EXPECT_FALSE(state.observe(13, 0, true).value().trusted_economic);
  EXPECT_TRUE(state.observe(14, 0, true).value().trusted_economic);
}

}  // namespace
