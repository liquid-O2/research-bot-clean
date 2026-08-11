// qr_carriers_nodestruct_probe — the production fingerprint of a carrier
// library compiled WITHOUT the section-7 destruction code.
//
// It links `qr_carriers_nodestruct`, the same sources built with
// `-DQR_CARRIERS_NO_DESTRUCTIONS`, in which `NativeCarrierControls` and every
// branch that reads it do not exist. It prints one line:
//
//     production_fingerprint <16 hex digits>
//
// `NativeOrderDestructions.TheProductionPathIsIdenticalToABuildWithoutTheFlagCode`
// runs this binary and requires that digest to equal the one the ordinary build
// produces with the flags off. See tools/destruction_guard.hpp.
#include <cstdio>

#include "destruction_guard.hpp"

int main() {
  std::printf("production_fingerprint %s\n",
              qr::carriers::guard::production_fingerprint().c_str());
  return 0;
}
