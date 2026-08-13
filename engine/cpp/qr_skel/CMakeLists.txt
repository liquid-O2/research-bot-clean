# qr_skel — the LABEL TENSOR ENGINE (PORT_M1B_SPEC.md §1 S3).
# Conventions: design/PORT_M1B_S3_CONV.md. Built on the qr_futsess session
# receipts (M1.A gate A) and the qr_core refusal carrier.
find_package(OpenSSL REQUIRED)

add_library(qr_skel STATIC
  src/binpack.cpp
  src/engine.cpp
  src/geom.cpp
  src/query.cpp
  src/session.cpp
  src/skeleton.cpp
)
target_include_directories(qr_skel PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_skel PUBLIC qr_core qr_futsess PRIVATE OpenSSL::Crypto)
qr_apply_flags(qr_skel)

add_executable(qr_skel_tests tests/test_skel.cpp)
target_link_libraries(qr_skel_tests PRIVATE qr_skel GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_skel_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_M1B_SPEC_PATH="${CMAKE_SOURCE_DIR}/../../design/PORT_M1B_SPEC.md")
qr_apply_flags(qr_skel_tests)

add_test(NAME qr_skel_tests COMMAND qr_skel_tests)

# The production driver: reads the whole candidate roster and every session
# receipt, so it is a run.sh job and never a test.
add_executable(qr_skel_build tools/qr_skel_build.cpp)
target_link_libraries(qr_skel_build PRIVATE qr_skel)
qr_apply_flags(qr_skel_build)
