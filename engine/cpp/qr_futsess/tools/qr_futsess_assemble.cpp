// qr_futsess_assemble — Globex session assembly from the day intermediates
// (M0 spec §5).
//
// usage: qr_futsess_assemble <ASSET> <day_dir> <out_dir> <phases_json> <s1_receipt_json>
#include <sys/stat.h>

#include <cstdio>
#include <string>

#include "qr_futsess/calendar.hpp"
#include "qr_futsess/sessions.hpp"

int main(int argc, char** argv) {
  if (argc != 6) {
    std::fprintf(stderr,
                 "usage: %s <ASSET> <day_dir> <out_dir> <phases_json> <s1_receipt_json>\n",
                 argv[0]);
    return 2;
  }
  qr::futsess::AssembleOptions opt;
  if (!qr::futsess::asset_from_name(argv[1], &opt.asset)) {
    std::fprintf(stderr, "unknown asset %s\n", argv[1]);
    return 2;
  }
  opt.day_dir = argv[2];
  opt.out_dir = argv[3];
  opt.phases_path = argv[4];

  auto tz = qr::futsess::init_globex_timezone();
  if (!tz) {
    std::fprintf(stderr, "REFUSED: %s\n", tz.error().message().c_str());
    return 1;
  }
  auto rule = qr::futsess::load_pinned_rule(argv[5]);
  if (!rule) {
    std::fprintf(stderr, "REFUSED: %s\n", rule.error().message().c_str());
    return 1;
  }
  opt.rule = rule.value();
  ::mkdir(opt.out_dir.c_str(), 0755);

  auto res = qr::futsess::assemble_asset(opt);
  if (!res) {
    std::fprintf(stderr, "REFUSED: %s\n", res.error().message().c_str());
    return 1;
  }
  std::fprintf(stderr, "[qr_futsess] %s DONE: %lld session receipts, %lld bars\n", argv[1],
               static_cast<long long>(res.value().n_sessions),
               static_cast<long long>(res.value().n_bars));
  return 0;
}
