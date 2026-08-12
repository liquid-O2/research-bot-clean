# qr_ivx — THE IV CROSS-SECTION MODULE (traded-IV skew/term from option prints,
# the model-free quote-skew proxy, and the CC-013 column census).
#
# TWO LIBRARIES, ONE WALL. `qr_ivx_meta` is the CC-013 column census and links
# ONLY qr_core/qr_registry/qr_parquet: the module that owns the option-print
# hard-refusal wall (`qr_sources`) is deliberately absent from that binary, so
# "this census never reads a forbidden VALUE" is a link-time fact rather than a
# code-review promise. `qr_ivx` is the constructor side and consumes decoded
# rows through `qr_sources`, exactly as qr_w20/qr_w21 do.
add_library(qr_ivx_meta STATIC
  src/tsv.cpp
  src/column_census.cpp
)
target_include_directories(qr_ivx_meta PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_ivx_meta PUBLIC qr_core qr_registry qr_parquet)
qr_apply_boundary_flags(qr_ivx_meta)

add_library(qr_ivx STATIC
  src/iv_cross.cpp
  src/quote_skew.cpp
  src/column_values.cpp
)
target_include_directories(qr_ivx PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_ivx PUBLIC qr_ivx_meta qr_clock qr_sources qr_w20 qr_w21)
# BOUNDARY MODULE: it turns decoded stream rows into typed channels.
qr_apply_boundary_flags(qr_ivx)

add_executable(qr_ivx_tests
  tests/test_column_census.cpp
  tests/test_iv_cross.cpp
  tests/test_quote_skew.cpp
)
target_link_libraries(qr_ivx_tests PRIVATE qr_ivx GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_ivx_tests PRIVATE
  QR_IVX_TEST_SCRATCH="${QR_TEST_SCRATCH_DIR}/ivx"
)
qr_apply_boundary_flags(qr_ivx_tests)

add_test(NAME qr_ivx_tests COMMAND qr_ivx_tests)

# The CC-013 column census run (schema + footer statistics only).
add_executable(qr_ivx_columns tools/qr_ivx_columns.cpp)
target_link_libraries(qr_ivx_columns PRIVATE qr_ivx_meta)
qr_apply_boundary_flags(qr_ivx_columns)

# The traded-IV skew/term census run (option prints, IWM and RUTW).
add_executable(qr_ivx_census tools/qr_ivx_census.cpp)
target_link_libraries(qr_ivx_census PRIVATE qr_ivx)
qr_apply_boundary_flags(qr_ivx_census)

# The model-free per-second quote-skew proxy run (option quotes).
add_executable(qr_ivx_qskew tools/qr_ivx_qskew.cpp)
target_link_libraries(qr_ivx_qskew PRIVATE qr_ivx)
qr_apply_boundary_flags(qr_ivx_qskew)

# The CC-013 VALUE census: the same five sessions, now through the reader.
add_executable(qr_ivx_colvalues tools/qr_ivx_colvalues.cpp)
target_link_libraries(qr_ivx_colvalues PRIVATE qr_ivx)
qr_apply_boundary_flags(qr_ivx_colvalues)

# The vol-index context join (ITEM C): FRED daily closes -> a strictly-prior
# per-session regime table. Links the registry only.
add_executable(qr_ivx_volindex tools/qr_ivx_volindex.cpp)
target_link_libraries(qr_ivx_volindex PRIVATE qr_ivx_meta)
qr_apply_boundary_flags(qr_ivx_volindex)
