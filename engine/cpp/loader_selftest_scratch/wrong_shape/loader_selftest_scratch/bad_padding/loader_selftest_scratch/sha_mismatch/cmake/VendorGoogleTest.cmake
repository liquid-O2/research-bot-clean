# GoogleTest from the sha-pinned vendored tarball. NEVER downloads.
#
# authorities/REGISTRY.tsv row `vendor_gtest_1_14_0`:
#   sha256 8ad598c73ad796e0d8280b082cebd82a630d73e73cd3c70057938a6501bba5d7
#   path   /workspace/artifacts/vendor/googletest-1.14.0.tar.gz
#
# The tarball's digest is re-verified at configure time against the digest read
# out of authorities/REGISTRY.tsv itself, so the authority file — not this
# script — remains the single source of truth.

set(QR_GTEST_TARBALL "/workspace/artifacts/vendor/googletest-1.14.0.tar.gz")
set(QR_AUTHORITIES_REGISTRY "/workspace/authorities/REGISTRY.tsv")
set(QR_GTEST_AUTHORITY_ID "vendor_gtest_1_14_0")
set(QR_GTEST_DIR "${CMAKE_CURRENT_SOURCE_DIR}/third_party/googletest-1.14.0")

if(NOT EXISTS "${QR_AUTHORITIES_REGISTRY}")
  message(FATAL_ERROR "authorities/REGISTRY.tsv is missing: ${QR_AUTHORITIES_REGISTRY}")
endif()
if(NOT EXISTS "${QR_GTEST_TARBALL}")
  message(FATAL_ERROR "vendored gtest tarball is missing: ${QR_GTEST_TARBALL}")
endif()

# Pull the pinned digest out of the authority row (field 4 of the TSV).
file(STRINGS "${QR_AUTHORITIES_REGISTRY}" _qr_rows REGEX "^${QR_GTEST_AUTHORITY_ID}\t")
list(LENGTH _qr_rows _qr_row_count)
if(NOT _qr_row_count EQUAL 1)
  message(FATAL_ERROR
    "authorities/REGISTRY.tsv must carry exactly one ${QR_GTEST_AUTHORITY_ID} row, found ${_qr_row_count}")
endif()
list(GET _qr_rows 0 _qr_row)
string(REPLACE "\t" ";" _qr_fields "${_qr_row}")
list(GET _qr_fields 3 QR_GTEST_EXPECTED_SHA256)

file(SHA256 "${QR_GTEST_TARBALL}" QR_GTEST_ACTUAL_SHA256)
if(NOT QR_GTEST_ACTUAL_SHA256 STREQUAL QR_GTEST_EXPECTED_SHA256)
  message(FATAL_ERROR
    "vendored gtest tarball digest mismatch:\n"
    "  expected (authorities/REGISTRY.tsv) ${QR_GTEST_EXPECTED_SHA256}\n"
    "  actual                              ${QR_GTEST_ACTUAL_SHA256}")
endif()

if(NOT EXISTS "${QR_GTEST_DIR}/CMakeLists.txt")
  message(STATUS "unpacking sha-verified ${QR_GTEST_TARBALL} into third_party/")
  file(MAKE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/third_party")
  file(ARCHIVE_EXTRACT
    INPUT "${QR_GTEST_TARBALL}"
    DESTINATION "${CMAKE_CURRENT_SOURCE_DIR}/third_party")
endif()
if(NOT EXISTS "${QR_GTEST_DIR}/CMakeLists.txt")
  message(FATAL_ERROR "gtest unpack did not produce ${QR_GTEST_DIR}/CMakeLists.txt")
endif()

set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
set(BUILD_GMOCK OFF CACHE BOOL "" FORCE)
set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
add_subdirectory("${QR_GTEST_DIR}" "${CMAKE_BINARY_DIR}/third_party/googletest" EXCLUDE_FROM_ALL)

# Our -Werror set is deliberately NOT applied to vendored code (we do not own
# it); sanitizer flags come from CMAKE_CXX_FLAGS in the preset, so gtest is
# still built with ASan/UBSan when the asan preset is used.
