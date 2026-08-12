// qr_w21_dump — THE D-020 PACK DUMP for the W2.1 option-quote surface.
//
// qr_w21_census proves the block constructs and publishes distribution
// censuses. A CASE PACK needs the SERIES: what PROXY_VOL, the straddle width,
// the coverage and the refill imbalance were doing over the last hour before a
// decision second, plus the requote-latency events in that window.
//
// It is census-style: read-only, no wall-clock value in the output, %.17g for
// every double, so two runs of the same arguments are byte-identical. The only
// difference from the census run is `SurfaceOptions::retain_seconds`, which the
// module already supports for exactly this reason.
//
// Q12 stays a TYPED state, never an error: ordinals 125..208 carry no
// option-quote payload, and the dump writes `modality MODALITY_ABSENT` and
// stops rather than inventing a series.
//
// TWO CONTRACT-LEVEL MODES (design/D020_SCALE_PROTOCOL.md §ORCH-6.3), which
// the surface CANNOT answer at any resolution because a bucket holds no
// contract-level price (Q4):
//   --top-k N       DISCOVERY: the N most active contracts of the window, each
//                   with the exact `strike_u6` a named run must pass back;
//   --contract ID   the named contract's quote series (ms, bid, ask, sizes).
// Either mode reads the B4 stream directly and does NOT build the surface, so
// `--prints` and `--tapes` are not required and nothing but the option-quote
// corpus is opened. They compose: one run may do both, over one pass.
//
// usage: qr_w21_dump --root DIR --prints DIR --tapes DIR --ordinal N
//                    --from-second A --to-second B [--stride N] --out TSV
//        qr_w21_dump --root DIR --ordinal N --from-second A --to-second B
//                    [--contract <YYYY-MM-DD>:<strike_u6>:<C|P>] [--top-k N]
//                    --out TSV
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "qr_clock/session_clock.hpp"
#include "qr_registry/registry.hpp"
#include "qr_sources/option_quotes.hpp"
#include "qr_w21/contract_series.hpp"
#include "qr_w21/surface.hpp"

