# qr_entry_v2 — causal raw-futures substrate for the entry-v2 research lane.
# It deliberately has a new artifact format and never reads/writes PORT M0-M3
# session artifacts.
find_package(OpenSSL REQUIRED)

add_library(qr_entry_v2 STATIC
  src/forecast.cpp
  src/forecast_artifacts.cpp
  src/g1.cpp
  src/g1_artifacts.cpp
  src/substrate.cpp
)
target_include_directories(qr_entry_v2 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_entry_v2 PUBLIC qr_core qr_databento qr_futsess_support
  PRIVATE OpenSSL::Crypto)
qr_apply_flags(qr_entry_v2)

add_executable(qr_entry_v2_build tools/qr_entry_v2_build.cpp)
target_link_libraries(qr_entry_v2_build PRIVATE qr_entry_v2)
qr_apply_flags(qr_entry_v2_build)

add_executable(qr_entry_v2_g1 tools/qr_entry_v2_g1.cpp)
target_link_libraries(qr_entry_v2_g1 PRIVATE qr_entry_v2)
qr_apply_flags(qr_entry_v2_g1)

add_executable(qr_entry_v2_forecast tools/qr_entry_v2_forecast.cpp)
target_link_libraries(qr_entry_v2_forecast PRIVATE qr_entry_v2)
qr_apply_flags(qr_entry_v2_forecast)

add_executable(qr_entry_v2_tests tests/test_entry_v2.cpp)
target_link_libraries(qr_entry_v2_tests PRIVATE qr_entry_v2 qr_dbn qr_zstd
  GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_entry_v2_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}")
qr_apply_flags(qr_entry_v2_tests)

add_test(NAME qr_entry_v2_tests COMMAND qr_entry_v2_tests)

add_executable(qr_entry_v2_g1_tests tests/test_g1.cpp)
target_link_libraries(qr_entry_v2_g1_tests PRIVATE qr_entry_v2
  GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_entry_v2_g1_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}")
qr_apply_flags(qr_entry_v2_g1_tests)

add_test(NAME qr_entry_v2_g1_tests COMMAND qr_entry_v2_g1_tests)

add_executable(qr_entry_v2_forecast_tests tests/test_forecast.cpp)
target_link_libraries(qr_entry_v2_forecast_tests PRIVATE qr_entry_v2
  GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_entry_v2_forecast_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}")
qr_apply_flags(qr_entry_v2_forecast_tests)

add_test(NAME qr_entry_v2_forecast_tests COMMAND qr_entry_v2_forecast_tests)
