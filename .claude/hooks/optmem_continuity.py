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


def normalize_payload(payload: dict) -> dict:
    """Grok sends camelCase (toolName, toolInput, sessionId); Claude sends snake_case."""
    p = dict(payload or {})
    for snake, camel in (
        ("session_id", "sessionId"),
        ("transcript_path", "transcriptPath"),
        ("tool_name", "toolName"),
        ("tool_input", "toolInput"),
        ("hook_event_name", "hookEventName"),
        ("stop_hook_active", "stopHookActive"),
        ("prompt", "prompt"),
    ):
        if not p.get(snake) and p.get(camel) is not None:
            p[snake] = p[camel]
    ti = p.get("tool_input")
    if isinstance(ti, str):
        try:
            ti = json.loads(ti)
        except Exception:
            ti = {}
    if not isinstance(ti, dict):
        ti = ti if isinstance(ti, dict) else {}
    p["tool_input"] = ti
    return p


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
        # Compaction drops skill text and OptMem from context. Re-arm
        # the D-104 gates and require memo wake (Grok ignores this
        # stdout; PreToolUse deny is the recall).
        try:
            (HOOK_STATE / f"{sid}.tdd_ok").unlink(missing_ok=True)
            (HOOK_STATE / f"{sid}.agent_ok").unlink(missing_ok=True)
        except Exception:
            pass
        _arm_need_wake(sid)
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
            "POST-COMPACT: OptMem and skills are out of context. Summaries "
            "are not the memory. Run ~/.optmem/memo wake NOW and follow it "
            "to the end. PreToolUse denies every tool until you have. Then "
            "re-invoke each skill at its next matching situation."
        )
    event_name = "PostCompact" if (
        verb in ("postcompact", "post_compact")
        or str(payload.get("hook_event_name") or "").lower()
        in ("postcompact", "post_compact")
    ) else "SessionStart"
    out = {
        "hookSpecificOutput": {
            "hookEventName": event_name,
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


def _need_wake_path(sid: str) -> Path:
    return HOOK_STATE / f"{sid}.need_wake"


def _arm_need_wake(sid: str) -> None:
    """Compaction dropped OptMem from the model. PreToolUse will deny
    until ~/.optmem/memo wake runs. Grok ignores SessionStart/PostCompact
    stdout, so this marker is the enforce path."""
    try:
        HOOK_STATE.mkdir(parents=True, exist_ok=True)
        _need_wake_path(sid).write_text(now())
    except Exception:
        pass


def _need_wake(sid: str) -> bool:
    try:
        return _need_wake_path(sid).exists()
    except Exception:
        return False


def _clear_need_wake(sid: str) -> None:
    try:
        _need_wake_path(sid).unlink(missing_ok=True)
    except Exception:
        pass


def _is_wake_command(command: str) -> bool:
    c = command or ""
    if "optmem" not in c or "memo" not in c:
        return False
    import re as _re
    return bool(_re.search(r"memo\s+(?:wake|nap)\b", c))


_WAKE_DENY_REASON = (
    "POST-COMPACT: OptMem is out of context. Compaction summaries are "
    "not the memory. Run ~/.optmem/memo wake now and do exactly what it "
    "prints to the end (including any memo nap). Then retry. This harness "
    "ignores SessionStart/PostCompact stdout, so the deny is the recall."
)


def do_precompact(payload: dict) -> None:
    payload = normalize_payload(payload)
    sid_full = (payload.get("session_id") or "nosid")[:32]
    _arm_need_wake(sid_full)
    sid = sid_full[:8]
    trigger = payload.get("trigger") or ""
    dst = spool(payload)
    if _throttled(sid, "precompact", PRECOMPACT_THROTTLE_S):
        log(f"precompact sid={sid} spool={dst} throttled need_wake=1")
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
    log(f"precompact sid={sid} spool={dst} need_wake=1")
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
        names.extend(_re.findall(r'skills/([a-z0-9_-]+)/SKILL\.md', raw))
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


UNLAZY_MAX_BLOCKS = 6
UNLAZY_STATE = Path("/workspace/.unlazy-hook-state.json")


def _unlazy_block(payload: dict) -> bool:
    """D-111 (user, 2026-08-22): the unlazy gate wall.

    Never end a turn while GATES.md / gates/*.md carry an unmet gate. Parsing is
    delegated to tools/unlazy_gates.py so the runner the agent calls and the wall
    that stops it can never disagree. Zero tokens: a file scan, not a model call.
    An `ABANDON: <id> <reason>` line is the honest exit; six consecutive blocks
    with no ledger change release rather than trap.
    """
    try:
        if "/workspace/tools" not in sys.path:
            sys.path.insert(0, "/workspace/tools")
        from unlazy_gates import unlazy_stop_verdict
        cwd = Path(payload.get("cwd") or "/workspace")
        unmet, digest = unlazy_stop_verdict(cwd)
    except Exception as exc:  # a broken wall must never trap a session
        log(f"unlazy scan skipped: {exc!r}")
        return False
    if not unmet:
        UNLAZY_STATE.unlink(missing_ok=True)
        return False
    try:
        state = json.loads(UNLAZY_STATE.read_text())
    except (OSError, ValueError):
        state = {"hash": "", "blocks": 0}
    if state.get("hash") != digest:
        state = {"hash": digest, "blocks": 0}
    state["blocks"] = int(state.get("blocks", 0)) + 1
    try:
        UNLAZY_STATE.write_text(json.dumps(state))
    except OSError:
        pass
    if state["blocks"] > UNLAZY_MAX_BLOCKS:
        log(f"unlazy release after {UNLAZY_MAX_BLOCKS} blocks, {len(unmet)} unmet")
        return False
    listed = ", ".join(unmet[:5]) + (f", +{len(unmet) - 5} more" if len(unmet) > 5 else "")
    print(json.dumps({"decision": "block", "reason": (
        f"unlazy gate wall (D-111): {len(unmet)} gate(s) unmet: {listed}. A checked "
        f"box whose EVIDENCE still reads 'pending' counts as unmet. Open the ledger, "
        f"work the next unchecked gate, then run "
        f"`python3 tools/unlazy_gates.py` to execute the CHECK lines and record "
        f"evidence. If a gate is genuinely impossible, add "
        f"`ABANDON: <id> <reason>` at column 0 and say so in your report. "
        f"Done means every box checked with evidence, never a status summary.")}))
    return True


def do_stop(payload: dict) -> None:
    # Grok treats Stop additionalContext as "keep working". Print nothing
    # (except the one-shot promise-catcher block below).
    sid = (payload.get("session_id") or "nosid")[:32]
    if _unlazy_block(payload):
        log(f"stop unlazy-block sid={sid[:8]}")
        return
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


SKILL_ROOT = "/workspace/.claude/skills"

# First matching group wins. "draft a plan" is a complete user message in this
# repo — it must load the plan cluster and must NOT load implement skills.
# Implement skills fire later, when the AGENT writes production code
# in any folder (PreToolUse). Skills are mandatory, not suggestions.
SKILL_KEYWORD_MAP = (
    (("draft a plan", "write a plan", "create a plan", "make a plan",
      "draft plan"),
     ("sharpening-specs", "grilling", "to-spec", "to-tickets", "wayfinder",
      "architect", "poteto-mode", "codebase-design", "entry-v2-goal",
      "keeping-continuity", "clean-code-for-agents")),
    (("implement this", "implement", "do this", "build this", "land this"),
     ("implementing-work", "tdd", "driving-tests-first", "poteto-mode",
      "clean-code-for-agents")),
    (("bug", "fail", "error", "broken", "stall", "crash", "refus"),
     ("debugging-with-a-loop", "driving-tests-first")),
    (("launch", "rehearsal", "long run", "experiment", "fit", "measure"),
     ("operating-long-runs", "preregistering-results", "running-evals")),
    (("review",), ("running-consolidated-review",)),
    (("break down", "breakdown", "decompos", "multi-stage", "roadmap",
      "too big", "stages"), ("breaking-down-work",)),
    (("refactor",), ("breaking-down-work", "shaping-code-for-agents")),
    (("plan", "design", "spec", "freeze", "adopt"),
     ("sharpening-specs", "breaking-down-work", "entry-v2-goal")),
    (("commit", "tidy", "clean up", "stray"), ("tidying-workspace",)),
    (("done", "verified", "passing", "receipt"), ("verifying-with-receipts",)),
    (("gate", "threshold", "criterion"), ("encoding-goals-in-gates",)),
    (("write a skill", "create a skill", "edit a skill"),
     ("writing-for-agents",)),
    (("agent", "lane", "brief", "subagent", "workflow", "spawn"),
     ("writing-for-agents", "briefing-agents")),
    (("port", "c++", "cpp", "schema", "boundary", "contract"),
     ("checking-data-contracts", "driving-tests-first")),
    (("continue", "resume", "pick up"),
     ("keeping-continuity", "entry-v2-goal")),
)


def _named_skills_for_prompt(prompt: str) -> list[str]:
    named: list[str] = []
    text = (prompt or "").lower()
    for keys, skills in SKILL_KEYWORD_MAP:
        if any(k in text for k in keys):
            for s in skills:
                if s not in named:
                    named.append(s)
        if named:
            break
    return named[:12]


def _read_skill_nudge(named: list[str]) -> str:
    if named:
        paths = ", ".join(f"{SKILL_ROOT}/{s}/SKILL.md" for s in named)
        return (
            "This prompt matches: " + ", ".join(named) + ". "
            "READ those SKILL.md files NOW and follow them "
            f"({paths}). Skills are mandatory, not suggestions. "
            "This harness may have no Skill tool — "
            "reading the file is the invocation. The user will "
            "barely send follow-ups. When YOU later write production "
            "code in any folder, READ implementing-work and "
            "driving-tests-first yourself; they will not say implement."
        )
    return (
        "READ the matching SKILL.md under /workspace/.claude/skills/ "
        "and follow it. Skills are mandatory, not suggestions. "
        "The user will barely send follow-ups and will "
        "not name skills. A message that is only 'draft a plan' loads "
        "sharpening-specs, breaking-down-work, entry-v2-goal. When YOU "
        "write production code in any folder, READ implementing-work and "
        "driving-tests-first yourself — do not wait for them to say "
        "implement."
    )


def do_userprompt(payload: dict) -> None:
    """Per-turn routing nudge. No subprocess calls: must return instantly.

    Grok ignores UserPromptSubmit stdout (observe-only). Claude/OpenCode
    inject additionalContext. Implement skills are NOT required to appear
    here — they bind at PreToolUse when the agent edits code.
    """
    payload = normalize_payload(payload)
    prompt = str(payload.get("prompt") or "")
    named = _named_skills_for_prompt(prompt)
    nudge = _read_skill_nudge(named)
    sid = (payload.get("session_id") or "nosid")[:32]
    if _need_wake(sid):
        nudge = (
            "POST-COMPACT: OptMem is out of context. Run ~/.optmem/memo "
            "wake NOW and do exactly what it prints, then continue. "
        ) + nudge
    nudge += (
        " STANDING voice: unslop is mandatory (pstack). Every user-visible "
        "sentence. Not optional polish. READ "
        "/workspace/.claude/skills/unslop/SKILL.md and write that way. "
        "writing-plainly still applies for outcome-first house form. "
        "Verdict first; plain words; no puffery, no filler-ing tails, no "
        "fragment/arrow chains; calibrated hedging stays in research "
        "claims. Grilling: take recommended options yourself; ask the "
        "user only about the actual goal."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": nudge,
        }
    }))


