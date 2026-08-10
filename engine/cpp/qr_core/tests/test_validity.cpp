// Fixture VAL-1..VAL-7: the frozen 14x14 worst-wins lattice.
//
// VAL-1 exhausts ALL 196 ordered pairs against the rule the frozen table
// encodes, so a mutant that flips any single cell of kCombineTable turns this
// red. The rule is the orchestrator's SEVERITY ruling of 2026-08-10, which is
// deliberately NOT the APPENDIX C1 declaration order: STALE_DIAG is
// diagnostic-only and sits directly above VALID, below every unavailability
// state. VAL-7 pins that ruling on its eight decided cells.
#include <array>
#include <cstddef>
#include <set>
#include <string>
#include <vector>

#include "gtest/gtest.h"
#include "qr_core/validity.hpp"

namespace {

using qr::combine;
using qr::Typed;
using qr::Validity;

constexpr std::array<Validity, qr::kValidityCount> kAllStates = {
    Validity::VALID,
    Validity::MISSING,
    Validity::EQUAL_TIME_UNORDERED,
    Validity::ATTACHMENT_FUTURE,
    Validity::WRONG_CIVIL_DAY,
    Validity::STALE_DIAG,
    Validity::LOCKED,
    Validity::CROSSED,
    Validity::ONE_SIDED,
    Validity::NONFINITE,
    Validity::NONPOSITIVE,
    Validity::CONDITION_INELIGIBLE,
    Validity::CLOCK_UNAVAILABLE,
    Validity::MODALITY_ABSENT,
};

// The SEVERITY order, best to worst, transcribed from the orchestrator ruling
// of 2026-08-10. This is the test's own copy of the rule; it is written out
// independently of kCombineTable so that the table is checked against the
// ruling rather than against itself.
constexpr std::array<Validity, qr::kValidityCount> kSeverityOrder = {
    Validity::VALID,
    Validity::STALE_DIAG,
    Validity::MISSING,
    Validity::EQUAL_TIME_UNORDERED,
    Validity::ATTACHMENT_FUTURE,
    Validity::WRONG_CIVIL_DAY,
    Validity::LOCKED,
    Validity::CROSSED,
    Validity::ONE_SIDED,
    Validity::NONFINITE,
    Validity::NONPOSITIVE,
    Validity::CONDITION_INELIGIBLE,
    Validity::CLOCK_UNAVAILABLE,
    Validity::MODALITY_ABSENT,
};

std::size_t severity_rank(Validity v) {
  for (std::size_t i = 0; i < kSeverityOrder.size(); ++i) {
    if (kSeverityOrder[i] == v) {
      return i;
    }
  }
  ADD_FAILURE() << "state " << qr::validity_name(v) << " has no place in the severity ruling";
  return kSeverityOrder.size();
}

// The rule the table must encode: the more severe of the two states survives.
Validity worst_of(Validity a, Validity b) {
  return (severity_rank(a) >= severity_rank(b)) ? a : b;
}

TEST(ValidityLattice, EnumIsExactlyTheFourteenSpecifiedStatesInOrder) {
  ASSERT_EQ(qr::kValidityCount, 14U);
  for (std::size_t i = 0; i < kAllStates.size(); ++i) {
    EXPECT_EQ(static_cast<std::size_t>(kAllStates[i]), i)
        << "state " << qr::validity_name(kAllStates[i]) << " moved in the frozen order";
  }
  EXPECT_EQ(static_cast<std::uint8_t>(Validity::VALID), 0U);
  EXPECT_EQ(static_cast<std::uint8_t>(Validity::WRONG_CIVIL_DAY), 4U);
  EXPECT_EQ(static_cast<std::uint8_t>(Validity::MODALITY_ABSENT), 13U);
}

TEST(ValidityLattice, AllOneHundredNinetySixPairsMatchTheFrozenTable) {
  // EVERY ordered pair is checked. Mismatches are collected and reported as a
  // count plus the first few, so one flipped table cell reads as one legible
  // failure rather than a wall of output.
  std::size_t pairs = 0;
  std::vector<std::string> wrong;
  for (const Validity a : kAllStates) {
    for (const Validity b : kAllStates) {
      ++pairs;
      if (combine(a, b) != worst_of(a, b)) {
        wrong.emplace_back(std::string("combine(") + qr::validity_name(a) + ", " +
                           qr::validity_name(b) + ") = " + qr::validity_name(combine(a, b)) +
                           ", expected " + qr::validity_name(worst_of(a, b)));
      }
    }
  }
  EXPECT_EQ(pairs, 196U);
  EXPECT_TRUE(wrong.empty()) << wrong.size() << " of 196 pairs disagree with the frozen table; "
                             << "first: " << (wrong.empty() ? std::string("-") : wrong.front())
                             << (wrong.size() > 1 ? " | second: " + wrong[1] : std::string());
}

TEST(ValidityLattice, StaleDiagIsDiagnosticOnlyAndNeverOutranksUnavailability) {
  // The eight cells the 2026-08-10 ruling decided: STALE_DIAG dominates VALID
  // and nothing else, because quote age gates nothing and the value stays
  // usable. Every one of these was STALE_DIAG under the declaration-order
  // reading and must not be.
  const std::array<Validity, 4> kUnavailable = {
      Validity::MISSING,
      Validity::EQUAL_TIME_UNORDERED,
      Validity::ATTACHMENT_FUTURE,
      Validity::WRONG_CIVIL_DAY,
  };
  for (const Validity state : kUnavailable) {
    EXPECT_EQ(combine(Validity::STALE_DIAG, state), state)
        << "STALE_DIAG outranked " << qr::validity_name(state);
    EXPECT_EQ(combine(state, Validity::STALE_DIAG), state)
        << "STALE_DIAG outranked " << qr::validity_name(state);
  }

  // It still dominates VALID, and still loses to everything more severe.
  EXPECT_EQ(combine(Validity::VALID, Validity::STALE_DIAG), Validity::STALE_DIAG);
  EXPECT_EQ(combine(Validity::STALE_DIAG, Validity::LOCKED), Validity::LOCKED);
  EXPECT_EQ(combine(Validity::STALE_DIAG, Validity::MODALITY_ABSENT), Validity::MODALITY_ABSENT);
  EXPECT_EQ(combine(Validity::STALE_DIAG, Validity::STALE_DIAG), Validity::STALE_DIAG);

  // The severity ruling is a permutation of the frozen declaration order:
  // every state appears exactly once, so no state is silently unranked.
  std::set<Validity> ranked(kSeverityOrder.begin(), kSeverityOrder.end());
  EXPECT_EQ(ranked.size(), qr::kValidityCount);
  EXPECT_EQ(kSeverityOrder.front(), Validity::VALID);
  EXPECT_EQ(kSeverityOrder[1], Validity::STALE_DIAG);
  EXPECT_EQ(kSeverityOrder.back(), Validity::MODALITY_ABSENT);
}

TEST(ValidityLattice, IsCommutativeIdempotentAndAssociative) {
  std::size_t idempotent_failures = 0;
  std::size_t commutative_failures = 0;
  std::size_t associative_failures = 0;
  for (const Validity a : kAllStates) {
    if (combine(a, a) != a) {
      ++idempotent_failures;
    }
    for (const Validity b : kAllStates) {
      if (combine(a, b) != combine(b, a)) {
        ++commutative_failures;
      }
      for (const Validity c : kAllStates) {
        if (combine(combine(a, b), c) != combine(a, combine(b, c))) {
          ++associative_failures;
        }
      }
    }
  }
  EXPECT_EQ(idempotent_failures, 0U) << "combine(a, a) != a";
  EXPECT_EQ(commutative_failures, 0U) << "combine(a, b) != combine(b, a)";
  EXPECT_EQ(associative_failures, 0U) << "the lattice is not associative";
}

TEST(ValidityLattice, ValidIsTheIdentityAndNeverResurrectsAnInvalidState) {
  for (const Validity a : kAllStates) {
    EXPECT_EQ(combine(Validity::VALID, a), a);
    EXPECT_EQ(combine(a, Validity::VALID), a);
    if (a != Validity::VALID) {
      EXPECT_NE(combine(a, Validity::VALID), Validity::VALID)
          << "combining with VALID must never repair " << qr::validity_name(a);
    }
  }
}

TEST(ValidityLattice, ModalityAbsentAbsorbsEveryState) {
  for (const Validity a : kAllStates) {
    EXPECT_EQ(combine(a, Validity::MODALITY_ABSENT), Validity::MODALITY_ABSENT);
    EXPECT_EQ(combine(Validity::MODALITY_ABSENT, a), Validity::MODALITY_ABSENT);
  }
}

TEST(ValidityLattice, EveryStateHasItsOwnStableName) {
  std::set<std::string> names;
  for (const Validity a : kAllStates) {
    names.insert(qr::validity_name(a));
  }
  EXPECT_EQ(names.size(), qr::kValidityCount);
  EXPECT_STREQ(qr::validity_name(Validity::VALID), "VALID");
  EXPECT_STREQ(qr::validity_name(Validity::MODALITY_ABSENT), "MODALITY_ABSENT");
}

TEST(TypedValue, CarriesItsValueAndValidityAndCombinesWorstWins) {
  const Typed<std::int64_t> good{42, Validity::VALID};
  EXPECT_TRUE(qr::is_valid(good));
  EXPECT_EQ(good.value, 42);

  const Typed<std::int64_t> masked = qr::with_combined(good, Validity::CROSSED);
  EXPECT_FALSE(qr::is_valid(masked));
  EXPECT_EQ(masked.v, Validity::CROSSED);
  EXPECT_EQ(masked.value, 42) << "combining validity must not touch the value";

  const Typed<std::int64_t> worse = qr::with_combined(masked, Validity::MODALITY_ABSENT);
  EXPECT_EQ(worse.v, Validity::MODALITY_ABSENT);
}

}  // namespace
