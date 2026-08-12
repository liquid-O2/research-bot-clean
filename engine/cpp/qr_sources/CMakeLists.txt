# qr_sources — the four pinned IWM stream readers (FINAL_PLAN APPENDIX B1-B4)
# plus the RUTW print reader (APPENDIX B5, sharing B3's column law and row laws),
# per design/DESIGN_SUBSTRATE.md M1 qr_sources bullet + APPENDIX C3.
add_library(qr_sources STATIC
  src/normalize.cpp
  src/option_prints.cpp
  src/option_quotes.cpp
  src/rutw_prints.cpp
  src/session_source.cpp
  src/stock_quotes.cpp
  src/stock_trades.cpp
  src/stream_spec.cpp
)
target_include_directories(qr_sources PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_sources PUBLIC qr_core qr_registry qr_clock qr_parquet)
# qr_sources is a BOUNDARY module: it turns decoded file values into typed
# stream rows, so every implicit conversion is an error here.
qr_apply_boundary_flags(qr_sources)

add_executable(qr_sources_tests
  tests/test_stream_spec.cpp
  tests/test_normalize.cpp
  tests/test_groups.cpp
  tests/test_readers.cpp
  tests/test_rutw_prints.cpp
  tests/test_real_file.cpp
)
target_link_libraries(qr_sources_tests PRIVATE qr_sources GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_sources_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_SOURCES_FIXTURE_DIR="${CMAKE_SOURCE_DIR}/tests/fixtures/sources"
  QR_SOURCES_EXPECTED_LITERALS="${CMAKE_SOURCE_DIR}/tests/fixtures/source_expected_literals.tsv"
  QR_SOURCES_REAL_DIGESTS="${CMAKE_SOURCE_DIR}/tests/fixtures/real_file_digests.tsv"
)
qr_apply_boundary_flags(qr_sources_tests)

add_test(NAME qr_sources_tests COMMAND qr_sources_tests)

# The probe: the authorized session-125 real-file read and the 3-stream
# throughput measurement. A binary rather than a test, for the same reason
# qr_parquet_probe is one — the stock-quote session is 15.4M rows and belongs in
# an artifact run (ci/wp4_sources_realfile_gate.sh), not in every ctest run.
add_executable(qr_sources_probe tools/qr_sources_probe.cpp)
target_link_libraries(qr_sources_probe PRIVATE qr_sources)
qr_apply_boundary_flags(qr_sources_probe)

# The D-020 V3 raw-tape ribbon: named projection slots over a decision
# neighbourhood, read-only and two-run identical. Nothing is derived here — the
# classified views come from the published DecisionTape group tables.
add_executable(qr_tape_ribbon tools/qr_tape_ribbon.cpp)
target_link_libraries(qr_tape_ribbon PRIVATE qr_sources qr_clock qr_registry)
qr_apply_boundary_flags(qr_tape_ribbon)
