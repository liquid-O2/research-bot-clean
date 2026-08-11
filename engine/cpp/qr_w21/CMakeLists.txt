# qr_w21 — W2.1 OPTION-QUOTE BLOCK (FINAL_PLAN APPENDIX A2 as amended by
# design/DESIGN_FEATURES.md §W21-PIN-1).
#
# It depends on qr_w20 for the strictly-prior spot grid and the exact-count
# census machinery the W2.0 dossiers already established — one reader of the
# emitted 1s grid, not two.
add_library(qr_w21 STATIC
  src/surface.cpp
)
target_include_directories(qr_w21 PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_w21 PUBLIC qr_core qr_registry qr_clock qr_sources qr_carriers qr_w20)
# BOUNDARY MODULE: it turns decoded stream rows into typed channels.
qr_apply_boundary_flags(qr_w21)

add_executable(qr_w21_tests
  tests/test_surface.cpp
)
target_link_libraries(qr_w21_tests PRIVATE qr_w21 qr_emit GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_w21_tests PRIVATE
  QR_W21_TEST_SCRATCH="${QR_TEST_SCRATCH_DIR}/w21"
)
qr_apply_boundary_flags(qr_w21_tests)

add_test(NAME qr_w21_tests COMMAND qr_w21_tests)

add_executable(qr_w21_census tools/qr_w21_census.cpp)
target_link_libraries(qr_w21_census PRIVATE qr_w21)
qr_apply_boundary_flags(qr_w21_census)
