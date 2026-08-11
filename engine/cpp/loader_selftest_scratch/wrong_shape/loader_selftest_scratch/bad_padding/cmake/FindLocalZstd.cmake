# ZSTD for qr_parquet. NEVER downloads.
#
# Primary: the system libzstd-dev already present in this container (1.5.5).
# Fallback: the sha-pinned vendored tarball registered in authorities/REGISTRY.tsv
# as `vendor_zstd_1_5_6`, unpacked and built in-tree exactly the way
# cmake/VendorGoogleTest.cmake handles googletest.
#
# Either way the result is one imported target, `qr_zstd`.

if(TARGET qr_zstd)
  return()
endif()

find_path(QR_ZSTD_INCLUDE_DIR zstd.h)
find_library(QR_ZSTD_LIBRARY NAMES zstd)

if(QR_ZSTD_INCLUDE_DIR AND QR_ZSTD_LIBRARY)
  add_library(qr_zstd INTERFACE)
  target_include_directories(qr_zstd INTERFACE "${QR_ZSTD_INCLUDE_DIR}")
  target_link_libraries(qr_zstd INTERFACE "${QR_ZSTD_LIBRARY}")
  message(STATUS "qr_parquet: system zstd ${QR_ZSTD_LIBRARY}")
  return()
endif()

# --- vendored fallback -----------------------------------------------------
set(QR_ZSTD_TARBALL "/workspace/artifacts/vendor/zstd-1.5.6.tar.gz")
set(QR_AUTHORITIES_REGISTRY "/workspace/authorities/REGISTRY.tsv")
set(QR_ZSTD_AUTHORITY_ID "vendor_zstd_1_5_6")
set(QR_ZSTD_DIR "${CMAKE_SOURCE_DIR}/third_party/zstd-1.5.6")

if(NOT EXISTS "${QR_ZSTD_TARBALL}")
  message(FATAL_ERROR
    "no system zstd and the vendored fallback is missing: ${QR_ZSTD_TARBALL}\n"
    "qr_parquet pins ZSTD as the only codec; there is no other decode path.")
endif()

file(STRINGS "${QR_AUTHORITIES_REGISTRY}" _qr_zstd_rows REGEX "^${QR_ZSTD_AUTHORITY_ID}\t")
list(LENGTH _qr_zstd_rows _qr_zstd_row_count)
if(NOT _qr_zstd_row_count EQUAL 1)
  message(FATAL_ERROR
    "authorities/REGISTRY.tsv must carry exactly one ${QR_ZSTD_AUTHORITY_ID} row, "
    "found ${_qr_zstd_row_count}")
endif()
list(GET _qr_zstd_rows 0 _qr_zstd_row)
string(REPLACE "\t" ";" _qr_zstd_fields "${_qr_zstd_row}")
list(GET _qr_zstd_fields 3 QR_ZSTD_EXPECTED_SHA256)

file(SHA256 "${QR_ZSTD_TARBALL}" QR_ZSTD_ACTUAL_SHA256)
if(NOT QR_ZSTD_ACTUAL_SHA256 STREQUAL QR_ZSTD_EXPECTED_SHA256)
  message(FATAL_ERROR
    "vendored zstd tarball digest mismatch:\n"
    "  expected (authorities/REGISTRY.tsv) ${QR_ZSTD_EXPECTED_SHA256}\n"
    "  actual                              ${QR_ZSTD_ACTUAL_SHA256}")
endif()

if(NOT EXISTS "${QR_ZSTD_DIR}/lib/zstd.h")
  message(STATUS "unpacking sha-verified ${QR_ZSTD_TARBALL} into third_party/")
  file(MAKE_DIRECTORY "${CMAKE_SOURCE_DIR}/third_party")
  file(ARCHIVE_EXTRACT INPUT "${QR_ZSTD_TARBALL}" DESTINATION "${CMAKE_SOURCE_DIR}/third_party")
endif()
if(NOT EXISTS "${QR_ZSTD_DIR}/build/cmake/CMakeLists.txt")
  message(FATAL_ERROR "zstd unpack did not produce ${QR_ZSTD_DIR}/build/cmake/CMakeLists.txt")
endif()

set(ZSTD_BUILD_PROGRAMS OFF CACHE BOOL "" FORCE)
set(ZSTD_BUILD_SHARED OFF CACHE BOOL "" FORCE)
set(ZSTD_BUILD_STATIC ON CACHE BOOL "" FORCE)
set(ZSTD_BUILD_TESTS OFF CACHE BOOL "" FORCE)
add_subdirectory("${QR_ZSTD_DIR}/build/cmake" "${CMAKE_BINARY_DIR}/third_party/zstd" EXCLUDE_FROM_ALL)

add_library(qr_zstd INTERFACE)
target_include_directories(qr_zstd INTERFACE "${QR_ZSTD_DIR}/lib")
target_link_libraries(qr_zstd INTERFACE libzstd_static)
message(STATUS "qr_parquet: vendored zstd ${QR_ZSTD_DIR}")
