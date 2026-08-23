#!/usr/bin/env python3
"""Gate ledger parser, runner and Stop verdict for the `unlazy` skill (D-111).

House authority for the gate-file format specified in
`.claude/skills/unlazy/references/gates.md`. The vendored upstream
`scripts/gate-check.mjs` is kept as the reference implementation only: it needs
node, and node is absent from the bare environment hooks run in
(`env -i sh -c 'command -v node'` -> nothing), while `/usr/bin/python3` is what
every harness hook in this repo already calls. One parser, so the runner the
agent uses and the wall the Stop hook applies can never disagree.

  python3 tools/unlazy_gates.py                 # run unmet checks, flip boxes
  python3 tools/unlazy_gates.py --status FILE   # report only, write nothing
  python3 tools/unlazy_gates.py --selftest      # fixtures, no repo state

Exit: 0 all met or honestly abandoned, 1 unmet remain, 2 usage/parse error.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

UNLAZY_GATE_RE = re.compile(r"^- \[( |x|X)\] (.*)$")
UNLAZY_ATTR_RE = re.compile(r"^\s+(CHECK|EXPECT|EVIDENCE):\s?(.*)$")
# Anchored at column 0 exactly as references/gates.md specifies, so a ledger
# that satisfies this parser also satisfies the upstream node scripts.
UNLAZY_ABANDON_RE = re.compile(r"^ABANDON:\s*(\S+)\s*(.*)$")
UNLAZY_EVIDENCE_MAX = 200
UNLAZY_DEFAULT_TIMEOUT_S = 120


@dataclass
class UnlazyGate:
    """One checkbox in a gate ledger."""

    gate_id: str
    title: str
    checked: bool
    line: int
    check: str | None = None
    expect: str | None = None
    evidence: str | None = None
    evidence_line: int = -1

    @property
    def evidence_pending(self) -> bool:
        return self.evidence is None or self.evidence.strip().lower() == "pending"


@dataclass
class UnlazyLedger:
    gates: list[UnlazyGate] = field(default_factory=list)
    abandoned: dict[str, str] = field(default_factory=dict)


def unlazy_parse_gates(text: str) -> UnlazyLedger:
    """Parse a gate ledger. Format spec: unlazy/references/gates.md."""
    ledger = UnlazyLedger()
    cur: UnlazyGate | None = None
    for i, line in enumerate(text.split("\n")):
        m = UNLAZY_GATE_RE.match(line)
        if m:
            body = m.group(2)
            id_m = re.match(r"^(\S+?):", body)
            cur = UnlazyGate(
                gate_id=id_m.group(1) if id_m else f"line{i + 1}",
                title=re.sub(r"^\S+?:\s*", "", body.strip()),
                checked=m.group(1).lower() == "x",
                line=i,
            )
            ledger.gates.append(cur)
            continue
        attr = UNLAZY_ATTR_RE.match(line) if cur else None
        if attr:
            key, val = attr.group(1).lower(), attr.group(2).strip()
            if key == "check":
                cur.check = val
            elif key == "expect":
                cur.expect = val
            else:
                cur.evidence = val
                cur.evidence_line = i
            continue
        ab = UNLAZY_ABANDON_RE.match(line)
        if ab:
            ledger.abandoned[ab.group(1).rstrip(":")] = ab.group(2) or "(no reason)"
        if line.startswith("#") or line.startswith("- "):
            cur = None
    return ledger


def unlazy_unmet(ledger: UnlazyLedger) -> list[tuple[str, str]]:
    """(gate_id, why) for every gate that is not honestly finished.

    A checked box whose EVIDENCE still reads `pending` counts as UNMET and is
    listed first: a checkbox is a claim, evidence is the proof, and
    checked-without-evidence is the exact failure this ledger exists to catch.
    """
    unmet: list[tuple[str, str]] = []
    for gate in ledger.gates:
        if gate.gate_id in ledger.abandoned:
            continue
        if not gate.checked:
            unmet.append((gate.gate_id, "unchecked"))
        elif gate.evidence_pending:
            unmet.append((gate.gate_id, "checked but EVIDENCE pending"))
    return unmet


def unlazy_expect_matches(expect: str, output: str) -> bool:
    """Substring match, or a regex when the EXPECT value is /slash-wrapped/."""
    rx = re.match(r"^/(.+)/([a-z]*)$", expect, re.DOTALL)
    if rx:
        flags = 0
        for ch in rx.group(2):
            flags |= {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}.get(ch, 0)
        try:
            return re.search(rx.group(1), output, flags) is not None
        except re.error:
            return False
    return expect in output


def unlazy_evidence_tail(output: str, limit: int = UNLAZY_EVIDENCE_MAX) -> str:
    """The deciding lines only. A gates file is re-read often; logs do not fit."""
    lines = [s.strip() for s in output.split("\n") if s.strip()]
    return (" | ".join(lines[-2:]) or "(no output)")[:limit]


UNLAZY_OWNED_DIR = Path("/workspace/.optmem/hook_state/unlazy_owned")


def unlazy_session_id() -> str:
    """This session, for ledger ownership. The harness supplies it; a bare
    fallback keeps the runner usable outside one."""
    return (os.environ.get("UNLAZY_SESSION")
            or os.environ.get("CLAUDE_SESSION_ID") or "nosession")[:64]


def unlazy_claim(path: Path, session: str | None = None) -> None:
    """Record that this session works this leaf ledger.

    Scope defect found 2026-08-23: the wall scanned every gates/*.md under the
    cwd, so two agents in /workspace walled each other. One session's in-flight
    leaf blocked the other's stop, and neither could clear a gate it does not
    own. A session is walled by ITS OWN ledgers.
    """
    try:
        UNLAZY_OWNED_DIR.mkdir(parents=True, exist_ok=True)
        marker = UNLAZY_OWNED_DIR / (session or unlazy_session_id())
        seen = set(marker.read_text().splitlines()) if marker.exists() else set()
        seen.add(str(path.resolve()))
        marker.write_text("\n".join(sorted(seen)) + "\n")
    except OSError:
        pass          # ownership is an optimisation; never break the runner


def unlazy_owned(session: str | None = None) -> set[str]:
    try:
        marker = UNLAZY_OWNED_DIR / (session or unlazy_session_id())
        return set(marker.read_text().splitlines()) if marker.exists() else set()
    except OSError:
        return set()


def unlazy_gate_files(directory: Path, session: str | None = None) -> list[Path]:
    """This session's ledgers: GATES.md always, plus leaves it has worked.

    GATES.md is the session's primary ledger and is always enforced. A leaf under
    gates/ is enforced only once this session has actually run the runner against
    it, which is what orchestrated mode does when it dispatches and verifies a
    leaf. A leaf belonging to another agent in the same directory is therefore
    that agent's wall, not this one's.
    """
    found: list[Path] = []
    top = directory / "GATES.md"
    if top.exists():
        found.append(top)
    gdir = directory / "gates"
    if gdir.is_dir():
        owned = unlazy_owned(session)
        found.extend(sorted(p for p in gdir.iterdir()
                            if p.suffix == ".md" and str(p.resolve()) in owned))
    return found


def unlazy_stop_verdict(directory: Path,
                        session: str | None = None) -> tuple[list[str], str]:
    """(unmet gate ids, content hash) for the Stop wall. Empty list = allow."""
    unmet: list[str] = []
    combined = ""
    for path in unlazy_gate_files(directory, session):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        combined += text
        unmet.extend(gid for gid, _ in unlazy_unmet(unlazy_parse_gates(text)))
    digest = hashlib.sha256(combined.encode("utf-8", "replace")).hexdigest()[:16]
    return unmet, digest


def unlazy_run_file(path: Path, status_only: bool, timeout_s: int) -> tuple[int, int, int]:
    """Run each unmet gate's CHECK, flip its box on EXPECT. -> (met, unmet, abandoned)."""
    # Working a leaf is what claims it for this session. It lives here, not in
    # the CLI wrapper, so any caller that runs a ledger is walled by it - the
    # driver in orchestrated mode included.
    if path.parent.name == "gates":
        unlazy_claim(path)
    text = path.read_text(errors="replace")
    lines = text.split("\n")
    ledger = unlazy_parse_gates(text)
    if not ledger.gates:
        print(f"{path}: no gates found")
        return (0, 0, 0)
    met = unmet = abandoned = 0
    changed = False

    for gate in ledger.gates:
        if gate.gate_id in ledger.abandoned:
            abandoned += 1
            print(f"  ABANDONED {gate.gate_id}: {ledger.abandoned[gate.gate_id]}")
            continue
        needs_run = (
            not status_only and gate.check and (not gate.checked or gate.evidence_pending)
        )
        if needs_run:
            try:
                proc = subprocess.run(
                    gate.check, shell=True, capture_output=True, text=True,
                    timeout=timeout_s, errors="replace",
                )
                output = f"{proc.stdout or ''}\n{proc.stderr or ''}"
                # An EXPECT decides when present: a check may exit non-zero by
                # design (a grep for absence, a battery that warns). Without an
                # EXPECT the exit code is the only signal there is.
                ok = (
                    unlazy_expect_matches(gate.expect, output)
                    if gate.expect else proc.returncode == 0
                )
            except subprocess.TimeoutExpired:
                output, ok = f"TIMEOUT after {timeout_s}s", False
            if ok:
                lines[gate.line] = re.sub(r"^- \[ \]", "- [x]", lines[gate.line])
                tail = unlazy_evidence_tail(output)
                if gate.evidence_line != -1:
                    indent = re.match(r"^\s*", lines[gate.evidence_line]).group(0)
                    lines[gate.evidence_line] = f"{indent}EVIDENCE: {tail}"
                gate.checked, gate.evidence, changed = True, tail, True
                print(f"  PASS {gate.gate_id}: {gate.title}")
            else:
                print(f"  FAIL {gate.gate_id}: {gate.title}\n       {unlazy_evidence_tail(output)}")

        if gate.checked and not gate.evidence_pending:
            met += 1
        else:
            unmet += 1
            if status_only:
                why = "unchecked" if not gate.checked else "checked but EVIDENCE pending"
                print(f"  UNMET {gate.gate_id} ({why}): {gate.title}")

    if changed:
        path.write_text("\n".join(lines))
    print(f"{path}: {len(ledger.gates)} gates")
    return (met, unmet, abandoned)


def unlazy_main(argv: list[str]) -> int:
    status_only = "--status" in argv
    timeout_s = UNLAZY_DEFAULT_TIMEOUT_S
    if "--timeout" in argv:
        idx = argv.index("--timeout")
        timeout_s = int(argv[idx + 1])
        argv = argv[:idx] + argv[idx + 2:]
    file_args = [Path(a) for a in argv if not a.startswith("--")]
    files = file_args or unlazy_gate_files(Path.cwd())
    if not files:
        print("unlazy_gates: no gate files found (GATES.md or gates/*.md)", file=sys.stderr)
        return 2
    met = unmet = abandoned = 0
    for path in files:
        if not path.exists():
            print(f"unlazy_gates: cannot read {path}", file=sys.stderr)
            return 2
        m, u, a = unlazy_run_file(path, status_only, timeout_s)
        met, unmet, abandoned = met + m, unmet + u, abandoned + a
    if unmet == 0:
        extra = f", {abandoned} abandoned" if abandoned else ""
        print(f"ALL MET ({met} met{extra})")
        return 0
    extra = f", abandoned: {abandoned}" if abandoned else ""
    print(f"UNMET: {unmet} (met: {met}{extra})")
    return 1


def unlazy_selftest() -> int:
    """Fixtures for every UNMET rule, each with its false-positive guard."""
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    unchecked = "- [ ] G1: a thing\n  EVIDENCE: pending\n"
    check("unchecked-is-unmet",
          [g for g, _ in unlazy_unmet(unlazy_parse_gates(unchecked))] == ["G1"])

    claimed = "- [x] G1: a thing\n  EVIDENCE: pending\n"
    why = unlazy_unmet(unlazy_parse_gates(claimed))
    check("checked-with-pending-evidence-is-unmet",
          [g for g, _ in why] == ["G1"] and "pending" in why[0][1], str(why))

    proved = "- [x] G1: a thing\n  EVIDENCE: 8/8 passed\n"
    check("checked-with-evidence-is-met", unlazy_unmet(unlazy_parse_gates(proved)) == [])

    surrendered = "- [ ] G1: a thing\n  EVIDENCE: pending\n\nABANDON: G1 hardware gone\n"
    check("abandon-resolves", unlazy_unmet(unlazy_parse_gates(surrendered)) == [])

    other = "- [ ] G1: a\n  EVIDENCE: pending\n- [ ] G2: b\n  EVIDENCE: pending\n\nABANDON: G2 nope\n"
    check("abandon-does-not-resolve-siblings",
          [g for g, _ in unlazy_unmet(unlazy_parse_gates(other))] == ["G1"])

    check("expect-substring", unlazy_expect_matches("ALL GREEN", "x\nALL GREEN\ny"))
    check("expect-substring-guard", not unlazy_expect_matches("ALL GREEN", "ALL RED"))
    check("expect-regex", unlazy_expect_matches(r"/\d+\/\d+ passed/", "note: 8/8 passed"))
    check("expect-regex-guard", not unlazy_expect_matches(r"/\d+\/\d+ passed/", "some passed"))
    check("expect-regex-broken-is-false", not unlazy_expect_matches("/[unclosed/", "anything"))
    check("evidence-capped", len(unlazy_evidence_tail("z" * 900)) == UNLAZY_EVIDENCE_MAX)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        ledger = tmp / "GATES.md"
        ledger.write_text(
            "# Gates: fixture\n\n"
            "- [ ] G1: passes\n  CHECK: echo READY_MARKER\n  EXPECT: READY_MARKER\n  EVIDENCE: pending\n\n"
            "- [ ] G2: fails\n  CHECK: echo WRONG\n  EXPECT: READY_MARKER\n  EVIDENCE: pending\n"
        )
        before = ledger.read_text()
        unlazy_run_file(ledger, status_only=True, timeout_s=10)
        check("status-only-writes-nothing", ledger.read_text() == before)

        unlazy_run_file(ledger, status_only=False, timeout_s=10)
        after = ledger.read_text()
        check("passing-check-flips-box", "- [x] G1: passes" in after, after)
        check("passing-check-records-evidence", "EVIDENCE: READY_MARKER" in after, after)
        check("failing-check-stays-unchecked", "- [ ] G2: fails" in after, after)
        check("failing-check-keeps-pending", after.count("EVIDENCE: pending") == 1, after)
        check("stop-verdict-sees-remaining", unlazy_stop_verdict(tmp)[0] == ["G2"])

        (tmp / "GATES.md").write_text("- [x] G1: done\n  EVIDENCE: real proof\n")
        check("stop-verdict-allows-when-clean", unlazy_stop_verdict(tmp)[0] == [])
        check("stop-verdict-empty-dir-allows", unlazy_stop_verdict(tmp / "nope")[0] == [])

        gdir = tmp / "gates"
        gdir.mkdir()
        leaf = gdir / "leaf.md"
        leaf.write_text("- [ ] L1: leaf\n  EVIDENCE: pending\n")
        # A leaf this session has NOT worked belongs to whoever did: it must not
        # wall us (scope defect, 2026-08-23 - two agents in one directory).
        check("stop-verdict-ignores-unowned-leaf",
              unlazy_stop_verdict(tmp, session="s-owner")[0] == [])
        unlazy_claim(leaf, "s-owner")
        check("stop-verdict-scans-owned-leaf",
              unlazy_stop_verdict(tmp, session="s-owner")[0] == ["L1"])
        check("stop-verdict-owner-is-per-session",
              unlazy_stop_verdict(tmp, session="s-other")[0] == [],
              "another session must not inherit this one's leaf")
        first = unlazy_stop_verdict(tmp, session="s-owner")[1]
        leaf.write_text("- [ ] L1: leaf\n  EVIDENCE: pending\n  CHECK: true\n")
        check("stop-verdict-hash-tracks-progress",
              unlazy_stop_verdict(tmp, session="s-owner")[1] != first)

        UNLAZY_OWNED_DIR.joinpath("s-owner").unlink(missing_ok=True)
        UNLAZY_OWNED_DIR.joinpath("s-other").unlink(missing_ok=True)
        # RUNNING the runner against a leaf is what claims it. Without this the
        # driver could work a leaf all day and never be walled by it, which
        # silently disarms orchestrated mode.
        import os as _os
        prev = _os.environ.get("UNLAZY_SESSION")
        _os.environ["UNLAZY_SESSION"] = "s-runner"
        UNLAZY_OWNED_DIR.joinpath("s-runner").unlink(missing_ok=True)
        claimed = tmp / "gates" / "claimed.md"
        claimed.write_text("- [ ] C1: leaf\n  EVIDENCE: pending\n")
        check("runner-does-not-claim-before-it-runs",
              unlazy_stop_verdict(tmp, session="s-runner")[0] == [])
        unlazy_run_file(claimed, status_only=True, timeout_s=5)
        check("runner-claims-the-leaf-it-runs",
              unlazy_stop_verdict(tmp, session="s-runner")[0] == ["C1"],
              "the runner must claim a leaf it works, or the driver is never walled")
        UNLAZY_OWNED_DIR.joinpath("s-runner").unlink(missing_ok=True)
        if prev is None:
            _os.environ.pop("UNLAZY_SESSION", None)
        else:
            _os.environ["UNLAZY_SESSION"] = prev
        noexpect = tmp / "gates" / "exit.md"
        noexpect.write_text("- [ ] E1: exit code decides\n  CHECK: true\n  EVIDENCE: pending\n")
        unlazy_run_file(noexpect, status_only=False, timeout_s=10)
        check("no-expect-uses-exit-code", "- [x] E1" in noexpect.read_text())

    failed = [f"FAIL {n}: {d}" for n, ok, d in checks if not ok]
    if failed:
        print("\n".join(failed), file=sys.stderr)
        print(f"unlazy_gates: SELFTEST FAILED {len(failed)}/{len(checks)}", file=sys.stderr)
        return 1
    print(f"unlazy_gates: SELFTEST PASS {len(checks)}/{len(checks)}")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(unlazy_selftest())
    raise SystemExit(unlazy_main(sys.argv[1:]))
