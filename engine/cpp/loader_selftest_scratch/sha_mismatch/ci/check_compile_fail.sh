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

# ---------------------------------------------------------------------------
# WP4: the qr_sources StreamSpec compile-time laws (APPENDIX C3, "compile-time
# asserts"). A spec that projects a FORBIDDEN column, projects out of order,
# runs past its own name list, repeats a name, or does not project its own
# clock leaf must not COMPILE. The runtime mirror of these cases lives in
# qr_sources/tests/test_stream_spec.cpp; this gate proves the stronger
# statement.
# ---------------------------------------------------------------------------

SPEC_INCLUDES=(-I "${CPP_ROOT}/qr_core/include" -I "${CPP_ROOT}/qr_registry/include"
               -I "${CPP_ROOT}/qr_parquet/include" -I "${CPP_ROOT}/qr_sources/include")

declare -a SPEC_NAMES=(
  "projection_contains_a_forbidden_column"
  "projection_is_not_ascending"
  "projection_runs_past_the_names"
  "two_columns_share_a_name"
  "clock_leaf_is_not_projected"
)
declare -a SPEC_BODIES=(
  '.projection = {0, 2}, .roles = {R::TimestampMs, R::Int}, .forbidden = {qr::sources::ForbiddenColumn{2, qr::sources::ForbidReason::NeverRead}}, .timestamp_leaf = 0,'
  '.projection = {2, 0}, .roles = {R::Int, R::TimestampMs}, .forbidden = {}, .timestamp_leaf = 0,'
  '.projection = {0, 9}, .roles = {R::TimestampMs, R::Int}, .forbidden = {}, .timestamp_leaf = 0,'
  '.projection = {0, 1}, .roles = {R::TimestampMs, R::Int}, .forbidden = {}, .timestamp_leaf = 0,'
  '.projection = {1, 2}, .roles = {R::Int, R::Int}, .forbidden = {}, .timestamp_leaf = 0,'
)
declare -a SPEC_NAMELISTS=(
  '"ts", "a", "b", "c"'
  '"ts", "a", "b", "c"'
  '"ts", "a", "b", "c"'
  '"ts", "a", "a", "c"'
  '"ts", "a", "b", "c"'
)
declare -a SPEC_FORB=(1 0 0 0 0)

for index in "${!SPEC_NAMES[@]}"; do
  name="${SPEC_NAMES[${index}]}"
  source="${SCRATCH}/spec_${name}.cpp"
  log="${SCRATCH}/spec_${name}.log"
  cat > "${source}" <<EOF
#include "qr_sources/stream_spec.hpp"
using R = qr::sources::ColumnRole;
inline constexpr qr::sources::StreamSpec<4, 2, ${SPEC_FORB[${index}]}> kBad{
    .stream = "bad",
    .names = {${SPEC_NAMELISTS[${index}]}},
    ${SPEC_BODIES[${index}]}
};
static_assert(spec_is_wellformed(kBad));
int main() { return 0; }
EOF
  if "${CXX}" -std=c++20 -fsyntax-only "${SPEC_INCLUDES[@]}" "${source}" > "${log}" 2>&1; then
    echo "FAIL: the '${name}' StreamSpec COMPILED — a compile-time spec law has a hole" >&2
    status=1
  fi
done

# Positive control: the same shape, LAWFUL, must compile — otherwise the five
# refusals above would prove nothing.
control="${SCRATCH}/spec_lawful_control.cpp"
cat > "${control}" <<EOF
#include "qr_sources/stream_spec.hpp"
using R = qr::sources::ColumnRole;
inline constexpr qr::sources::StreamSpec<4, 2, 1> kGood{
    .stream = "good",
    .names = {"ts", "a", "b", "c"},
    .projection = {0, 1},
    .roles = {R::TimestampMs, R::Int},
    .forbidden = {qr::sources::ForbiddenColumn{2, qr::sources::ForbidReason::NeverRead}},
    .timestamp_leaf = 0,
};
static_assert(spec_is_wellformed(kGood));
static_assert(spec_is_wellformed(qr::sources::kStockQuoteSpec));
static_assert(spec_is_wellformed(qr::sources::kStockTradeSpec));
static_assert(spec_is_wellformed(qr::sources::kOptionPrintSpec));
static_assert(spec_is_wellformed(qr::sources::kOptionQuoteSpec));
int main() { return 0; }
EOF
if ! "${CXX}" -std=c++20 -fsyntax-only "${SPEC_INCLUDES[@]}" "${control}" \
     > "${SCRATCH}/spec_lawful_control.log" 2>&1; then
  echo "FAIL: the lawful StreamSpec control does NOT compile; the five refusals above prove nothing" >&2
  cat "${SCRATCH}/spec_lawful_control.log" >&2
  status=1
fi

if [[ ${status} -eq 0 ]]; then
  echo "OK: all ${#NAMES[@]} frame-wall snippets and ${#SPEC_NAMES[@]} StreamSpec snippets are rejected by the compiler"
fi
exit ${status}
