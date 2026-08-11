# qr_carriers — the prior-state machines, per-modality channel constructors,
# DIRECT_RAW 60-column summaries, the reduced equal-time group vectors, the
# native 128-group micro and 120-bin full carriers with the section-7
# destructions built into the same constructors, the 1s midpoint grid, the 16
# location/clock values, the 24-field candidate-set rows and the TRAIN-only
# normalization scaffolding (FINAL_PLAN.md section 6 WP8 "qr_carriers"; task card
# V4 section 4 + section 5 + section 7). WP8a built everything but the native
# carriers; WP8b added group_vector/native_order and the destruction guard.
find_package(OpenSSL REQUIRED)

set(QR_CARRIERS_SOURCES
  src/channels.cpp
  src/attach.cpp
  src/prior_state.cpp
  src/group_vector.cpp
  src/stock_print_stream.cpp
  src/nbbo_stream.cpp
  src/option_print_stream.cpp
  src/direct_raw.cpp
  src/native_order.cpp
  src/grid_1s.cpp
  src/location.cpp
  src/candidate_set.cpp
  src/normalization.cpp
)

add_library(qr_carriers STATIC ${QR_CARRIERS_SOURCES})
target_include_directories(qr_carriers PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_carriers
  PUBLIC qr_core qr_registry qr_clock qr_sources qr_nbbo
  PRIVATE OpenSSL::Crypto)
# BOUNDARY MODULE: it turns typed stream state into scientific feature values, so
# every implicit conversion is an error here exactly as in qr_core and qr_nbbo.
qr_apply_boundary_flags(qr_carriers)

# THE DESTRUCTION GUARD'S SECOND BUILD. The same sources with
# QR_CARRIERS_NO_DESTRUCTIONS defined: the section-7 control flags and every
# branch that reads them are not compiled at all. Its only consumer is
# qr_carriers_nodestruct_probe, whose fingerprint the test suite compares against
# the ordinary build's — "destruction-flag off = production path byte-identical
# to a build without the flag code compiled".
add_library(qr_carriers_nodestruct STATIC ${QR_CARRIERS_SOURCES})
target_include_directories(qr_carriers_nodestruct PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_definitions(qr_carriers_nodestruct PUBLIC QR_CARRIERS_NO_DESTRUCTIONS)
target_link_libraries(qr_carriers_nodestruct
  PUBLIC qr_core qr_registry qr_clock qr_sources qr_nbbo
  PRIVATE OpenSSL::Crypto)
qr_apply_boundary_flags(qr_carriers_nodestruct)

add_executable(qr_carriers_tests
  tests/test_transforms.cpp
  tests/test_prior_state.cpp
  tests/test_channels.cpp
  tests/test_direct_raw.cpp
  tests/test_grid_location_candset.cpp
  tests/test_normalization.cpp
  tests/test_native_order.cpp
)
# qr_emit comes in for ONE fixture: the C4 leaf set is written through the real
# shard writer and read back out of the published manifest, so the emitted
# names/dtypes/shapes are proved against APPENDIX C4 rather than asserted.
target_link_libraries(qr_carriers_tests PRIVATE qr_carriers qr_emit GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_carriers_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_CARRIERS_FIXTURE_DIR="${CMAKE_SOURCE_DIR}/tests/fixtures"
)
target_include_directories(qr_carriers_tests PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/tests
  ${CMAKE_CURRENT_SOURCE_DIR}/tools)
qr_apply_boundary_flags(qr_carriers_tests)

add_test(NAME qr_carriers_tests COMMAND qr_carriers_tests)

# The WP8a real-file probe: the authorized session-125 three-stream construction.
# A binary rather than a ctest case for the reason WP3/WP4/WP5 established —
# 15.4M NBBO rows do not belong in every ctest invocation, twice, under ASan.
# ci/wp8a_carriers_realfile_gate.sh runs it against the release build.
add_executable(qr_carriers_probe tools/qr_carriers_probe.cpp)
target_link_libraries(qr_carriers_probe PRIVATE qr_carriers)
qr_apply_boundary_flags(qr_carriers_probe)

# The destruction guard's second binary (see qr_carriers_nodestruct above).
add_executable(qr_carriers_nodestruct_probe tools/qr_carriers_nodestruct_probe.cpp)
target_link_libraries(qr_carriers_nodestruct_probe PRIVATE qr_carriers_nodestruct)
target_include_directories(qr_carriers_nodestruct_probe PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tools)
qr_apply_boundary_flags(qr_carriers_nodestruct_probe)
