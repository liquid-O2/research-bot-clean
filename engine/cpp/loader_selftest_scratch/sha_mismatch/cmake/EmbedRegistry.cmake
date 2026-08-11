# Embeds the frozen registry TSV into the binary, the way the Rust build does
# with include_str! (engine/crates/corpus/src/registry.rs:29). Generated at
# configure time; the runtime sha256 gate in qr_registry is what proves the
# embedded bytes are still the pinned bytes, so any mangling here is caught by
# a test rather than assumed away.

set(QR_REGISTRY_TSV "/workspace/engine/crates/corpus/registry/accepted_compact_sessions.tsv")
if(NOT EXISTS "${QR_REGISTRY_TSV}")
  message(FATAL_ERROR "frozen registry TSV is missing: ${QR_REGISTRY_TSV}")
endif()

file(SIZE "${QR_REGISTRY_TSV}" QR_REGISTRY_TSV_SIZE)
file(READ "${QR_REGISTRY_TSV}" QR_REGISTRY_TSV_CONTENT)
set(QR_REGISTRY_BLOB_CPP "${CMAKE_CURRENT_BINARY_DIR}/generated/qr_registry_blob.cpp")

file(WRITE "${QR_REGISTRY_BLOB_CPP}"
"// GENERATED at CMake configure time from
// ${QR_REGISTRY_TSV}
// Do not edit. Regenerate by re-running cmake.
#include <cstddef>

namespace qr {
namespace registry_blob {

extern const char kRegistryTsv[];
extern const std::size_t kRegistryTsvSize;

const char kRegistryTsv[] = R\"QRREGISTRY(${QR_REGISTRY_TSV_CONTENT})QRREGISTRY\";
const std::size_t kRegistryTsvSize = sizeof(kRegistryTsv) - 1;

static_assert(sizeof(kRegistryTsv) - 1 == ${QR_REGISTRY_TSV_SIZE},
              \"embedded registry blob size drifted from the pinned TSV size\");

}  // namespace registry_blob
}  // namespace qr
")

# Re-run configure (and so regenerate the blob) whenever the TSV changes.
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${QR_REGISTRY_TSV}")

# The blob is data, not logic: -Woverlength-strings (pulled in by -Wpedantic)
# is the only diagnostic exempted, and only on this one generated file.
set_source_files_properties("${QR_REGISTRY_BLOB_CPP}" PROPERTIES
  COMPILE_OPTIONS "-Wno-overlength-strings")
