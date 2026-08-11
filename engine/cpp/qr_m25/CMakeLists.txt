# qr_m25 — M2.5 reachability + decomposition (FINAL_PLAN.md section 8).
#
# It OWNS no economics: every dollar in this module comes out of qr_replay's one
# kernel. What it owns is the .npy reader, the tape -> ScoredAction loader with
# its TRAIN wall, the parametric skill law, the decomposition arms, and the
# twin-discordance ceiling.
add_library(qr_m25 STATIC
  src/npy.cpp
  src/tape.cpp
  src/skill.cpp
  src/arms.cpp
  src/twins.cpp
)
target_include_directories(qr_m25 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_m25 PUBLIC qr_core qr_replay)
qr_apply_flags(qr_m25)

add_executable(qr_m25_run tools/qr_m25_run.cpp)
target_link_libraries(qr_m25_run PRIVATE qr_m25)
qr_apply_flags(qr_m25_run)

add_executable(qr_m25_synth tools/qr_m25_synth.cpp)
target_link_libraries(qr_m25_synth PRIVATE qr_m25 qr_emit)
qr_apply_flags(qr_m25_synth)

add_executable(qr_m25_tests
  tests/test_skill_law.cpp
  tests/test_train_wall.cpp
  tests/test_arms_arithmetic.cpp
  tests/test_twin_ceiling.cpp
  tests/m25_test_support.cpp
)
target_include_directories(qr_m25_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_link_libraries(qr_m25_tests PRIVATE qr_m25 qr_emit GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_m25_tests PRIVATE
  QR_M25_TEST_SCRATCH="${QR_TEST_SCRATCH_DIR}/m25"
)
qr_apply_flags(qr_m25_tests)

add_test(NAME qr_m25_tests COMMAND qr_m25_tests)
