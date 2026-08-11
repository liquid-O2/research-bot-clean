# qr_labels — WP7: the watches, the decision clock and THE label kernel
# (design/DESIGN_SUBSTRATE.md section 6 "`qr_labels` (7-horizon stop-aware menu
# vector + certificate diagnostics via ONE shared stop_scan primitive)",
# FINAL_PLAN.md APPENDIX C5 + A13, task card V4 section 3).
add_library(qr_labels STATIC
  src/money.cpp
  src/execution_tape.cpp
  src/watches.cpp
  src/label_kernel.cpp
)
target_include_directories(qr_labels PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_labels PUBLIC qr_core qr_registry qr_clock qr_sources qr_nbbo qr_replay)
# BOUNDARY MODULE, for qr_replay's reason: every integer here is money, a clock
# or a key, so an implicit narrowing conversion is a silent economic error.
qr_apply_boundary_flags(qr_labels)

add_executable(qr_labels_tests
  tests/test_money.cpp
  tests/test_execution_tape.cpp
  tests/test_watches.cpp
  tests/test_label_kernel.cpp
)
target_include_directories(qr_labels_tests
  PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests ${CMAKE_SOURCE_DIR}/qr_sources/tests)
target_link_libraries(qr_labels_tests PRIVATE qr_labels GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_labels_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  # The shared WP4 fixture support needs its own two roots; qr_labels reads no
  # fixture file itself (its tapes are hand-built rows) but reuses `scope_125()`
  # so every micro-tape is clocked by the REAL registry session.
  QR_SOURCES_FIXTURE_DIR="${CMAKE_SOURCE_DIR}/tests/fixtures/sources"
  QR_SOURCES_EXPECTED_LITERALS="${CMAKE_SOURCE_DIR}/tests/fixtures/source_expected_literals.tsv"
)
qr_apply_boundary_flags(qr_labels_tests)

add_test(NAME qr_labels_tests COMMAND qr_labels_tests)

# The probe: the authorized session-125 watch + label run. A binary rather than
# a ctest case for the reason WP3/WP4/WP5 established — 15.4M rows and 2.8M
# groups do not belong in every ctest invocation.
# ci/wp7_labels_realfile_gate.sh runs it against the release build.
add_executable(qr_labels_probe tools/qr_labels_probe.cpp)
target_link_libraries(qr_labels_probe PRIVATE qr_labels)
qr_apply_boundary_flags(qr_labels_probe)
