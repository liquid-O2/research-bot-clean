#!/usr/bin/env bash
# PORT M3 — copy the walk-forward deliverables out of the D-018 bulk cache into
# the COMMITTED record.  artifacts/ is gitignored by design (D-018: bulk data
# never enters the overlay or the repo), but the harness's verdict tables are
# small and are the project's memory, so they are published to provenance/.
#
#   publish.sh [WALK_SUBDIR] [SUFFIX]
#
# With no arguments this publishes `walk/` under the plain names, as it always
# has.  With arguments it publishes an ALTERNATE ARM under a suffix — the D-078
# runs are `publish.sh walk_tf _TEACHER` and `publish.sh walk_notf _NOTEACHER`
# — so an arm can be committed BESIDE the reference curve instead of over it.
# The pre-teacher ERA_CURVE.tsv is the control the teacher diff is read
# against, and overwriting it would destroy the comparison.
set -euo pipefail
SRC=/workspace/artifacts/cache/port/m3
DST=/workspace/provenance/port_m3
WALK="${1:-walk}"
SFX="${2:-}"
mkdir -p "$DST"
for f in ERA_CURVE ERA_ASSET TARGET_COMPARE DECOMPOSITION \
         MIRROR HOLM ADAPTATION_LATENCY IMPORTANCE \
         IMPORTANCE_STABILITY; do
  [ -f "$SRC/$WALK/$f.tsv" ] && cp "$SRC/$WALK/$f.tsv" "$DST/$f$SFX.tsv"
done
cp "$SRC/$WALK/walk.receipt.json" "$DST/walk$SFX.receipt.json"
cp "$SRC/matrix/matrix.receipt.json" "$DST/matrix.receipt.json"
cp "$SRC/red_first.receipt.json" "$DST/red_first.receipt.json"
# PER_SESSION.tsv is ~3,000 rows per era — the per-session curve the D-084
# latency numbers are read off, so it is published too.
cp "$SRC/$WALK/PER_SESSION.tsv" "$DST/PER_SESSION$SFX.tsv"
echo "published $WALK -> $DST (suffix='$SFX')"
ls -la "$DST"
