// qr_skel/binpack.hpp — the {JSON sidecar + flat little-endian .bin} receipt
// pair this repository already writes (qr_futsess QRSESS1) and this module
// both reads and writes (QRCAND1 input, QRSKEL1 output).
//
// The reader refuses anything it does not fully understand: an unknown format
// tag, an unknown dtype, an array whose [offset, offset + count*width) runs
// past the blob, a duplicate array name. Nothing is guessed and nothing is
// clamped.
#ifndef QR_SKEL_BINPACK_HPP
#define QR_SKEL_BINPACK_HPP

#include <cstdint>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_futsess/json.hpp"

namespace qr::skel {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;

struct PackedArray {
  std::string dtype;
  std::size_t count = 0;
  std::size_t offset = 0;
};

/// A loaded receipt pair. `blob` owns the .bin bytes; typed views borrow it.
class BinPack {
 public:
  [[nodiscard]] static Expected<BinPack, Refusal> load(const std::string& stem,
                                                       const std::string& expect_format);

  [[nodiscard]] const qr::futsess::Json& sidecar() const { return sidecar_; }
  [[nodiscard]] bool has(const std::string& name) const { return arrays_.count(name) != 0; }

  /// Typed view of one array. Refuses on a missing name or a dtype mismatch.
  template <class T>
  [[nodiscard]] Expected<std::vector<T>, Refusal> get(const std::string& name,
                                                      const char* dtype) const {
    const auto it = arrays_.find(name);
    if (it == arrays_.end()) {
      return refuse<std::vector<T>>(
          Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::BinPack::get", "no such array in receipt"));
    }
    if (it->second.dtype != dtype) {
      return refuse<std::vector<T>>(Refusal(RefusalCode::SCHEMA_MISMATCH, "qr_skel::BinPack::get",
                                            "array dtype is not the one the caller expects"));
    }
    std::vector<T> out(it->second.count);
    if (it->second.count != 0) {
      std::memcpy(out.data(), blob_.data() + it->second.offset, it->second.count * sizeof(T));
    }
    return out;
  }

 private:
  qr::futsess::Json sidecar_;
  std::vector<std::uint8_t> blob_;
  std::map<std::string, PackedArray> arrays_;  // ordered: deterministic iteration
};

/// Deterministic writer for the same pair. Arrays are emitted in call order.
class BinPackWriter {
 public:
  template <class T>
  void add(const std::string& name, const char* dtype, const std::vector<T>& v) {
    descs_.push_back(Desc{name, dtype, v.size(), bytes_.size()});
    const auto* p = reinterpret_cast<const std::uint8_t*>(v.data());
    bytes_.insert(bytes_.end(), p, p + v.size() * sizeof(T));
  }

  /// Emit `<stem>.bin` and `<stem>.json`. `extra` is invoked to write further
  /// sidecar members (after "arrays"), so the caller controls their order.
  template <class F>
  [[nodiscard]] Expected<std::monostate, Refusal> write(const std::string& stem,
                                                        const std::string& format,
                                                        F&& extra) const {
    qr::futsess::JsonWriter jw;
    jw.begin_object();
    jw.key("format");
    jw.value_string(format);
    jw.key("bin");
    jw.value_string(basename(stem) + ".bin");
    jw.key("arrays");
    jw.begin_array();
    for (const Desc& d : descs_) {
      jw.begin_object();
      jw.key("name");
      jw.value_string(d.name);
      jw.key("dtype");
      jw.value_string(d.dtype);
      jw.key("count");
      jw.value_int(static_cast<std::int64_t>(d.count));
      jw.key("offset");
      jw.value_int(static_cast<std::int64_t>(d.offset));
      jw.end_object();
    }
    jw.end_array();
    extra(jw);
    jw.end_object();
    return write_pair(stem, bytes_, jw.text());
  }

  [[nodiscard]] std::size_t byte_size() const { return bytes_.size(); }
  [[nodiscard]] std::size_t array_count() const { return descs_.size(); }

 private:
  struct Desc {
    std::string name;
    const char* dtype;
    std::size_t count;
    std::size_t offset;
  };
  static std::string basename(const std::string& stem);
  [[nodiscard]] static Expected<std::monostate, Refusal> write_pair(
      const std::string& stem, const std::vector<std::uint8_t>& bytes, const std::string& json);

  std::vector<Desc> descs_;
  std::vector<std::uint8_t> bytes_;
};

}  // namespace qr::skel

#endif  // QR_SKEL_BINPACK_HPP
