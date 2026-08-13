#!/usr/bin/env bash
# port-m1-s11-skel: S3 label skeleton re-derived for the S1.1+S1.2 ENRICHED
# roster.  The engine is ROSTER-AGNOSTIC (S3 CONV C2): only the candidate
# receipt changes, so export_candidates.py is re-pointed and qr_skel_build is
# re-run unchanged.
set -euo pipefail
BIN=/workspace/artifacts/cache/cpp/release/bin/qr_skel_build
ROOT=/workspace/artifacts/cache/port/m1
export QR_SKEL_ROSTER_DIR="$ROOT/generation_v3"
export QR_SKEL_CANDIDATE_DIR="$ROOT/skel_v3/candidates"
mkdir -p "$QR_SKEL_CANDIDATE_DIR" "$ROOT/skel_v3/shards"
/usr/bin/python3 /workspace/engine/port_m1b/export_candidates.py
for A in SI HG NKD; do
  "$BIN" --asset "$A" \
    --candidates "$QR_SKEL_CANDIDATE_DIR/$A" \
    --sessions   "$ROOT/cpp_sessions/$A" \
    --sanity     "$ROOT/skel/sanity/$A" \
    --out        "$ROOT/skel_v3/shards" --workers 3
done
