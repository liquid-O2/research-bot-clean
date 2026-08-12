#include "qr_ivx/tsv.hpp"

#include <cmath>
#include <cstdio>
#include <utility>

namespace qr::ivx {

std::string g17(double value) {
  if (std::isnan(value)) {
    return "NAN";
  }
  if (std::isinf(value)) {
    return value > 0 ? "INF" : "-INF";
  }
  char buffer[40];
  const int written = std::snprintf(buffer, sizeof(buffer), "%.17g", value);
  if (written <= 0 || static_cast<std::size_t>(written) >= sizeof(buffer)) {
    return "NAN";  // unreachable for a finite double; never a truncated number.
  }
  return std::string(buffer, static_cast<std::size_t>(written));
}

void Report::metric(std::string scope, std::string key, std::string name, std::int64_t value) {
  rows_.push_back(Row{std::move(scope), std::move(key), std::move(name), std::to_string(value)});
}

void Report::real(std::string scope, std::string key, std::string name, double value) {
  rows_.push_back(Row{std::move(scope), std::move(key), std::move(name), g17(value)});
}

void Report::text(std::string scope, std::string key, std::string name, std::string value) {
  rows_.push_back(Row{std::move(scope), std::move(key), std::move(name), std::move(value)});
}

void Report::typed(std::string scope, std::string key, std::string name, Typed<double> value) {
  const bool ok = value.v == Validity::VALID;
  rows_.push_back(Row{scope, key, name, ok ? g17(value.value) : qr::validity_name(value.v)});
  rows_.push_back(
      Row{std::move(scope), std::move(key), name + "_v", qr::validity_name(value.v)});
}

Expected<std::monostate, Refusal> Report::write(const std::filesystem::path& path) const {
  std::FILE* out = std::fopen(path.c_str(), "wb");
  if (out == nullptr) {
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_ivx::Report", "cannot open the census output for writing"));
  }
  std::fprintf(out, "scope\tkey\tmetric\tvalue\n");
  for (const Row& row : rows_) {
    std::fprintf(out, "%s\t%s\t%s\t%s\n", row.scope.c_str(), row.key.c_str(), row.metric.c_str(),
                 row.value.c_str());
  }
  if (std::fclose(out) != 0) {
    return refuse<std::monostate>(
        Refusal(RefusalCode::IO, "qr_ivx::Report", "the census output did not close cleanly"));
  }
  return std::monostate{};
}

}  // namespace qr::ivx
