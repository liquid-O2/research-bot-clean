#!/usr/bin/env bash
# ENSEMBLE FIRST (the decisive treatment: the noise floor that adjudicates the
# provisional +$524.88), then abstention.  E3-E7 family; E8 is spent.
set -u
PY=/usr/bin/python3
cd /workspace
echo "[harvest] TREATMENT 1 ensemble + NOISE FLOOR"
$PY engine/port_m2/harvest.py --ensemble --eras E3,E5,E7 --inflate 5 --pairs 16
echo "[harvest] ensemble rc=$?"
echo "[harvest] TREATMENT 3 abstention"
$PY engine/port_m2/harvest.py --abstain --eras E3,E4,E5,E6,E7 --inflate 5 --pairs 16
echo "[harvest] abstain rc=$?"
echo "[harvest] DONE"
