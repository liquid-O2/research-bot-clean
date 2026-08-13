#include "qr_futsess/seal.hpp"

#include <cctype>

#include "qr_futsess/constants.hpp"

namespace qr::futsess {
namespace {

std::string basename_of(const std::string& path) {
  const std::size_t slash = path.find_last_of('/');
  return slash == std::string::npos ? path : path.substr(slash + 1);
}

bool is_digit(char c) { return c >= '0' && c <= '9'; }

}  // namespace

std::vector<int> filename_dates(const std::string& path) {
  // Port of common.py's `(?<!\d)(\d{8})(?!\d)`: a run of EXACTLY eight digits,
  // not adjacent to another digit on either side.
  const std::string base = basename_of(path);
  std::vector<int> out;
  std::size_t i = 0;
  while (i < base.size()) {
    if (!is_digit(base[i])) {
      ++i;
      continue;
    }
    std::size_t j = i;
    while (j < base.size() && is_digit(base[j])) {
      ++j;
    }
    if (j - i == 8) {
      int v = 0;
      for (std::size_t k = i; k < j; ++k) {
        v = v * 10 + (base[k] - '0');
      }
      out.push_back(v);
    }
    i = j;
  }
  return out;
}

bool is_sealed(const std::string& path) {
  for (const int d : filename_dates(path)) {
    if (d >= kSealCutoff) {
      return true;
    }
  }
  return false;
}

Expected<std::monostate, Refusal> guard_seal(const std::string& path,
                                             std::vector<std::string>* refusals) {
  if (is_sealed(path)) {
    if (refusals != nullptr) {
      refusals->push_back(basename_of(path));
    }
    return refuse<std::monostate>(Refusal(RefusalCode::DAY_OUTSIDE_CALENDAR,
                                          "qr_futsess::guard_seal",
                                          "SEAL: refusing a 2026-dated payload file"));
  }
  return std::monostate{};
}

}  // namespace qr::futsess
