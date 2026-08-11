include(${CMAKE_SOURCE_DIR}/cmake/EmbedRegistry.cmake)

find_package(OpenSSL REQUIRED)

add_library(qr_registry STATIC
  src/day_scope.cpp
  src/warmup_scope.cpp
  src/registry.cpp
  ${QR_REGISTRY_BLOB_CPP}
)
target_include_directories(qr_registry PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_registry PUBLIC qr_core PRIVATE OpenSSL::Crypto)
qr_apply_boundary_flags(qr_registry)

add_executable(qr_registry_tests
  tests/test_day_scope.cpp
  tests/test_warmup_scope.cpp
  tests/test_registry.cpp
)
target_link_libraries(qr_registry_tests PRIVATE qr_registry GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_registry_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_REGISTRY_TSV_PATH="${QR_REGISTRY_TSV}"
)
qr_apply_boundary_flags(qr_registry_tests)

add_test(NAME qr_registry_tests COMMAND qr_registry_tests)
