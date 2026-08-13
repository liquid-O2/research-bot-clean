#include "qr_dbn/dbn.hpp"

#include <algorithm>
#include <cstring>

namespace qr::dbn {
namespace {

// Decompressed-side buffer. PORT_M0_CENSUS_SPEC §0 pins 4 MiB chunks on the
// proven decode path; the same size is used here so the record stream is fed in
// the same-sized bites.
constexpr std::size_t kOutChunk = 1u << 22;

// Fixed metadata-header geometry, DBN v1, verified against real bytes:
//   0  dataset[16] | 16 schema u16 | 18 start u64 | 26 end u64 | 34 limit u64
//   42 record_count u64 (v1 only) | 50 stype_in u8 | 51 stype_out u8
//   52 ts_out u8 | 53 reserved[47] | 100 schema_definition_length u32
// then the four symbology blocks.
constexpr std::size_t kV1FixedLen = 100;
constexpr std::size_t kV1ReservedLen = 47;

template <class T>
T load_le(const std::uint8_t* p) {
  T v{};
  std::memcpy(&v, p, sizeof(T));
  return v;  // the substrate is little-endian x86-64; DBN is little-endian.
}

/// Bounds-checked cursor over the metadata frame. Every read is guarded; a read
/// past the frame is a refusal, never a wrap or a zero.
class Cursor {
 public:
  Cursor(const std::uint8_t* base, std::size_t len) : base_(base), len_(len) {}

  [[nodiscard]] bool have(std::size_t n) const { return pos_ + n <= len_; }
  [[nodiscard]] std::size_t pos() const { return pos_; }
  [[nodiscard]] std::size_t len() const { return len_; }

  template <class T>
  T take() {
    const T v = load_le<T>(base_ + pos_);
    pos_ += sizeof(T);
    return v;
  }

  std::string take_cstr(std::size_t width) {
    const std::uint8_t* p = base_ + pos_;
    std::size_t n = 0;
    while (n < width && p[n] != 0u) {
      ++n;
    }
    pos_ += width;
    return std::string(reinterpret_cast<const char*>(p), n);
  }

  void skip(std::size_t n) { pos_ += n; }

