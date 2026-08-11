add_library(qr_clock STATIC
  src/session_clock.cpp
)
target_include_directories(qr_clock PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_clock PUBLIC qr_core qr_registry)
qr_apply_boundary_flags(qr_clock)

add_executable(qr_clock_tests
  tests/test_classify_attach.cpp
  tests/test_session_clock.cpp
)
target_include_directories(qr_clock_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/tests)
target_link_libraries(qr_clock_tests PRIVATE qr_clock GTest::gtest GTest::gtest_main)
qr_apply_boundary_flags(qr_clock_tests)

add_test(NAME qr_clock_tests COMMAND qr_clock_tests)
