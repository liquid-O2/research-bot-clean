// qr_wave2_nodestruct_probe — the production fingerprint of a wave-2 library
// compiled WITHOUT the destruction code.
//
// It links `qr_wave2_nodestruct`, the same sources built with
// `-DQR_WAVE2_NO_DESTRUCTIONS`, in which the `DestructionControls` flags and
// every branch that reads them do not exist. It prints one line:
//
//     production_fingerprint <16 hex digits>
//
// `Wave2Destructions.TheProductionPathIsIdenticalToABuildWithoutTheFlagCode`
// runs this binary and requires that digest to equal the one the ordinary build
// produces with the flags off. See tools/wave2_guard.hpp.
#include <cstdio>

#include "wave2_guard.hpp"

int main() {
  std::printf("production_fingerprint %s\n",
              qr::wave2::guard::production_fingerprint().c_str());
  return 0;
}
