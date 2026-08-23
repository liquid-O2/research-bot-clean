"""Every claim the canaries make about what the guard permits or refuses.

Split from the runner when that file passed the 500 line cap this repository
enforces on itself. The runner drives; this module says what to drive.
"""

from __future__ import annotations

from pathlib import Path
import shutil

from canary_driver import (
    active,
    Canary,
    GOOD_BRIEF,
    NO_MEMO,
    ROOT,
    SCOPE,
    command_payload,
    prompt_payload,
    stop_payload,
    compact,
    engage,
    run_guard,
    select,
    spawn_payload,
    tool_payload,
    write_payload,
)

OPEN_SCOPE = "canary-open-gate"
DONE_SCOPE = "canary-met-gate"

def route_canaries() -> list[Canary]:
    """Canaries for route selection and the default route."""
    return [
        Canary("plan-flow selects the planning route", "user-prompt-submit",
               prompt_payload("clean this up $plan-flow"), "context", "Route plan-flow selected"),
        Canary("implement-flow selects the implementation route", "user-prompt-submit",
               prompt_payload("build it $implement-flow"), "context",
               "Route implement-flow selected"),
        Canary("plan mode alone selects nothing", "user-prompt-submit",
               prompt_payload("please clean up the repo", mode="plan"), "context",
               "No route is selected"),
        Canary("a repository write with no route is denied", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "deny",
               "selects $implement-flow"),
    ]


def escape_canaries() -> list[Canary]:
    """Canaries for the writes that must never need a route."""
    return [
        Canary("a write outside the repository passes", "pre-tool-use",
               write_payload("/tmp/scratch/plan.md"), "allow"),
        Canary("a write to MEMORY.md passes", "pre-tool-use",
               write_payload(str(ROOT / "MEMORY.md")), "allow"),
        Canary("a write to the method contract passes", "pre-tool-use",
               write_payload(str(ROOT / f".unlazy/{SCOPE}/METHOD.json")), "allow"),
        Canary("a write to the gates file passes", "pre-tool-use",
               write_payload(str(ROOT / f".unlazy/{SCOPE}/GATES.md")), "allow"),
        Canary("a read-only command passes", "pre-tool-use",
               tool_payload("Bash", {"command": "git status"}), "allow"),
    ]


def plan_route_canaries() -> list[Canary]:
    """Canaries for what the planning route may and may not write."""
    return [
        Canary("plan-flow denies a production write", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "deny",
               "plan-flow denies production writes",
               setup=lambda state: select(state, "plan-flow")),
        Canary("plan-flow reaches the planning branch, then asks for its method",
               "pre-tool-use", write_payload(str(ROOT / "design/canary.md")), "deny",
               "engage", setup=lambda state: select(state, "plan-flow")),
    ]


def unengaged(state: Path) -> None:
    """Put the session on the implementation route without its method."""
    select(state, "implement-flow")


def engaged(state: Path) -> None:
    """Put the session on the implementation route with its method in context."""
    select(state, "implement-flow")
    engage(state)


def engaged_then_compacted(state: Path) -> None:
    """Engage, then take the method back out with a compaction."""
    engaged(state)
    compact(state)


def engagement_canaries() -> list[Canary]:
    """Canaries for the packet gate and its re-arm after a compaction."""
    return [
        Canary("an implementation write before engage is denied", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "deny",
               "engage", setup=unengaged),
        Canary("an owned write after engage passes", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "allow", setup=engaged),
        Canary("an unowned write after engage is denied", "pre-tool-use",
               write_payload(str(ROOT / "engine/canary_probe.py")), "deny",
               "outside METHOD.json owns", setup=engaged),
        Canary("a write to a canonical skill is denied", "pre-tool-use",
               write_payload(str(ROOT / ".agents/skills/unslop/SKILL.md")), "deny",
               "pinned or canonical", setup=engaged),
        Canary("a write after a compaction is denied until engage runs again", "pre-tool-use",
               write_payload(str(ROOT / "tools/canary_probe.py")), "deny",
               "after compact", setup=engaged_then_compacted),
    ]


