// qr_ivx_census — THE TRADED-IV SKEW / TERM CENSUS RUN.
//
// SPEC: the IV-COMPLEX brief items B1, B2 and D1-D9, pinned into formulas by
// qr_ivx/iv_cross.hpp. It is census-style in the established sense: read-only,
// no wall-clock value in the output, `%.17g` for every real, so two runs of the
// same arguments are byte-identical.
//
// usage:
//   qr_ivx_census --prints DIR --out TSV --ordinals LIST
//                 [--rutw-prints DIR] [--tapes DIR] [--quotes DIR] [--plane N]
//
//   --prints        the IWM option-print corpus (APPENDIX B3)
//   --rutw-prints   the RUTW option-print corpus (APPENDIX B5) — enables D6
//   --tapes         the emitted DecisionTape root; enables the independent
//                   moneyness cross-check
//   --quotes        the option-quote corpus; enables the W2.1 surface and with
//                   it D1 (richness), D7 (vol-of-vol), D8 (FD ratio), D9 (A3)
//   --plane         the DTE plane the surface channels are read from (0 or 1)
//
// EVERY OPTIONAL INPUT IS A TYPED ABSENCE WHEN OMITTED, never a substitute: no
// grid means no cross-check counters, no quotes means the surface-coupled
// channels are absent rows, and nothing is back-filled from a proxy.
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_ivx/iv_cross.hpp"
#include "qr_ivx/tsv.hpp"
#include "qr_registry/registry.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/rutw_prints.hpp"
#include "qr_w20/mechanics.hpp"
#include "qr_w21/surface.hpp"

