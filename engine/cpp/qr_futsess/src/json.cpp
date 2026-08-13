#include "qr_futsess/json.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace qr::futsess {
namespace {

class Parser {
 public:
  Parser(const char* p, std::size_t n) : p_(p), n_(n) {}

  Expected<Json, Refusal> parse_document() {
    skip_ws();
    auto v = parse_value(0);
    if (!v) {
      return v;
    }
    skip_ws();
    if (i_ != n_) {
      return refuse<Json>(bad("trailing bytes after the JSON document"));
    }
    return v;
  }

 private:
  static Refusal bad(const char* what) {
    return Refusal(RefusalCode::DECODE_FAILED, "qr_futsess::json_parse", what);
  }

  void skip_ws() {
    while (i_ < n_ && (p_[i_] == ' ' || p_[i_] == '\t' || p_[i_] == '\n' || p_[i_] == '\r')) {
      ++i_;
    }
  }

  bool literal(const char* s) {
    const std::size_t len = std::strlen(s);
    if (i_ + len <= n_ && std::memcmp(p_ + i_, s, len) == 0) {
      i_ += len;
      return true;
    }
    return false;
  }

  Expected<Json, Refusal> parse_value(int depth) {
    if (depth > 64) {
      return refuse<Json>(bad("JSON nesting is deeper than this reader allows"));
    }
    if (i_ >= n_) {
      return refuse<Json>(bad("unexpected end of JSON"));
    }
    const char c = p_[i_];
    if (c == '{') {
      return parse_object(depth);
    }
    if (c == '[') {
      return parse_array(depth);
    }
    if (c == '"') {
      Json j;
      auto s = parse_string();
      if (!s) {
        return refuse<Json>(s.error());
      }
      j.set_string(std::move(s).value());
      return j;
    }
    Json j;
    if (literal("null")) {
      j.set_null();
      return j;
    }
    if (literal("true")) {
      j.set_bool(true);
      return j;
    }
    if (literal("false")) {
      j.set_bool(false);
      return j;
    }
    // Python's json emits these bare literals for non-finite floats and the
    // reference receipts contain them.
    if (literal("NaN")) {
      j.set_number(std::nan(""));
      return j;
    }
    if (literal("-Infinity")) {
      j.set_number(-HUGE_VAL);
      return j;
    }
    if (literal("Infinity")) {
      j.set_number(HUGE_VAL);
      return j;
    }
    const char* start = p_ + i_;
    char* endp = nullptr;
    const double v = std::strtod(start, &endp);
    if (endp == start) {
      return refuse<Json>(bad("not a JSON value"));
    }
    i_ += static_cast<std::size_t>(endp - start);
    j.set_number(v);
    return j;
  }

  /// Read exactly four hex digits into `out`.
  bool hex4(unsigned& out) {
    if (i_ + 4 > n_) {
      return false;
    }
    unsigned code = 0;
    for (int k = 0; k < 4; ++k) {
      const char h = p_[i_ + static_cast<std::size_t>(k)];
      unsigned d = 0;
      if (h >= '0' && h <= '9') {
        d = static_cast<unsigned>(h - '0');
      } else if (h >= 'a' && h <= 'f') {
        d = static_cast<unsigned>(h - 'a') + 10u;
      } else if (h >= 'A' && h <= 'F') {
        d = static_cast<unsigned>(h - 'A') + 10u;
      } else {
        return false;
      }
      code = code * 16u + d;
    }
    i_ += 4;
    out = code;
    return true;
  }

  static void append_utf8(std::string& out, unsigned cp) {
    if (cp < 0x80u) {
      out.push_back(static_cast<char>(cp));
    } else if (cp < 0x800u) {
      out.push_back(static_cast<char>(0xC0u | (cp >> 6)));
      out.push_back(static_cast<char>(0x80u | (cp & 0x3Fu)));
    } else if (cp < 0x10000u) {
      out.push_back(static_cast<char>(0xE0u | (cp >> 12)));
      out.push_back(static_cast<char>(0x80u | ((cp >> 6) & 0x3Fu)));
      out.push_back(static_cast<char>(0x80u | (cp & 0x3Fu)));
    } else {
      out.push_back(static_cast<char>(0xF0u | (cp >> 18)));
      out.push_back(static_cast<char>(0x80u | ((cp >> 12) & 0x3Fu)));
      out.push_back(static_cast<char>(0x80u | ((cp >> 6) & 0x3Fu)));
      out.push_back(static_cast<char>(0x80u | (cp & 0x3Fu)));
    }
  }

