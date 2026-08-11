// qr_m25/tests/test_train_wall.cpp — the M2.5 TRAIN wall.
//
// FINAL_PLAN section 8: "On the exact DecisionTape/menu/replay, TRAIN sessions
// only (F4 125-395; F5 125-520)". The wall is a DOOR: a CAL, embargo or TEST
// ordinal is refused at load, with its bytes on disk and readable, and no
// measurement of any kind is produced for it.
#include <gtest/gtest.h>

#include <filesystem>

#include "m25_test_support.hpp"
#include "qr_m25/tape.hpp"

namespace {

using qr::m25::assert_train_session;
using qr::m25::Fold;
using qr::m25::test::Spec;

std::filesystem::path scratch(const char* name) {
  const std::filesystem::path root = std::filesystem::path(QR_M25_TEST_SCRATCH) / name;
  std::filesystem::remove_all(root);
  std::filesystem::create_directories(root);
  return root;
}

std::vector<Spec> two_rows() {
  std::vector<Spec> specs;
  Spec a;
  a.clock = 0;
  a.is_long = true;
  a.net_cent = 1000;
  specs.push_back(a);
  Spec b = a;
  b.is_long = false;
  b.net_cent = -1000;
  specs.push_back(b);
  return specs;
}

}  // namespace

TEST(TrainWall, F4AdmitsOnlyItsOwnTrainRange) {
  EXPECT_FALSE(assert_train_session(Fold::F4, 124).has_value());
  EXPECT_TRUE(assert_train_session(Fold::F4, 125).has_value());
  EXPECT_TRUE(assert_train_session(Fold::F4, 395).has_value());
  // inner embargo 396..397, calibration 398..497, outer embargo 498..499,
  // test 500..624 — every one of them refused.
  for (const std::int64_t ordinal : {396LL, 397LL, 398LL, 450LL, 497LL, 498LL, 499LL, 500LL, 624LL,
                                     625LL, 749LL, 750LL}) {
    const auto refused = assert_train_session(Fold::F4, ordinal);
    ASSERT_FALSE(refused.has_value()) << "ordinal " << ordinal;
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
    EXPECT_EQ(refused.error().context(), ordinal);
  }
}

TEST(TrainWall, F5AdmitsOnlyItsOwnTrainRange) {
  EXPECT_TRUE(assert_train_session(Fold::F5, 125).has_value());
  EXPECT_TRUE(assert_train_session(Fold::F5, 520).has_value());
  for (const std::int64_t ordinal : {124LL, 521LL, 522LL, 523LL, 600LL, 622LL, 623LL, 625LL, 749LL}) {
    const auto refused = assert_train_session(Fold::F5, ordinal);
    ASSERT_FALSE(refused.has_value()) << "ordinal " << ordinal;
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  }
}

TEST(TrainWall, ACalibrationSessionOnDiskIsStillRefused) {
  // THE SMUGGLING MUTANT: the shard exists, is lawful, and would load fine —
  // the only thing standing between it and the measurement is the wall.
  const std::filesystem::path run = scratch("wall_cal");
  ASSERT_TRUE(qr::m25::test::publish_specs(run, 400, "2024-03-01", two_rows()).has_value());
  const qr::m25::TapeRoot root = qr::m25::tape_root(run);

  const auto refused = qr::m25::load_session(root, Fold::F4, 400);
  ASSERT_FALSE(refused.has_value());
  EXPECT_EQ(refused.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  EXPECT_EQ(refused.error().context(), 400);

  // The same bytes under the fold that DOES own them load without complaint,
  // which is what proves the refusal was the wall and not a broken shard.
  const auto admitted = qr::m25::load_session(root, Fold::F5, 400);
  ASSERT_TRUE(admitted.has_value()) << (admitted.has_value() ? "" : admitted.error().message());
  EXPECT_EQ(admitted.value().rows.size(), 2u);
}

TEST(TrainWall, ATestSessionOnDiskIsRefusedByBothFolds) {
  const std::filesystem::path run = scratch("wall_test");
  ASSERT_TRUE(qr::m25::test::publish_specs(run, 700, "2024-11-04", two_rows()).has_value());
  const qr::m25::TapeRoot root = qr::m25::tape_root(run);
  for (const Fold fold : {Fold::F4, Fold::F5}) {
    const auto refused = qr::m25::load_session(root, fold, 700);
    ASSERT_FALSE(refused.has_value());
    EXPECT_EQ(refused.error().code(), qr::RefusalCode::ORDINAL_OUTSIDE_SCOPE);
  }
}

TEST(TrainWall, APublishedShardRoundTripsThroughTheLoader) {
  const std::filesystem::path run = scratch("roundtrip");
  std::vector<Spec> specs = two_rows();
  Spec later;
  later.clock = 5;
  later.is_long = true;
  later.net_cent = 4242;
  later.available = false;
  specs.push_back(later);
  ASSERT_TRUE(qr::m25::test::publish_specs(run, 130, "2022-07-11", specs).has_value());
  const qr::m25::TapeRoot root = qr::m25::tape_root(run);

  const auto loaded = qr::m25::load_session(root, Fold::F4, 130);
  ASSERT_TRUE(loaded.has_value()) << (loaded.has_value() ? "" : loaded.error().message());
  const qr::m25::SessionTape& tape = loaded.value();
  EXPECT_EQ(tape.rows.size(), 3u);
  EXPECT_EQ(tape.clock_count(), 2u);
  EXPECT_EQ(tape.long_rows, 2);
  EXPECT_EQ(tape.short_rows, 1);
  EXPECT_EQ(tape.label_ok_rows, 2);
  EXPECT_EQ(tape.label_entry_unavailable_rows, 1);
  EXPECT_EQ(tape.year, 2022);
  EXPECT_EQ(tape.day, "2022-07-11");
  // The merged stream is chronological and LONG leads its clock.
  EXPECT_EQ(tape.rows[0].key.side, qr::replay::Side::LONG);
  EXPECT_EQ(tape.rows[1].key.side, qr::replay::Side::SHORT);
  EXPECT_LT(tape.rows[1].key.decision_ts_ns, tape.rows[2].key.decision_ts_ns);
  // The truth arrived intact.
  EXPECT_EQ(tape.rows[0].label.menu_net_cent[2], 1000);
  EXPECT_EQ(tape.rows[1].label.menu_net_cent[2], -1000);
  EXPECT_EQ(tape.rows[0].label.cost_charged_cent, qr::replay::kTradeCostCent);
}

TEST(TrainWall, TheFrozenCardShaIsReadFromTheShardItself) {
  const std::filesystem::path run = scratch("cardsha");
  ASSERT_TRUE(qr::m25::test::publish_specs(run, 131, "2022-07-12", two_rows()).has_value());
  const qr::m25::TapeRoot root = qr::m25::tape_root(run);
  const auto sha = qr::m25::shard_card_sha(root, 131);
  ASSERT_TRUE(sha.has_value());
  EXPECT_EQ(sha.value(), std::string(64, 'a'));
}
