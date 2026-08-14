#!/usr/bin/env bash
# Build dbn_dump — the DBN differential-oracle dumper built on the OFFICIAL
# databento-cpp library vendored (read-only) at /workspace/vendor/databento-cpp.
#
# Reproduces the build from scratch. Network is used to FetchContent the official
# library's header-only dependencies (nlohmann_json, cpp-httplib, HowardHinnant date);
# apt is used only if libzstd-dev / libssl-dev / cmake / g++ are missing.
#
# Build tree lives under /workspace/artifacts/cache/ (D-018). NEVER commit it.
#
# Usage:
#   /workspace/engine/cpp/dbn_diff/build.sh              # full official library (default)
#   /workspace/engine/cpp/dbn_diff/build.sh --decode-only # trimmed DBN+zstd TUs only
#   /workspace/engine/cpp/dbn_diff/build.sh --clean       # wipe the build tree first
#
# Result: /workspace/artifacts/cache/cpp/dbn_diff/build/bin/dbn_dump

set -euo pipefail

SRC_DIR=/workspace/engine/cpp/dbn_diff
VENDOR_DIR=/workspace/vendor/databento-cpp
# Override only to build a second variant side by side; must stay under artifacts/cache.
BUILD_DIR=${DBN_DIFF_BUILD_DIR:-/workspace/artifacts/cache/cpp/dbn_diff/build}

DECODE_ONLY=OFF
CLEAN=0
for arg in "$@"; do
  case "$arg" in
    --decode-only) DECODE_ONLY=ON ;;
    --clean) CLEAN=1 ;;
    *) echo "build.sh: unknown argument '$arg'" >&2; exit 2 ;;
  esac
done

if [ ! -d "$VENDOR_DIR" ]; then
  echo "build.sh: missing vendored library at $VENDOR_DIR" >&2
  exit 1
fi

# ---------------------------------------------------------------- system deps
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 && SUDO="sudo"
fi

need_apt=()
command -v cmake >/dev/null 2>&1 || need_apt+=(cmake)
command -v g++ >/dev/null 2>&1 || need_apt+=(g++)
[ -f /usr/include/zstd.h ] || need_apt+=(libzstd-dev)
# OpenSSL is needed by BOTH routes: databento/exceptions.hpp force-defines
# CPPHTTPLIB_OPENSSL_SUPPORT before including <httplib.h>, and record.hpp includes
# exceptions.hpp, so even a pure DBN decode TU pulls in the SSL-enabled httplib.
[ -f /usr/include/openssl/ssl.h ] || need_apt+=(libssl-dev)
if [ ${#need_apt[@]} -gt 0 ]; then
  echo "build.sh: installing ${need_apt[*]}" >&2
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq "${need_apt[@]}"
fi

# ------------------------------------------------ decode-only header-only deps
CMAKE_EXTRA=()
if [ "$DECODE_ONLY" = "ON" ]; then
  # dbn_decoder.cpp / symbol_map.cpp need date/date.h; exceptions.cpp needs
  # nlohmann/json.hpp; and databento/exceptions.hpp includes <httplib.h>
  # unconditionally, so even the pure decode path needs that header. All three are
  # header-only — fetch them next to the build tree rather than pulling in the full
  # dependency graph. Note this route still links OpenSSL (see above); what it saves
  # is the historical/live/tcp/http client translation units.
  DEPS_DIR=/workspace/artifacts/cache/cpp/dbn_diff/deps
  mkdir -p "$DEPS_DIR/include/date" "$DEPS_DIR/include/nlohmann"
  if [ ! -f "$DEPS_DIR/include/date/date.h" ]; then
    echo "build.sh: fetching date.h" >&2
    curl -sSfL -o "$DEPS_DIR/include/date/date.h" \
      https://raw.githubusercontent.com/HowardHinnant/date/v3.0.5/include/date/date.h
  fi
  if [ ! -f "$DEPS_DIR/include/nlohmann/json.hpp" ]; then
    echo "build.sh: fetching nlohmann/json.hpp" >&2
    curl -sSfL -o "$DEPS_DIR/include/nlohmann/json.hpp" \
      https://github.com/nlohmann/json/releases/download/v3.12.0/json.hpp
  fi
  if [ ! -f "$DEPS_DIR/include/nlohmann/json_fwd.hpp" ]; then
    curl -sSfL -o "$DEPS_DIR/include/nlohmann/json_fwd.hpp" \
      https://raw.githubusercontent.com/nlohmann/json/v3.12.0/single_include/nlohmann/json_fwd.hpp
  fi
  if [ ! -f "$DEPS_DIR/include/httplib.h" ]; then
    echo "build.sh: fetching httplib.h" >&2
    curl -sSfL -o "$DEPS_DIR/include/httplib.h" \
      https://raw.githubusercontent.com/yhirose/cpp-httplib/v0.51.0/httplib.h
  fi
  CMAKE_EXTRA+=(
    -DDBN_DIFF_DECODE_ONLY=ON
    "-DDBN_DIFF_DATE_INCLUDE_DIR=$DEPS_DIR/include"
    "-DDBN_DIFF_JSON_INCLUDE_DIR=$DEPS_DIR/include"
  )
fi

# ----------------------------------------------------------------- configure/build
if [ "$CLEAN" = "1" ]; then
  rm -rf "$BUILD_DIR"
fi
mkdir -p "$BUILD_DIR"

cmake -S "$SRC_DIR" -B "$BUILD_DIR" \
  -DCMAKE_BUILD_TYPE=Release \
  "-DDBN_DIFF_VENDOR_DIR=$VENDOR_DIR" \
  "${CMAKE_EXTRA[@]+"${CMAKE_EXTRA[@]}"}"

cmake --build "$BUILD_DIR" -j"$(nproc)" --target dbn_dump

echo "build.sh: built $BUILD_DIR/bin/dbn_dump" >&2
"$BUILD_DIR/bin/dbn_dump" 2>&1 | head -1 || true
