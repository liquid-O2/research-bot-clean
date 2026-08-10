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
