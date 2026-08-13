# qr_dbn — exact DBN GLBX mbp-1 decode (PORT_M1_SPEC section 1.1).
#
# ZSTD: system libzstd is primary, the sha-pinned vendored tarball is the
# offline fallback. Same policy as qr_parquet; nothing downloads.
include(${CMAKE_SOURCE_DIR}/cmake/FindLocalZstd.cmake)

add_library(qr_dbn STATIC
  src/dbn.cpp
  src/zstd_stream.cpp
)
target_include_directories(qr_dbn PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_dbn PUBLIC qr_core PRIVATE qr_zstd)
# qr_dbn is a BOUNDARY module: it turns untrusted file bytes into typed values,
# so every implicit conversion is an error here exactly as in qr_core.
qr_apply_boundary_flags(qr_dbn)

# The real-file cross-check pins the struct layout against actual corpus bytes.
# It is an UNSEALED payload (2024); the seal forbids any 2026-dated file.
set(QR_DBN_REAL_FILE
  "/workspace/artifacts/reference/futures_mbp1/[Copper] GLBX-20260606-NC7JE46DYS/glbx-mdp3-20240101-20241231.mbp-1.dbn.zst")

add_executable(qr_dbn_tests
  tests/test_dbn.cpp
  tests/test_real_file.cpp
)
target_link_libraries(qr_dbn_tests PRIVATE qr_dbn qr_zstd GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_dbn_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_DBN_REAL_FILE="${QR_DBN_REAL_FILE}"
)
qr_apply_boundary_flags(qr_dbn_tests)

add_test(NAME qr_dbn_tests COMMAND qr_dbn_tests)
