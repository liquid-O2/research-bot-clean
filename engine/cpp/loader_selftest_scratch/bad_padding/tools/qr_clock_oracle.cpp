// tools/qr_clock_oracle.cpp — the WP2 payload-free cross-check print.
//
// Prints one line per registered session:
//
//   day \t session_start_ns \t session_end_ns \t open_b_ns \t offset_ns
//
// The frozen Rust port (corpus::SessionClock) prints exactly the same five
// fields for exactly the same 1,003 sessions; the two outputs must diff empty.
// Payload-free by construction: this opens no parquet, forms no path, and
// touches nothing but the embedded registry.
//
// Determinism: registry order is the frozen TSV's own order and nothing here
// sorts, hashes or maps. Two runs are byte-identical, which is the WP
// acceptance law.
#include <cstdio>
#include <string_view>

#include "qr_clock/session_clock.hpp"
#include "qr_registry/registry.hpp"

int main() {
  const auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", registry.error().message().c_str());
    return 1;
  }
  std::printf("day\tsession_start_ns\tsession_end_ns\topen_b_ns\toffset_ns\n");
  for (const qr::Session& row : registry.value().sessions()) {
    const auto clock = qr::SessionClock::from_session(row);
    if (!clock.has_value()) {
      std::fprintf(stderr, "REFUSED %s: %s\n", row.day.c_str(), clock.error().message().c_str());
      return 1;
    }
    const std::string_view day = clock.value().day();
    std::printf("%.*s\t%lld\t%lld\t%lld\t%lld\n", static_cast<int>(day.size()), day.data(),
                static_cast<long long>(clock.value().session_start_a().ns()),
                static_cast<long long>(clock.value().session_end_a().ns()),
                static_cast<long long>(clock.value().open_b().ns()),
                static_cast<long long>(clock.value().offset_ns()));
  }
  return 0;
}
