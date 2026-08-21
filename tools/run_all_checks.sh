#!/bin/bash
# One command for the whole check battery (Akita E-A3, ported 2026-08-21):
# every lane, freeze, and session runs the same named set instead of
# assembling it by hand. Any non-zero exit fails the whole run.
# Usage: bash tools/run_all_checks.sh [--fast]   (--fast skips >60s modules)
set -u
cd /workspace
FAST="${1:-}"
FAILED=0
run() {
  echo "== $*"
  "$@" || { echo "FAILED: $*"; FAILED=1; }
}
run python3 -m unittest engine.entry_v2.test_tabular_walk_twin
run python3 -m unittest engine.entry_v2.test_tabular_fit_backends
run python3 -m unittest engine.entry_v2.test_tabular_fit_roster_homogeneity
run python3 -m unittest engine.entry_v2.test_perfect_actions_check
run python3 -m unittest engine.entry_v2.test_disc_native_harness
run /usr/bin/python3 tools/receipt_gpu_fit_determinism.py --selftest
run /usr/bin/python3 tools/probe_gpu_quantile_bigfold.py --selftest
run /usr/bin/python3 tools/probe_boosters_gpu.py --selftest
run /usr/bin/python3 tools/adopt_teacher_identity_transcribe.py --selftest
# apply_freeze_batch_20260821 --selftest is EXCLUDED: single-use lever, batch
# applied 2026-08-21T20:31Z — its mutant fixtures stage from live bytes whose
# anchors the apply itself consumed. Historical tool, receipts on record.
if [ "$FAST" != "--fast" ]; then
  run python3 -m unittest engine.entry_v2.test_qrdisc_state_marshal
  run python3 -m unittest engine.entry_v2.test_tabular_recovery
fi
if [ "$FAILED" -eq 0 ]; then echo "ALL CHECKS GREEN"; else echo "BATTERY FAILED"; fi
exit $FAILED
