// qr_futsess/json.hpp — a minimal JSON reader (for the FROZEN m0 phase tables)
// and a deterministic writer (for the session sidecars).
//
// Scope is deliberately small: this parses the receipts this repository itself
// wrote, and it refuses anything it does not fully understand rather than
// guessing. It is not a general-purpose JSON library.
#ifndef QR_FUTSESS_JSON_HPP
#define QR_FUTSESS_JSON_HPP

#include <cstdint>
#include <map>
#include <memory>
#include <string>
#include <vector>

#include "qr_core/refusal.hpp"

namespace qr::futsess {

class Json {
 public:
  enum class Type : std::uint8_t { Null, Bool, Number, String, Array, Object };

  [[nodiscard]] Type type() const { return type_; }
  [[nodiscard]] bool is_null() const { return type_ == Type::Null; }
  [[nodiscard]] double number() const { return num_; }
  [[nodiscard]] bool boolean() const { return num_ != 0.0; }
  [[nodiscard]] const std::string& str() const { return str_; }
  [[nodiscard]] const std::vector<Json>& items() const { return items_; }
  [[nodiscard]] const std::map<std::string, Json>& fields() const { return fields_; }
  /// Member of an object, or nullptr.
  [[nodiscard]] const Json* find(const std::string& key) const;

  // Builders, used by the parser (and by fixtures that construct a document
  // directly). Kept explicit rather than exposing the members.
  void set_null();
  void set_bool(bool v);
  void set_number(double v);
  void set_string(std::string v);
  void set_array();
  void set_object();
  void push_item(Json v);
  void put_field(std::string k, Json v);

 private:
  Type type_ = Type::Null;
  double num_ = 0.0;
  std::string str_;
  std::vector<Json> items_;
  std::map<std::string, Json> fields_;  // ordered: iteration is deterministic
};

[[nodiscard]] Expected<Json, Refusal> json_parse(const std::string& text);
[[nodiscard]] Expected<Json, Refusal> json_parse_file(const std::string& path);

/// Deterministic JSON emitter. Members are written in call order; the caller
/// controls the order, so two runs emit byte-identical text.
class JsonWriter {
 public:
  void begin_object();
  void end_object();
  void begin_array();
  void end_array();
  void key(const std::string& k);
  void value_null();
  void value_bool(bool v);
  void value_int(std::int64_t v);
  /// Emitted with %.17g, which round-trips every finite IEEE-754 double
  /// exactly. Non-finite values are emitted as the Python json literals
  /// NaN / Infinity / -Infinity, which is what the reference receipts carry.
  void value_double(double v);
  void value_string(const std::string& v);

  [[nodiscard]] const std::string& text() const { return out_; }

 private:
  void comma();
  std::string out_;
  std::vector<int> counts_;
  bool pending_key_ = false;
};

}  // namespace qr::futsess

#endif  // QR_FUTSESS_JSON_HPP