 private:
  const std::uint8_t* base_;
  std::size_t len_;
  std::size_t pos_ = 0;
};

/// Record types that carry no book levels and may legitimately share an mbp-1
/// batch stream: Status (0x12), Error (0x15), SymbolMapping (0x16),
/// System (0x17). Measured on this corpus: SI 2024-06-03 decodes as
/// 1 Metadata + 951,739 Mbp1Msg and nothing else.
[[nodiscard]] bool is_benign_skippable(std::uint8_t rtype) {
  return rtype == 0x12u || rtype == 0x15u || rtype == 0x16u || rtype == 0x17u;
}

Refusal short_frame(const char* what) {
  return Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::parse_metadata_frame", what);
}

Expected<std::vector<std::string>, Refusal> take_symbol_list(Cursor& cur, std::size_t width,
                                                             const char* what) {
  if (!cur.have(sizeof(std::uint32_t))) {
    return refuse<std::vector<std::string>>(short_frame(what));
  }
  const std::uint32_t n = cur.take<std::uint32_t>();
  std::vector<std::string> out;
  out.reserve(n);
  for (std::uint32_t i = 0; i < n; ++i) {
    if (!cur.have(width)) {
      return refuse<std::vector<std::string>>(short_frame(what));
    }
    out.push_back(cur.take_cstr(width));
  }
  return out;
}

}  // namespace

// ---------------------------------------------------------------- metadata --
Expected<Metadata, Refusal> parse_metadata_frame(std::uint8_t version, const std::uint8_t* body,
                                                 std::size_t len) {
  if (version != kSupportedVersion) {
    // Refuse by name. A guessed layout for an unverified version would decode
    // into plausible-looking numbers, which is worse than stopping.
    return refuse<Metadata>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::parse_metadata_frame",
                                    "unsupported DBN stream version (only v1 is byte-verified)",
                                    static_cast<std::int64_t>(version)));
  }
  Cursor cur(body, len);
  if (!cur.have(kV1FixedLen)) {
    return refuse<Metadata>(short_frame("metadata frame shorter than the fixed v1 header"));
  }
  Metadata md;
  md.version = version;
  md.dataset = cur.take_cstr(16);
  md.schema = cur.take<std::uint16_t>();
  md.start = cur.take<std::uint64_t>();
  md.end = cur.take<std::uint64_t>();
  md.limit = cur.take<std::uint64_t>();
  cur.skip(sizeof(std::uint64_t));  // v1 record_count, deprecated (u64::MAX = none)
  md.stype_in = cur.take<std::uint8_t>();
  md.stype_out = cur.take<std::uint8_t>();
  md.ts_out = cur.take<std::uint8_t>();
  cur.skip(kV1ReservedLen);

  if (md.schema != kSchemaMbp1) {
    return refuse<Metadata>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_dbn::parse_metadata_frame",
                                    "payload is not the mbp-1 schema",
                                    static_cast<std::int64_t>(md.schema)));
  }

  const std::uint32_t schema_def_len = cur.take<std::uint32_t>();
  if (schema_def_len != 0u) {
    return refuse<Metadata>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_dbn::parse_metadata_frame",
                                    "non-empty schema definition block is not supported",
                                    static_cast<std::int64_t>(schema_def_len)));
  }

  const std::size_t width = kSymbolCstrLenV1;
  auto symbols = take_symbol_list(cur, width, "truncated symbols block");
  if (!symbols) {
    return refuse<Metadata>(symbols.error());
  }
  md.symbols = std::move(symbols).value();
  auto partial = take_symbol_list(cur, width, "truncated partial block");
  if (!partial) {
    return refuse<Metadata>(partial.error());
  }
  md.partial = std::move(partial).value();
  auto not_found = take_symbol_list(cur, width, "truncated not_found block");
  if (!not_found) {
    return refuse<Metadata>(not_found.error());
  }
  md.not_found = std::move(not_found).value();

  if (!cur.have(sizeof(std::uint32_t))) {
    return refuse<Metadata>(short_frame("truncated mappings count"));
  }
  const std::uint32_t n_map = cur.take<std::uint32_t>();
  md.mappings.reserve(n_map);
  for (std::uint32_t i = 0; i < n_map; ++i) {
    if (!cur.have(width + sizeof(std::uint32_t))) {
      return refuse<Metadata>(short_frame("truncated mapping row"));
    }
    SymbolMapping row;
    row.raw_symbol = cur.take_cstr(width);
    const std::uint32_t n_iv = cur.take<std::uint32_t>();
    row.intervals.reserve(n_iv);
    for (std::uint32_t j = 0; j < n_iv; ++j) {
      if (!cur.have(2 * sizeof(std::uint32_t) + width)) {
        return refuse<Metadata>(short_frame("truncated mapping interval"));
      }
      MappingInterval iv;
      iv.start_date = static_cast<std::int32_t>(cur.take<std::uint32_t>());
      iv.end_date = static_cast<std::int32_t>(cur.take<std::uint32_t>());
      iv.symbol = cur.take_cstr(width);
      row.intervals.push_back(std::move(iv));
    }
    md.mappings.push_back(std::move(row));
  }

  // THE STRUCTURAL GUARD. A layout error anywhere above lands the cursor off
  // the end of the declared frame; an exact landing is strong evidence the
  // whole geometry is right. Any leftover or overrun is a refusal.
  if (cur.pos() != cur.len()) {
    return refuse<Metadata>(Refusal(RefusalCode::CONTENT_MISMATCH, "qr_dbn::parse_metadata_frame",
                                    "metadata parse did not consume the declared frame exactly",
                                    static_cast<std::int64_t>(cur.len()) -
                                        static_cast<std::int64_t>(cur.pos())));
  }
  return md;
}

