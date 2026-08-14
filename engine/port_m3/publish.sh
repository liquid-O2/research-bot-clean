#!/usr/bin/env bash
# PORT M3 — copy the walk-forward deliverables out of the D-018 bulk cache into
# the COMMITTED record.  artifacts/ is gitignored by design (D-018: bulk data
# never enters the overlay or the repo), but the harness's verdict tables are
# small and are the project's memory, so they are published to provenance/.
set -euo pipefail
SRC=/workspace/artifacts/cache/port/m3
DST=/workspace/provenance/port_m3
mkdir -p "$DST"
for f in ERA_CURVE.tsv ERA_ASSET.tsv TARGET_COMPARE.tsv DECOMPOSITION.tsv \
         MIRROR.tsv HOLM.tsv ADAPTATION_LATENCY.tsv IMPORTANCE.tsv \
         IMPORTANCE_STABILITY.tsv; do
  [ -f "$SRC/walk/$f" ] && cp "$SRC/walk/$f" "$DST/$f"
done
cp "$SRC/walk/walk.receipt.json" "$DST/walk.receipt.json"
cp "$SRC/matrix/matrix.receipt.json" "$DST/matrix.receipt.json"
cp "$SRC/red_first.receipt.json" "$DST/red_first.receipt.json"
# PER_SESSION.tsv is ~3,000 rows per era — the per-session curve the D-084
# latency numbers are read off, so it is published too.
cp "$SRC/walk/PER_SESSION.tsv" "$DST/PER_SESSION.tsv"
echo "published -> $DST"
ls -la "$DST"