  Expected<std::string, Refusal> parse_string() {
    ++i_;  // opening quote
    std::string out;
    while (i_ < n_) {
      const char c = p_[i_++];
      if (c == '"') {
        return out;
      }
      if (c != '\\') {
        out.push_back(c);
        continue;
      }
      if (i_ >= n_) {
        break;
      }
      const char e = p_[i_++];
      switch (e) {
        case '"': out.push_back('"'); break;
        case '\\': out.push_back('\\'); break;
        case '/': out.push_back('/'); break;
        case 'b': out.push_back('\b'); break;
        case 'f': out.push_back('\f'); break;
        case 'n': out.push_back('\n'); break;
        case 'r': out.push_back('\r'); break;
        case 't': out.push_back('\t'); break;
        case 'u': {
          // The frozen m0 receipts carry § (the section sign) in their
          // spec_section strings, so this must be real, not a stub.
          unsigned code = 0;
          if (!hex4(code)) {
            return refuse<std::string>(bad("bad or truncated \\u escape"));
          }
          if (code >= 0xD800u && code <= 0xDBFFu) {
            unsigned low = 0;
            if (i_ + 2 > n_ || p_[i_] != '\\' || p_[i_ + 1] != 'u') {
              return refuse<std::string>(bad("high surrogate without a low surrogate"));
            }
            i_ += 2;
            if (!hex4(low) || low < 0xDC00u || low > 0xDFFFu) {
              return refuse<std::string>(bad("malformed surrogate pair"));
            }
            code = 0x10000u + ((code - 0xD800u) << 10) + (low - 0xDC00u);
          } else if (code >= 0xDC00u && code <= 0xDFFFu) {
            return refuse<std::string>(bad("lone low surrogate"));
          }
          append_utf8(out, code);
          break;
        }
        default:
          return refuse<std::string>(bad("unknown string escape"));
      }
    }
    return refuse<std::string>(bad("unterminated string"));
  }

  Expected<Json, Refusal> parse_array(int depth) {
    Json j;
    j.set_array();
    ++i_;
    skip_ws();
    if (i_ < n_ && p_[i_] == ']') {
      ++i_;
      return j;
    }
    for (;;) {
      skip_ws();
      auto v = parse_value(depth + 1);
      if (!v) {
        return v;
      }
      j.push_item(std::move(v).value());
      skip_ws();
      if (i_ < n_ && p_[i_] == ',') {
        ++i_;
        continue;
      }
      if (i_ < n_ && p_[i_] == ']') {
        ++i_;
        return j;
      }
      return refuse<Json>(bad("expected ',' or ']' in array"));
    }
  }

  Expected<Json, Refusal> parse_object(int depth) {
    Json j;
    j.set_object();
    ++i_;
    skip_ws();
    if (i_ < n_ && p_[i_] == '}') {
      ++i_;
      return j;
    }
    for (;;) {
      skip_ws();
      if (i_ >= n_ || p_[i_] != '"') {
        return refuse<Json>(bad("expected a string key in object"));
      }
      auto k = parse_string();
      if (!k) {
        return refuse<Json>(k.error());
      }
      skip_ws();
      if (i_ >= n_ || p_[i_] != ':') {
        return refuse<Json>(bad("expected ':' after object key"));
      }
      ++i_;
      skip_ws();
      auto v = parse_value(depth + 1);
      if (!v) {
        return v;
      }
      j.put_field(std::move(k).value(), std::move(v).value());
      skip_ws();
      if (i_ < n_ && p_[i_] == ',') {
        ++i_;
        continue;
      }
      if (i_ < n_ && p_[i_] == '}') {
        ++i_;
        return j;
      }
      return refuse<Json>(bad("expected ',' or '}' in object"));
    }
  }

