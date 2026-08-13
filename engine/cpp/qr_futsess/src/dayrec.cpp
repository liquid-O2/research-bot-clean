#include "qr_futsess/dayrec.hpp"

#include <zstd.h>

#include <algorithm>
#include <cstdio>
#include <cstring>

namespace qr::futsess {
namespace {

// "QRDAY001" — the intermediate's own magic. Bumping it invalidates stale
// intermediates rather than letting a changed layout be misread as data.
constexpr char kMagic[8] = {'Q', 'R', 'D', 'A', 'Y', '0', '0', '1'};
constexpr int kCompressionLevel = 1;  // I/O relief, not archival density

class ByteSink {
 public:
  void put(const void* p, std::size_t n) {
    const auto* b = static_cast<const std::uint8_t*>(p);
    buf_.insert(buf_.end(), b, b + n);
  }
  template <class T>
  void scalar(T v) {
    put(&v, sizeof(T));
  }
  template <class T>
  void array(const std::vector<T>& v) {
    scalar<std::uint64_t>(v.size());
    if (!v.empty()) {
      put(v.data(), v.size() * sizeof(T));
    }
  }
  void strings(const std::vector<std::string>& v) {
    scalar<std::uint64_t>(v.size());
    for (const std::string& s : v) {
      scalar<std::uint32_t>(static_cast<std::uint32_t>(s.size()));
      put(s.data(), s.size());
    }
  }
  [[nodiscard]] const std::vector<std::uint8_t>& bytes() const { return buf_; }

 private:
  std::vector<std::uint8_t> buf_;
};

class ByteSource {
 public:
  ByteSource(const std::uint8_t* p, std::size_t n) : p_(p), n_(n) {}

  [[nodiscard]] bool ok() const { return ok_; }

  template <class T>
  T scalar() {
    T v{};
    if (pos_ + sizeof(T) > n_) {
      ok_ = false;
      return v;
    }
    std::memcpy(&v, p_ + pos_, sizeof(T));
    pos_ += sizeof(T);
    return v;
  }
  template <class T>
  void array(std::vector<T>& out) {
    const auto n = static_cast<std::size_t>(scalar<std::uint64_t>());
    if (!ok_ || pos_ + n * sizeof(T) > n_) {
      ok_ = false;
      return;
    }
    out.resize(n);
    if (n != 0) {
      std::memcpy(out.data(), p_ + pos_, n * sizeof(T));
      pos_ += n * sizeof(T);
    }
  }
  void strings(std::vector<std::string>& out) {
    const auto n = static_cast<std::size_t>(scalar<std::uint64_t>());
    if (!ok_) {
      return;
    }
    out.clear();
    out.reserve(n);
    for (std::size_t i = 0; i < n; ++i) {
      const auto len = static_cast<std::size_t>(scalar<std::uint32_t>());
      if (!ok_ || pos_ + len > n_) {
        ok_ = false;
        return;
      }
      out.emplace_back(reinterpret_cast<const char*>(p_ + pos_), len);
      pos_ += len;
    }
  }
  [[nodiscard]] std::size_t pos() const { return pos_; }
  [[nodiscard]] std::size_t size() const { return n_; }

