# ============================================================================
# research-bot-clean C++ substrate (FINAL_PLAN.md section 6 / design/DESIGN_SUBSTRATE.md)
#
# Layout law:  sources live in /workspace/engine/cpp; BUILD TREES LIVE ONLY IN
#              /workspace/artifacts/cache/cpp/{dev,asan,release,mutant}.
#              Nothing is ever written under /tmp (container overlay).
# Warning law: -Wall -Wextra -Wpedantic -Werror everywhere we own, plus
#              -Werror=conversion -Werror=sign-conversion on the boundary
#              modules qr_core and qr_registry.
# FP law:      -ffp-contract=off on every target we own; no fast-math anywhere.
# Test law:    GoogleTest comes from the sha-pinned vendored tarball in
#              /workspace/artifacts/vendor (authorities/REGISTRY.tsv row
#              vendor_gtest_1_14_0). Nothing is downloaded, ever.
# ============================================================================
cmake_minimum_required(VERSION 3.28)
project(qr_substrate LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
# Every test binary lands in <build>/bin so scripts/check_red_ledger.sh can
# enumerate the suite without guessing directory layout.
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")

# --- build-tree wall -------------------------------------------------------
get_filename_component(_qr_binary_real "${CMAKE_BINARY_DIR}" REALPATH)
if(NOT _qr_binary_real MATCHES "^/workspace/artifacts/cache/cpp/")
  message(FATAL_ERROR
    "build tree must live under /workspace/artifacts/cache/cpp/{dev,asan,release,mutant}; "
    "got ${_qr_binary_real}. Use one of the CMakePresets.json presets.")
endif()

# --- warning / FP flags for the code we own --------------------------------
set(QR_COMMON_FLAGS -Wall -Wextra -Wpedantic -Werror -ffp-contract=off)
# Boundary modules additionally promote every implicit-conversion diagnostic.
set(QR_BOUNDARY_FLAGS -Werror=conversion -Werror=sign-conversion -Wconversion -Wsign-conversion)

function(qr_apply_flags target)
  target_compile_options(${target} PRIVATE ${QR_COMMON_FLAGS})
endfunction()

function(qr_apply_boundary_flags target)
  target_compile_options(${target} PRIVATE ${QR_COMMON_FLAGS} ${QR_BOUNDARY_FLAGS})
endfunction()

# Scratch space for tests that must write files. Never /tmp: the container
# overlay is ~5GB and banned by the machine law.
set(QR_TEST_SCRATCH_DIR "${CMAKE_BINARY_DIR}/test_scratch")
file(MAKE_DIRECTORY "${QR_TEST_SCRATCH_DIR}")

# --- vendored GoogleTest (sha-pinned, offline) -----------------------------
include(cmake/VendorGoogleTest.cmake)

# --- modules ---------------------------------------------------------------
enable_testing()
add_subdirectory(qr_core)
add_subdirectory(qr_registry)
add_subdirectory(qr_clock)
add_subdirectory(qr_parquet)
add_subdirectory(qr_sources)
add_subdirectory(qr_nbbo)
add_subdirectory(qr_candidates)
add_subdirectory(qr_carriers)
add_subdirectory(qr_wave2)
add_subdirectory(qr_census)
add_subdirectory(qr_replay)
add_subdirectory(qr_labels)
add_subdirectory(qr_emit)
add_subdirectory(qr_campaign)
add_subdirectory(qr_m25)
add_subdirectory(qr_w20)
add_subdirectory(qr_w21)
add_subdirectory(tools)
