// qr_ivx_qskew — THE MODEL-FREE QUOTE-SKEW PROXY RUN (brief item B3).
//
// SPEC: qr_ivx/quote_skew.hpp. One pass over the B4 option-quote stream; no
// model inversion of any kind; two runs byte-identical.
//
// usage: qr_ivx_qskew --root DIR --tapes DIR --out TSV --ordinals LIST
//                     [--plane N] [--from-second A] [--to-second B]
//
// `--from-second`/`--to-second` bound the RETAINED per-second series only; the
// 30-minute aggregates always cover the whole session. Omitting them emits the
// aggregates alone, which is what a multi-session census wants.
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <utility>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_ivx/quote_skew.hpp"
#include "qr_ivx/tsv.hpp"
#include "qr_registry/registry.hpp"
#include "qr_sources/option_quotes.hpp"
#include "qr_w20/mechanics.hpp"
#include "qr_w21/surface.hpp"

namespace {

int usage() {
  std::fprintf(stderr,
               "usage: qr_ivx_qskew --root DIR --tapes DIR --out TSV --ordinals LIST\n"
               "                    [--plane N] [--from-second A] [--to-second B]\n");
  return 2;
}

std::vector<std::int64_t> parse_ordinals(const std::string& text) {
  std::vector<std::int64_t> out;
  std::size_t start = 0;
  while (start <= text.size()) {
    const std::size_t comma = text.find(',', start);
    const std::string token =
        text.substr(start, comma == std::string::npos ? std::string::npos : comma - start);
    if (!token.empty()) out.push_back(std::strtoll(token.c_str(), nullptr, 10));
    if (comma == std::string::npos) break;
    start = comma + 1;
  }
  return out;
}

}  // namespace

int main(int argc, char** argv) {
  std::string root;
  std::string tapes;
  std::string out_path;
  std::string ordinals_text;
  std::int64_t plane = 0;
  std::int64_t from_second = -1;
  std::int64_t to_second = -1;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    if (index + 1 >= argc) return usage();
    const std::string value = argv[++index];
    if (flag == "--root") {
      root = value;
    } else if (flag == "--tapes") {
      tapes = value;
    } else if (flag == "--out") {
      out_path = value;
    } else if (flag == "--ordinals") {
      ordinals_text = value;
    } else if (flag == "--plane") {
      plane = std::strtoll(value.c_str(), nullptr, 10);
    } else if (flag == "--from-second") {
      from_second = std::strtoll(value.c_str(), nullptr, 10);
    } else if (flag == "--to-second") {
      to_second = std::strtoll(value.c_str(), nullptr, 10);
    } else {
      return usage();
    }
  }
  if (root.empty() || tapes.empty() || out_path.empty() || ordinals_text.empty()) return usage();
  if (plane < 0 || plane > 1) return usage();
  const bool retain = from_second >= 0 && to_second >= from_second;

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }

  qr::ivx::Report report;
  report.text("run", "spec", "charter", "IV-COMPLEX brief B3");
  report.text("run", "spec", "method", "QUOTED_MIDPOINT_RATIOS_NO_INVERSION");
  report.metric("run", "spec", "plane_dte", plane);
  report.metric("run", "spec", "retain_seconds", retain ? 1 : 0);

  for (const std::int64_t ordinal : parse_ordinals(ordinals_text)) {
    const auto scope = qr::DayScope::admit(registry.value(), ordinal);
    if (!scope.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
      return 1;
    }
    const std::string key = "s" + std::to_string(ordinal) + "/p" + std::to_string(plane);
    report.text("session", key, "day", scope.value().day());
    // Q12 is a TYPED STATE, never an error: below ordinal 209 there is no
    // option-quote payload and the run says so instead of inventing a series.
    if (qr::w21::SurfaceBuilder::session_is_modality_absent(ordinal)) {
      report.text("session", key, "modality",
                  qr::validity_name(qr::Validity::MODALITY_ABSENT));
      continue;
    }
    const auto clock = qr::SessionClock::from_session(scope.value().session());
    if (!clock.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", clock.error().message().c_str());
      return 1;
    }
    const std::int64_t open_ms_b = clock.value().open_b().ns() / 1'000'000;
    const std::int64_t session_epoch_day = open_ms_b / 86'400'000;

    char padded[32];
    std::snprintf(padded, sizeof(padded), "s%04lld", static_cast<long long>(ordinal));
    const std::filesystem::path side = std::filesystem::path(tapes) / padded / "L";
    const auto grid_opened =
        qr::w20::SpotGrid::open(side, open_ms_b, clock.value().expected_bar_count());
    if (!grid_opened.has_value()) {
      std::fprintf(stderr, "REFUSED s%lld grid: %s\n", static_cast<long long>(ordinal),
                   grid_opened.error().message().c_str());
      return 1;
    }
    std::vector<std::int64_t> grid;
    grid.reserve(static_cast<std::size_t>(grid_opened.value().endpoints()));
    for (std::int64_t index = 0; index < grid_opened.value().endpoints(); ++index) {
      grid.push_back(grid_opened.value().mid_u6_endpoint(index));
    }

    qr::ivx::QuoteSkewBuilder builder(open_ms_b, session_epoch_day, plane, &grid,
                                      retain ? from_second : -1, retain ? to_second : -1);
    auto opened = qr::sources::OptionQuoteReader::open(scope.value(), std::filesystem::path(root));
    if (!opened.has_value()) {
      std::fprintf(stderr, "REFUSED s%lld quotes: %s\n", static_cast<long long>(ordinal),
                   opened.error().refusal().message().c_str());
      return 1;
    }
    qr::sources::OptionQuoteReader reader = std::move(opened).value();
    qr::sources::OptionQuoteReader::Group group;
    for (;;) {
      const auto more = reader.next_group(group);
      if (!more.has_value()) {
        std::fprintf(stderr, "REFUSED: %s\n", more.error().refusal().message().c_str());
        return 1;
      }
      if (!more.value()) break;
      for (const qr::sources::OptionQuoteRow& row : group.rows) {
        builder.observe(row);
      }
    }
    builder.finish();
    report.metric("session", key, "quote_rth_rows", reader.rth_rows());
    emit(report, key, builder, retain);
    std::fprintf(stderr, "done s%lld plane=%lld on_plane=%lld\n", static_cast<long long>(ordinal),
                 static_cast<long long>(plane), static_cast<long long>(builder.rows_on_plane()));
  }

  const auto written = report.write(out_path);
  if (!written.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", written.error().message().c_str());
    return 1;
  }
  return 0;
}
