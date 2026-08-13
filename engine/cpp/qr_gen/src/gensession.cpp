#include "qr_gen/gensession.hpp"

#include <cstdio>

#include "qr_futsess/json.hpp"
#include "qr_skel/binpack.hpp"

namespace qr::gen {

Expected<GenSession, Refusal> GenSession::load(const std::string& dir, std::int32_t date8,
                                               const qr::skel::SanityPolicy& policy) {
  auto view = qr::skel::SessionView::load(dir, date8, policy);
  if (!view) {
    return refuse<GenSession>(view.error());
  }
  char stem[512];
  std::snprintf(stem, sizeof(stem), "%s/%08d", dir.c_str(), date8);
  auto pack = qr::skel::BinPack::load(stem, "QRSESS1");
  if (!pack) {
    return refuse<GenSession>(pack.error());
  }
  const qr::skel::BinPack& p = pack.value();
  auto ts = p.get<std::int64_t>("trades_sec", "int64");
  auto tp = p.get<std::int64_t>("trades_px", "int64");
  auto tz = p.get<std::int64_t>("trades_size", "int64");
  if (!ts) {
    return refuse<GenSession>(ts.error());
  }
  if (!tp) {
    return refuse<GenSession>(tp.error());
  }
  if (!tz) {
    return refuse<GenSession>(tz.error());
  }
  GenSession s;
  s.view_ = std::move(view).value();
  s.trades_sec_ = std::move(ts).value();
  s.trades_px_ = std::move(tp).value();
  s.trades_size_ = std::move(tz).value();
  if (s.trades_sec_.size() != s.trades_px_.size() || s.trades_sec_.size() != s.trades_size_.size()) {
    return refuse<GenSession>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_gen::GenSession::load",
                                      "trade columns have unequal lengths"));
  }
  const qr::futsess::Json* iid = p.sidecar().find("g0_iid");
  if (iid == nullptr || iid->type() != qr::futsess::Json::Type::Number) {
    return refuse<GenSession>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_gen::GenSession::load",
                                      "session receipt carries no g0_iid"));
  }
  s.iid_ = static_cast<std::int64_t>(iid->number());
  const qr::futsess::Json* meta = p.sidecar().find("meta");
  const qr::futsess::Json* dom =
      (meta == nullptr) ? nullptr : meta->find("dominant_share");
  if (dom == nullptr || dom->type() != qr::futsess::Json::Type::Number) {
    return refuse<GenSession>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_gen::GenSession::load",
                                      "session receipt carries no meta.dominant_share"));
  }
  s.dominant_share_ = dom->number();
  return s;
}

}  // namespace qr::gen
