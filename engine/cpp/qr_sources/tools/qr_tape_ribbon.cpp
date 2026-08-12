// qr_tape_ribbon — THE D-020 V3 RAW-TAPE RIBBON.
//
// The decision neighbourhood's ACTUAL events, printed from the three lawful
// session readers with their OWN named projection slots and NOTHING derived.
// The classified views (aggressor, concession, oriented flow) live in the
// published DecisionTape group tables and are read there; this tool exists so
// the pack can also show the literal rows — price, bid, ask, sizes, venue,
// conditions, strike, right, expiry, vendor IV and Greeks — without any
// consumer having to guess a column layout.
//
// EVERY FIELD IS A NAMED SLOT of `qr::sources::{StockTradeRow, StockQuoteRow,
// OptionPrintRow}`. Nulls are printed as `NA`, never as a zero that could
// collide with a real value (the readers' own rule). No classification, no
// eligibility, no orientation, no arithmetic beyond the frame-B -> frame-A
// clock conversion the readers' consumers all use.
//
// It is census-style: read-only, no wall-clock value in the output, so two runs
// of the same arguments are byte-identical.
//
// THE RUTW STREAM (B5) IS OPT-IN. `--streams` must name `rutw` for it to be
// emitted, and the `rutw_option` rows carry EXACTLY the `option` columns — B5
// is the same 62-name profile under the same laws, so the same named slots
// print the same way. It is a SEPARATE row kind and never merged into
// `option`: IWM and RUTW are different instruments, and W2.12's whole content
// is the DIVERGENCE between them, which a merged stream would destroy.
//
// usage: qr_tape_ribbon --ordinal N --from-second A --to-second B --out TSV
//                       [--quotes-root DIR] [--trades-root DIR] [--options-root DIR]
//                       [--rutw-root DIR] [--streams prints,quotes,options,rutw]
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <string>

#include "qr_clock/session_clock.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_registry/registry.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/rutw_prints.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace {

[[noreturn]] void die(const std::string& message) {
  std::fprintf(stderr, "qr_tape_ribbon: %s\n", message.c_str());
  std::exit(1);
}

int usage() {
  std::fprintf(stderr,
               "usage: qr_tape_ribbon --ordinal N --from-second A --to-second B --out TSV\n"
               "       [--quotes-root DIR] [--trades-root DIR] [--options-root DIR]\n"
               "       [--rutw-root DIR] [--streams prints,quotes,options,rutw]\n");
  return 2;
}

/// `NA` for a null projected cell, the exact integer otherwise.
void put_i64(std::FILE* out, bool null, std::int64_t value) {
  if (null) {
    std::fputs("\tNA", out);
  } else {
    std::fprintf(out, "\t%" PRId64, value);
  }
}

void put_f64(std::FILE* out, bool null, double value) {
  if (null) {
    std::fputs("\tNA", out);
  } else {
    std::fprintf(out, "\t%.17g", value);
  }
}

/// One option-print row, in named projection slots. B3 and B5 share the row
/// type because they share the profile and the laws, so they share this
/// printer too — and differ only in the `kind` column, which names the corpus
/// the row came from.
void put_option_row(std::FILE* out, const char* kind, std::int64_t ms,
                    const qr::sources::OptionPrintRow& row) {
  std::fprintf(out, "%s\t%" PRId64, kind, ms);
  put_i64(out, row.is_null(qr::sources::kPrintSlotSize), row.size);
  put_i64(out, row.is_null(qr::sources::kPrintSlotPrice), row.price_u6);
  put_i64(out, row.is_null(qr::sources::kPrintSlotStrike), row.strike_u6);
  std::fprintf(out, "\t%s", qr::sources::right_name(row.right));
  put_i64(out, row.is_null(qr::sources::kPrintSlotExpiration),
          static_cast<std::int64_t>(row.expiration_day));
  put_i64(out, row.is_null(qr::sources::kPrintSlotBid), row.bid_u6);
  put_i64(out, row.is_null(qr::sources::kPrintSlotAsk), row.ask_u6);
  put_i64(out, row.is_null(qr::sources::kPrintSlotBidSize), row.bid_size);
  put_i64(out, row.is_null(qr::sources::kPrintSlotAskSize), row.ask_size);
  put_f64(out, row.is_null(qr::sources::kPrintSlotDelta), row.delta);
  put_f64(out, row.is_null(qr::sources::kPrintSlotGamma), row.gamma);
  put_f64(out, row.is_null(qr::sources::kPrintSlotVanna), row.vanna);
  put_f64(out, row.is_null(qr::sources::kPrintSlotCharm), row.charm);
  put_f64(out, row.is_null(qr::sources::kPrintSlotImpliedVol), row.implied_vol);
  put_f64(out, row.is_null(qr::sources::kPrintSlotUnderlyingPrice), row.underlying_price);
  put_i64(out, row.is_null(qr::sources::kPrintSlotCondition), row.condition);
  put_i64(out, row.is_null(qr::sources::kPrintSlotSequence), row.sequence);
  std::fputc('\n', out);
}

}  // namespace

