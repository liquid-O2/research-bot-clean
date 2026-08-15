#!/bin/bash
# persistent re-alert: emits a line when dead-air/suspect PERSISTS 2 consecutive checks (10 min apart)
BAD=0
while true; do
  sleep 600
  V=$(/workspace/lab/alive.sh)
  case "$V" in
    RUNNING*) BAD=0 ;;
    *) BAD=$((BAD+1)); if [ $BAD -ge 2 ]; then echo "PERSISTENT-STALL(${BAD}x): $V"; fi ;;
  esac
done
