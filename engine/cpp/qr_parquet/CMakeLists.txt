# qr_parquet — the dialect-pinned minimal parquet decoder (FINAL_PLAN section 6,
# design/DESIGN_SUBSTRATE.md M1 qr_parquet bullet).
#
# ZSTD: the system libzstd-dev (1.5.5) is primary. authorities/REGISTRY.tsv row
# `vendor_zstd_1_5_6` is the sha-pinned offline fallback; nothing downloads, and
# a missing system library is a hard configure error naming the tarball rather
# than a silent switch to some other codec.
include(${CMAKE_SOURCE_DIR}/cmake/FindLocalZstd.cmake)

add_library(qr_parquet STATIC
  src/column.cpp
  src/dialect.cpp
  src/metadata.cpp
  src/reader.cpp
  src/thrift.cpp
)
target_include_directories(qr_parquet PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_parquet PUBLIC qr_core PRIVATE qr_zstd)
# qr_parquet is a BOUNDARY module: it turns untrusted file bytes into typed
# values, so every implicit conversion is an error here exactly as in qr_core.
qr_apply_boundary_flags(qr_parquet)

add_executable(qr_parquet_tests
  tests/test_thrift.cpp
  tests/test_dialect_refusals.cpp
  tests/test_decode_values.cpp
  tests/test_real_file.cpp
)
target_link_libraries(qr_parquet_tests PRIVATE qr_parquet GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_parquet_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_PARQUET_FIXTURE_DIR="${CMAKE_SOURCE_DIR}/tests/fixtures/parquet"
  QR_PARQUET_REAL_DIGESTS="${CMAKE_SOURCE_DIR}/tests/fixtures/real_file_digests.tsv"
)
qr_apply_boundary_flags(qr_parquet_tests)

add_test(NAME qr_parquet_tests COMMAND qr_parquet_tests)

# The probe tool: real-file digests and the decode-throughput measurement. It is
# a binary, not a test, because the option-quote shard it can be pointed at is
# 704MB and belongs in an artifact run, not in every ctest invocation (the same
# rule ci/run_all.sh already applies to the WP0 whole-corpus census).
add_executable(qr_parquet_probe tools/qr_parquet_probe.cpp)
target_link_libraries(qr_parquet_probe PRIVATE qr_parquet)
qr_apply_boundary_flags(qr_parquet_probe)
