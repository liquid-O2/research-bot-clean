// qr_replay/src/action.cpp — stable names for the typed states of an action row.
#include "qr_replay/action.hpp"

namespace qr::replay {

const char* label_state_name(LabelState state) noexcept {
  switch (state) {
    case LabelState::OK: return "OK";
    case LabelState::ENTRY_UNAVAILABLE: return "ENTRY_UNAVAILABLE";
    case LabelState::EXIT_UNAVAILABLE: return "EXIT_UNAVAILABLE";
  }
  return "UNKNOWN_LABEL_STATE";
}

const char* side_name(Side side) noexcept {
  switch (side) {
    case Side::LONG: return "LONG";
    case Side::SHORT: return "SHORT";
  }
  return "UNKNOWN_SIDE";
}

}  // namespace qr::replay
