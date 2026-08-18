# qr_databento -- narrow, hash-gated production adapter over official
# databento-cpp.  The handwritten qr_dbn decoder remains a test oracle only.
include(${CMAKE_SOURCE_DIR}/cmake/FindLocalZstd.cmake)
find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

set(QR_DATABENTO_VENDOR_DIR "/workspace/vendor/databento-cpp" CACHE PATH
    "Read-only upstream-identical databento-cpp v0.64.0 source tree")
set(QR_DATABENTO_DEPS_INCLUDE_DIR
    "/workspace/artifacts/cache/cpp/dbn_diff/deps/include" CACHE PATH
    "Existing read-only date/json/httplib headers; never downloaded here")

set(_qr_vendor_tree_expected
    "9aa9aede26acf2f0e442a84867819f0efd93c64f6cb606ba4320f3ad100175b8")
file(GLOB_RECURSE _qr_vendor_files CONFIGURE_DEPENDS LIST_DIRECTORIES false
     RELATIVE "${QR_DATABENTO_VENDOR_DIR}" "${QR_DATABENTO_VENDOR_DIR}/*")
list(SORT _qr_vendor_files)
list(LENGTH _qr_vendor_files _qr_vendor_file_count)
if(NOT _qr_vendor_file_count EQUAL 254)
  message(FATAL_ERROR
    "qr_databento: official vendor tree file count drift: expected 254, got ${_qr_vendor_file_count}")
endif()
set(_qr_vendor_manifest "")
foreach(_qr_rel IN LISTS _qr_vendor_files)
  file(SHA256 "${QR_DATABENTO_VENDOR_DIR}/${_qr_rel}" _qr_file_sha)
  # Canonical authority frozen in databento_clock_law.receipt.json.  This is
  # byte-for-byte the manifest emitted by `sha256sum` after the absolute vendor
  # prefix is removed: HASH, two spaces, relative path, LF.
  string(APPEND _qr_vendor_manifest "${_qr_file_sha}  ${_qr_rel}\n")
endforeach()
string(SHA256 _qr_vendor_tree_sha "${_qr_vendor_manifest}")
if(NOT _qr_vendor_tree_sha STREQUAL _qr_vendor_tree_expected)
  message(FATAL_ERROR
    "qr_databento: official vendor tree SHA-256 drift: expected ${_qr_vendor_tree_expected}, got ${_qr_vendor_tree_sha}")
endif()

function(qr_verify_cached_header relative expected)
  set(_path "${QR_DATABENTO_DEPS_INCLUDE_DIR}/${relative}")
  if(NOT EXISTS "${_path}")
    message(FATAL_ERROR
      "qr_databento portability gap: required cached header is absent: ${_path}; no download fallback is permitted")
  endif()
  file(SHA256 "${_path}" _actual)
  if(NOT _actual STREQUAL expected)
    message(FATAL_ERROR
      "qr_databento cached header drift for ${relative}: expected ${expected}, got ${_actual}")
  endif()
endfunction()

qr_verify_cached_header("date/date.h"
  "8c295bc53964ec02fa99ef10816c190a4c34fdcbf1ce2dcc8e451a29932f9d2c")
qr_verify_cached_header("nlohmann/json.hpp"
  "aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63")
qr_verify_cached_header("nlohmann/json_fwd.hpp"
  "fb6aa70cbece087f37ab4685c182b287c53be54f785f981b9db9d30d2d028b37")
qr_verify_cached_header("httplib.h"
  "dfbaccb76432ed6d56ddd9983fd9d262b61ba6ba0958f6b00db35c802607bd35")

set(_qr_gen_dir "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${_qr_gen_dir}/databento" "${_qr_gen_dir}/qr_databento")
function(qr_configure_databento_headers)
  set(PROJECT_VERSION "0.64.0")
  set(PROJECT_VERSION_MAJOR 0)
  set(PROJECT_VERSION_MINOR 64)
  set(PROJECT_VERSION_PATCH 0)
  configure_file("${QR_DATABENTO_VENDOR_DIR}/cmake/version.hpp.in"
                 "${_qr_gen_dir}/databento/version.hpp" @ONLY)
  configure_file("${QR_DATABENTO_VENDOR_DIR}/cmake/system.hpp.in"
                 "${_qr_gen_dir}/databento/system.hpp" @ONLY)
endfunction()
qr_configure_databento_headers()

set(_qr_adapter_authority_inputs
  CMakeLists.txt
  include/qr_databento/adapter.hpp
  src/adapter.cpp)
set(_qr_adapter_manifest "")
foreach(_qr_rel IN LISTS _qr_adapter_authority_inputs)
  file(SHA256 "${CMAKE_CURRENT_SOURCE_DIR}/${_qr_rel}" _qr_file_sha)
  string(APPEND _qr_adapter_manifest "${_qr_rel}\t${_qr_file_sha}\n")
