// Shared test support for the qr_sources suite.
//
// The fixture trees mirror the corpus layout, so every reader under test forms
// its path the only lawful way: from an ADMITTED DayScope.
#ifndef QR_SOURCES_TESTS_FIXTURE_SUPPORT_HPP
#define QR_SOURCES_TESTS_FIXTURE_SUPPORT_HPP

#include <gtest/gtest.h>

#include <filesystem>
#include <fstream>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

#include "qr_registry/day_scope.hpp"
#include "qr_registry/registry.hpp"

namespace qr::sources::testing {

/// Session 125 = 2022-07-05, the ordinal every WP4 fixture is written against
/// and the one session this work package is authorized to read for real.
inline constexpr std::int64_t kSession125 = 125;
inline constexpr const char* kSession125Day = "2022-07-05";

inline const qr::Registry* registry_or_null() {
  static qr::Expected<qr::Registry, qr::Refusal> loaded = qr::Registry::load_embedded();
  return loaded.has_value() ? &loaded.value() : nullptr;
}

/// The admitted scope for session 125, or nullopt when the registry or the
/// wall refused (which a test must report as a FAILURE, never as a skip).
inline std::optional<qr::DayScope> scope_125() {
  const qr::Registry* const registry = registry_or_null();
  if (registry == nullptr) {
    return std::nullopt;
  }
  qr::Expected<qr::DayScope, qr::Refusal> scope = qr::DayScope::admit(*registry, kSession125);
  if (!scope.has_value()) {
    return std::nullopt;
  }
  return scope.value();
}

/// Root of one fixture tree, e.g. `fixture_root("sq_cent")`.
inline std::filesystem::path fixture_root(const std::string& tree) {
  return std::filesystem::path(QR_SOURCES_FIXTURE_DIR) / tree;
}

/// The generator-derived literals, keyed "<stream>/<key>/<field>".
using Literals = std::map<std::string, std::string>;

inline const Literals& literals() {
  static const Literals table = [] {
    Literals out;
    std::ifstream input(QR_SOURCES_EXPECTED_LITERALS);
    std::string line;
    while (std::getline(input, line)) {
      if (line.empty() || line[0] == '#') {
        continue;
      }
      std::vector<std::string> fields;
      std::string field;
      std::istringstream stream(line);
      while (std::getline(stream, field, '\t')) {
        fields.push_back(field);
      }
      if (fields.size() != 4 || fields[0] == "stream") {
        continue;
      }
      out[fields[0] + "/" + fields[1] + "/" + fields[2]] = fields[3];
    }
    return out;
  }();
  return table;
}

inline std::string literal_text(const std::string& key) {
  const Literals& table = literals();
  const auto found = table.find(key);
  EXPECT_NE(found, table.end()) << "expected literal missing: " << key;
  return found == table.end() ? std::string() : found->second;
}

inline std::int64_t literal_int(const std::string& key) {
  const std::string text = literal_text(key);
  return text.empty() ? -1 : std::strtoll(text.c_str(), nullptr, 10);
}

}  // namespace qr::sources::testing

#endif  // QR_SOURCES_TESTS_FIXTURE_SUPPORT_HPP
