#!/usr/bin/env python3
"""Selftest for the D-104 skill-routing gate and the 'draft a plan' nudge.

Does not touch engine/ hardware. Run:
  python3 tools/test_skill_routing_gate.py --selftest
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

HOOK = Path("/workspace/.claude/hooks/optmem_continuity.py")


def _load():
    spec = importlib.util.spec_from_file_location("optmem_continuity", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _stdout(fn, payload):
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(payload)
    raw = buf.getvalue().strip()
    return json.loads(raw) if raw else {}


def selftest() -> int:
    mod = _load()
    failures = []

    def check(name, cond, detail=""):
        if not cond:
            failures.append(f"FAIL {name}: {detail}")

    # 1. Grok camelCase engine edit is denied without a skill read.
    grok_edit = {
        "sessionId": "gate1",
        "toolName": "search_replace",
        "toolInput": {"file_path": "/workspace/engine/entry_v2/foo.py"},
        "transcriptPath": "/no/such/transcript.jsonl",
    }
    grok_edit = mod.normalize_payload(grok_edit)
    offender = mod._gate_verdict(grok_edit, "gate1")
    check("grok-camel-deny", offender is not None, f"got {offender!r}")

    # 2. Reading SKILL.md via Grok target_file counts as engagement.
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "t.jsonl"
        tp.write_text(
            json.dumps({
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use",
                    "name": "read_file",
                    "input": {
                        "target_file":
                            "/workspace/.claude/skills/driving-tests-first/SKILL.md",
                    },
                }]},
            })
            + "\n"
        )
        engaged = {
            "sessionId": "gate2",
            "toolName": "search_replace",
            "toolInput": {"file_path": "/workspace/engine/entry_v2/foo.py"},
            "transcriptPath": str(tp),
        }
        engaged = mod.normalize_payload(engaged)
        # Force a unique sid so the TTL marker file is fresh.
        sid = "gate2test"
        marker = mod.HOOK_STATE / f"{sid}.tdd_ok"
        marker.unlink(missing_ok=True)
        lane = mod.HOOK_STATE / f"{sid}.lane_active"
        lane.unlink(missing_ok=True)
        offender2 = mod._gate_verdict(engaged, sid)
        check("grok-target-file-engagement", offender2 is None,
              f"still denied: {offender2!r}")
        marker.unlink(missing_ok=True)

    # 3. Deny JSON carries Grok's decision:deny AND Claude permissionDecision.
    denied = _stdout(mod.do_pretooluse, grok_edit)
    check("deny-decision", denied.get("decision") == "deny",
          f"keys={list(denied)}")
    reason = denied.get("reason") or ""
    nested = (denied.get("hookSpecificOutput") or {})
    check("deny-read-skillmd", "SKILL.md" in reason
          or "SKILL.md" in nested.get("permissionDecisionReason", ""),
          reason[:200])
    check("deny-no-skill-tool-only", "Skill tool" not in reason
          or "read" in reason.lower(), reason[:200])

    # 4. test_ files are exempt.
    test_edit = mod.normalize_payload({
        "sessionId": "gate4",
        "toolName": "search_replace",
        "toolInput": {"file_path": "/workspace/engine/entry_v2/test_foo.py"},
        "transcriptPath": "/nope",
    })
    check("test-exempt", mod._gate_verdict(test_edit, "gate4") is None)

    # 5. The whole user message is "draft a plan" — load plan skills.
    plan = _stdout(mod.do_userprompt, {"prompt": "draft a plan"})
    ctx = ((plan.get("hookSpecificOutput") or {}).get("additionalContext") or "")
    for need in ("sharpening-specs", "grilling", "to-spec", "to-tickets",
                 "wayfinder", "architect", "poteto-mode", "entry-v2-goal"):
        check(f"draft-a-plan-loads-{need}", need in ctx, ctx[:500])
    named_plan = mod._named_skills_for_prompt("draft a plan")
    check("draft-a-plan-named-cluster",
          "sharpening-specs" in named_plan
          and "grilling" in named_plan
          and "to-tickets" in named_plan
          and "implementing-work" not in named_plan,
          repr(named_plan))

    # 6. "implement this" is a different prompt and loads implement skills.
    impl = _stdout(mod.do_userprompt, {"prompt": "implement this"})
    ictx = ((impl.get("hookSpecificOutput") or {}).get("additionalContext") or "")
    check("implement-this-loads", "implementing-work" in ictx
          or "driving-tests-first" in ictx, ictx[:400])

    # 7. Nudge tells the agent to READ SKILL.md (Grok has no Skill tool).
    check("nudge-says-read", "SKILL.md" in ctx, ctx[:200])
    check("nudge-mandatory", "mandatory, not suggestions" in ctx.lower(),
          ctx[:250])

    def _skill_read_transcript(td, skill_name):
        tp = Path(td) / "t.jsonl"
        tp.write_text(
            json.dumps({
                "type": "assistant",
                "message": {"content": [{
                    "type": "tool_use",
                    "name": "read_file",
                    "input": {
                        "target_file":
                            f"/workspace/.claude/skills/{skill_name}/SKILL.md",
                    },
                }]},
            })
            + "\n"
        )
        return str(tp)

    def _edit(sid, path, transcript="/nope"):
        return mod.normalize_payload({
            "sessionId": sid,
            "toolName": "search_replace",
            "toolInput": {"file_path": path},
            "transcriptPath": transcript,
        })

    # 8. Production code in a new folder is gated (not only engine/tools).
    lab = _edit("gate8", "/workspace/lab/entry_policy.py")
    check("other-folder-code-denied",
          mod._gate_verdict(lab, "gate8") is not None)

    src_cpp = _edit("gate8b", "/workspace/src/walk.cpp")
    check("other-folder-cpp-denied",
          mod._gate_verdict(src_cpp, "gate8b") is not None)

    # 9. design/ markdown is not product code.
    spec = _edit("gate9", "/workspace/design/ENTRY_PLAN.md")
    check("design-md-allowed", mod._gate_verdict(spec, "gate9") is None)

    # 10. Harness Python under .claude/ is exempt.
    hookf = _edit("gate10",
                  "/workspace/.claude/hooks/optmem_continuity.py")
    check("harness-py-allowed",
          mod._gate_verdict(hookf, "gate10") is None)

    # 11. Shell write into a new code folder is denied.
    bash_lab = mod.normalize_payload({
        "sessionId": "gate11",
        "toolName": "run_terminal_command",
        "toolInput": {
            "command": "cat > /workspace/lab/foo.py <<'EOF'\nprint(1)\nEOF",
        },
        "transcriptPath": "/nope",
    })
    check("bash-other-folder-denied",
          mod._gate_verdict(bash_lab, "gate11") is not None)

    # 12. Running a script is not a write.
    bash_run = mod.normalize_payload({
        "sessionId": "gate12",
        "toolName": "run_terminal_command",
        "toolInput": {"command": "python3 /workspace/lab/foo.py"},
        "transcriptPath": "/nope",
    })
    check("bash-run-not-write",
          mod._gate_verdict(bash_run, "gate12") is None)

    # 13. spawn_subagent is denied until writing-for-agents is read.
    spawn = mod.normalize_payload({
        "sessionId": "gate13",
        "toolName": "spawn_subagent",
        "toolInput": {"prompt": "do a thing", "description": "x"},
        "transcriptPath": "/nope",
    })
    check("spawn-denied", mod._gate_verdict(spawn, "gate13") is not None)

    # 14. Reading writing-for-agents unlocks spawn.
    with tempfile.TemporaryDirectory() as td:
        tp = _skill_read_transcript(td, "writing-for-agents")
        sid = "gate14test"
        (mod.HOOK_STATE / f"{sid}.agent_ok").unlink(missing_ok=True)
        (mod.HOOK_STATE / f"{sid}.lane_active").unlink(missing_ok=True)
        engaged_spawn = mod.normalize_payload({
            "sessionId": sid,
            "toolName": "spawn_subagent",
            "toolInput": {"prompt": "do a thing", "description": "x"},
            "transcriptPath": tp,
        })
        check("spawn-engaged",
              mod._gate_verdict(engaged_spawn, sid) is None,
              "still denied after writing-for-agents read")
        (mod.HOOK_STATE / f"{sid}.agent_ok").unlink(missing_ok=True)

    # 15. Every-turn nudge names unslop as standing voice law.
    check("standing-unslop", "unslop is mandatory" in ctx.lower(), ctx[:300])

    # 16. Subagent start names writing-for-agents.
    sub = _stdout(mod.do_subagentstart, {"sessionId": "subnudge1"})
    actx = ((sub.get("hookSpecificOutput") or {}).get("additionalContext")
            or "")
    check("subagent-nudge-wfa", "writing-for-agents" in actx, actx[:300])
    (mod.HOOK_STATE / "subnudge1.lane_active").unlink(missing_ok=True)

    # 17. "create a workflow" loads writing-for-agents + briefing-agents.
    named_wf = mod._named_skills_for_prompt("create a workflow")
    check("workflow-names-wfa",
          "writing-for-agents" in named_wf
          and "briefing-agents" in named_wf,
          repr(named_wf))

    # 18. CLAUDE.md and AGENTS.md stay a pair on the standing laws.
    claude_txt = Path("/workspace/CLAUDE.md").read_text()
    agents_txt = Path("/workspace/AGENTS.md").read_text()
    for needle in ("unslop", "writing-for-agents", "production code",
                   "Skills are mandatory, not suggestions",
                   "Unslop is mandatory",
                   "Post-compact"):
        check(f"claude-has-{needle}", needle in claude_txt,
              f"missing {needle!r} in CLAUDE.md")
        check(f"agents-has-{needle}", needle in agents_txt,
              f"missing {needle!r} in AGENTS.md")

    # 19. After compact, every tool is denied until memo wake.
    sid_w = "waketest1"
    (mod.HOOK_STATE / f"{sid_w}.need_wake").unlink(missing_ok=True)
    (mod.HOOK_STATE / f"{sid_w}.tdd_ok").unlink(missing_ok=True)
    (mod.HOOK_STATE / f"{sid_w}.lane_active").unlink(missing_ok=True)
    mod._arm_need_wake(sid_w)
    blocked = _edit(sid_w, "/workspace/design/ENTRY_PLAN.md")
    check("postcompact-blocks-read",
          mod._gate_verdict(blocked, sid_w) is not None)
    denied = _stdout(mod.do_pretooluse, blocked)
    reason = (denied.get("reason") or "") + (
        (denied.get("hookSpecificOutput") or {}).get(
            "permissionDecisionReason") or "")
    check("postcompact-reason-wake", "memo wake" in reason, reason[:240])
    wake_cmd = mod.normalize_payload({
        "sessionId": sid_w,
        "toolName": "run_terminal_command",
        "toolInput": {"command": "~/.optmem/memo wake"},
        "transcriptPath": "/nope",
    })
    check("wake-cmd-allowed",
          mod._gate_verdict(wake_cmd, sid_w) is None)
    check("wake-clears-marker",
          not (mod.HOOK_STATE / f"{sid_w}.need_wake").exists())
    check("after-wake-md-allowed",
          mod._gate_verdict(blocked, sid_w) is None)
    (mod.HOOK_STATE / f"{sid_w}.need_wake").unlink(missing_ok=True)

    # 20. Grok/Codex PreToolUse must not be Edit-only — compact recall
    # has to fire on the first tool, which is often a read.
    for hook_path, label in (
        ("/workspace/.grok/hooks/optmem.json", "grok"),
        ("/workspace/.codex/hooks.json", "codex"),
        ("/workspace/.claude/settings.local.json", "claude"),
    ):
        cfg = json.loads(Path(hook_path).read_text())
        ptu = (cfg.get("hooks") or {}).get("PreToolUse") or []
        matchers = [g.get("matcher") for g in ptu]
        all_tools = any(m in (None, "", ".*") for m in matchers)
        check(f"{label}-pretooluse-all-tools", all_tools,
              f"matchers={matchers}")

    # 21. D-111 unlazy gate wall: the Stop hook is the ledger's enforcement.
    # Four fixtures + a false-positive guard. A gate with no fixture is a nudge.
    def _stop_verdict(files: dict, blocks_reset: bool = True) -> dict:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel, text in files.items():
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text)
            if blocks_reset:
                mod.UNLAZY_STATE.unlink(missing_ok=True)
            return _stdout(mod._unlazy_block, {"cwd": str(root)})

    unmet = _stop_verdict({"GATES.md": "- [ ] G1: undone\n  EVIDENCE: pending\n"})
    check("unlazy-unmet-blocks",
          unmet.get("decision") == "block" and "G1" in unmet.get("reason", ""),
          f"got {unmet!r}")

    claimed = _stop_verdict({"GATES.md": "- [x] G1: claimed\n  EVIDENCE: pending\n"})
    check("unlazy-checked-pending-evidence-blocks",
          claimed.get("decision") == "block" and "G1" in claimed.get("reason", ""),
          f"got {claimed!r}")

    proved = _stop_verdict({"GATES.md": "- [x] G1: done\n  EVIDENCE: 8/8 passed\n"})
    check("unlazy-met-allows", proved == {}, f"got {proved!r}")

    quit_line = _stop_verdict(
        {"GATES.md": "- [ ] G1: impossible\n  EVIDENCE: pending\n\nABANDON: G1 no hardware\n"})
    check("unlazy-abandon-allows", quit_line == {}, f"got {quit_line!r}")

    none_at_all = _stop_verdict({"README.md": "not a ledger\n"})
    check("unlazy-no-ledger-allows", none_at_all == {}, f"got {none_at_all!r}")

    # A leaf under gates/ walls this session only once this session has worked
    # it (scope defect 2026-08-23: two agents in one directory walled each
    # other). Unowned, it is somebody else's ledger and must not block us.
    leafed = _stop_verdict({"gates/leaf-a.md": "- [ ] L1: leaf\n  EVIDENCE: pending\n"})
    check("unlazy-unowned-leaf-does-not-block", leafed == {}, f"got {leafed!r}")

    # Release valve: MAX_BLOCKS consecutive stops with an unchanged ledger must
    # let the session go rather than trap it.
    stuck = {"GATES.md": "- [ ] G1: stuck\n  EVIDENCE: pending\n"}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "GATES.md").write_text(stuck["GATES.md"])
        mod.UNLAZY_STATE.unlink(missing_ok=True)
        seen = [_stdout(mod._unlazy_block, {"cwd": str(root)})
                for _ in range(mod.UNLAZY_MAX_BLOCKS + 1)]
    check("unlazy-blocks-up-to-max",
          all(s.get("decision") == "block" for s in seen[:mod.UNLAZY_MAX_BLOCKS]),
          f"got {[s.get('decision') for s in seen]!r}")
    check("unlazy-releases-after-max", seen[-1] == {}, f"got {seen[-1]!r}")
    mod.UNLAZY_STATE.unlink(missing_ok=True)

    # 21b. End-to-end wiring: do_stop itself must emit the block, not just
    # _unlazy_block. A fixture on the helper alone would pass even if the wall
    # were never called from the hook's Stop path.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "GATES.md").write_text("- [ ] W1: wired\n  EVIDENCE: pending\n")
        mod.UNLAZY_STATE.unlink(missing_ok=True)
        wired = _stdout(mod.do_stop, {"cwd": str(root), "session_id": "unlazywire"})
    check("unlazy-do_stop-emits-block",
          wired.get("decision") == "block" and "W1" in wired.get("reason", ""),
          f"got {wired!r}")
    mod.UNLAZY_STATE.unlink(missing_ok=True)

    # 21c. D-111 scope defect, found 2026-08-23: the wall scanned every
    # gates/*.md under the cwd, so two agents working in /workspace walled each
    # other - one session's in-flight leaf ledger blocked the other's stop, and
    # neither could clear a gate it does not own. A session is walled by ITS OWN
    # ledgers: GATES.md always, plus any leaf ledger this session has actually
    # run the runner against.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "GATES.md").write_text("- [x] M1: mine\n  EVIDENCE: done\n")
        (root / "gates").mkdir()
        (root / "gates" / "someone-else.md").write_text(
            "- [ ] X1: another session's leaf\n  EVIDENCE: pending\n")
        mod.UNLAZY_STATE.unlink(missing_ok=True)
        foreign = _stdout(mod._unlazy_block, {"cwd": str(root), "session_id": "mine"})
        check("unlazy-foreign-ledger-does-not-wall-me", foreign == {}, f"got {foreign!r}")

        # But a leaf this session HAS worked is enforced, so orchestrated mode
        # still walls its own driver.
        import subprocess
        subprocess.run([sys.executable, "/workspace/tools/unlazy_gates.py", "--status",
                        str(root / "gates" / "someone-else.md")],
                       capture_output=True, env={**os.environ, "UNLAZY_SESSION": "mine"})
        mod.UNLAZY_STATE.unlink(missing_ok=True)
        owned = _stdout(mod._unlazy_block, {"cwd": str(root), "session_id": "mine"})
        check("unlazy-own-leaf-still-walls-me",
              owned.get("decision") == "block" and "X1" in owned.get("reason", ""),
              f"got {owned!r}")
    mod.UNLAZY_STATE.unlink(missing_ok=True)

    # 22. The routing table names unlazy in BOTH always-on files (SKILLS.md law).
    for doc in ("/workspace/AGENTS.md", "/workspace/CLAUDE.md"):
        check(f"unlazy-routed-{Path(doc).stem.lower()}",
              "unlazy" in Path(doc).read_text(), doc)

    if failures:
        print("\n".join(failures), file=sys.stderr)
        print(f"{len(failures)} failed", file=sys.stderr)
        return 1
    print("test_skill_routing_gate: PASS")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv or len(sys.argv) == 1:
        raise SystemExit(selftest())
    print("usage: python3 tools/test_skill_routing_gate.py --selftest",
          file=sys.stderr)
    raise SystemExit(2)
