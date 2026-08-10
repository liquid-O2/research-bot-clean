#!/usr/bin/env bash
# watchdog.sh — pid-file-only dead/stalled run detector.
#
#   watchdog.sh               one check pass (this is what the cron line runs)
#   watchdog.sh --check       same, explicit
#   watchdog.sh --install     idempotently install the cron package, start the
#                             daemon best-effort, and register the */5 line
#
# For each runs/<name>.pid that has no matching .rc yet (i.e. still "running"
# by the registry):
#   - pid not alive              -> DIED    appended to runs/ALERTS.log + bell
#   - .hb file older than 10 min -> STALLED appended to runs/ALERTS.log + bell
# Re-fires on every 5-minute pass while the condition persists — this is a
# tripwire meant to keep ringing until a human/agent handles it (writes .rc,
# relaunches, or otherwise clears the .pid), not a one-shot notice. The
# block_stop_with_open_work.py Stop hook runs the same check at every turn
# boundary, independently of this cron line.
#
# Law: liveness is ALWAYS `kill -0 <pid recorded in a .pid file>`. Never
# pgrep/pkill/ps-grep by name — that is exactly the class of bug the
# exact-PID-kill law exists to stop. The one exception is the cron DAEMON's
# own liveness in --install, which is also a pidfile read
# (/run/crond.pid) but needs `sudo` to signal because the daemon runs as
# root while this script runs as an unprivileged user (measured: plain
# `kill -0` on a root-owned pid returns EPERM, which is NOT "dead").
#
# RUSSELL_RUNS_DIR overrides the registry directory; tests only. Production
# (including the installed cron line) always uses the real default.
set -u

RUNS_DIR="${RUSSELL_RUNS_DIR:-/workspace/artifacts/workflow_memory/runs}"
STALE_SECONDS=$(( 10 * 60 ))
SELF="/workspace/lab/watchdog.sh"
CRON_SCHEDULE="*/5 * * * *"
CRON_MARK="lab/watchdog.sh"   # substring used to find/replace our own line, idempotently

is_alive() {
  [[ "$1" =~ ^[0-9]+$ ]] && kill -0 "$1" 2>/dev/null
}

do_check() {
  mkdir -p "$RUNS_DIR"
  local alerts="$RUNS_DIR/ALERTS.log"
  shopt -s nullglob
  local files=("$RUNS_DIR"/*.pid)
  shopt -u nullglob
  local now pidfile name pid rcfile hbfile mtime age utc
  now=$(date -u +%s)
  for pidfile in "${files[@]}"; do
    name=$(basename "$pidfile" .pid)
    rcfile="$RUNS_DIR/$name.rc"
    [[ -f "$rcfile" ]] && continue   # finished — not this hook's concern
    pid=$(cat "$pidfile" 2>/dev/null || true)
    utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    if ! is_alive "$pid"; then
      echo "DIED $name $utc pid=${pid:-UNKNOWN}" >> "$alerts"
      printf '\a'
      continue
    fi
    hbfile="$RUNS_DIR/$name.hb"
    if [[ -f "$hbfile" ]]; then
      mtime=$(stat -c %Y "$hbfile" 2>/dev/null || echo "$now")
      age=$(( now - mtime ))
      if (( age > STALE_SECONDS )); then
        echo "STALLED $name $utc hb_age_s=$age hb=$hbfile" >> "$alerts"
        printf '\a'
      fi
    fi
    # No .hb at all yet is not itself stalled — a job may legitimately take a
    # moment before its first heartbeat; the pid-liveness branch above already
    # catches a launch that died before writing one.
  done
}

install_line() {
  local line="$CRON_SCHEDULE $SELF >> $RUNS_DIR/watchdog_cron.log 2>&1"

  if ! command -v crontab >/dev/null 2>&1; then
    echo "watchdog.sh --install: no crontab binary — installing the cron package (sudo apt-get)..." >&2
    sudo -n apt-get update -qq >&2 2>&1 || true
    sudo -n apt-get install -y cron -qq >&2 2>&1 || true
  fi
  if ! command -v crontab >/dev/null 2>&1; then
    echo "watchdog.sh --install: FAILED — no crontab binary and the package install did not provide one. Repair: sudo apt-get install -y cron" >&2
    return 1
  fi

  local cron_pidfile="/run/crond.pid"
  local cron_pid=""
  [[ -f "$cron_pidfile" ]] && cron_pid=$(cat "$cron_pidfile" 2>/dev/null || true)
  if [[ -n "$cron_pid" ]] && sudo -n kill -0 "$cron_pid" 2>/dev/null; then
    echo "watchdog.sh --install: cron daemon already running (pid $cron_pid from $cron_pidfile)." >&2
  else
    echo "watchdog.sh --install: starting the cron daemon (sudo /usr/sbin/cron)..." >&2
    sudo -n /usr/sbin/cron >&2 2>&1 || true
    sleep 0.3
    cron_pid=$(cat "$cron_pidfile" 2>/dev/null || true)
    if [[ -n "$cron_pid" ]] && sudo -n kill -0 "$cron_pid" 2>/dev/null; then
      echo "watchdog.sh --install: cron daemon is now running (pid $cron_pid)." >&2
    else
      echo "watchdog.sh --install: WARNING — could not confirm a live cron daemon at $cron_pidfile; the crontab line will still be installed (repair: sudo /usr/sbin/cron)." >&2
    fi
  fi

  mkdir -p "$RUNS_DIR"
  # Idempotent: drop any prior line naming this script, then add exactly one
  # fresh line. Running --install any number of times converges to one line.
  { crontab -l 2>/dev/null | grep -vF "$CRON_MARK"; echo "$line"; } | crontab -
  echo "watchdog.sh --install: crontab line installed:"
  echo "  $line"
  crontab -l 2>&1 | grep -F "$CRON_MARK"
}

case "${1:-}" in
  --install) install_line ;;
  --check|"") do_check ;;
  *)
    echo "usage: watchdog.sh [--check|--install]" >&2
    exit 2
    ;;
esac
