find_program(QR_PYTHON3 python3 REQUIRED)

add_executable(qr_tools_tests tests/test_dialect_census.cpp)
target_link_libraries(qr_tools_tests PRIVATE GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_tools_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_PYTHON3="${QR_PYTHON3}"
  QR_CENSUS_TOOL="${CMAKE_CURRENT_SOURCE_DIR}/qr_dialect_census.py"
  QR_FIXTURE_DIR="${CMAKE_SOURCE_DIR}/tests/fixtures"
)
qr_apply_flags(qr_tools_tests)

add_test(NAME qr_tools_tests COMMAND qr_tools_tests)

# The WP2 payload-free cross-check print (see qr_clock_oracle.cpp). Not a test
# binary — check_red_ledger.sh enumerates qr_*_tests only.
add_executable(qr_clock_oracle qr_clock_oracle.cpp)
target_link_libraries(qr_clock_oracle PRIVATE qr_clock qr_registry)
qr_apply_boundary_flags(qr_clock_oracle)
