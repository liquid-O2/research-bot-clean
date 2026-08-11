# qr_emit — the DecisionTape container layer (FINAL_PLAN.md APPENDIX C4,
# design/DESIGN_SUBSTRATE.md M1 `qr_emit` bullet).
#
# NOTE ON THE INTERPOSING OBJECT. src/fd_census_interpose.cpp defines
# open/openat/fopen for the whole binary. That is the point (APPENDIX C4's
# process separation is only a proof if it sees every open), and it is why the
# object lives in this library rather than in a test: a production feature
# builder needs the same door. Binaries that do not link qr_emit are untouched.
# The engine/cpp root, derived from this file rather than from CMAKE_SOURCE_DIR,
# so the module also configures under a single-module lane build tree.
get_filename_component(QR_CPP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}" DIRECTORY)

find_package(OpenSSL REQUIRED)

add_library(qr_emit STATIC
  src/fd_census.cpp
  src/fd_census_interpose.cpp
  src/npy_writer.cpp
  src/shard_writer.cpp
)
target_include_directories(qr_emit
  PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include
  PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src
)
target_link_libraries(qr_emit PUBLIC qr_core PRIVATE OpenSSL::Crypto)
# qr_emit is a BOUNDARY module: it turns typed values into bytes on disk that
# another process will trust, so every implicit conversion is an error here.
qr_apply_boundary_flags(qr_emit)

add_executable(qr_emit_tests
  tests/test_fd_census.cpp
  tests/test_npy_writer.cpp
  tests/test_shard_writer.cpp
)
target_include_directories(qr_emit_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_link_libraries(qr_emit_tests PRIVATE qr_emit OpenSSL::Crypto GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_emit_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_EMIT_NPY_FIXTURE_DIR="${QR_CPP_ROOT}/tests/fixtures/npy"
)
qr_apply_boundary_flags(qr_emit_tests)

add_test(NAME qr_emit_tests COMMAND qr_emit_tests)

# The synthetic-shard tool. It writes the reference DecisionTape that the Python
# loader's self-test reads, so the round trip crosses the language boundary the
# way the real pipeline will (C++ writes, numpy mmaps).
add_executable(qr_emit_make_shard tools/qr_emit_make_shard.cpp)
target_link_libraries(qr_emit_make_shard PRIVATE qr_emit)
qr_apply_boundary_flags(qr_emit_make_shard)

# The throughput gate's measuring instrument: a 1GB synthetic shard plus a raw
# write(2) baseline on the same filesystem, so "we are slow" and "the mount is
# slow" are distinguishable facts rather than one number.
add_executable(qr_emit_bench tools/qr_emit_bench.cpp)
target_link_libraries(qr_emit_bench PRIVATE qr_emit)
qr_apply_boundary_flags(qr_emit_bench)
