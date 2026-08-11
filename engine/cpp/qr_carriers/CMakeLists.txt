# qr_carriers — the prior-state machines, per-modality channel constructors,
# DIRECT_RAW 60-column summaries, the 1s midpoint grid, the 16 location/clock
# values, the 24-field candidate-set rows and the TRAIN-only normalization
# scaffolding (FINAL_PLAN.md section 6 WP8 "qr_carriers"; task card V4 section 4
# + section 5). WP8a: the native 128-group / 120-bin carriers and the
# destructions are WP8b and are NOT in this target.
find_package(OpenSSL REQUIRED)

add_library(qr_carriers STATIC
  src/channels.cpp
  src/attach.cpp
  src/prior_state.cpp
  src/stock_print_stream.cpp
  src/nbbo_stream.cpp
  src/option_print_stream.cpp
  src/direct_raw.cpp
  src/grid_1s.cpp
  src/location.cpp
  src/candidate_set.cpp
  src/normalization.cpp
)
target_include_directories(qr_carriers PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_carriers
  PUBLIC qr_core qr_registry qr_clock qr_sources qr_nbbo
  PRIVATE OpenSSL::Crypto)
# BOUNDARY MODULE: it turns typed stream state into scientific feature values, so
# every implicit conversion is an error here exactly as in qr_core and qr_nbbo.
qr_apply_boundary_flags(qr_carriers)

add_executable(qr_carriers_tests
  tests/test_transforms.cpp
  tests/test_prior_state.cpp
  tests/test_channels.cpp
  tests/test_direct_raw.cpp
  tests/test_grid_location_candset.cpp
  tests/test_normalization.cpp
)
target_link_libraries(qr_carriers_tests PRIVATE qr_carriers GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_carriers_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_CARRIERS_FIXTURE_DIR="${CMAKE_SOURCE_DIR}/tests/fixtures"
)
target_include_directories(qr_carriers_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests)
qr_apply_boundary_flags(qr_carriers_tests)

add_test(NAME qr_carriers_tests COMMAND qr_carriers_tests)

# The WP8a real-file probe: the authorized session-125 three-stream construction.
# A binary rather than a ctest case for the reason WP3/WP4/WP5 established —
# 15.4M NBBO rows do not belong in every ctest invocation, twice, under ASan.
# ci/wp8a_carriers_realfile_gate.sh runs it against the release build.
add_executable(qr_carriers_probe tools/qr_carriers_probe.cpp)
target_link_libraries(qr_carriers_probe PRIVATE qr_carriers)
qr_apply_boundary_flags(qr_carriers_probe)
