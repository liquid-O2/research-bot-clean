#!/usr/bin/env bash
# PORT M3 — the harness driver.  ONE entry point, three stages, in order.
#
#   lab/run.sh port-m3-harness -- bash engine/port_m3/harness.sh
#
# Stage 1  RED-FIRST TESTS.  The holdout red and the future-feature red must
#          both fire on planted mutants before anything is built.  A failure
#          here stops the run: a harness whose guards are asleep produces
#          numbers nobody may quote.
# Stage 2  THE FEATURE MATRIX (candidate grain, v3 roster, holdout excluded by
#          the guarded enumerator and REFUSED by the guard).
# Stage 3  THE WALK-FORWARD LADDER E1->E8 and every receipt the brief names.
#
# Workers: the matrix scan uses M3_WORKERS (default 8, the brief's <=10 cap);
# the model fits use M3_NTHREAD (default 8) inside one process.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=/usr/bin/python3
WORKERS="${M3_WORKERS:-8}"
NTHREAD="${M3_NTHREAD:-8}"

echo "== stage 0: the RED-FIRST proof (guards removed -> both reds must fail) =="
"$PY" "$HERE/test_m3.py" --red-first

echo "== stage 1: red-first tests =="
"$PY" "$HERE/test_m3.py" --fast

echo "== stage 2: feature matrix (workers=$WORKERS) =="
"$PY" "$HERE/m3_matrix.py" --build --workers "$WORKERS"

echo "== stage 2b: post-build tests (the built matrix's own guards) =="
"$PY" "$HERE/test_m3.py"

echo "== stage 3: walk-forward ladder (nthread=$NTHREAD) =="
"$PY" "$HERE/m3_walk.py" --run --nthread "$NTHREAD"

echo "== stage 4: publish the verdict tables into the committed record =="
bash "$HERE/publish.sh"

echo "== done =="
ls -la /workspace/artifacts/cache/port/m3/walk/
