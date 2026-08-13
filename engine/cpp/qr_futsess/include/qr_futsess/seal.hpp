// qr_futsess/seal.hpp — the 2026 SEAL, a hard wall on payload filenames.
//
// SPEC: design/PORT_M0_CENSUS_SPEC.md §0 — "never open any payload file whose
// filename dates touch 2026 ... Every script hard-refuses by filename test
// `date_component >= 20260101` and logs the refused list."
//
// The test reads the BASENAME only, never the directory: the asset directories
// themselves carry 2026 job dates ("[Silver] GLBX-20260531-RPHWMFRBFW") and
// testing the full path would refuse the entire corpus.
#ifndef QR_FUTSESS_SEAL_HPP
#define QR_FUTSESS_SEAL_HPP

#include <string>
#include <vector>

#include "qr_core/refusal.hpp"

namespace qr::futsess {

/// Every maximal 8-digit run in the basename (M0 `common.filename_dates`).
/// A run of digits longer than 8 is NOT a date and yields nothing.
[[nodiscard]] std::vector<int> filename_dates(const std::string& path);

/// True when any basename date component is 2026 or later.
[[nodiscard]] bool is_sealed(const std::string& path);

/// Hard wall. Refuses a sealed path; appends its basename to `refusals` so the
/// refused list can be logged as the spec requires.
[[nodiscard]] Expected<std::monostate, Refusal> guard_seal(const std::string& path,
                                                           std::vector<std::string>* refusals);

}  // namespace qr::futsess

#endif  // QR_FUTSESS_SEAL_HPP