SUBAGENT_NUDGE = (
    "House rules bind subagents too: follow the coding-conduct block and the "
    "skill table in /workspace/CLAUDE.md. Skills are mandatory, not "
    "suggestions. Skills live at "
    "/workspace/.claude/skills/<name>/SKILL.md — READ the matching file "
    "and follow it before acting. Before this spawn, the parent must have read "
    "writing-for-agents and briefing-agents. The user will not say "
    "implement; if you write production code in any folder, read "
    "implementing-work and driving-tests-first first. HARDWARE: "
    "/workspace/HARDWARE.md (13.6 cores). Evidence: verbatim quote + "
    "file:line; empty findings valid only after reading; the report is a "
    "claim, the diff/receipt is the evidence."
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


# Routing gate (user ruling 2026-08-21, Grok-fixed 2026-08-22,
# folder-agnostic 2026-08-22): a production-code write in ANY folder,
# in a session that never engaged a tests-first/implement/review/debug
# skill, is refused. Matches REAL engagements only — a Skill tool call
# ("skill": "<name>") OR a Read of SKILL.md via file_path (Claude) or
# target_file (Grok). Never a bare path substring from ls/find (audit
# defect 2). Marker expires 20 min (D-104.4). THIS is how implement
# skills auto-trigger: the user will not say "implement"; the first
# production-code write is the trigger, wherever the file lives.
TDD_MARKER_SKILLS = (
    "driving-tests-first",
    "tdd",
    "implementing-work",
    "poteto-mode",
    "running-consolidated-review",
    "debugging-with-a-loop",
    "diagnosing-bugs",
    "generalizing-fixes",
    "clean-code-for-agents",
)
AGENT_MARKER_SKILLS = (
    "writing-for-agents",
    "briefing-agents",
)
TDD_MARKER_TTL_S = 1200
_SHELL_TOOLS = frozenset({
    "Bash", "bash", "run_terminal_command", "Shell", "shell",
})
_AGENT_TOOLS = frozenset({
    "spawn_subagent", "Task", "task", "workflow", "Agent", "agent",
})
_CODE_EXTS = frozenset({
    ".py", ".pyi", ".pyx", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh",
    ".hpp", ".hxx", ".cu", ".cuh", ".rs", ".go", ".java",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
})
_EXEMPT_PREFIXES = (
    ".claude/", ".grok/", ".codex/", ".opencode/", ".agents/",
    ".optmem/", "design/", "docs/", "attic/", "artifacts/",
    "provenance/", "compaction/",
)
_DENY_REASON = (
    "Routing gate: {offender} is production code. The user did not "
    "and will not say 'implement'. READ these files, then retry the "
    "edit: /workspace/.claude/skills/implementing-work/SKILL.md and "
    "/workspace/.claude/skills/driving-tests-first/SKILL.md. Reading "
    "the file is the engagement (this harness may have no Skill tool). "
    "Markers expire after 20 min (D-104.4). Test files and "
    "harness/design/docs dirs are exempt. The folder name does not "
    "matter — lab/src/lib are gated the same as engine/tools."
)
_AGENT_DENY_REASON = (
    "Routing gate: {offender} talks to another agent. READ "
    "/workspace/.claude/skills/writing-for-agents/SKILL.md and "
    "/workspace/.claude/skills/briefing-agents/SKILL.md, then retry. "
    "Reading the file is the engagement. Markers expire after 20 min "
    "(D-104.4)."
)


def _engagement_re(skill_names: tuple[str, ...]) -> str:
    names = "|".join(skill_names)
    return (
        r'(?:"skill"\s*:\s*"(?:' + names + r')"'
        r'|"(?:file_path|target_file)"\s*:\s*"[^"]*skills/(?:'
        + names + r')/SKILL\.md")'
    )


def _session_engaged(
    payload: dict,
    sid: str,
    *,
    skills: tuple[str, ...],
    marker_stem: str,
    ttl_s: float,
) -> bool:
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
    marker = HOOK_STATE / f"{sid}.{marker_stem}"
    try:
        if marker.exists():
            if time.time() - marker.stat().st_mtime < ttl_s:
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
    if _re.search(_engagement_re(skills), raw[-400_000:]):
        try:
            marker.write_text(now())
        except Exception:
            pass
        return True
    return False


def _session_engaged_marker_skill(payload: dict, sid: str) -> bool:
    return _session_engaged(
        payload, sid,
        skills=TDD_MARKER_SKILLS, marker_stem="tdd_ok", ttl_s=TDD_MARKER_TTL_S,
    )


def _session_engaged_agent_skill(payload: dict, sid: str) -> bool:
    return _session_engaged(
        payload, sid,
        skills=AGENT_MARKER_SKILLS, marker_stem="agent_ok",
        ttl_s=TDD_MARKER_TTL_S,
    )


# Fallback for engine/tools shell writes the dest parser might miss.
_BASH_WRITE_RE = (
    r'(?:sed\s+-i|>\s*/?(?:workspace/)?(?:engine|tools)/'
    r'|>>\s*/?(?:workspace/)?(?:engine|tools)/'
    r'|\btee\s+(?:-a\s+)?/?(?:workspace/)?(?:engine|tools)/'
    r'|\b(?:cp|mv)\s+[^|;&]*\s/?(?:workspace/)?(?:engine|tools)/)'
)


def _tool_path(tool_input: dict) -> str:
    return str(
        tool_input.get("file_path")
        or tool_input.get("target_file")
        or tool_input.get("path")
        or tool_input.get("script_path")
        or ""
    )


def _workspace_rel(path: str) -> str | None:
    p = (path or "").replace("\\", "/").strip().strip("'\"")
    if not p or p in {".", "/"}:
        return None
    if p.startswith("/workspace/"):
        p = p[len("/workspace/"):]
    elif p.startswith("workspace/"):
        p = p[len("workspace/"):]
    elif p.startswith("./"):
        p = p[2:]
    elif p.startswith("/") or p.startswith("~") or p.startswith("../"):
        return None
    return p.lstrip("/") or None


def _is_test_path(rel: str) -> bool:
    base = rel.rsplit("/", 1)[-1]
    padded = f"/{rel}/"
    return (
        "/tests/" in padded
        or "/test/" in padded
        or base.startswith("test_")
        or "_test." in base
        or base.endswith("_test")
    )


def _is_gated_code_path(path: str) -> bool:
    """True for production source in the workspace, any folder.

    Exempt: tests, harness config, design/docs/attic/artifacts.
    The folder name is not the trigger — the file type is.
    """
    rel = _workspace_rel(path)
    if not rel:
        return False
    if any(rel.startswith(p) for p in _EXEMPT_PREFIXES):
        return False
    if _is_test_path(rel):
        return False
    base = rel.rsplit("/", 1)[-1]
    if "." not in base:
        return False
    ext = "." + base.rsplit(".", 1)[-1].lower()
    return ext in _CODE_EXTS


def _shell_write_destinations(command: str) -> list[str]:
    """Destinations of write-verbs in a shell command. Not the files it runs."""
    import re as _re
    dests: list[str] = []
    dests.extend(_re.findall(r'(?:>>?|\btee(?:\s+-a)?)\s*(\S+)', command))
    for m in _re.finditer(r'\b(?:cp|mv)\s+(.+?)(?:\s*[|;&]|$)', command):
        args = m.group(1).split()
        if args:
            dests.append(args[-1])
    for m in _re.finditer(r'\bsed\s+-i\S*(?:\s+\S+)+', command):
        toks = m.group(0).split()
        if toks:
            dests.append(toks[-1])
    return dests


def _gate_verdict(payload: dict, sid: str) -> str | None:
    """Return the offending target description, or None if allowed.

    Agent spawns are prefixed with 'agent:' so do_pretooluse can pick
    the writing-for-agents reason.
    """
    payload = normalize_payload(payload)
    tool = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    if _need_wake(sid):
        if tool in _SHELL_TOOLS:
            command = str(tool_input.get("command") or "")
            if _is_wake_command(command):
                if "wake" in command:
                    _clear_need_wake(sid)
                return None
        return "wake:post-compact"
    if tool in _AGENT_TOOLS:
        if _session_engaged_agent_skill(payload, sid):
            return None
        return "agent:" + tool
    if tool in _SHELL_TOOLS:
        command = str(tool_input.get("command") or "")
        import re as _re
        dests = [
            d for d in _shell_write_destinations(command)
            if _is_gated_code_path(d)
        ]
        if dests:
            if _session_engaged_marker_skill(payload, sid):
                return None
            return "shell write " + dests[0]
        hit = _re.search(_BASH_WRITE_RE, command)
        if not hit:
            return None
        if "test_" in command or "/tests/" in command:
            return None
        if _session_engaged_marker_skill(payload, sid):
            return None
        return "shell write into engine/tools (" + hit.group(0).strip()[:40] + ")"
    path = _tool_path(tool_input)
    if not _is_gated_code_path(path):
        return None
    if _session_engaged_marker_skill(payload, sid):
        return None
    rel = _workspace_rel(path) or path
    return rel


def do_pretooluse(payload: dict) -> None:
    """Production-code write gate + agent-spawn gate. Fails OPEN (D-108).

    Emits both Grok `{decision: deny, reason}` and Claude
    `permissionDecision` so either harness actually blocks.
    """
    payload = normalize_payload(payload)
    sid = (payload.get("session_id") or "nosid")[:32]
    try:
        offender = _gate_verdict(payload, sid)
    except Exception as exc:
        log(f"pretooluse fail-open: {type(exc).__name__}")
        offender = None
    if offender is None:
        print("{}")
        return
    if str(offender).startswith("wake:"):
        reason = _WAKE_DENY_REASON
    elif str(offender).startswith("agent:"):
        reason = _AGENT_DENY_REASON.format(offender=offender)
    else:
        reason = _DENY_REASON.format(offender=offender)
    print(json.dumps({
        "decision": "deny",
        "reason": reason,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }))
    log(f"pretooluse DENY sid={sid[:8]} target={offender}")


def main() -> int:
    verb = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    payload = normalize_payload(read_payload())
    event = (
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or ""
    ).lower()
    verb = verb or event
    try:
        if verb in ("userprompt", "user_prompt_submit"):
            do_userprompt(payload)
        elif verb in ("pretooluse", "pre_tool_use"):
            do_pretooluse(payload)
        elif verb in ("subagentstart", "subagent_start"):
            do_subagentstart(payload)
        elif verb in ("sessionstart", "session_start", "postcompact",
                      "post_compact"):
            do_sessionstart(payload, verb)
        elif verb in ("precompact", "pre_compact"):
            do_precompact(payload)
        elif verb == "stop":
            do_stop(payload)
        elif verb in ("sessionend", "session_end"):
            do_sessionend(payload)
        else:
            log(f"unknown verb {verb!r} event {event!r}")
    except Exception as ext:
        log(f"FATAL {verb}: {type(ext).__name__}: {ext}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
