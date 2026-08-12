# qr_wave2 — the M4 wave-2 families that need cross-session prior state:
# W2.13 prior-session structure (+ADD-1, 14 channels) and W2.2 variance-budget
# normalization (8 channels), plus the CC-012 warmup pass that feeds both.
# Constructors, fixtures and censuses ONLY — no tape emission (W2.2-PIN-1:
# "C4 tape schema untouched; wave-2 emission = M4 registration via change
# control (tape v4.1)").

set(QR_WAVE2_SOURCES
  src/prior_state.cpp
  src/prior_structure.cpp
  src/variance_budget.cpp
  src/session_pass.cpp
)

add_library(qr_wave2 STATIC ${QR_WAVE2_SOURCES})
target_include_directories(qr_wave2 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_wave2 PUBLIC qr_core qr_registry qr_clock qr_sources qr_nbbo qr_carriers)
# BOUNDARY MODULE: it turns typed session state into scientific feature values.
qr_apply_boundary_flags(qr_wave2)

# THE DESTRUCTION GUARD'S SECOND BUILD (the qr_carriers idiom): the same sources
# with QR_WAVE2_NO_DESTRUCTIONS defined, in which the control flags and every
# branch reading them are not compiled at all. Its only consumer is
# qr_wave2_nodestruct_probe, whose fingerprint the suite compares against the
# ordinary build's — "destruction-flag off = production path byte-identical to a
# build without the flag code compiled".
add_library(qr_wave2_nodestruct STATIC ${QR_WAVE2_SOURCES})
target_include_directories(qr_wave2_nodestruct PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_compile_definitions(qr_wave2_nodestruct PUBLIC QR_WAVE2_NO_DESTRUCTIONS)
target_link_libraries(qr_wave2_nodestruct
  PUBLIC qr_core qr_registry qr_clock qr_sources qr_nbbo qr_carriers)
qr_apply_boundary_flags(qr_wave2_nodestruct)

add_executable(qr_wave2_tests
  tests/test_prior_state.cpp
  tests/test_prior_structure.cpp
  tests/test_variance_budget.cpp
  tests/test_warmup_and_identity.cpp
)
# qr_labels comes in for ONE fixture: CC-012 r3 asserts that the LABEL path is
# not even invocable with a WarmupScope, which needs its real entry point.
target_link_libraries(qr_wave2_tests PRIVATE qr_wave2 qr_labels GTest::gtest GTest::gtest_main)
target_include_directories(qr_wave2_tests PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/tests
  ${CMAKE_CURRENT_SOURCE_DIR}/tools)
target_compile_definitions(qr_wave2_tests PRIVATE QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}")
qr_apply_boundary_flags(qr_wave2_tests)

add_test(NAME qr_wave2_tests COMMAND qr_wave2_tests)

# The real-payload census: the warmup accumulation over ordinals 0..124 and the
# two families' per-channel presence census on scoped sessions. A binary rather
# than a ctest case for the reason WP3/WP4/WP5 established — whole sessions of
# NBBO rows do not belong in every ctest invocation, twice, under ASan.
add_executable(qr_wave2_census tools/qr_wave2_census.cpp)
target_link_libraries(qr_wave2_census PRIVATE qr_wave2)
target_include_directories(qr_wave2_census PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tools)
qr_apply_boundary_flags(qr_wave2_census)

# The D-020 pack dump: the same pathway as the census, with the CHANNEL VALUES
# printed at named decision seconds instead of folded into a presence counter.
add_executable(qr_wave2_dump tools/qr_wave2_dump.cpp)
target_link_libraries(qr_wave2_dump PRIVATE qr_wave2)
target_include_directories(qr_wave2_dump PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tools)
qr_apply_boundary_flags(qr_wave2_dump)

# The destruction guard's second binary (see qr_wave2_nodestruct above).
add_executable(qr_wave2_nodestruct_probe tools/qr_wave2_nodestruct_probe.cpp)
target_link_libraries(qr_wave2_nodestruct_probe PRIVATE qr_wave2_nodestruct)
target_include_directories(qr_wave2_nodestruct_probe PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tools)
qr_apply_boundary_flags(qr_wave2_nodestruct_probe)