// ------------------------------------------------------------ SymbolIndex ---
void SymbolIndex::build(const Metadata& md) {
  entries_.clear();
  for (const SymbolMapping& row : md.mappings) {
    for (const MappingInterval& iv : row.intervals) {
      if (iv.symbol.empty()) {
        continue;
      }
      // The mapped-to side is the instrument id as decimal text. Anything else
      // is skipped, exactly as M0 `invert_mappings` skips a non-int symbol.
      std::uint64_t iid = 0;
      bool numeric = true;
      for (const char ch : iv.symbol) {
        if (ch < '0' || ch > '9') {
          numeric = false;
          break;
        }
        iid = iid * 10u + static_cast<std::uint64_t>(ch - '0');
        if (iid > 0xFFFFFFFFull) {
          numeric = false;
          break;
        }
      }
      if (!numeric) {
        continue;
      }
      entries_.push_back(Entry{static_cast<std::uint32_t>(iid), iv.start_date, iv.end_date,
                               row.raw_symbol});
    }
  }
  // M0 sorts each id's interval list by (start_date, end_date, raw_symbol).
  std::stable_sort(entries_.begin(), entries_.end(), [](const Entry& a, const Entry& b) {
    if (a.iid != b.iid) {
      return a.iid < b.iid;
    }
    if (a.start_date != b.start_date) {
      return a.start_date < b.start_date;
    }
    if (a.end_date != b.end_date) {
      return a.end_date < b.end_date;
    }
    return a.raw_symbol < b.raw_symbol;
  });
}

const std::string& SymbolIndex::symbol_for(std::uint32_t iid, std::int32_t yyyymmdd) const {
  static const std::string kEmpty;
  const auto lo = std::lower_bound(entries_.begin(), entries_.end(), iid,
                                   [](const Entry& e, std::uint32_t v) { return e.iid < v; });
  auto hi = lo;
  while (hi != entries_.end() && hi->iid == iid) {
    ++hi;
  }
  if (lo == hi) {
    return kEmpty;
  }
  for (auto it = lo; it != hi; ++it) {
    if (it->start_date <= yyyymmdd && yyyymmdd < it->end_date) {
      return it->raw_symbol;
    }
  }
  return lo->raw_symbol;  // M0 fallback: the first interval's raw symbol
}

bool SymbolIndex::is_outright(const std::string& raw_symbol) {
  return !raw_symbol.empty() && raw_symbol.find('-') == std::string::npos;
}

// -------------------------------------------------------------- DbnStream ---
Expected<std::size_t, Refusal> DbnStream::ensure(std::size_t want) {
  if (tail_ - head_ >= want) {
    return tail_ - head_;
  }
  if (head_ > 0) {
    const std::size_t keep = tail_ - head_;
    if (keep > 0) {
      std::memmove(buf_.data(), buf_.data() + head_, keep);
    }
    head_ = 0;
    tail_ = keep;
  }
  if (buf_.size() < want) {
    buf_.resize(want);
  }
  while (tail_ < want) {
    auto got = zs_.read(buf_.data() + tail_, buf_.size() - tail_);
    if (!got) {
      return refuse<std::size_t>(got.error());
    }
    const std::size_t n = got.value();
    if (n == 0) {
      break;  // clean end of stream
    }
    tail_ += n;
  }
  return tail_ - head_;
}

Expected<std::monostate, Refusal> DbnStream::open(const std::string& path) {
  path_ = path;
  head_ = 0;
  tail_ = 0;
  n_skipped_ = 0;
  n_mbp1_ = 0;
  buf_.assign(kOutChunk, 0u);
  auto opened = zs_.open(path);
  if (!opened) {
    return opened;
  }

  auto pre = ensure(8);
  if (!pre) {
    return refuse<std::monostate>(pre.error());
  }
  if (pre.value() < 8) {
    return refuse<std::monostate>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::DbnStream::open",
                                          "stream ends before the DBN magic"));
  }
  const std::uint8_t* p = buf_.data() + head_;
  if (p[0] != 'D' || p[1] != 'B' || p[2] != 'N') {
    return refuse<std::monostate>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::DbnStream::open",
                                          "payload does not start with the DBN magic"));
  }
  const std::uint8_t version = p[3];
  const std::uint32_t frame_len = load_le<std::uint32_t>(p + 4);
  head_ += 8;

  auto body = ensure(frame_len);
  if (!body) {
    return refuse<std::monostate>(body.error());
  }
  if (body.value() < frame_len) {
    return refuse<std::monostate>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::DbnStream::open",
                                          "metadata frame is truncated",
                                          static_cast<std::int64_t>(frame_len)));
  }
  auto md = parse_metadata_frame(version, buf_.data() + head_, frame_len);
  if (!md) {
    return refuse<std::monostate>(md.error());
  }
  head_ += frame_len;
  metadata_ = std::move(md).value();
  return std::monostate{};
}

