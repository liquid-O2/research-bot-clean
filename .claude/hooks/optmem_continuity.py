#!/usr/bin/env python3
"""OptMem lifecycle hook + short markdown backup.

Verbs (argv[1], cross-checked against stdin hook_event_name):
  sessionstart  self-heal, memo wake, refresh CONTINUITY.md snapshot; inject wake only
  postcompact   same as sessionstart
  precompact    spool + memo note + refresh snapshot
  stop          spool + refresh snapshot (throttled). Print nothing.
  sessionend    spool + refresh snapshot

Law: continuity verbs are output-only and never block; the D-104 pretooluse
gate MAY deny with a reason and fails OPEN on error (D-108 amends D-013).
Grok Stop additionalContext keeps the agent working — this script never
prints decision/additionalContext on Stop.
Grok SessionStart stdout is ignored; the agent still runs memo wake.
CONTINUITY.md is an overwritten token-bounded snapshot (backup if OptMem is down).
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME_OPTMEM = Path.home() / ".optmem"
WS_OPTMEM = Path("/workspace/.optmem")
MEMO_HOME = HOME_OPTMEM / "memo"
MEMO_WS = WS_OPTMEM / "memo"
CONTINUITY = Path("/workspace/CONTINUITY.md")
STATE_MD = Path("/workspace/STATE.md")
SPOOL_DIR = Path("/workspace/artifacts/cache/continuity")
HOOK_STATE = WS_OPTMEM / "hook_state"
LOG = HOOK_STATE / "hook.log"
STOP_THROTTLE_S = 600
PRECOMPACT_THROTTLE_S = 30
SNIPPET_CHARS = 220
WAKE_CAP_LINES = 40
STATE_CAP_LINES = 40
BACKUP_CAP_CHARS = 8000


def log(msg: str) -> None:
    try:
        HOOK_STATE.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"{now()} {msg}\n")
    except Exception:
        pass


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def read_payload() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def run(cmd, timeout=6):
    try:
        env = os.environ.copy()
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env
        )
        return (p.stdout or "") + (p.stderr or "")
    except Exception as exc:
        log(f"run failed {cmd[:2]}: {type(exc).__name__}")
        return ""


def run_memo(args, timeout=6):
    """Always invoke via /usr/bin/python3: Grok/opencode PATH hides env python3."""
    return run(["/usr/bin/python3", memo_path(), *args], timeout=timeout)


def memo_path() -> str:
    if MEMO_HOME.exists():
        return str(MEMO_HOME)
    return str(MEMO_WS)


def self_heal() -> None:
    """Overlay wipe recovery: restore ~/.optmem/memo and the store symlink."""
    try:
        HOME_OPTMEM.mkdir(parents=True, exist_ok=True)
        if not MEMO_HOME.exists() and MEMO_WS.exists():
            shutil.copy2(MEMO_WS, MEMO_HOME)
            os.chmod(MEMO_HOME, 0o755)
        mem = HOME_OPTMEM / "memory"
        if not mem.is_symlink():
            if mem.exists():
                mem.rename(HOME_OPTMEM / f"memory.displaced.{int(time.time())}")
            mem.symlink_to(WS_OPTMEM / "memory")
    except Exception as exc:
        log(f"self_heal: {type(exc).__name__}: {exc}")


def git_line() -> str:
    head = run(["git", "-C", "/workspace", "rev-parse", "--short", "HEAD"], 1).strip()
    dirty = run(["git", "-C", "/workspace", "status", "--porcelain"], 1)
    n = len([l for l in dirty.splitlines() if l.strip()])
    return f"HEAD {head or '?'} dirty {n}"


def tail_of(path: Path, lines: int) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8").splitlines()[-lines:])
    except Exception:
        return ""


def spool(payload: dict) -> Path | None:
    """Lossless incremental copy of the session transcript to the durable volume.

    Tracks a byte offset per (session, generation). If the source shrank
    (harness rewrote it, e.g. post-compact), a new generation segment starts,
    so the union of segments is a superset of every byte ever observed.
    """
    tp = payload.get("transcript_path") or ""
    sid = (payload.get("session_id") or "nosid")[:32]
    src = Path(tp)
    if not tp or not src.is_file():
        return None
    try:
        SPOOL_DIR.mkdir(parents=True, exist_ok=True)
        HOOK_STATE.mkdir(parents=True, exist_ok=True)
        meta = HOOK_STATE / f"{sid}.spool.json"
        st = {"gen": 0, "offset": 0}
        try:
            st = json.loads(meta.read_text())
        except Exception:
            pass
        size = src.stat().st_size
        if size < st["offset"]:
            st = {"gen": st["gen"] + 1, "offset": 0}
        dst = SPOOL_DIR / f"{sid}.g{st['gen']}.jsonl"
        if size > st["offset"]:
            with open(src, "rb") as fin:
                fin.seek(st["offset"])
                data = fin.read()
            with open(dst, "ab") as fout:
                fout.write(data)
            st["offset"] = size
            meta.write_text(json.dumps(st))
        return dst
    except Exception as exc:
        log(f"spool: {type(exc).__name__}: {exc}")
        return None


def last_user_snippet(payload: dict) -> str:
    tp = payload.get("transcript_path") or ""
    try:
        raw = Path(tp).read_bytes()[-8_000_000:]
        text = ""
        for line in raw.decode("utf-8", "replace").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") != "user":
                continue
            content = (rec.get("message") or {}).get("content")
            if isinstance(content, str):
                cand = content
            elif isinstance(content, list):
                cand = " ".join(
                    c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
                )
            else:
                continue
            cand = " ".join(cand.split())
            if cand and not cand.startswith(("<system", "[SYSTEM", "<task-notification", "<local-command")):
                text = cand
        return text[:SNIPPET_CHARS]
    except Exception:
        return ""


def write_backup(payload: dict, event: str, extra: str = "") -> None:
    """Overwrite CONTINUITY.md with a short current snapshot. Backup only."""
    try:
        sid = (payload.get("session_id") or "nosid")[:12]
        snip = last_user_snippet(payload)
        wake = run_memo(["wake"], timeout=8).strip()
        wake_txt = "\n".join(wake.splitlines()[:WAKE_CAP_LINES]) or "(memo wake unavailable)"
        state = tail_of(STATE_MD, STATE_CAP_LINES) or "(STATE.md missing)"
        extra_line = f"- {extra}\n" if extra else ""
        body = (
            "# CONTINUITY — backup if OptMem is down\n\n"
            "Overwritten snapshot from `optmem_continuity.py`. "
            "Primary memory is OptMem (`memo wake`). Read this file only if wake fails.\n\n"
            f"- Updated: {now()}\n"
            f"- Event: {event}\n"
            f"- Session: {sid}\n"
            f"- Git: {git_line()}\n"
            f"- Last user: {snip or '(none)'}\n"
            f"{extra_line}\n"
            "## Last OptMem wake\n\n"
            f"```\n{wake_txt}\n```\n\n"
            "## STATE.md\n\n"
            f"```\n{state}\n```\n"
        )
        if len(body) > BACKUP_CAP_CHARS:
            body = body[:BACKUP_CAP_CHARS] + "\n…truncated\n"
        CONTINUITY.write_text(body, encoding="utf-8")
    except Exception as exc:
        log(f"write_backup: {type(exc).__name__}: {exc}")


def do_sessionstart(payload: dict, verb: str = "") -> None:
    self_heal()
    wake = run_memo(["wake"], timeout=8).strip()
    event = (payload.get("hook_event_name") or "SessionStart")
    # The real compact resume arrives as {"hook_event_name":"SessionStart",
    # "source":"compact"} (hook.log: `sessionstart source=compact`); the
    # postcompact verb only ever comes from argv. Both must re-arm.
    is_postcompact = (
        verb == "postcompact" or str(payload.get("source", "")).lower() == "compact"
    )
    sid = (payload.get("session_id") or "nosid")[:32]
    if is_postcompact:
        # Compaction drops skill text from context. Re-arm the D-104 edit
        # gate so the next engine/tools edit forces re-engagement, and say so.
        try:
            (HOOK_STATE / f"{sid}.tdd_ok").unlink(missing_ok=True)
        except Exception:
            pass
    write_backup(payload, event)
    parts = [
        "OptMem `memo wake` (if it asks a compression, run that `memo nap` "
        "before other work). If wake failed, read /workspace/CONTINUITY.md.",
        "```\n" + (wake or "(memo wake unavailable)") + "\n```",
    ]
    # User ruling 2026-08-21: skill routing is audited, not hoped. Surface the
    # previous sessions' ledger at wake so a skills=NONE code session is seen.
    ledger_tail = tail_of(HOOK_STATE / "skill_usage.log", 3).strip()
    if ledger_tail:
        parts.append(
            "Skill-usage ledger (previous sessions; skills=NONE on a session "
            "that edited code violated the routing law — audit it):\n```\n"
            + ledger_tail + "\n```"
        )
    if is_postcompact:
        parts.append(
            "POST-COMPACTION SKILL RESET: skill rules loaded before compaction "
            "are NO LONGER in context (summaries are not the skill). The edit "
            "gate has been re-armed. Re-invoke each skill at its next matching "
            "situation per the CLAUDE.md routing table; the ledger above shows "
            "what this session had engaged."
        )
    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n".join(parts),
        }
    }
    print(json.dumps(out))
    log(f"sessionstart source={payload.get('source', '')} wake_bytes={len(wake)}")


def _throttled(sid: str, name: str, window_s: float) -> bool:
    """True if this (session, name) already ran inside window_s."""
    HOOK_STATE.mkdir(parents=True, exist_ok=True)
    tfile = HOOK_STATE / f"{sid}.{name}_ts"
    last = 0.0
    try:
        last = float(tfile.read_text().strip())
    except Exception:
        pass
    if time.time() - last < window_s:
        return True
    try:
        tfile.write_text(str(time.time()))
    except Exception:
        pass
    return False


def do_precompact(payload: dict) -> None:
    sid = (payload.get("session_id") or "nosid")[:8]
    trigger = payload.get("trigger") or ""
    dst = spool(payload)
    if _throttled(sid, "precompact", PRECOMPACT_THROTTLE_S):
        log(f"precompact sid={sid} spool={dst} throttled")
        print("{}")
        return
    snip = last_user_snippet(payload)
    write_backup(
        payload,
        f"PreCompact:{trigger or 'unknown'}",
        extra=f"spool: {dst or '(spool failed)'}",
    )
    note = f"{time.strftime('%Y-%m-%d')} compact s{sid}: {snip}"[:270]
    if snip:
        run_memo(["note", note], timeout=6)
    log(f"precompact sid={sid} spool={dst}")
    print("{}")


def _ledger_skill_usage(payload: dict, sid: str) -> None:
    """Observability, not enforcement: count Skill invocations in the transcript
    so skill usage is measured per session (hook_state/skill_usage.log)."""
    try:
        tp = payload.get("transcript_path") or ""
        raw = Path(tp).read_bytes().decode("utf-8", "replace")
        import re as _re
        names = _re.findall(r'"name"\s*:\s*"Skill"[^}]*?"skill"\s*:\s*"([a-z0-9:_-]+)"', raw)
        if not names:
            names = _re.findall(r'"skill"\s*:\s*"([a-z0-9:_-]+)"', raw)
        from collections import Counter
        counts = Counter(names)
        line = f"{now()} sid={sid[:8]} turns_seen skills={dict(counts) if counts else 'NONE'}\n"
        with open(HOOK_STATE / "skill_usage.log", "a", encoding="utf-8") as f:
            f.write(line)
    except Exception as exc:
        log(f"skill_ledger: {type(exc).__name__}")


_PROMISE_RE = None


def _last_assistant_text(payload: dict) -> str:
    path = payload.get("transcript_path") or ""
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines[-400:]):
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") != "assistant":
            continue
        parts = ((obj.get("message") or {}).get("content") or [])
        texts = [p.get("text", "") for p in parts if isinstance(p, dict)
                 and p.get("type") == "text"]
        if texts:
            return "\n".join(texts)
    return ""


def _promise_block(payload: dict) -> bool:
    """User order 2026-08-22: never end a turn on a bare 'next' promise — do the
    work, launch it, or state the deferral reason. Blocks the stop ONCE."""
    global _PROMISE_RE
    if payload.get("stop_hook_active"):
        return False
    import re
    if _PROMISE_RE is None:
        _PROMISE_RE = re.compile(
            r"(?i)\b(next:|next steps?\b|next up\b|the (decisive|remaining) next\b|"
            r"i(?:'|’)ll (then|now|next)\b|will (build|run|measure|fit|launch|"
            r"dispatch|synthesize) \w+ (next|after|when)\b|"
            r"next (build|measure|action|work)\b)")
    text = _last_assistant_text(payload)
    tail = text[-600:]
    m = _PROMISE_RE.search(tail)
    if not m:
        return False
    deferral = re.compile(
        r"(?i)(deferred because|blocked on|waiting (on|for) (the )?(user|a1|lane|"
        r"task|notification)|running in (the )?background|launched|dispatched|"
        r"in flight)")
    if deferral.search(tail):
        return False
    print(json.dumps({"decision": "block", "reason": (
        f"Stop-hook promise-catcher (user order 2026-08-22): your final message "
        f"promises next work (matched: {m.group(0)!r}) without starting it. Do it "
        f"now or launch it in background — or restate it as explicitly deferred "
        f"with the blocking reason. This blocks only once.")}))
    return True


def do_stop(payload: dict) -> None:
    # Grok treats Stop additionalContext as "keep working". Print nothing
    # (except the one-shot promise-catcher block below).
    sid = (payload.get("session_id") or "nosid")[:32]
    if _promise_block(payload):
        log(f"stop promise-block sid={sid[:8]}")
        return
    spool(payload)
    if _throttled(sid, "stop", STOP_THROTTLE_S):
        return
    write_backup(payload, "Stop")
    _ledger_skill_usage(payload, sid)
    log(f"stop heartbeat sid={sid[:8]}")


def do_sessionend(payload: dict) -> None:
    sid = (payload.get("session_id") or "nosid")[:8]
    reason = payload.get("reason") or ""
    spool(payload)
    write_backup(payload, f"SessionEnd:{reason}")
    log(f"sessionend sid={sid} reason={reason}")


ROUTING_NUDGE = (
    "Skill routing check (harness-enforced): before responding, match this request "
    "against the situation->skill table in /workspace/CLAUDE.md and invoke every "
    "matching skill via the Skill tool. The user never names skills; the situation "
    "is the trigger. Follow the CLAUDE.md coding-conduct block on any code change."
)

# Situational routing map (user ruling 2026-08-21: name the matching skills,
# a named miss is harder to ignore than a table pointer). Keys are lowercase
# substrings of the prompt; order = priority.
SKILL_KEYWORD_MAP = (
    (("bug", "fail", "error", "broken", "stall", "crash", "refus"),
     ("debugging-with-a-loop", "driving-tests-first")),
    (("launch", "rehearsal", "long run", "experiment", "fit", "measure"),
     ("operating-long-runs", "preregistering-results", "running-evals")),
    (("review",), ("running-consolidated-review",)),
    # breaking-down-work leads on big-work words: decomposition precedes the
    # grilling/design/spec skills in time (installed 2026-08-21 skill port).
    (("break down", "breakdown", "decompos", "multi-stage", "roadmap",
      "too big", "stages"), ("breaking-down-work",)),
    (("refactor",), ("breaking-down-work", "shaping-code-for-agents")),
    (("plan", "design", "spec", "freeze", "adopt"),
     ("breaking-down-work", "stress-testing-plans", "designing-it-twice",
      "sharpening-specs")),
    (("commit", "tidy", "clean up", "stray"), ("tidying-workspace",)),
    (("done", "verified", "passing", "receipt"), ("verifying-with-receipts",)),
    (("gate", "threshold", "criterion"), ("encoding-goals-in-gates",)),
    (("agent", "lane", "brief", "subagent", "workflow"), ("briefing-agents",)),
    (("port", "c++", "cpp", "schema", "boundary", "contract"),
     ("checking-data-contracts", "driving-tests-first")),
    (("implement", "build", "create", "add a", "write code"),
     ("driving-tests-first", "researching-first")),
)


def do_userprompt(payload: dict) -> None:
    """Per-turn routing nudge. No subprocess calls: must return instantly."""
    prompt = str(payload.get("prompt") or "").lower()
    named: list[str] = []
    for keys, skills in SKILL_KEYWORD_MAP:
        if any(k in prompt for k in keys):
            for s in skills:
                if s not in named:
                    named.append(s)
        if len(named) >= 5:
            break
    nudge = ROUTING_NUDGE
    if named:
        nudge = (
            "Skill routing check (harness-enforced): this turn's situation "
            "matches: " + ", ".join(named[:5]) + " — invoke each matching one "
            "via the Skill tool before acting (situations, not keywords, are "
            "the trigger; full table in /workspace/CLAUDE.md). Follow the "
            "coding-conduct block on any code change."
        )
    # User order 2026-08-21: unslop binds ALWAYS, from the first sentence —
    # a standing rule on every turn, not a routed suggestion.
    nudge += (
        " STANDING (writing-plainly, every user-visible sentence): verdict "
        "first; plain words; no puffery, no filler-ing tails, no fragment/"
        "arrow chains; calibrated hedging stays in research claims."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": nudge,
        }
    }))


SUBAGENT_NUDGE = (
    "House rules bind subagents too: follow the coding-conduct block and the "
    "situation->skill routing table in /workspace/CLAUDE.md (skills live at "
    "/workspace/.claude/skills/<name>/SKILL.md — read the matching one before "
    "acting on its situation). HARDWARE truth: /workspace/HARDWARE.md (13.6 cores "
    "effective; pin library thread counts). Evidence rules: verbatim quote + "
    "file:line anchors for claims; empty findings valid only after reading; "
    "your report is a claim — the diff/receipt is the evidence."
)


LANE_ACTIVE_TTL_S = 5400


def do_subagentstart(payload: dict) -> None:
    # Lanes cannot register Skill engagements in the transcript the gate
    # reads (their transcripts are separate files) — a lane was falsely
    # denied 4x on 2026-08-21. Lanes are governed by briefs + orchestrator
    # diff verification (D-002/D-010); mark the window so the gate defers.
    sid = (payload.get("session_id") or "nosid")[:32]
    try:
        HOOK_STATE.mkdir(parents=True, exist_ok=True)
        (HOOK_STATE / f"{sid}.lane_active").write_text(now())
    except Exception:
        pass
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": SUBAGENT_NUDGE,
        }
    }))


# Routing gate (user ruling 2026-08-21, hardened per the 2026-08-21 enforcement
# audit): an engine/tools edit in a session that never engaged a
# tests-first/review/debug skill is refused with the reason. Matches REAL
# engagements only — a Skill tool call ("skill": "<name>") or a tool call
# whose file_path targets the SKILL.md — never a bare path substring, which
# any ls/find output would contain (audit defect 2). The marker expires
# (D-104.4: salience at the moment of application; audit defect 1).
TDD_MARKER_SKILLS = (
    "driving-tests-first",
    "running-consolidated-review",
    "debugging-with-a-loop",
    "generalizing-fixes",
)
_TDD_NAMES = "|".join(TDD_MARKER_SKILLS)
_TDD_MARKER_RE = (
    r'(?:"skill"\s*:\s*"(?:' + _TDD_NAMES + r')"'
    r'|"file_path"\s*:\s*"[^"]*skills/(?:' + _TDD_NAMES + r')/SKILL\.md")'
)
TDD_MARKER_TTL_S = 1200


def _session_engaged_marker_skill(payload: dict, sid: str) -> bool:
    """True while this session holds a FRESH marker-skill engagement.
    Cached in a marker file with a TTL so re-invocation stays required.
    A recently spawned lane defers the gate (subagent engagements are
    invisible to this transcript — see do_subagentstart)."""
    HOOK_STATE.mkdir(parents=True, exist_ok=True)
    lane = HOOK_STATE / f"{sid}.lane_active"
    try:
        if lane.exists() and time.time() - lane.stat().st_mtime < LANE_ACTIVE_TTL_S:
            return True
    except Exception:
        pass
    marker = HOOK_STATE / f"{sid}.tdd_ok"
    try:
        if marker.exists():
            if time.time() - marker.stat().st_mtime < TDD_MARKER_TTL_S:
                return True
            marker.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        raw = Path(payload.get("transcript_path") or "").read_bytes().decode(
            "utf-8", "replace")
    except Exception:
        return False
    import re as _re
    # Only the TAIL can renew an expired marker: an old engagement earlier in
    # the transcript must not satisfy the gate forever (D-104.4).
    if _re.search(_TDD_MARKER_RE, raw[-400_000:]):
        try:
            marker.write_text(now())
        except Exception:
            pass
        return True
    return False


# Bash write-verbs that can modify code without Edit|Write (audit defect 3).
_BASH_WRITE_RE = (
    r'(?:sed\s+-i|>\s*/?(?:workspace/)?(?:engine|tools)/'
    r'|>>\s*/?(?:workspace/)?(?:engine|tools)/'
    r'|\btee\s+(?:-a\s+)?/?(?:workspace/)?(?:engine|tools)/'
    r'|\b(?:cp|mv)\s+[^|;&]*\s/?(?:workspace/)?(?:engine|tools)/)'
)


def _gate_verdict(payload: dict, sid: str) -> str | None:
    """Return the offending target description, or None if allowed."""
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    if tool == "Bash":
        command = str(tool_input.get("command") or "")
        import re as _re
        hit = _re.search(_BASH_WRITE_RE, command)
        if not hit:
            return None
        if "test_" in command or "/tests/" in command:
            return None
        if _session_engaged_marker_skill(payload, sid):
            return None
        return "Bash write into engine/tools (" + hit.group(0).strip()[:40] + ")"
    path = str(tool_input.get("file_path") or "")
    rel = path[len("/workspace/"):] if path.startswith("/workspace/") else path
    basename = rel.rsplit("/", 1)[-1]
    if (not rel.startswith(("engine/", "tools/"))
            or basename.startswith("test_") or "/tests/" in rel):
        return None
    if _session_engaged_marker_skill(payload, sid):
        return None
    return rel


def do_pretooluse(payload: dict) -> None:
    """Edit|Write|Bash gate on engine/ and tools/ code. Fails OPEN on any
    error — a broken gate must never block lawful work."""
    sid = (payload.get("session_id") or "nosid")[:32]
    try:
        offender = _gate_verdict(payload, sid)
    except Exception as exc:
        log(f"pretooluse fail-open: {type(exc).__name__}")
        offender = None
    if offender is None:
        print("{}")
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Routing gate: " + offender + " is engine/tools code but "
                "this session has no FRESH tests-first/review/debug skill "
                "engagement (markers expire after 20 min — D-104.4). Invoke "
                "the matching skill via the Skill tool, then retry. Test "
                "files are exempt."
            ),
        }
    }))
    log(f"pretooluse DENY sid={sid[:8]} target={offender}")


def main() -> int:
    verb = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    payload = read_payload()
    if "session_id" not in payload and payload.get("sessionId"):
        payload["session_id"] = payload["sessionId"]
    if "transcript_path" not in payload and payload.get("transcriptPath"):
        payload["transcript_path"] = payload["transcriptPath"]
    event = (
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or ""
    ).lower()
    verb = verb or event
    try:
        if verb == "userprompt":
            do_userprompt(payload)
        elif verb == "pretooluse":
            do_pretooluse(payload)
        elif verb == "subagentstart":
            do_subagentstart(payload)
        elif verb in ("sessionstart", "postcompact"):
            do_sessionstart(payload, verb)
        elif verb == "precompact":
            do_precompact(payload)
        elif verb == "stop":
            do_stop(payload)
        elif verb == "sessionend":
            do_sessionend(payload)
        else:
            log(f"unknown verb {verb!r} event {event!r}")
    except Exception as exc:
        log(f"FATAL {verb}: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