endforeach()
string(SHA256 QR_DATABENTO_ADAPTER_SOURCE_SHA256 "${_qr_adapter_manifest}")
file(SHA256 "/workspace/design/ENTRY_V2_DATABENTO_CLOCK_LAW.md"
     QR_DATABENTO_CLOCK_LAW_SHA256)
set(QR_DATABENTO_VENDOR_TREE_SHA256 "${_qr_vendor_tree_sha}")
set(QR_DATABENTO_UPSTREAM_COMMIT
    "12eca77e70137ea848e4af3f4173ee0569cbf1aa")
configure_file(cmake/build_authority.hpp.in
               "${_qr_gen_dir}/qr_databento/build_authority.hpp" @ONLY)
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/qr_databento.authority.tsv"
  "schema\tQRDATABENTOAUTH1\n"
  "databento_version\t0.64.0\n"
  "declared_upstream_commit\t${QR_DATABENTO_UPSTREAM_COMMIT}\n"
  "vendor_tree_sha256\t${QR_DATABENTO_VENDOR_TREE_SHA256}\n"
  "vendor_tree_law\tSHA256(sorted FILE_SHA256<SP><SP>RELPATH<LF>)\n"
  "vendor_tree_files\t254\n"
  "adapter_source_sha256\t${QR_DATABENTO_ADAPTER_SOURCE_SHA256}\n"
  "clock_law_sha256\t${QR_DATABENTO_CLOCK_LAW_SHA256}\n"
  "portability_gap\tdate/json/httplib headers are hash-gated build-cache inputs without an immutable vendor registry\n")

set(_qr_official_sources
  src/datetime.cpp
  src/dbn.cpp
  src/dbn_decoder.cpp
  src/dbn_store.cpp
  src/detail/buffer.cpp
  src/detail/json_helpers.cpp
  src/detail/zstd_stream.cpp
  src/enums.cpp
  src/exceptions.cpp
  src/file_stream.cpp
  src/flag_set.cpp
  src/log.cpp
  src/metadata.cpp
  src/pretty.cpp
  src/publishers.cpp
  src/record.cpp
  src/symbol_map.cpp
  src/v1.cpp
  src/v2.cpp)
list(TRANSFORM _qr_official_sources PREPEND "${QR_DATABENTO_VENDOR_DIR}/")

add_library(qr_databento_official STATIC ${_qr_official_sources})
set_target_properties(qr_databento_official PROPERTIES
  CXX_STANDARD 17 CXX_STANDARD_REQUIRED ON CXX_EXTENSIONS OFF)
target_include_directories(qr_databento_official SYSTEM PRIVATE
  "${QR_DATABENTO_VENDOR_DIR}/include"
  "${QR_DATABENTO_VENDOR_DIR}/src"
  "${_qr_gen_dir}"
  "${QR_DATABENTO_DEPS_INCLUDE_DIR}")
target_compile_definitions(qr_databento_official PRIVATE CPPHTTPLIB_OPENSSL_SUPPORT)
target_compile_options(qr_databento_official PRIVATE -ffp-contract=off)
target_link_libraries(qr_databento_official PRIVATE qr_zstd OpenSSL::SSL
  OpenSSL::Crypto Threads::Threads)

add_library(qr_databento STATIC src/adapter.cpp)
target_include_directories(qr_databento
  PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/include"
  PRIVATE "${QR_DATABENTO_VENDOR_DIR}/include" "${_qr_gen_dir}")
target_include_directories(qr_databento SYSTEM PRIVATE
  "${QR_DATABENTO_DEPS_INCLUDE_DIR}")
target_link_libraries(qr_databento PUBLIC qr_core PRIVATE
  qr_databento_official qr_zstd OpenSSL::SSL OpenSSL::Crypto Threads::Threads)
qr_apply_boundary_flags(qr_databento)

add_executable(qr_databento_tests tests/test_adapter.cpp)
target_link_libraries(qr_databento_tests PRIVATE qr_databento qr_dbn qr_zstd
  GTest::gtest GTest::gtest_main)
target_compile_definitions(qr_databento_tests PRIVATE
  QR_TEST_SCRATCH_DIR="${QR_TEST_SCRATCH_DIR}"
  QR_DATABENTO_SI_SNAPSHOT_FILE="/workspace/artifacts/reference/futures_mbp1/[Silver] GLBX-20260531-RPHWMFRBFW/glbx-mdp3-20210531.mbp-1.dbn.zst")
qr_apply_boundary_flags(qr_databento_tests)
add_test(NAME qr_databento_tests COMMAND qr_databento_tests)