  const char* p_;
  std::size_t n_;
  std::size_t i_ = 0;
};

}  // namespace

void Json::set_null() { type_ = Type::Null; }
void Json::set_bool(bool v) {
  type_ = Type::Bool;
  num_ = v ? 1.0 : 0.0;
}
void Json::set_number(double v) {
  type_ = Type::Number;
  num_ = v;
}
void Json::set_string(std::string v) {
  type_ = Type::String;
  str_ = std::move(v);
}
void Json::set_array() { type_ = Type::Array; }
void Json::set_object() { type_ = Type::Object; }
void Json::push_item(Json v) { items_.push_back(std::move(v)); }
void Json::put_field(std::string k, Json v) { fields_.emplace(std::move(k), std::move(v)); }

const Json* Json::find(const std::string& key) const {
  const auto it = fields_.find(key);
  return it == fields_.end() ? nullptr : &it->second;
}

Expected<Json, Refusal> json_parse(const std::string& text) {
  Parser p(text.data(), text.size());
  return p.parse_document();
}

Expected<Json, Refusal> json_parse_file(const std::string& path) {
  std::FILE* fh = std::fopen(path.c_str(), "rb");
  if (fh == nullptr) {
    return refuse<Json>(
        Refusal(RefusalCode::IO, "qr_futsess::json_parse_file", "cannot open JSON file"));
  }
  std::string text;
  char chunk[1 << 16];
  for (;;) {
    const std::size_t n = std::fread(chunk, 1, sizeof(chunk), fh);
    if (n == 0) {
      break;
    }
    text.append(chunk, n);
  }
  std::fclose(fh);
  return json_parse(text);
}

// --------------------------------------------------------------- writer -----
void JsonWriter::comma() {
  // A value that follows a key is not a new member: the key already claimed
  // this slot's separator.
  if (pending_key_) {
    pending_key_ = false;
    return;
  }
  if (!counts_.empty()) {
    if (counts_.back() > 0) {
      out_ += ',';
    }
    ++counts_.back();
  }
}

void JsonWriter::begin_object() {
  comma();
  out_ += '{';
  counts_.push_back(0);
}
void JsonWriter::end_object() {
  out_ += '}';
  counts_.pop_back();
}
void JsonWriter::begin_array() {
  comma();
  out_ += '[';
  counts_.push_back(0);
}
void JsonWriter::end_array() {
  out_ += ']';
  counts_.pop_back();
}

void JsonWriter::key(const std::string& k) {
  comma();
  out_ += '"';
  for (const char c : k) {
    if (c == '"' || c == '\\') {
      out_ += '\\';
    }
    out_ += c;
  }
  out_ += "\":";
  pending_key_ = true;
}

void JsonWriter::value_null() {
  comma();
  out_ += "null";
}
void JsonWriter::value_bool(bool v) {
  comma();
  out_ += v ? "true" : "false";
}
void JsonWriter::value_int(std::int64_t v) {
  comma();
  out_ += std::to_string(v);
}

void JsonWriter::value_double(double v) {
  comma();
  if (std::isnan(v)) {
    out_ += "NaN";
    return;
  }
  if (std::isinf(v)) {
    out_ += (v > 0) ? "Infinity" : "-Infinity";
    return;
  }
  char buf[40];
  std::snprintf(buf, sizeof(buf), "%.17g", v);
  out_ += buf;
}

void JsonWriter::value_string(const std::string& v) {
  comma();
  out_ += '"';
  for (const char c : v) {
    if (c == '"' || c == '\\') {
      out_ += '\\';
      out_ += c;
    } else if (static_cast<unsigned char>(c) < 0x20u) {
      char buf[8];
      std::snprintf(buf, sizeof(buf), "\\u%04x", static_cast<unsigned>(c));
      out_ += buf;
    } else {
      out_ += c;
    }
  }
  out_ += '"';
}

}  // namespace qr::futsess
