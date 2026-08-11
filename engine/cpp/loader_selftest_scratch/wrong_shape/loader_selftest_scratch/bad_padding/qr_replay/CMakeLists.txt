# qr_replay — WP11: THE economic replay kernel + scorecard aggregates
# (FINAL_PLAN.md APPENDIX C6, section 6 "qr_replay (one-position chronological
# kernel + scorecard)"; card section 6 chronology/selection law; the A6 gate;
# FINAL_PLAN section 11 null-control side streams).
add_library(qr_replay STATIC
  src/action.cpp
  src/pcg64.cpp
  src/policy_gate.cpp
  src/replay.cpp
  src/scorecard.cpp
)
target_include_directories(qr_replay PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_replay PUBLIC qr_core)
# BOUNDARY MODULE: this kernel is the only place the program turns predictions
# and labels into dollars, and every one of its integers is money, a clock, or a
# key. An implicit narrowing conversion here is a silent economic error, so the
# conversion diagnostics are errors exactly as in qr_core.
qr_apply_boundary_flags(qr_replay)

add_executable(qr_replay_tests
  tests/test_pcg64_numpy_parity.cpp
  tests/test_policy_gate.cpp
  tests/test_replay_chronology.cpp
  tests/test_replay_laws.cpp
  tests/test_scorecard.cpp
  tests/test_replay_budget.cpp
)
target_include_directories(qr_replay_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_link_libraries(qr_replay_tests PRIVATE qr_replay GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_replay_tests PRIVATE
  QR_REPLAY_FIXTURE_DIR="${CMAKE_SOURCE_DIR}/tests/fixtures/replay"
)
qr_apply_boundary_flags(qr_replay_tests)

add_test(NAME qr_replay_tests COMMAND qr_replay_tests)