 private:
  const std::uint8_t* p_;
  std::size_t n_;
  std::size_t pos_ = 0;
  bool ok_ = true;
};

void serialize(const DayReceipt& r, ByteSink& s) {
  s.scalar<std::int32_t>(r.date.yyyymmdd());
  s.scalar<std::int64_t>(r.n_records);
  s.scalar<std::int64_t>(r.n_dropped_sentinel);
  s.scalar<std::int64_t>(r.n_no_flast_seconds);
  s.scalar<std::int64_t>(r.tick_gcd_raw);
  s.array(r.tracked_ids);
  s.array(r.bid_px);
  s.array(r.ask_px);
  s.array(r.bid_sz);
  s.array(r.ask_sz);
  s.array(r.state);
  s.array(r.upd_count);
  s.array(r.trades_iid);
  s.array(r.trades_sec);
  s.array(r.trades_px);
  s.array(r.trades_size);
  s.array(r.trades_side);
  s.array(r.tally_iid);
  s.array(r.tally_updates);
  s.array(r.tally_trades);
  s.array(r.tally_trade_size_sum);
  s.array(r.map_iid);
  s.strings(r.map_symbol);
  s.array(r.map_outright);
  s.array(r.carry_iid);
  s.array(r.carry_bid);
  s.array(r.carry_ask);
  s.array(r.carry_bsz);
  s.array(r.carry_asz);
  s.array(r.carry_state);
  s.array(r.carry_last_sec);
}

void deserialize(ByteSource& s, DayReceipt& r) {
  r.date = date_from_yyyymmdd(s.scalar<std::int32_t>());
  r.n_records = s.scalar<std::int64_t>();
  r.n_dropped_sentinel = s.scalar<std::int64_t>();
  r.n_no_flast_seconds = s.scalar<std::int64_t>();
  r.tick_gcd_raw = s.scalar<std::int64_t>();
  s.array(r.tracked_ids);
  s.array(r.bid_px);
  s.array(r.ask_px);
  s.array(r.bid_sz);
  s.array(r.ask_sz);
  s.array(r.state);
  s.array(r.upd_count);
  s.array(r.trades_iid);
  s.array(r.trades_sec);
  s.array(r.trades_px);
  s.array(r.trades_size);
  s.array(r.trades_side);
  s.array(r.tally_iid);
  s.array(r.tally_updates);
  s.array(r.tally_trades);
  s.array(r.tally_trade_size_sum);
  s.array(r.map_iid);
  s.strings(r.map_symbol);
  s.array(r.map_outright);
  s.array(r.carry_iid);
  s.array(r.carry_bid);
  s.array(r.carry_ask);
  s.array(r.carry_bsz);
  s.array(r.carry_asz);
  s.array(r.carry_state);
  s.array(r.carry_last_sec);
}

int index_of(const std::vector<std::int64_t>& ids, std::int64_t iid) {
  const auto it = std::lower_bound(ids.begin(), ids.end(), iid);
  if (it == ids.end() || *it != iid) {
    return -1;
  }
  return static_cast<int>(it - ids.begin());
}

}  // namespace

int DayReceipt::row_index(std::int64_t iid) const { return index_of(tracked_ids, iid); }
int DayReceipt::carry_index(std::int64_t iid) const { return index_of(carry_iid, iid); }

Expected<std::monostate, Refusal> write_day_receipt(const std::string& path,
                                                    const DayReceipt& rec) {
  ByteSink sink;
  serialize(rec, sink);
  const std::vector<std::uint8_t>& raw = sink.bytes();
  const std::size_t bound = ZSTD_compressBound(raw.size());
  std::vector<std::uint8_t> comp(bound);
  // The frame CONTENT CHECKSUM is switched on deliberately: without it a single
  // flipped byte in the compressed body decompresses to the declared size and
  // hands the assembler silently wrong prices. A corrupt intermediate must be a
  // refusal, never plausible data.
  ZSTD_CCtx* cctx = ZSTD_createCCtx();
  if (cctx == nullptr) {
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_futsess::write_day_receipt", "ZSTD_createCCtx failed"));
  }
  ZSTD_CCtx_setParameter(cctx, ZSTD_c_compressionLevel, kCompressionLevel);
  ZSTD_CCtx_setParameter(cctx, ZSTD_c_checksumFlag, 1);
  const std::size_t csize = ZSTD_compress2(cctx, comp.data(), comp.size(), raw.data(), raw.size());
  ZSTD_freeCCtx(cctx);
  if (ZSTD_isError(csize) != 0u) {
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_futsess::write_day_receipt", "zstd compression failed"));
  }
  // Write to a temp then rename: a crashed run must never leave a half receipt
  // that the assembler would read as a short day.
  const std::string tmp = path + ".tmp";
  std::FILE* fh = std::fopen(tmp.c_str(), "wb");
  if (fh == nullptr) {
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_futsess::write_day_receipt", "cannot create receipt"));
  }
  const std::uint64_t raw_size = raw.size();
  bool ok = std::fwrite(kMagic, 1, sizeof(kMagic), fh) == sizeof(kMagic);
  ok = ok && std::fwrite(&raw_size, 1, sizeof(raw_size), fh) == sizeof(raw_size);
  ok = ok && std::fwrite(comp.data(), 1, csize, fh) == csize;
  ok = (std::fclose(fh) == 0) && ok;
  if (!ok) {
    std::remove(tmp.c_str());
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_futsess::write_day_receipt", "short write on receipt"));
  }
  if (std::rename(tmp.c_str(), path.c_str()) != 0) {
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_futsess::write_day_receipt", "cannot rename receipt"));
  }
  return std::monostate{};
}

Expected<DayReceipt, Refusal> read_day_receipt(const std::string& path) {
  std::FILE* fh = std::fopen(path.c_str(), "rb");
  if (fh == nullptr) {
    return refuse<DayReceipt>(
        Refusal(RefusalCode::IO, "qr_futsess::read_day_receipt", "cannot open receipt"));
  }
  char magic[sizeof(kMagic)];
  std::uint64_t raw_size = 0;
  if (std::fread(magic, 1, sizeof(magic), fh) != sizeof(magic) ||
      std::memcmp(magic, kMagic, sizeof(kMagic)) != 0 ||
      std::fread(&raw_size, 1, sizeof(raw_size), fh) != sizeof(raw_size)) {
    std::fclose(fh);
    return refuse<DayReceipt>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                      "qr_futsess::read_day_receipt", "not a QRDAY001 receipt"));
  }
  std::vector<std::uint8_t> comp;
  std::uint8_t chunk[1 << 16];
  for (;;) {
    const std::size_t n = std::fread(chunk, 1, sizeof(chunk), fh);
    if (n == 0) {
      break;
    }
    comp.insert(comp.end(), chunk, chunk + n);
  }
  std::fclose(fh);
  std::vector<std::uint8_t> raw(static_cast<std::size_t>(raw_size));
  const std::size_t got = ZSTD_decompress(raw.data(), raw.size(), comp.data(), comp.size());
  if (ZSTD_isError(got) != 0u || got != raw.size()) {
    return refuse<DayReceipt>(Refusal(RefusalCode::DECODE_FAILED, "qr_futsess::read_day_receipt",
                                      "receipt body failed to decompress to its declared size"));
  }
  DayReceipt rec;
  ByteSource src(raw.data(), raw.size());
  deserialize(src, rec);
  if (!src.ok() || src.pos() != src.size()) {
    return refuse<DayReceipt>(Refusal(RefusalCode::CONTENT_MISMATCH,
                                      "qr_futsess::read_day_receipt",
                                      "receipt body was not consumed exactly"));
  }
  return rec;
}

}  // namespace qr::futsess