namespace {

int usage() {
  std::fprintf(stderr,
               "usage: qr_ivx_census --prints DIR --out TSV --ordinals LIST\n"
               "                     [--rutw-prints DIR] [--tapes DIR] [--quotes DIR]\n"
               "                     [--plane N]\n");
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

std::filesystem::path tape_side_dir(const std::string& tapes, std::int64_t ordinal) {
  char padded[16];
  std::snprintf(padded, sizeof(padded), "s%04lld", static_cast<long long>(ordinal));
  return std::filesystem::path(tapes) / padded / "L";
}

/// Streams one print tape through one accumulator. Templated over the READER,
/// not over the row: B5 says "same laws" and the two readers already emit the
/// same `OptionPrintRow`, so one loop serves both tapes (D6).
template <class Reader>
bool run_tape(Reader reader, qr::ivx::TradedIvSession& session) {
  typename Reader::Group group;
  for (;;) {
    const auto more = reader.next_group(group);
    if (!more.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", more.error().refusal().message().c_str());
      return false;
    }
    if (!more.value()) break;
    for (const qr::sources::OptionPrintRow& row : group.rows) {
      session.observe(row);
    }
  }
  return true;
}

}  // namespace

int main(int argc, char** argv) {
  std::string prints;
  std::string rutw_prints;
  std::string tapes;
  std::string quotes;
  std::string out_path;
  std::string ordinals_text;
  std::int64_t plane = 0;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    if (index + 1 >= argc) return usage();
    const std::string value = argv[++index];
    if (flag == "--prints") {
      prints = value;
    } else if (flag == "--rutw-prints") {
      rutw_prints = value;
    } else if (flag == "--tapes") {
      tapes = value;
    } else if (flag == "--quotes") {
      quotes = value;
    } else if (flag == "--out") {
      out_path = value;
    } else if (flag == "--ordinals") {
      ordinals_text = value;
    } else if (flag == "--plane") {
      plane = std::strtoll(value.c_str(), nullptr, 10);
    } else {
      return usage();
    }
  }
  if (prints.empty() || out_path.empty() || ordinals_text.empty()) return usage();
  if (plane < 0 || plane >= static_cast<std::int64_t>(qr::ivx::SurfaceSeries::kPlanes)) {
    return usage();
  }

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }

  qr::ivx::Report report;
  report.text("run", "spec", "charter", "IV-COMPLEX brief B1,B2,D1-D9");
  report.text("run", "spec", "iv_source", "VENDOR_implied_vol_34_NO_INVERSION");
  report.metric("run", "spec", "window_seconds", qr::ivx::kWindowSeconds);
  report.metric("run", "spec", "bands", static_cast<std::int64_t>(qr::ivx::kBands));
  report.metric("run", "spec", "surface_plane", plane);
  for (std::size_t band = 0; band < qr::ivx::kBands; ++band) {
    report.text("run", "band", "b" + std::to_string(band), qr::ivx::band_label(band));
  }

  for (const std::int64_t ordinal : parse_ordinals(ordinals_text)) {
    const auto scope = qr::DayScope::admit(registry.value(), ordinal);
    if (!scope.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
      return 1;
    }
    const auto clock = qr::SessionClock::from_session(scope.value().session());
    if (!clock.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", clock.error().message().c_str());
      return 1;
    }
    const std::int64_t open_ms_b = clock.value().open_b().ns() / 1'000'000;
    // The session's own civil day as a frame-B epoch-day ordinal: the print
    // tape's `expiration` is days-since-epoch, so DTE is exact integer
    // arithmetic against this and never a date parse.
    const std::int64_t session_epoch_day = open_ms_b / 86'400'000;

    // The emitted 1s grid, for the independent moneyness cross-check only.
    std::vector<std::int64_t> grid;
    if (!tapes.empty()) {
      const auto opened = qr::w20::SpotGrid::open(tape_side_dir(tapes, ordinal), open_ms_b,
                                                  clock.value().expected_bar_count());
      if (!opened.has_value()) {
        std::fprintf(stderr, "REFUSED s%lld grid: %s\n", static_cast<long long>(ordinal),
                     opened.error().message().c_str());
        return 1;
      }
      grid.reserve(static_cast<std::size_t>(opened.value().endpoints()));
      for (std::int64_t index = 0; index < opened.value().endpoints(); ++index) {
        grid.push_back(opened.value().mid_u6_endpoint(index));
      }
    }

    // The W2.1 surface, for D1/D7/D8/D9. Q12: below ordinal 209 the option
    // quote modality is ABSENT, and that is a typed state, not a failure.
    qr::ivx::SurfaceSeries series;
    bool have_surface = false;
    if (!quotes.empty() && !qr::w21::SurfaceBuilder::session_is_modality_absent(ordinal)) {
      qr::w21::SurfaceOptions options;
      options.prints_root = std::filesystem::path(prints);
      options.retain_seconds = true;
      const auto built = qr::w21::SurfaceBuilder::build(
          scope.value(), std::filesystem::path(quotes), tape_side_dir(tapes, ordinal), options);
      if (!built.has_value()) {
        std::fprintf(stderr, "REFUSED s%lld surface: %s\n", static_cast<long long>(ordinal),
                     built.error().message().c_str());
        return 1;
      }
      const qr::w21::SurfaceBuilder& surface = built.value();
      series.seconds = surface.seconds();
      series.spot_u6.reserve(static_cast<std::size_t>(series.seconds));
      const std::size_t cells =
          static_cast<std::size_t>(series.seconds) * qr::ivx::SurfaceSeries::kPlanes;
      series.pv_mid.assign(cells, std::numeric_limits<double>::quiet_NaN());
      series.pv_bid.assign(cells, std::numeric_limits<double>::quiet_NaN());
      series.pv_ask.assign(cells, std::numeric_limits<double>::quiet_NaN());
      for (std::int64_t second = 0; second < series.seconds; ++second) {
        const auto at = static_cast<std::size_t>(second);
        series.spot_u6.push_back(at < surface.surface().size() ? surface.surface()[at].spot_u6 : 0);
        for (std::size_t which = 0; which < qr::ivx::SurfaceSeries::kPlanes; ++which) {
          const std::size_t index = at * qr::w21::kDtePlanes + which;
          if (index >= surface.straddle_channels().size()) continue;
          const qr::w21::StraddleChannels& channels = surface.straddle_channels()[index];
          const std::size_t slot = at * qr::ivx::SurfaceSeries::kPlanes + which;
          if (channels.proxy_vol_mid.v == qr::Validity::VALID) {
            series.pv_mid[slot] = channels.proxy_vol_mid.value;
          }
          if (channels.proxy_vol_bid.v == qr::Validity::VALID) {
            series.pv_bid[slot] = channels.proxy_vol_bid.value;
          }
          if (channels.proxy_vol_ask.v == qr::Validity::VALID) {
            series.pv_ask[slot] = channels.proxy_vol_ask.value;
          }
        }
      }
      have_surface = true;
    }

    qr::ivx::TradedIvOptions options;
    if (!grid.empty()) options.grid_mid_u6 = &grid;
    if (have_surface) options.surface = &series;

    qr::ivx::TradedIvSession iwm(ordinal, scope.value().day(), "IWM", open_ms_b,
                                 session_epoch_day, options);
    auto iwm_reader =
        qr::sources::OptionPrintReader::open(scope.value(), std::filesystem::path(prints));
    if (!iwm_reader.has_value()) {
      std::fprintf(stderr, "REFUSED s%lld prints: %s\n", static_cast<long long>(ordinal),
                   iwm_reader.error().refusal().message().c_str());
      return 1;
    }
    if (!run_tape(std::move(iwm_reader).value(), iwm)) return 1;
    const qr::ivx::TradedIvTables iwm_tables = iwm.finish();
    emit(report, iwm_tables);
    std::fprintf(stderr, "done s%lld IWM admitted=%lld cells=%lld\n",
                 static_cast<long long>(ordinal),
                 static_cast<long long>(iwm_tables.census.admitted),
                 static_cast<long long>(iwm_tables.cells.size()));

    if (have_surface) {
      const qr::ivx::SurfaceDynamics dynamics =
          qr::ivx::surface_dynamics(series, static_cast<std::size_t>(plane));
      emit(report, "s" + std::to_string(ordinal), dynamics);
    }

    if (!rutw_prints.empty()) {
      // D6: the second tape. The RUTW reader refuses a non-RUTW root by name,
      // so pointing this at the IWM corpus is a loud refusal, never a silent
      // relabelling of one instrument's tape as another's.
      qr::ivx::TradedIvOptions rutw_options;  // no IWM grid: the spot scale differs
      if (have_surface) {
        // The surface is IWM's; richness against it is meaningless for RUTW and
        // is therefore NOT offered rather than offered wrong.
      }
      qr::ivx::TradedIvSession rutw(ordinal, scope.value().day(), "RUTW", open_ms_b,
                                    session_epoch_day, rutw_options);
      auto rutw_reader = qr::sources::RutwPrintReader::open(scope.value(),
                                                            std::filesystem::path(rutw_prints));
      if (!rutw_reader.has_value()) {
        std::fprintf(stderr, "REFUSED s%lld rutw: %s\n", static_cast<long long>(ordinal),
                     rutw_reader.error().refusal().message().c_str());
        return 1;
      }
      if (!run_tape(std::move(rutw_reader).value(), rutw)) return 1;
      const qr::ivx::TradedIvTables rutw_tables = rutw.finish();
      emit(report, rutw_tables);
      const qr::ivx::CrossTapeSpread spread =
          qr::ivx::cross_tape_spread(iwm_tables, rutw_tables);
      emit(report, "s" + std::to_string(ordinal) + "/IWM_minus_RUTW", spread);
      std::fprintf(stderr, "done s%lld RUTW admitted=%lld cells=%lld\n",
                   static_cast<long long>(ordinal),
                   static_cast<long long>(rutw_tables.census.admitted),
                   static_cast<long long>(rutw_tables.cells.size()));
    }
  }

  const auto written = report.write(out_path);
  if (!written.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", written.error().message().c_str());
    return 1;
  }
  return 0;
}
