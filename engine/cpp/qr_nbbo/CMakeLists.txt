# qr_nbbo — the equal-millisecond NBBO group machine and its census
# (design/DESIGN_SUBSTRATE.md section 6 + APPENDIX C1/C5, WP5).
add_library(qr_nbbo STATIC
  src/census.cpp
  src/group_machine.cpp
  src/quote_groups.cpp
)
target_include_directories(qr_nbbo PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_nbbo PUBLIC qr_core qr_registry qr_clock qr_sources)
# qr_nbbo is a BOUNDARY module: it turns stream rows into typed group state, so
# every implicit conversion is an error here.
qr_apply_boundary_flags(qr_nbbo)

add_executable(qr_nbbo_tests
  tests/test_member_classification.cpp
  tests/test_group_machine.cpp
  tests/test_census.cpp
)
target_link_libraries(qr_nbbo_tests PRIVATE qr_nbbo GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_nbbo_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_SOURCES_FIXTURE_DIR="${CMAKE_SOURCE_DIR}/tests/fixtures/sources"
  QR_SOURCES_EXPECTED_LITERALS="${CMAKE_SOURCE_DIR}/tests/fixtures/source_expected_literals.tsv"
  QR_NBBO_SESSION125_CENSUS="${CMAKE_SOURCE_DIR}/tests/fixtures/nbbo_session125_census.tsv"
)
target_include_directories(qr_nbbo_tests PRIVATE ${CMAKE_SOURCE_DIR}/qr_sources/tests)
qr_apply_boundary_flags(qr_nbbo_tests)

add_test(NAME qr_nbbo_tests COMMAND qr_nbbo_tests)

# The probe: the authorized session-125 full-day group-machine run. A binary
# rather than a ctest case for the reason WP3 and WP4 established — 15.4M rows
# do not belong in every ctest invocation. ci/wp5_nbbo_realfile_gate.sh runs it
# against the release build.
add_executable(qr_nbbo_probe tools/qr_nbbo_probe.cpp)
target_link_libraries(qr_nbbo_probe PRIVATE qr_nbbo)
qr_apply_boundary_flags(qr_nbbo_probe)
