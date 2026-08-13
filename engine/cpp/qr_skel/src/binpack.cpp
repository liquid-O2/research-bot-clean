#include "qr_skel/binpack.hpp"

#include <cstdio>

namespace qr::skel {
namespace {

std::size_t dtype_width(const std::string& d) {
  if (d == "int64" || d == "float64") {
    return 8;
  }
  if (d == "int32" || d == "float32") {
    return 4;
  }
  if (d == "int8" || d == "uint8") {
    return 1;
  }
  return 0;  // unknown -> refused by the caller
}

Expected<std::vector<std::uint8_t>, Refusal> read_all(const std::string& path) {
  std::FILE* fh = std::fopen(path.c_str(), "rb");
  if (fh == nullptr) {
    return refuse<std::vector<std::uint8_t>>(
        Refusal(RefusalCode::IO, "qr_skel::read_all", "cannot open receipt file"));
  }
  std::vector<std::uint8_t> out;
  std::uint8_t buf[1 << 16];
  for (;;) {
    const std::size_t got = std::fread(buf, 1, sizeof(buf), fh);
    if (got == 0) {
      break;
    }
    out.insert(out.end(), buf, buf + got);
  }
  const bool bad = (std::ferror(fh) != 0);
  std::fclose(fh);
  if (bad) {
    return refuse<std::vector<std::uint8_t>>(
        Refusal(RefusalCode::IO, "qr_skel::read_all", "read error on receipt file"));
  }
  return out;
}

}  // namespace

Expected<BinPack, Refusal> BinPack::load(const std::string& stem, const std::string& expect_format) {
  auto side = qr::futsess::json_parse_file(stem + ".json");
  if (!side) {
    return refuse<BinPack>(side.error());
  }
  BinPack pack;
  pack.sidecar_ = std::move(side).value();
  const qr::futsess::Json* fmt = pack.sidecar_.find("format");
  if (fmt == nullptr || fmt->type() != qr::futsess::Json::Type::String ||
      fmt->str() != expect_format) {
    return refuse<BinPack>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::BinPack::load",
                                   "receipt format tag is not the expected one"));
  }
  auto blob = read_all(stem + ".bin");
  if (!blob) {
    return refuse<BinPack>(blob.error());
  }
  pack.blob_ = std::move(blob).value();

  const qr::futsess::Json* arrays = pack.sidecar_.find("arrays");
  if (arrays == nullptr || arrays->type() != qr::futsess::Json::Type::Array) {
    return refuse<BinPack>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::BinPack::load",
                                   "receipt sidecar has no arrays list"));
  }
  for (const qr::futsess::Json& d : arrays->items()) {
    const qr::futsess::Json* n = d.find("name");
    const qr::futsess::Json* t = d.find("dtype");
    const qr::futsess::Json* c = d.find("count");
    const qr::futsess::Json* o = d.find("offset");
    if (n == nullptr || t == nullptr || c == nullptr || o == nullptr ||
        n->type() != qr::futsess::Json::Type::String ||
        t->type() != qr::futsess::Json::Type::String ||
        c->type() != qr::futsess::Json::Type::Number ||
        o->type() != qr::futsess::Json::Type::Number) {
      return refuse<BinPack>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::BinPack::load",
                                     "malformed array descriptor in receipt sidecar"));
    }
    PackedArray pa;
    pa.dtype = t->str();
    const double cd = c->number();
    const double od = o->number();
    if (cd < 0 || od < 0) {
      return refuse<BinPack>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::BinPack::load",
                                     "negative count or offset in receipt sidecar"));
    }
    pa.count = static_cast<std::size_t>(cd);
    pa.offset = static_cast<std::size_t>(od);
    const std::size_t w = dtype_width(pa.dtype);
    if (w == 0) {
      return refuse<BinPack>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::BinPack::load",
                                     "unknown array dtype in receipt sidecar"));
    }
    // The bound is checked in the widest type available; a receipt whose
    // descriptor overruns the blob is a refusal, never a truncated read.
    if (pa.count > (pack.blob_.size() / w) + 1 ||
        pa.offset > pack.blob_.size() ||
        pack.blob_.size() - pa.offset < pa.count * w) {
      return refuse<BinPack>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_skel::BinPack::load",
                                     "array descriptor runs past the end of the bin blob"));
    }
    if (!pack.arrays_.emplace(n->str(), pa).second) {
      return refuse<BinPack>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::BinPack::load",
                                     "duplicate array name in receipt sidecar"));
    }
  }
  return pack;
}

std::string BinPackWriter::basename(const std::string& stem) {
  const std::size_t slash = stem.find_last_of('/');
  return (slash == std::string::npos) ? stem : stem.substr(slash + 1);
}

Expected<std::monostate, Refusal> BinPackWriter::write_pair(const std::string& stem,
                                                            const std::vector<std::uint8_t>& bytes,
                                                            const std::string& json) {
  struct Part {
    std::string path;
    const void* data;
    std::size_t n;
  };
  const Part parts[2] = {{stem + ".bin", bytes.data(), bytes.size()},
                         {stem + ".json", json.data(), json.size()}};
  for (const Part& p : parts) {
    const std::string tmp = p.path + ".tmp";
    std::FILE* fh = std::fopen(tmp.c_str(), "wb");
    if (fh == nullptr) {
      return refuse<std::monostate>(
          Refusal(RefusalCode::IO, "qr_skel::write_pair", "cannot create output file"));
    }
    const bool ok = (p.n == 0) || (std::fwrite(p.data, 1, p.n, fh) == p.n);
    const bool closed = (std::fclose(fh) == 0);
    if (!ok || !closed) {
      std::remove(tmp.c_str());
      return refuse<std::monostate>(
          Refusal(RefusalCode::IO, "qr_skel::write_pair", "short write on output file"));
    }
    if (std::rename(tmp.c_str(), p.path.c_str()) != 0) {
      return refuse<std::monostate>(
          Refusal(RefusalCode::IO, "qr_skel::write_pair", "cannot rename output file"));
    }
  }
  return std::monostate{};
}

}  // namespace qr::skel
