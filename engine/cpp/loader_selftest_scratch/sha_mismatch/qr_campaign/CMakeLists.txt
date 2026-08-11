# qr_campaign — the CAMPAIGN CORPUS-BUILD DRIVER (FINAL_PLAN.md section 9 R2).
#
# Pure orchestration: it composes qr_candidates (roster + seal), qr_labels
# (watches + kernel), qr_carriers (streams + DIRECT + native carriers) and
# qr_emit (ShardWriter + fd census) into the complete APPENDIX C4 DecisionTape
# of a session, and dispatches one worker per session over the 625 in scope.
# It introduces NO new science and owns NO formula.
add_library(qr_campaign STATIC
  src/driver.cpp
  src/roster_view.cpp
  src/handoff.cpp
  src/session_build.cpp
)
target_include_directories(qr_campaign PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
target_link_libraries(qr_campaign
  PUBLIC qr_core qr_registry qr_clock qr_sources qr_nbbo qr_candidates qr_labels
         qr_carriers qr_replay qr_emit)
# BOUNDARY MODULE: it turns typed constructor output into the bytes a trainer
# will trust, so every implicit conversion is an error here.
qr_apply_boundary_flags(qr_campaign)

# The driver itself. It links qr_emit, so the fd-census door is interposed for
# the whole binary — which is exactly what makes the tagged constructor phase's
# census a proof rather than a convention.
add_executable(qr_campaign_build tools/qr_campaign_build.cpp)
target_link_libraries(qr_campaign_build PRIVATE qr_campaign)
qr_apply_boundary_flags(qr_campaign_build)

add_executable(qr_campaign_tests tests/test_campaign_driver.cpp)
target_link_libraries(qr_campaign_tests PRIVATE qr_campaign GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_campaign_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
)
qr_apply_boundary_flags(qr_campaign_tests)

add_test(NAME qr_campaign_tests COMMAND qr_campaign_tests)
