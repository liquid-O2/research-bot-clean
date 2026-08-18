#!/bin/bash
# MemPalace hub-bridge hook (2026-08-18). Replaces the daemon-routed plugin
# hooks: the palace's single-writer lease is held permanently by the MCP HTTP
# hub (127.0.0.1:8765), so separate-process mines can never acquire it. This
# wrapper fires the SAME mine through the hub itself (tools/call
# mempalace_mine, in-process, re-entrant lock) — fire-and-forget, output-only,
# never blocking (D-013). Stop events are throttled to one mine per 30 min per
# session; PreCompact/SessionEnd always fire.
set -u
PAYLOAD=$(cat 2>/dev/null || true)
VERB="${1:-stop}"
TRANSCRIPT=$(printf '%s' "$PAYLOAD" | /usr/bin/python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("transcript_path",""))
except Exception: print("")' 2>/dev/null)
SID=$(printf '%s' "$PAYLOAD" | /usr/bin/python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("session_id","nosid"))
except Exception: print("nosid")' 2>/dev/null)
STATE_DIR="$HOME/.mempalace/hook_state"; mkdir -p "$STATE_DIR" 2>/dev/null
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
  FIRE=1
  if [ "$VERB" = "stop" ]; then
    TFILE="$STATE_DIR/hub_mine_last_$SID"
    NOW=$(date +%s); LAST=$(cat "$TFILE" 2>/dev/null || echo 0)
    [ $((NOW - LAST)) -lt 1800 ] && FIRE=0 || echo "$NOW" > "$TFILE"
  fi
  if [ "$FIRE" = "1" ]; then
    BODY=$(/usr/bin/python3 -c 'import json,sys
print(json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"mempalace_mine","arguments":{"source":sys.argv[1],"mode":"convos"}}}))' "$TRANSCRIPT")
    setsid nohup curl -s --max-time 900 -X POST http://127.0.0.1:8765/mcp \
      -H "Content-Type: application/json" -d "$BODY" \
      >> "$STATE_DIR/hub_mine_$SID.log" 2>&1 < /dev/null &
  fi
fi
echo '{}'
exit 0
