#!/bin/bash
# one-line liveness verdict: RUNNING (evidence) or DEAD-AIR (what stopped)
R=/workspace/artifacts/workflow_memory/runs
CPU=$(ps aux | grep "[p]ython" | awk '$3>50 {n++} END {print n+0}')
NEWEST=$(ls -t $R/*.hb 2>/dev/null | head -1)
AGE=$(( $(date +%s) - $(stat -c %Y "$NEWEST" 2>/dev/null || echo 0) ))
RC=$(cat "${NEWEST%.hb}.rc" 2>/dev/null || echo pending)
if [ "$CPU" -gt 0 ] && [ $AGE -lt 900 ]; then
  echo "RUNNING: $CPU workers computing; $(basename $NEWEST) hb ${AGE}s old; last: $(tail -1 $NEWEST | cut -c1-90)"
elif [ "$RC" != "pending" ] && [ "$CPU" -eq 0 ]; then
  echo "DEAD-AIR: newest run $(basename $NEWEST) closed rc=$RC ${AGE}s ago and no compute is live"
else
  echo "SUSPECT: cpu=$CPU workers, hb ${AGE}s old, rc=$RC — investigate"
fi
