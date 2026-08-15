#!/usr/bin/env bash
set -u
PY=/usr/bin/python3
cd /workspace
echo "[harvest] TREATMENT 1 ensemble (also measures the NOISE FLOOR)"
$PY engine/port_m2/harvest.py --ensemble --eras E3,E5,E7 --inflate 5 --pairs 16
echo "[harvest] ensemble rc=$?"
echo "[harvest] TREATMENT 3 abstention"
$PY engine/port_m2/harvest.py --abstain --eras E3,E4,E5,E6,E7 --inflate 5 --pairs 16
echo "[harvest] abstain rc=$?"
echo "[harvest] DONE"
