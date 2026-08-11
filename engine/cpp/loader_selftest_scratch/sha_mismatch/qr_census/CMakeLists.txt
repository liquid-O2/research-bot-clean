# qr_census — WP9: the differential machinery and its merge gate
# (design/DESIGN_SUBSTRATE.md M1 module list "qr_census"; FINAL_PLAN.md
# section 6 "Correctness oracles" 2 and 3).
add_library(qr_census STATIC
  src/differential.cpp
  src/verdict.cpp
)
target_include_directories(qr_census PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
# qr_candidates carries the streaming OpenSSL SHA-256 the canonical byte image
# is absorbed into; the differential reuses it rather than growing a second
# implementation of a cryptographic primitive.
target_link_libraries(qr_census PUBLIC qr_core qr_registry qr_clock qr_sources qr_candidates)
# BOUNDARY MODULE: `parse_dump` turns untrusted archive text into typed state,
# so every implicit conversion is an error here.
qr_apply_boundary_flags(qr_census)

add_executable(qr_census_tests
  tests/test_differential.cpp
  tests/test_verdict.cpp
)
target_link_libraries(qr_census_tests PRIVATE qr_census GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_census_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
)
qr_apply_boundary_flags(qr_census_tests)

add_test(NAME qr_census_tests COMMAND qr_census_tests)

# The full-scope artifact runs. Binaries rather than ctest cases for the reason
# WP3/WP4/WP5/WP6 established: the 625-session pass decodes 7.46 billion rows.
add_executable(qr_census_dump tools/qr_census_dump.cpp)
target_link_libraries(qr_census_dump PRIVATE qr_census)
qr_apply_boundary_flags(qr_census_dump)

add_executable(qr_census_compare tools/qr_census_compare.cpp)
target_link_libraries(qr_census_compare PRIVATE qr_census)
qr_apply_boundary_flags(qr_census_compare)
