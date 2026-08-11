# qr_w20 — W2.0 STREAM MECHANICS CENSUSES (FINAL_PLAN.md section 10 W2.0;
# APPENDIX B3/B4). Dossiers D3 (option prints) and D4 (option quotes) are
# census-driven, and this module is the census.
#
# It owns NO feature: A2's bucket edges are not stated in the cited spec, so
# nothing here bins for a model. Every number it emits is an exact count.
add_library(qr_w20 STATIC
  src/mechanics.cpp
)
target_include_directories(qr_w20 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
# qr_m25 carries the .npy READER the spot grid is read back through; the census
# reuses it rather than growing a second .npy parser.
target_link_libraries(qr_w20 PUBLIC qr_core qr_registry qr_clock qr_sources qr_m25)
# BOUNDARY MODULE: it turns decoded stream rows into typed counts, so every
# implicit conversion is an error here.
qr_apply_boundary_flags(qr_w20)

add_executable(qr_w20_tests
  tests/test_mechanics.cpp
)
target_link_libraries(qr_w20_tests PRIVATE qr_w20 qr_emit GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_w20_tests PRIVATE
  QR_W20_TEST_SCRATCH="${QR_TEST_SCRATCH_DIR}/w20"
)
qr_apply_boundary_flags(qr_w20_tests)

add_test(NAME qr_w20_tests COMMAND qr_w20_tests)

# The census runs. A binary rather than a ctest case, for the reason
# WP3/WP4/WP5 established: one option-quote session is 27M-148M rows.
add_executable(qr_w20_census tools/qr_w20_census.cpp)
target_link_libraries(qr_w20_census PRIVATE qr_w20)
qr_apply_boundary_flags(qr_w20_census)
