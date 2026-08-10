#!/usr/bin/env bash
# ci/check_compile_fail.sh — the compile-level half of the frame type wall.
#
# The runtime fixture in qr_core/tests/test_frames.cpp asserts the type traits;
# this gate proves the stronger statement the spec actually makes: the offending
# code DOES NOT COMPILE ("deleted implicit conversions + static_assert
# non-convertibility", FINAL_PLAN section 6). Every snippet below must fail to
# compile; a snippet that compiles is a hole in the wall.
set -uo pipefail

CPP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRATCH="${QR_COMPILE_FAIL_SCRATCH:-/workspace/artifacts/cache/cpp/compile_fail}"
CXX="${CXX:-g++}"
mkdir -p "${SCRATCH}"

declare -a NAMES=(
  "int64_implicitly_becomes_frame_b"
  "int_narrows_into_frame_b"
  "double_becomes_frame_b"
  "frame_b_decays_to_int64"
  "frame_a_has_a_public_constructor"
  "frame_a_converts_to_frame_b"
  "int64_implicitly_becomes_civil_date"
)
declare -a BODIES=(
  'qr::FrameB b = std::int64_t{5}; (void)b;'
  'qr::FrameB b(5); (void)b;'
  'qr::FrameB b(5.0); (void)b;'
  'std::int64_t n = qr::FrameB{std::int64_t{5}}; (void)n;'
  'qr::FrameA a(std::int64_t{5}); (void)a;'
  'qr::FrameB b = qr::FrameA::from_published_utc_epoch_ns(5); (void)b;'
  'qr::CivilDate d = std::int64_t{5}; (void)d;'
)

status=0
for index in "${!NAMES[@]}"; do
  name="${NAMES[${index}]}"
  body="${BODIES[${index}]}"
  source="${SCRATCH}/${name}.cpp"
  log="${SCRATCH}/${name}.log"
  cat > "${source}" <<EOF
#include <cstdint>
#include "qr_core/frames.hpp"
int main() {
  ${body}
  return 0;
}
EOF
  if "${CXX}" -std=c++20 -fsyntax-only -I "${CPP_ROOT}/qr_core/include" "${source}" > "${log}" 2>&1; then
    echo "FAIL: '${body}' COMPILED — the frame type wall has a hole (${name})" >&2
    status=1
  fi
done

if [[ ${status} -eq 0 ]]; then
  echo "OK: all ${#NAMES[@]} frame-wall snippets are rejected by the compiler"
fi
exit ${status}
