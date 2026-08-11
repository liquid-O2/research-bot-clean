# qr_candidates — the causal candidate roster and side authentication
# (FINAL_PLAN.md section 6 WP6, design/DESIGN_SUBSTRATE.md M1 qr_candidates
# bullet: "rowgroup-addressed projection + bounded non-prefetch pread TSV prefix
# reader + LOW->LONG/HIGH->SHORT side auth + both physical-key mutants").
find_package(OpenSSL REQUIRED)

add_library(qr_candidates STATIC
  src/signal_root.cpp
  src/prefix_reader.cpp
  src/rowgroup_table.cpp
  src/roster.cpp
)
target_include_directories(qr_candidates PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_candidates PUBLIC qr_core qr_parquet PRIVATE OpenSSL::Crypto)
# BOUNDARY MODULE: it turns untrusted publication bytes into typed scientific
# state, so every implicit conversion is an error here exactly as in qr_core.
qr_apply_boundary_flags(qr_candidates)

add_executable(qr_candidates_tests
  tests/test_signal_root.cpp
  tests/test_prefix_reader.cpp
  tests/test_rowgroup_table.cpp
  tests/test_roster.cpp
)
target_link_libraries(qr_candidates_tests PRIVATE qr_candidates GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_candidates_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_CANDIDATES_FIXTURE_DIR="${CMAKE_SOURCE_DIR}/tests/fixtures/candidates"
)
qr_apply_boundary_flags(qr_candidates_tests)

add_test(NAME qr_candidates_tests COMMAND qr_candidates_tests)

# The WP6 real-data seal. A binary rather than a ctest case because it walks
# 10.7GB of sealed publication text: that belongs in an artifact run, exactly as
# ci/run_all.sh already treats the WP0 census and the WP3 shard probe.
add_executable(qr_candidates_seal tools/qr_candidates_seal.cpp)
target_link_libraries(qr_candidates_seal PRIVATE qr_candidates)
qr_apply_boundary_flags(qr_candidates_seal)