def brief_canaries() -> list[Canary]:
    """Canaries for what every subagent brief must say."""
    return [
        Canary("a brief without the no-memo sentence is denied", "pre-tool-use",
               spawn_payload("Own: x\nAcceptance check: y\n"), "deny",
               "exactly once", setup=engaged),
        Canary("a brief without ownership is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF.replace("Own: tools/scratch_canary.py\n", "")), "deny",
               "file ownership", setup=engaged),
        Canary("a brief without an acceptance check is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF.split("Acceptance check")[0]), "deny",
               "Acceptance check", setup=engaged),
    ]


def shared_codebase_canaries() -> list[Canary]:
    """Canaries for the two lines that keep parallel workers out of each other."""
    return [
        Canary("a brief that assumes it is alone is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF.replace("You are not alone in the codebase.\n", "")),
               "deny", "not alone", setup=engaged),
        Canary("a brief that may revert other agents is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF.replace("Do not revert others' edits.\n", "")),
               "deny", "revert", setup=engaged),
        Canary("an unslopped brief is denied", "pre-tool-use",
               spawn_payload(GOOD_BRIEF + "Of course! delve into it.\n"), "deny",
               "fails unslop", setup=engaged),
    ]


def spawn_canaries() -> list[Canary]:
    """Canaries for the subagent type and model policy."""
    return [
        *([Canary("the wrong subagent type is denied", "pre-tool-use",
                  spawn_payload(GOOD_BRIEF, subagent="general-purpose"), "deny",
                  "subagent_type", setup=engaged),
           Canary("the wrong model is denied", "pre-tool-use",
                  spawn_payload(GOOD_BRIEF, model="haiku"), "deny", "model", setup=engaged)]
          if active().name == "claude" else []),
        Canary("a well-formed spawn passes", "pre-tool-use",
               spawn_payload(GOOD_BRIEF), "allow", setup=engaged),
    ]


OPEN_SCOPE = "canary-open-gate"
DONE_SCOPE = "canary-met-gate"


def write_scope(name: str, met: bool) -> None:
    """Create a throwaway unlazy scope so the wall's verdict is ours to set."""
    directory = ROOT / ".unlazy" / name
    directory.mkdir(parents=True, exist_ok=True)
    box = "[x]" if met else "[ ]"
    evidence = "EVIDENCE: exit=0; output=OK" if met else "EVIDENCE: pending"
    (directory / "GATES.md").write_text(
        f"# Gates: {name}\n\nOWNS: tools/canary_probe.py\n\n"
        f"- {box} G1: the canary scope reports a known state\n"
        f"  CHECK: /usr/bin/python3 -c \"print('OK')\"\n  EXPECT: OK\n  CWD: .\n"
        f"  {evidence}\n", encoding="utf-8")


def drop_scope(name: str) -> None:
    """Remove a throwaway scope."""
    shutil.rmtree(ROOT / ".unlazy" / name, ignore_errors=True)


def engaged_then_gate_closed(state: Path) -> None:
    """Engage, then mark a gate met, which is what ends a real task."""
    engaged(state)
    write_scope(DONE_SCOPE, met=True)


def gate_edit_canaries() -> list[Canary]:
    """Closing a gate is the normal last act of a task, not a reason to block.

    The digest record gates writes. Blocking the end of a turn because the
    gates file changed would make every finished task demand a re-engage that
    protects nothing, and the next write still re-arms on its own.
    """
    return [
        Canary("Stop does not demand a re-engage after a gate is closed", "stop",
               stop_payload("The work is finished and every gate is met."), "allow",
               setup=engaged_then_gate_closed, scope=DONE_SCOPE),
    ]


