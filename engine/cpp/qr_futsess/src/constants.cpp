#include "qr_futsess/constants.hpp"

namespace qr::futsess {
namespace {

// PORT_M0_CENSUS_SPEC §1 / engine/port_m0/common.py:54-97. Pre-registered; the
// spec's own words: "never tuned after numbers are seen".
constexpr AssetSpec kSpecs[] = {
    {"SI", 5000, 1e-9, 25.00, 20.0, 40.0, "[Silver] GLBX-20260531-RPHWMFRBFW", true},
    {"HG", 25000, 1e-9, 12.50, 3.0, 6.0, "[Copper] GLBX-20260606-NC7JE46DYS", false},
    {"NKD", 5, 1e-9, 25.00, 25000.0, 45000.0, "[NKD] GLBX-20260601-3F35RY4L5X", false},
};

}  // namespace

const AssetSpec& asset_spec(Asset a) { return kSpecs[static_cast<std::size_t>(a)]; }

bool asset_from_name(const std::string& name, Asset* out) {
  for (std::size_t i = 0; i < sizeof(kSpecs) / sizeof(kSpecs[0]); ++i) {
    if (name == kSpecs[i].name) {
      *out = static_cast<Asset>(i);
      return true;
    }
  }
  return false;
}

}  // namespace qr::futsess
