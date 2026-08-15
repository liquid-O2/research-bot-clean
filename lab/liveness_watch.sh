#!/bin/bash
# standing watchdog: logs liveness transitions every 5 min to LIVENESS.log
L=/workspace/artifacts/workflow_memory/LIVENESS.log
PREV=""
while true; do
  V=$(/workspace/lab/alive.sh)
  S=${V%%:*}
  if [ "$S" != "$PREV" ]; then echo "[$(date -u +%H:%M:%S)] $V" >> $L; PREV=$S; fi
  sleep 300
done
