#!/usr/bin/env bash
# port-m1-s11-atlas: the S4 atlas screen re-run on the S1.1+S1.2 ENRICHED
# roster, CHAMPION CLASS ONLY (families ratio / certificate / mae_budget /
# path_shape).  Same machinery, same grid enumeration; only the universe, the
# skeleton, the probe-feature set and the fitted subset change.
set -euo pipefail
ROOT=/workspace/artifacts/cache/port/m1
export QR_SKEL_ROSTER_DIR="$ROOT/generation_v3"
export QR_SKEL_CANDIDATE_DIR="$ROOT/skel_v3/candidates"
export QR_SKEL_SHARD_DIR="$ROOT/skel_v3/shards"
export S4_OUT_DIR=atlas_v3
export S4_LEVELS_DIR=levels_v4
export S4_FAMILY_SET=v3
export S4_CLASSES=ratio,certificate,mae_budget,path_shape
export M1_WORKERS=${M1_WORKERS:-5}
cd /workspace
/usr/bin/python3 engine/port_m1b/s4_features.py
/usr/bin/python3 engine/port_m1b/s4_screen.py
/usr/bin/python3 engine/port_m1b/s4_confirm.py
/usr/bin/python3 engine/port_m1b/s4_report_v3.py
