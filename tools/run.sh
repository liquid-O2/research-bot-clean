#!/usr/bin/env bash
# run.sh — the ONLY launcher for long jobs in this workspace.
#
#   run.sh <name> -- <cmd...>   launch <cmd...> under a stable identity <name>
#   run.sh --list               table of every registered run
#
# Contract (Russell process-layer rebuild, PART IX.1):
#   runs/<name>.pid  the PID of the CHILD command itself, never a wrapper shell.
#   runs/<name>.hb   the child's stderr, appended — a heartbeat line the child
#                    prints (e.g. "done/total rate eta") lands here with a
#                    fresh mtime. The child is launched under `stdbuf -oL -eL`
#                    so line buffering is forced even when its stderr is not a
#                    tty (Rust's own stderr is unbuffered regardless).
#   runs/<name>.rc   written once, on exit, with the child's exit code.
#   runs/<name>.log  the child's stdout, for reference (additive, not part of
#                    the core pid/hb/rc contract).
#
# Launch refuses if <name>.pid already names a still-live process. The launch
# is setsid-detached so it survives this shell/task dying (Russell
# launch-survival law, measured 2026-08-05: a process launched inside any
# agent/task shell dies with that task's process-group cleanup, even under
# nohup, unless setsid-detached). Liveness is ALWAYS `kill -0` against the
# recorded pid — no process-name matching anywhere, ever (exact-PID law).
#
# RUSSELL_RUNS_DIR overrides the registry directory; tests only. Production
# callers must never set it — the default is the one real registry that
# watchdog.sh and the Stop-hook dead-run check also read.
set -u

RUNS_DIR="${RUSSELL_RUNS_DIR:-/workspace/artifacts/workflow_memory/runs}"

usage() {
  echo "usage: run.sh <name> -- <cmd...>" >&2
  echo "       run.sh --list" >&2
  exit 2
}

is_alive() {
  # $1 = pid text, possibly garbage/empty. True only for a live numeric pid.
  [[ "$1" =~ ^[0-9]+$ ]] && kill -0 "$1" 2>/dev/null
}

cmd_list() {
  mkdir -p "$RUNS_DIR"
  printf '%-32s %-8s %-6s %-10s %-6s\n' "NAME" "PID" "ALIVE" "HB_AGE_S" "RC"
  shopt -s nullglob
  local files=("$RUNS_DIR"/*.pid)
  shopt -u nullglob
  [[ ${#files[@]} -eq 0 ]] && return 0
  local now pidfile name pid alive hbfile rcfile hb_age rc mtime
  now=$(date -u +%s)
  for pidfile in "${files[@]}"; do
    name=$(basename "$pidfile" .pid)
    pid=$(cat "$pidfile" 2>/dev/null || true)
    [[ -z "$pid" ]] && pid="?"
    if is_alive "$pid"; then alive="yes"; else alive="no"; fi
    hbfile="$RUNS_DIR/$name.hb"
    if [[ -f "$hbfile" ]]; then
      mtime=$(stat -c %Y "$hbfile" 2>/dev/null || echo "$now")
      hb_age=$(( now - mtime ))
    else
      hb_age="-"
    fi
    rcfile="$RUNS_DIR/$name.rc"
    if [[ -f "$rcfile" ]]; then
      rc=$(cat "$rcfile" 2>/dev/null || echo "?")
    else
      rc="-"
    fi
    printf '%-32s %-8s %-6s %-10s %-6s\n' "$name" "$pid" "$alive" "$hb_age" "$rc"
  done | sort
}

if [[ "${1:-}" == "--list" ]]; then
  cmd_list
  exit 0
fi

[[ $# -ge 1 ]] || usage
NAME="$1"; shift
[[ "${1:-}" == "--" ]] || usage
shift
[[ $# -ge 1 ]] || usage

if [[ ! "$NAME" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "run.sh: refusing name '$NAME' — use [A-Za-z0-9][A-Za-z0-9._-]* only" >&2
  exit 2
fi

mkdir -p "$RUNS_DIR"
PIDFILE="$RUNS_DIR/$NAME.pid"
HBFILE="$RUNS_DIR/$NAME.hb"
RCFILE="$RUNS_DIR/$NAME.rc"
LOGFILE="$RUNS_DIR/$NAME.log"

if [[ -f "$PIDFILE" ]]; then
  OLDPID=$(cat "$PIDFILE" 2>/dev/null || true)
  if is_alive "$OLDPID"; then
    echo "run.sh: refusing to start '$NAME' — pid $OLDPID is still alive ($PIDFILE)" >&2
    exit 1
  fi
fi

# A fresh launch under this name starts a new lifetime: the old .rc (if any)
# described the PREVIOUS run and must not be misread as this one's result.
# .hb is append-only forever (law) and is left untouched across relaunches.
rm -f "$RCFILE"

SUPERVISOR='
  pidfile="$1"; hbfile="$2"; rcfile="$3"; logfile="$4"; shift 4
  stdbuf -oL -eL "$@" >"$logfile" 2> >(tee -a "$hbfile" >/dev/null) &
  child=$!
  echo "$child" > "$pidfile"
  rc=0
  wait "$child" || rc=$?
  echo "$rc" > "$rcfile"
'

setsid bash -c "$SUPERVISOR" run.sh-supervisor \
  "$PIDFILE" "$HBFILE" "$RCFILE" "$LOGFILE" "$@" < /dev/null >/dev/null 2>&1 &
disown 2>/dev/null || true

# The supervisor writes PIDFILE almost immediately; wait briefly so the caller
# gets back the real pid instead of racing it. This does NOT wait for the job.
for ((_i = 0; _i < 40; _i++)); do
  [[ -s "$PIDFILE" ]] && break
  sleep 0.05
done

if [[ -s "$PIDFILE" ]]; then
  echo "run.sh: launched '$NAME' pid=$(cat "$PIDFILE") hb=$HBFILE rc_pending=$RCFILE log=$LOGFILE"
else
  echo "run.sh: launched '$NAME' but pidfile not observed yet — check $RUNS_DIR" >&2
fi