int main(int argc, char** argv) {
  std::string quotes_root = "/workspace/data/tokens/stock_quotes/IWM";
  std::string trades_root = "/workspace/data/tokens/stock_trades/IWM";
  std::string options_root = "/workspace/data/tokens/options_prints/IWM";
  std::string rutw_root = "/workspace/data/tokens/RUTW/options_prints";
  std::string out_path;
  std::string streams = "prints,quotes,options";
  std::int64_t ordinal = -1;
  std::int64_t from_second = -1;
  std::int64_t to_second = -1;
  for (int index = 1; index < argc; ++index) {
    const std::string flag = argv[index];
    if (index + 1 >= argc) {
      return usage();
    }
    const std::string value = argv[++index];
    if (flag == "--quotes-root") {
      quotes_root = value;
    } else if (flag == "--trades-root") {
      trades_root = value;
    } else if (flag == "--options-root") {
      options_root = value;
    } else if (flag == "--rutw-root") {
      rutw_root = value;
    } else if (flag == "--out") {
      out_path = value;
    } else if (flag == "--streams") {
      streams = value;
    } else if (flag == "--ordinal") {
      ordinal = std::strtoll(value.c_str(), nullptr, 10);
    } else if (flag == "--from-second") {
      from_second = std::strtoll(value.c_str(), nullptr, 10);
    } else if (flag == "--to-second") {
      to_second = std::strtoll(value.c_str(), nullptr, 10);
    } else {
      return usage();
    }
  }
  if (out_path.empty() || ordinal < 0 || from_second < 0 || to_second < from_second) {
    return usage();
  }
  const bool want_prints = streams.find("prints") != std::string::npos;
  const bool want_quotes = streams.find("quotes") != std::string::npos;
  const bool want_options = streams.find("options") != std::string::npos;
  // OPT-IN, so an existing invocation's output is unchanged byte for byte.
  // `options` does not contain `rutw`, so the two tokens never alias.
  const bool want_rutw = streams.find("rutw") != std::string::npos;

  auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    die(std::string("registry: ") + registry.error().message());
  }
  const auto scope = qr::DayScope::admit(registry.value(), ordinal);
  if (!scope.has_value()) {
    die(std::string("scope: ") + scope.error().message());
  }
  const auto clock = qr::SessionClock::from_session(scope.value().session());
  if (!clock.has_value()) {
    die(std::string("clock: ") + clock.error().message());
  }
  const std::int64_t start_ns = clock.value().session_start_a().ns();
  constexpr std::int64_t kNanosPerSecond = 1'000'000'000;

  /// The one conversion: a frame-B stamp to this session's own second index.
  /// `classify_attach_ms` is the readers' consumers' conversion, unchanged.
  const auto second_of = [&](std::int64_t ts_ms_b) -> std::int64_t {
    const auto attach = clock.value().classify_attach_ms(ts_ms_b);
    if (!attach.is_on_day()) {
      return -1;
    }
    return (attach.frame_a().ns() - start_ns) / kNanosPerSecond;
  };
  const auto millis_of = [&](std::int64_t ts_ms_b) -> std::int64_t {
    const auto attach = clock.value().classify_attach_ms(ts_ms_b);
    if (!attach.is_on_day()) {
      return -1;
    }
    return (attach.frame_a().ns() - start_ns) / 1'000'000;
  };

  std::FILE* out = std::fopen(out_path.c_str(), "wb");
  if (out == nullptr) {
    die("cannot write " + out_path);
  }
  std::fprintf(out, "# qr_tape_ribbon (raw named projection slots; nothing derived)\n");
  std::fprintf(out, "session\tordinal\t%" PRId64 "\n", ordinal);
  std::fprintf(out, "session\tday\t%s\n", scope.value().day().c_str());
  std::fprintf(out, "session\tsession_start_ns\t%" PRId64 "\n", start_ns);
  std::fprintf(out, "session\tfrom_second\t%" PRId64 "\n", from_second);
  std::fprintf(out, "session\tto_second\t%" PRId64 "\n", to_second);
  std::fprintf(out,
               "# print\tms\tsize\tprice_u6\tbid_u6\task_u6\tbid_shares\task_shares"
               "\texchange\tcondition\text1\text2\text3\text4\tsequence\tquote_ts_ms\n");
  std::fprintf(out,
               "# quote\tms\tbid_u6\task_u6\tbid_shares\task_shares\tbid_exchange"
               "\task_exchange\tbid_condition\task_condition\n");
  std::fprintf(out,
               "# option\tms\tsize\tprice_u6\tstrike_u6\tright\texpiration_day\tbid_u6\task_u6"
               "\tbid_size\task_size\tdelta\tgamma\tvanna\tcharm\timplied_vol"
               "\tunderlying_price\tcondition\tsequence\n");
  if (want_rutw) {
    std::fprintf(out,
                 "# rutw_option\tms\tsize\tprice_u6\tstrike_u6\tright\texpiration_day\tbid_u6"
                 "\task_u6\tbid_size\task_size\tdelta\tgamma\tvanna\tcharm\timplied_vol"
                 "\tunderlying_price\tcondition\tsequence\n");
  }

  if (want_prints) {
    auto opened = qr::sources::StockTradeReader::open(scope.value(), trades_root);
    if (!opened.has_value()) {
      die(std::string("trades: ") + opened.error().refusal().message());
    }
    qr::sources::StockTradeReader reader = std::move(opened).value();
    qr::sources::StockTradeReader::Group group;
    for (;;) {
      auto more = reader.next_group(group);
      if (!more.has_value()) {
        die(std::string("trades: ") + more.error().refusal().message());
      }
      if (!more.value()) {
        break;
      }
      const std::int64_t second = second_of(group.ts_ms_b);
      if (second < from_second) {
        continue;
      }
      if (second > to_second) {
        break;
      }
      for (const qr::sources::StockTradeRow& row : group.rows) {
        std::fprintf(out, "print\t%" PRId64, millis_of(row.ts_ms_b));
        put_i64(out, row.is_null(qr::sources::kTradeSlotSize), row.size);
        put_i64(out, row.is_null(qr::sources::kTradeSlotPrice), row.price_u6);
        put_i64(out, row.is_null(qr::sources::kTradeSlotBid), row.bid_u6);
        put_i64(out, row.is_null(qr::sources::kTradeSlotAsk), row.ask_u6);
        put_i64(out, row.is_null(qr::sources::kTradeSlotBidSize), row.bid_shares);
        put_i64(out, row.is_null(qr::sources::kTradeSlotAskSize), row.ask_shares);
        put_i64(out, row.is_null(qr::sources::kTradeSlotExchange), row.exchange);
        put_i64(out, row.is_null(qr::sources::kTradeSlotCondition), row.condition);
        put_i64(out, row.is_null(qr::sources::kTradeSlotExtCondition1), row.ext_condition[0]);
        put_i64(out, row.is_null(qr::sources::kTradeSlotExtCondition2), row.ext_condition[1]);
        put_i64(out, row.is_null(qr::sources::kTradeSlotExtCondition3), row.ext_condition[2]);
        put_i64(out, row.is_null(qr::sources::kTradeSlotExtCondition4), row.ext_condition[3]);
        put_i64(out, row.is_null(qr::sources::kTradeSlotSequence), row.sequence);
        put_i64(out, row.is_null(qr::sources::kTradeSlotQuoteTimestamp),
                millis_of(row.quote_ts_ms_b));
        std::fputc('\n', out);
      }
    }
  }

  if (want_quotes) {
    auto opened = qr::sources::StockQuoteReader::open(scope.value(), quotes_root,
                                                      scope.value().profile());
    if (!opened.has_value()) {
      die(std::string("quotes: ") + opened.error().refusal().message());
    }
    qr::sources::StockQuoteReader reader = std::move(opened).value();
    qr::sources::StockQuoteReader::Group group;
    for (;;) {
      auto more = reader.next_group(group);
      if (!more.has_value()) {
        die(std::string("quotes: ") + more.error().refusal().message());
      }
      if (!more.value()) {
        break;
      }
      const std::int64_t second = second_of(group.ts_ms_b);
      if (second < from_second) {
        continue;
      }
      if (second > to_second) {
        break;
      }
      for (const qr::sources::StockQuoteRow& row : group.rows) {
        std::fprintf(out, "quote\t%" PRId64, millis_of(row.ts_ms_b));
        put_i64(out, row.is_null(qr::sources::kQuoteSlotBid), row.bid_u6);
        put_i64(out, row.is_null(qr::sources::kQuoteSlotAsk), row.ask_u6);
        put_i64(out, row.is_null(qr::sources::kQuoteSlotBidSize), row.bid_shares);
        put_i64(out, row.is_null(qr::sources::kQuoteSlotAskSize), row.ask_shares);
        put_i64(out, row.is_null(qr::sources::kQuoteSlotBidExchange), row.bid_exchange);
        put_i64(out, row.is_null(qr::sources::kQuoteSlotAskExchange), row.ask_exchange);
        put_i64(out, row.is_null(qr::sources::kQuoteSlotBidCondition), row.bid_condition);
        put_i64(out, row.is_null(qr::sources::kQuoteSlotAskCondition), row.ask_condition);
        std::fputc('\n', out);
      }
    }
  }

  if (want_options) {
    auto opened = qr::sources::OptionPrintReader::open(scope.value(), options_root);
    if (!opened.has_value()) {
      die(std::string("options: ") + opened.error().refusal().message());
    }
    qr::sources::OptionPrintReader reader = std::move(opened).value();
    qr::sources::OptionPrintReader::Group group;
    for (;;) {
      auto more = reader.next_group(group);
      if (!more.has_value()) {
        die(std::string("options: ") + more.error().refusal().message());
      }
      if (!more.value()) {
        break;
      }
      const std::int64_t second = second_of(group.ts_ms_b);
      if (second < from_second) {
        continue;
      }
      if (second > to_second) {
        break;
      }
      for (const qr::sources::OptionPrintRow& row : group.rows) {
        put_option_row(out, "option", millis_of(row.ts_ms_b), row);
      }
    }
  }

  if (want_rutw) {
    // B5, through its OWN reader. The IWM print reader would refuse this root
    // by name, and this reader refuses every other root by name — the wall is
    // two-way, so the tool cannot silently read one corpus into the other's
    // stream.
    auto opened = qr::sources::RutwPrintReader::open(scope.value(), rutw_root);
    if (!opened.has_value()) {
      die(std::string("rutw: ") + opened.error().refusal().message());
    }
    qr::sources::RutwPrintReader reader = std::move(opened).value();
    qr::sources::RutwPrintReader::Group group;
    for (;;) {
      auto more = reader.next_group(group);
      if (!more.has_value()) {
        die(std::string("rutw: ") + more.error().refusal().message());
      }
      if (!more.value()) {
        break;
      }
      const std::int64_t second = second_of(group.ts_ms_b);
      if (second < from_second) {
        continue;
      }
      if (second > to_second) {
        break;
      }
      for (const qr::sources::OptionPrintRow& row : group.rows) {
        put_option_row(out, "rutw_option", millis_of(row.ts_ms_b), row);
      }
    }
  }

  std::fclose(out);
  return 0;
}