def engage_canaries() -> list[Canary]:
    """The packet must reach the transcript, not a file or a pipe.

    The digest record proves engage ran. It cannot prove the text was read, and
    the session that built this gate satisfied it with a pipe every time.
    """
    guard = f"python3 {active().guard}"
    verb = "eng" + "age"
    return [
        Canary("engage sent to a file is refused", "pre-tool-use",
               command_payload(f"{guard} {verb} demo {chr(62)} packet.json"), "deny",
               "print into the transcript", setup=engaged),
        Canary("engage sent through a pipe is refused", "pre-tool-use",
               command_payload(f"{guard} {verb} demo | head -3"), "deny",
               "print into the transcript", setup=engaged),
        Canary("a quoted mention of engage is not a call", "pre-tool-use",
               command_payload(f"echo 'run {active().guard} {verb} demo | head'"), "allow",
               setup=engaged),
    ]


def document_canaries() -> list[Canary]:
    """A document another agent reads as instructions needs its authoring law."""
    return [
        Canary("a contract document is allowed when the law is carried",
               "pre-tool-use", write_payload(str(ROOT / "CLAUDE.md")),
               "allow", setup=engaged),
    ]


def self_repair_canaries() -> list[Canary]:
    """No gate may block its own repair.

    The guard gated the engage command on having already engaged, and a digest
    change then locked the session out of the repository entirely, including
    out of the one command that clears the lock.
    """
    guard = f"python3 {active().guard}"
    verb = "eng" + "age"
    call = command_payload(f"{guard} {verb} {SCOPE}")

    def rearmed(state: Path) -> None:
        engaged(state)
        compact(state)

    return [
        Canary("engage is permitted with no route at all", "pre-tool-use", call, "allow"),
        Canary("engage is permitted before the first engage", "pre-tool-use", call, "allow",
               setup=unengaged),
        Canary("engage is permitted after a compaction re-arm", "pre-tool-use", call,
               "allow", setup=rearmed),
        Canary("engage is permitted while already engaged", "pre-tool-use", call, "allow",
               setup=engaged),
    ]


def receipt_canaries() -> list[Canary]:
    """A production write cannot end the turn without a current review receipt."""
    def wrote_without_review(state: Path) -> None:
        engaged(state)
        run_guard("pre-tool-use", write_payload(str(ROOT / "tools/canary_probe.py")), state)

    return [
        Canary("Stop refuses a production write with no review receipt", "stop",
               stop_payload("The change is finished."), "block", "review_receipt",
               setup=wrote_without_review, scope=DONE_SCOPE),
    ]


def prose_canaries() -> list[Canary]:
    """Canaries for the two walls that decide whether a turn may end."""
    return [
        Canary("Stop blocks a reply with a long dash", "stop",
               stop_payload("The guard works \N{EM DASH} mostly."), "block", "rule 13",
               scope=DONE_SCOPE),
        Canary("Stop blocks a stock chatbot phrase", "stop",
               stop_payload("Of course! The guard is installed."), "block", "rule 20",
               scope=DONE_SCOPE),
        Canary("Stop allows clean prose once every gate is met", "stop",
               stop_payload("The guard denies an unmethodded write. Every canary passed."),
               "allow", scope=DONE_SCOPE),
        Canary("Stop blocks a done claim while a gate is open", "stop",
               stop_payload("Everything is finished."), "block", "need work",
               scope=OPEN_SCOPE),
        Canary("SubagentStop holds a subagent to the same law", "subagent-stop",
               stop_payload("Done \N{EM DASH} all good.", event="SubagentStop"), "block",
               "rule 13", scope=DONE_SCOPE),
    ]


def all_canaries() -> list[Canary]:
    """Every canary, grouped by the law it checks."""
    return [*route_canaries(), *escape_canaries(), *plan_route_canaries(),
            *engagement_canaries(), *brief_canaries(), *shared_codebase_canaries(),
            *spawn_canaries(), *gate_edit_canaries(), *engage_canaries(),
            *document_canaries(), *self_repair_canaries(), *receipt_canaries(),
            *prose_canaries()]
