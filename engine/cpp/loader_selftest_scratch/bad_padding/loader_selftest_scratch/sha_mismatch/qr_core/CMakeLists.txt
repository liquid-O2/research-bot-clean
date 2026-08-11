add_library(qr_core STATIC
  src/frames.cpp
  src/refusal.cpp
  src/validity.cpp
)
target_include_directories(qr_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
qr_apply_boundary_flags(qr_core)

add_executable(qr_core_tests
  tests/test_checked.cpp
  tests/test_frames.cpp
  tests/test_validity.cpp
)
target_link_libraries(qr_core_tests PRIVATE qr_core GTest::gtest GTest::gtest_main)
qr_apply_boundary_flags(qr_core_tests)

add_test(NAME qr_core_tests COMMAND qr_core_tests)