Expected<const Mbp1Msg*, Refusal> DbnStream::next_mbp1() {
  for (;;) {
    auto avail = ensure(sizeof(RecordHeader));
    if (!avail) {
      return refuse<const Mbp1Msg*>(avail.error());
    }
    if (avail.value() == 0) {
      return static_cast<const Mbp1Msg*>(nullptr);  // clean end of stream
    }
    if (avail.value() < sizeof(RecordHeader)) {
      return refuse<const Mbp1Msg*>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::DbnStream::next",
                                            "trailing bytes are shorter than a record header",
                                            static_cast<std::int64_t>(avail.value())));
    }
    const std::uint8_t* p = buf_.data() + head_;
    const std::size_t rec_len = static_cast<std::size_t>(p[0]) * kLengthUnit;
    const std::uint8_t rtype = p[1];
    // GUARD: a zero/short length byte would make the stream walk in place or
    // step into the middle of the next record. Refuse; never resynchronise.
    if (rec_len < sizeof(RecordHeader)) {
      return refuse<const Mbp1Msg*>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::DbnStream::next",
                                            "record length field is shorter than a record header",
                                            static_cast<std::int64_t>(rec_len)));
    }
    // GUARD: mbp-1 records are fixed-size. A different length under rtype 1 is
    // a corrupt or misaligned stream, not a variant to be tolerated.
    if (rtype == kRTypeMbp1 && rec_len != sizeof(Mbp1Msg)) {
      return refuse<const Mbp1Msg*>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::DbnStream::next",
                                            "Mbp1 record length is not 80 bytes",
                                            static_cast<std::int64_t>(rec_len)));
    }
    auto full = ensure(rec_len);
    if (!full) {
      return refuse<const Mbp1Msg*>(full.error());
    }
    if (full.value() < rec_len) {
      return refuse<const Mbp1Msg*>(Refusal(RefusalCode::DECODE_FAILED, "qr_dbn::DbnStream::next",
                                            "stream ends inside a record",
                                            static_cast<std::int64_t>(rec_len)));
    }
    const std::uint8_t* rec = buf_.data() + head_;
    head_ += rec_len;
    if (rtype != kRTypeMbp1) {
      // GUARD: only the level-less record types that may legitimately share an
      // mbp-1 batch stream are stepped over (M0 skips them with `if not lv`).
      // An unknown rtype means the framing is not what we think it is, and
      // stepping over it would resynchronise the reader onto garbage — a second
      // concatenated DBN header lands here as rtype 'B'.
      if (!is_benign_skippable(rtype)) {
        return refuse<const Mbp1Msg*>(Refusal(RefusalCode::DECODE_FAILED,
                                              "qr_dbn::DbnStream::next",
                                              "unknown record type in an mbp-1 stream",
                                              static_cast<std::int64_t>(rtype)));
      }
      ++n_skipped_;
      continue;
    }
    ++n_mbp1_;
    // The buffer is a std::vector<std::uint8_t>, whose data is suitably aligned
    // for the 8-byte members only when the record offset happens to be aligned;
    // records are 80 bytes and the metadata frame length is arbitrary, so copy
    // into a properly aligned scratch object rather than casting.
    std::memcpy(&scratch_, rec, sizeof(Mbp1Msg));
    return static_cast<const Mbp1Msg*>(&scratch_);
  }
}

}  // namespace qr::dbn
