// qr_ivx/tsv.hpp — the census emitter this module shares.
//
// It is `qr::w20::CensusReport`'s shape — (scope, key, metric, value) rows in
// INSERTION order — with one addition the IV work needs and the W2.0 censuses
// did not: a REAL column. Every number the W2.0 censuses emit is an exact
// integer count; a skew slope is not.
//
// It is a separate type rather than a field on `CensusReport` for a wall
// reason, not a style one: `qr_w20` links `qr_sources`, and the CC-013 column
// census must be linkable WITHOUT the option-print reader in the binary at all
// (see column_census.hpp). One 90-line writer buys that separation.
//
// TWO-RUN IDENTITY. `%.17g` round-trips every finite double exactly, and the
// three non-finite forms are emitted as their own tokens rather than as
// libc-dependent text ("nan" vs "-nan" vs "NAN" differs between platforms and
// would break byte identity across a compiler change).
#ifndef QR_IVX_TSV_HPP
#define QR_IVX_TSV_HPP

#include <cstdint>
#include <filesystem>
#include <string>
#include <variant>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_core/validity.hpp"

namespace qr::ivx {

using qr::Expected;
using qr::Refusal;
using qr::RefusalCode;
using qr::Typed;
using qr::Validity;

/// `%.17g` of a finite double; `NAN`, `INF`, `-INF` otherwise.
[[nodiscard]] std::string g17(double value);

struct Row {
  std::string scope;
  std::string key;
  std::string metric;
  std::string value;
};

class Report {
 public:
  void metric(std::string scope, std::string key, std::string name, std::int64_t value);
  void real(std::string scope, std::string key, std::string name, double value);
  void text(std::string scope, std::string key, std::string name, std::string value);
  /// A typed real: the value column carries `%.17g` when VALID and the
  /// validity NAME otherwise, so an absent channel can never be read as a
  /// number. A companion `<name>_v` row always carries the state.
  void typed(std::string scope, std::string key, std::string name, Typed<double> value);

  [[nodiscard]] const std::vector<Row>& rows() const noexcept { return rows_; }
  [[nodiscard]] Expected<std::monostate, Refusal> write(const std::filesystem::path& path) const;

 private:
  std::vector<Row> rows_;
};

}  // namespace qr::ivx

#endif  // QR_IVX_TSV_HPP
