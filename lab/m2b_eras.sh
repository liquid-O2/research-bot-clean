#!/usr/bin/env bash
# P-M2b era STUDY renders, chained under ONE run.sh identity so the two eras
# never run concurrently (the worker cap is 6 for the whole lane).
set -u
cd /workspace
/usr/bin/python3 engine/port_m2/era_build.py --era E1 --block STUDY --workers 6
rc1=$?
/usr/bin/python3 engine/port_m2/era_build.py --era E2 --block STUDY --workers 6
rc2=$?
echo "E1 rc=$rc1 E2 rc=$rc2"
exit $(( rc1 | rc2 ))
