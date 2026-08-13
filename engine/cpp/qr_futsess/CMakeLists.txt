# qr_futsess — the M0 program-mode session substrate in C++
# (PORT_M1_SPEC section 1.2; semantics from PORT_M0_CENSUS_SPEC sections 0/4/5).
include(${CMAKE_SOURCE_DIR}/cmake/FindLocalZstd.cmake)

add_library(qr_futsess STATIC
  src/calendar.cpp
  src/constants.cpp
  src/dayrec.cpp
  src/decode.cpp
  src/json.cpp
  src/seal.cpp
  src/sessions.cpp
)
target_include_directories(qr_futsess PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_futsess PUBLIC qr_core qr_dbn PRIVATE qr_zstd)
qr_apply_flags(qr_futsess)

add_executable(qr_futsess_tests tests/test_futsess.cpp)
target_link_libraries(qr_futsess_tests PRIVATE qr_futsess GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_futsess_tests PRIVATE QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}")
qr_apply_flags(qr_futsess_tests)

add_test(NAME qr_futsess_tests COMMAND qr_futsess_tests)

# The two production binaries. They are tools, not tests: they read the whole
# 48 GB payload corpus and belong in a run.sh job.
add_executable(qr_futsess_decode tools/qr_futsess_decode.cpp)
target_link_libraries(qr_futsess_decode PRIVATE qr_futsess)
qr_apply_flags(qr_futsess_decode)

add_executable(qr_futsess_assemble tools/qr_futsess_assemble.cpp)
target_link_libraries(qr_futsess_assemble PRIVATE qr_futsess)
qr_apply_flags(qr_futsess_assemble)