namespace {

int usage() {
  std::fprintf(stderr,
               "usage: qr_w21_dump --root DIR --prints DIR --tapes DIR --ordinal N\n"
               "                   --from-second A --to-second B [--stride N] --out TSV\n"
               "       qr_w21_dump --root DIR --ordinal N --from-second A --to-second B\n"
               "                   [--contract <YYYY-MM-DD>:<strike_u6>:<C|P>] [--top-k N]\n"
               "                   --out TSV\n");
  return 2;
}

void print_typed(std::FILE* out, const char* kind, std::int64_t second, const char* name,
                 qr::Typed<double> typed) {
  std::fprintf(out, "%s\t%" PRId64 "\t%s\t%.17g\t%s\n", kind, second, name, typed.value,
               qr::validity_name(typed.v));
}

/// `NA` for an absent projected cell, the exact integer otherwise. The readers'
/// own rule: absence is never a zero that could collide with a real value.
void put_i64(std::FILE* out, bool null, std::int64_t value) {
  if (null) {
    std::fputs("\tNA", out);
  } else {
    std::fprintf(out, "\t%" PRId64, value);
  }
}

/// THE CONTRACT-LEVEL PASS. One walk of the B4 stream feeds both the named
/// series and the discovery census, so a run that asks for both pays for one
/// read. Nothing is derived: every emitted number is a retained projected value
/// or the session second/millisecond of the row that carried it.
int dump_contracts(std::FILE* out, const qr::DayScope& scope, const std::string& root,
                   const std::string& contract_text, std::int64_t top_k,
                   std::int64_t from_second, std::int64_t to_second) {
  std::optional<qr::w21::ContractId> named;
  if (!contract_text.empty()) {
    const auto parsed = qr::w21::parse_contract_id(contract_text);
    if (!parsed.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", parsed.error().message().c_str());
      std::fclose(out);
      return 1;
    }
    named = parsed.value();
  }

  const auto clock = qr::SessionClock::from_session(scope.session());
  if (!clock.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", clock.error().message().c_str());
    std::fclose(out);
    return 1;
  }
  // THE SAME SECOND ARITHMETIC THE SURFACE USES — the session's own frame-B
  // open, floored to seconds. A second clock here would put the contract series
  // and the surface series on different grids.
  const std::int64_t open_ms_b = clock.value().open_b().ns() / 1'000'000;

  auto opened = qr::sources::OptionQuoteReader::open(scope, std::filesystem::path(root));
  if (!opened.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", opened.error().refusal().message().c_str());
    std::fclose(out);
    return 1;
  }
  qr::sources::OptionQuoteReader reader = std::move(opened).value();

  qr::w21::ActivityCensus census(from_second, to_second);
  qr::w21::ContractSeries series(named.value_or(qr::w21::ContractId{}), from_second, to_second);

  qr::sources::OptionQuoteReader::Group group;
  for (;;) {
    const auto more = reader.next_group(group);
    if (!more.has_value()) {
      std::fprintf(stderr, "REFUSED: %s\n", more.error().refusal().message().c_str());
      std::fclose(out);
      return 1;
    }
    if (!more.value()) {
      break;
    }
    const std::int64_t ms = group.ts_ms_b - open_ms_b;
    const std::int64_t second = ms / 1000;
    for (const qr::sources::OptionQuoteRow& row : group.rows) {
      if (top_k > 0) {
        census.observe(second, ms, row);
      }
      if (named.has_value()) {
        series.observe(second, ms, row);
      }
    }
  }

  std::fprintf(out, "session\tfrom_second\t%" PRId64 "\n", from_second);
  std::fprintf(out, "session\tto_second\t%" PRId64 "\n", to_second);
  std::fprintf(out, "session\tquote_rth_rows\t%" PRId64 "\n", reader.rth_rows());
  std::fprintf(out, "session\tquote_shards\t%" PRId64 "\n",
               static_cast<std::int64_t>(reader.shards().size()));

  if (top_k > 0) {
    std::fprintf(out, "# top_contract\trank\tcontract\texpiration_day\tstrike_u6\tright"
                      "\trows\tseconds_present\tfirst_ms\tlast_ms\n");
    std::fprintf(out, "window\tcontracts\t%" PRId64 "\n", census.contracts());
    std::fprintf(out, "window\trows\t%" PRId64 "\n", census.rows());
    const std::vector<qr::w21::ContractActivity> top =
        census.top(static_cast<std::size_t>(top_k));
    for (std::size_t rank = 0; rank < top.size(); ++rank) {
      const qr::w21::ContractActivity& one = top[rank];
      std::fprintf(out,
                   "top_contract\t%" PRId64 "\t%s\t%" PRId64 "\t%" PRId64 "\t%s\t%" PRId64
                   "\t%" PRId64 "\t%" PRId64 "\t%" PRId64 "\n",
                   static_cast<std::int64_t>(rank), qr::w21::format_contract_id(one.id).c_str(),
                   static_cast<std::int64_t>(one.id.expiration_day), one.id.strike_u6,
                   qr::sources::right_name(one.id.right), one.rows, one.seconds_present,
                   one.first_ms, one.last_ms);
    }
  }

  if (named.has_value()) {
    std::fprintf(out, "# contract_quote\tsecond\tms\tbid_u6\task_u6\tbid_size\task_size"
                      "\tmid_u6\n");
    std::fprintf(out, "contract\tid\t%s\n",
                 qr::w21::format_contract_id(named.value()).c_str());
    std::fprintf(out, "contract\texpiration_day\t%" PRId64 "\n",
                 static_cast<std::int64_t>(named.value().expiration_day));
    std::fprintf(out, "contract\tstrike_u6\t%" PRId64 "\n", named.value().strike_u6);
    std::fprintf(out, "contract\tright\t%s\n", qr::sources::right_name(named.value().right));
    std::fprintf(out, "contract\tsession_rows\t%" PRId64 "\n", series.session_rows());
    std::fprintf(out, "contract\twindow_rows\t%" PRId64 "\n",
                 static_cast<std::int64_t>(series.quotes().size()));
    for (const qr::w21::ContractQuote& quote : series.quotes()) {
      std::fprintf(out, "contract_quote\t%" PRId64 "\t%" PRId64, quote.second, quote.ms);
      put_i64(out, quote.is_null(qr::sources::kOptionQuoteSlotBid), quote.bid_u6);
      put_i64(out, quote.is_null(qr::sources::kOptionQuoteSlotAsk), quote.ask_u6);
      put_i64(out, quote.is_null(qr::sources::kOptionQuoteSlotBidSize), quote.bid_size);
      put_i64(out, quote.is_null(qr::sources::kOptionQuoteSlotAskSize), quote.ask_size);
      // The midpoint is computed BEFORE the call, not inside its argument
      // list: the order in which a call's arguments are evaluated is
      // unspecified, so `put_i64(out, !quote.mid_u6(mid), mid)` may read `mid`
      // before it is written.
      std::int64_t mid = 0;
      const bool two_sided = quote.mid_u6(mid);
      put_i64(out, !two_sided, mid);
      std::fputc('\n', out);
    }
  }

  std::fclose(out);
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  std::string root;
  std::string prints;
  std::string tapes;
  std::string out_path;
  std::int64_t ordinal = -1;
  std::int64_t from_second = -1;
  std::int64_t to_second = -1;
  std::int64_t stride = 1;
  std::string contract_text;
  std::int64_t top_k = 0;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    if (index + 1 >= argc) {
      return usage();
    }
    const std::string value = argv[++index];
    if (flag == "--root") {
      root = value;
    } else if (flag == "--prints") {
      prints = value;
    } else if (flag == "--tapes") {
      tapes = value;
    } else if (flag == "--out") {
      out_path = value;
    } else if (flag == "--ordinal") {
      ordinal = std::strtoll(value.c_str(), nullptr, 10);
    } else if (flag == "--from-second") {
      from_second = std::strtoll(value.c_str(), nullptr, 10);
    } else if (flag == "--to-second") {
      to_second = std::strtoll(value.c_str(), nullptr, 10);
    } else if (flag == "--stride") {
      stride = std::strtoll(value.c_str(), nullptr, 10);
    } else if (flag == "--contract") {
      contract_text = value;
    } else if (flag == "--top-k") {
      top_k = std::strtoll(value.c_str(), nullptr, 10);
    } else {
      return usage();
    }
  }
  const bool contract_mode = !contract_text.empty() || top_k > 0;
  if (root.empty() || out_path.empty() || ordinal < 0 || from_second < 0 ||
      to_second < from_second || stride < 1 || top_k < 0) {
    return usage();
  }
  // The surface pass needs the print corpus and the emitted 1s grid; the
  // contract pass needs neither, and demanding them would make a read-only
  // quote dump depend on artifacts it never opens.
  if (!contract_mode && (prints.empty() || tapes.empty())) {
    return usage();
  }

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    std::fprintf(stderr, "the embedded registry refused to load\n");
    return 1;
  }
  const auto scope = qr::DayScope::admit(registry.value(), ordinal);
  if (!scope.has_value()) {
    std::fprintf(stderr, "REFUSED: %s\n", scope.error().message().c_str());
    return 1;
  }

  std::FILE* out = std::fopen(out_path.c_str(), "wb");
  if (out == nullptr) {
    std::fprintf(stderr, "cannot write %s\n", out_path.c_str());
    return 1;
  }
  std::fprintf(out, "# qr_w21_dump (FINAL_PLAN A2 as amended by DESIGN_FEATURES §W21-PIN-1)\n");
  std::fprintf(out, "session\tordinal\t%" PRId64 "\n", ordinal);
  std::fprintf(out, "session\tday\t%s\n", scope.value().day().c_str());

  if (qr::w21::SurfaceBuilder::session_is_modality_absent(ordinal)) {
    std::fprintf(out, "session\tmodality\t%s\n",
                 qr::validity_name(qr::Validity::MODALITY_ABSENT));
    std::fclose(out);
    return 0;
  }

  // --- the contract-level modes -------------------------------------------
  if (contract_mode) {
    return dump_contracts(out, scope.value(), root, contract_text, top_k, from_second, to_second);
  }

  char padded[32];
  std::snprintf(padded, sizeof(padded), "s%04lld", static_cast<long long>(ordinal));
  const std::filesystem::path tape_side_dir = std::filesystem::path(tapes) / padded / "L";
  qr::w21::SurfaceOptions options;
  options.prints_root = std::filesystem::path(prints);
  options.retain_seconds = true;
  const auto built = qr::w21::SurfaceBuilder::build(scope.value(), std::filesystem::path(root),
                                                    tape_side_dir, options);
  if (!built.has_value()) {
    std::fprintf(stderr, "REFUSED s%lld: %s\n", static_cast<long long>(ordinal),
                 built.error().message().c_str());
    std::fclose(out);
    return 1;
  }
  const qr::w21::SurfaceBuilder& surface = built.value();
  std::fprintf(out, "session\tmodality\t%s\n", qr::validity_name(surface.modality()));
  std::fprintf(out, "session\tseconds\t%" PRId64 "\n", surface.seconds());
  std::fprintf(out, "session\tvalid_bucket_seconds\t%" PRId64 "\n",
               surface.valid_bucket_seconds());
  std::fprintf(out, "session\tstraddle_present_seconds\t%" PRId64 "\n",
               surface.straddle_present_seconds());
  std::fprintf(out, "session\tevaporation_events\t%" PRId64 "\n", surface.evaporation_events());
  std::fprintf(out, "session\tno_requote_5s_events\t%" PRId64 "\n", surface.no_requote_5s_events());
  std::fprintf(out, "session\tbuckets\t%" PRId64 "\n", static_cast<std::int64_t>(qr::w21::kBuckets));
  std::fprintf(out, "session\tdte_planes\t%" PRId64 "\n",
               static_cast<std::int64_t>(qr::w21::kDtePlanes));

  const std::int64_t last = surface.seconds() - 1;
  const std::int64_t lo = from_second;
  const std::int64_t hi = to_second < last ? to_second : last;
  std::fprintf(out, "session\tstride\t%" PRId64 "\n", stride);
  for (std::int64_t second = lo; second <= hi; second += stride) {
    const auto index = static_cast<std::size_t>(second);
    if (index >= surface.surface().size()) {
      break;
    }
    const qr::w21::SurfaceSecond& row = surface.surface()[index];
    std::fprintf(out, "surface\t%" PRId64 "\tspot_u6\t%" PRId64 "\n", second, row.spot_u6);
    std::fprintf(out, "surface\t%" PRId64 "\tlive_contracts\t%" PRId64 "\n", second,
                 row.live_contracts);
    std::fprintf(out, "surface\t%" PRId64 "\tone_sided_contracts\t%" PRId64 "\n", second,
                 row.one_sided_contracts);
    std::fprintf(out, "surface\t%" PRId64 "\tvalid_buckets\t%" PRId64 "\n", second,
                 row.valid_buckets());

    for (std::size_t plane = 0; plane < qr::w21::kDtePlanes; ++plane) {
      const std::size_t at = index * qr::w21::kDtePlanes + plane;
      if (at >= surface.straddle_channels().size()) {
        break;
      }
      const qr::w21::StraddleChannels& ch = surface.straddle_channels()[at];
      char name[64];
      std::snprintf(name, sizeof(name), "proxy_vol_mid_p%zu", plane);
      print_typed(out, "straddle", second, name, ch.proxy_vol_mid);
      std::snprintf(name, sizeof(name), "proxy_vol_bid_p%zu", plane);
      print_typed(out, "straddle", second, name, ch.proxy_vol_bid);
      std::snprintf(name, sizeof(name), "proxy_vol_ask_p%zu", plane);
      print_typed(out, "straddle", second, name, ch.proxy_vol_ask);
      std::snprintf(name, sizeof(name), "width_bps_p%zu", plane);
      print_typed(out, "straddle", second, name, ch.width_bps);
      for (std::size_t horizon = 0; horizon < 3; ++horizon) {
        std::snprintf(name, sizeof(name), "dlog_proxy_vol_mid_h%zu_p%zu", horizon, plane);
        print_typed(out, "straddle", second, name, ch.dlog_proxy_vol_mid[horizon]);
        std::snprintf(name, sizeof(name), "dlog_proxy_vol_bid_h%zu_p%zu", horizon, plane);
        print_typed(out, "straddle", second, name, ch.dlog_proxy_vol_bid[horizon]);
        std::snprintf(name, sizeof(name), "dlog_proxy_vol_ask_h%zu_p%zu", horizon, plane);
        print_typed(out, "straddle", second, name, ch.dlog_proxy_vol_ask[horizon]);
        std::snprintf(name, sizeof(name), "dwidth_bps_h%zu_p%zu", horizon, plane);
        print_typed(out, "straddle", second, name, ch.dwidth_bps[horizon]);
      }
    }

    if (index < surface.thinning().size()) {
      const qr::w21::ThinningSecond& th = surface.thinning()[index];
      print_typed(out, "thinning", second, "valid_bucket_fraction", th.valid_bucket_fraction);
      print_typed(out, "thinning", second, "valid_bucket_fraction_delta_60s",
                  th.valid_bucket_fraction_delta_60s);
      print_typed(out, "thinning", second, "one_sided_fraction", th.one_sided_fraction);
      print_typed(out, "thinning", second, "wide_vs_trailing_median_fraction",
                  th.wide_vs_trailing_median_fraction);
    }

    // The refill imbalance, aggregated the only way a pack can read it: per
    // bucket, bucket-major, exactly as the module stores it.
    for (std::size_t bucket = 0; bucket < qr::w21::kBuckets; ++bucket) {
      const std::size_t at = index * qr::w21::kBuckets + bucket;
      if (at >= surface.refill().size()) {
        break;
      }
      const qr::w21::RefillSecond& rf = surface.refill()[at];
      if (rf.mean_refill_bid.v != qr::Validity::VALID &&
          rf.mean_refill_ask.v != qr::Validity::VALID &&
          rf.oriented_refill_difference.v != qr::Validity::VALID) {
        continue;  // an entirely absent bucket-second carries no information
      }
      char name[64];
      std::snprintf(name, sizeof(name), "mean_refill_bid_b%zu", bucket);
      print_typed(out, "refill", second, name, rf.mean_refill_bid);
      std::snprintf(name, sizeof(name), "mean_refill_ask_b%zu", bucket);
      print_typed(out, "refill", second, name, rf.mean_refill_ask);
      std::snprintf(name, sizeof(name), "oriented_refill_difference_b%zu", bucket);
      print_typed(out, "refill", second, name, rf.oriented_refill_difference);
    }

    // Q6/Q7 + §W21-PIN-2 — the Greek-residual repricing block, read out the same
    // way the module stores it: per bucket, bucket-major, over the three
    // trailing windows.  The stored mean is the sigma=+1 (LONG) orientation; a
    // SHORT reading is its negation and the dispersion is reflection-invariant,
    // so one copy is emitted and the reader reflects.  An entirely absent
    // bucket-second is skipped, exactly as the refill block skips one.
    for (std::size_t bucket = 0; bucket < qr::w21::kBuckets; ++bucket) {
      const std::size_t at = index * qr::w21::kBuckets + bucket;
      if (at >= surface.residual().size()) {
        break;
      }
      const qr::w21::ResidualSecond& rs = surface.residual()[at];
      bool present = false;
      for (std::size_t horizon = 0; horizon < rs.mean_bps.size(); ++horizon) {
        if (rs.mean_bps[horizon].v == qr::Validity::VALID ||
            rs.stdev_bps[horizon].v == qr::Validity::VALID) {
          present = true;
          break;
        }
      }
      if (!present) {
        continue;
      }
      char name[64];
      for (std::size_t horizon = 0; horizon < rs.mean_bps.size(); ++horizon) {
        std::snprintf(name, sizeof(name), "resid_mean_bps_b%zu_h%zu", bucket, horizon);
        print_typed(out, "residual", second, name, rs.mean_bps[horizon]);
        std::snprintf(name, sizeof(name), "resid_stdev_bps_b%zu_h%zu", bucket, horizon);
        print_typed(out, "residual", second, name, rs.stdev_bps[horizon]);
        std::snprintf(name, sizeof(name), "resid_observations_b%zu_h%zu", bucket, horizon);
        std::fprintf(out, "residual\t%" PRId64 "\t%s\t%" PRId64 "\tVALID\n", second, name,
                     rs.observations[horizon]);
      }
    }
  }

  for (const qr::w21::RequoteEventRecord& event : surface.requote_events()) {
    if (event.event_second < lo || event.event_second > hi) {
      continue;
    }
    std::fprintf(out,
                 "requote\t%" PRId64 "\t%" PRId64 "\t%" PRId64 "\t%d\t%d\n", event.event_second,
                 event.denominator_buckets, event.latency_micros, event.half_reached ? 1 : 0,
                 event.any_reached ? 1 : 0);
  }

  std::fclose(out);
  return 0;
}
