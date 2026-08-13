# qr_gen — PRODUCTION EVENT GENERATION (PORT_M1B_SPEC.md §1 S2).
# Built on the qr_futsess session receipts (M1.A gate A), the qr_skel session
# view / receipt pair / skeleton kernel (P-M1h) and the qr_core refusal carrier.
find_package(OpenSSL REQUIRED)

add_library(qr_gen STATIC
  src/generate.cpp
  src/gensession.cpp
  src/levels.cpp
  src/tables.cpp
)
target_include_directories(qr_gen PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_gen PUBLIC qr_core qr_futsess qr_skel PRIVATE OpenSSL::Crypto)
qr_apply_flags(qr_gen)

add_executable(qr_gen_tests tests/test_gen.cpp)
target_link_libraries(qr_gen_tests PRIVATE qr_gen GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_gen_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_M1B_SPEC_PATH="${CMAKE_SOURCE_DIR}/../../design/PORT_M1B_SPEC.md"
  QR_M1_SPEC_PATH="${CMAKE_SOURCE_DIR}/../../design/PORT_M1_SPEC.md")
qr_apply_flags(qr_gen_tests)

add_test(NAME qr_gen_tests COMMAND qr_gen_tests)

# The production driver: reads every session receipt of an asset, so it is a
# run.sh job and never a test.
add_executable(qr_gen_build tools/qr_gen_build.cpp)
target_link_libraries(qr_gen_build PRIVATE qr_gen)
qr_apply_flags(qr_gen_build)
