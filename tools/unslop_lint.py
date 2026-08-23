#!/usr/bin/env python3
"""Lint prose against the mechanically checkable rules of the unslop skill.

The unslop skill is mandatory for every user-visible sentence and every memory
line (AGENTS.md, "Agent method"). This tool is the enforcement point for the
half of that skill a machine can decide. Findings name the upstream rule number
so the writer can read the rule rather than guess at the fix.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Iterable, Iterator, Sequence, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parent))

from unslop_rules import (  # noqa: E402
    EMOJI_PATTERN,
    JUDGEMENT_ITEMS,
    PATTERN_RULES,
)

ALLOWLIST_PATH = Path(__file__).resolve().parent / "unslop_allowlist.txt"
FENCE = re.compile(r"^\s*(?:```|~~~)")
FRONTMATTER = re.compile(r"^---\s*$")
VERBATIM_BEGIN = re.compile(r"<!--\s*(?:\w+_UPSTREAM_BLOCK_BEGIN|unslop:ignore-start)\s*-->")
VERBATIM_END = re.compile(r"<!--\s*(?:\w+_UPSTREAM_BLOCK_END|unslop:ignore-end)\s*-->")
CODE_SPAN = re.compile(r"`[^`\n]*`")
URL = re.compile(r"(?:https?|file)://\S+")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")
CAPITALIZED = re.compile(r"^[A-Z][a-z]+$")
COLON = re.compile(r"(?<![:\d]):(?![:/\d])")
WORD = re.compile(r"[A-Za-z][\w'-]*")
MIN_WORDS_BEFORE_COLON = 5
MAX_TITLE_CASE_WORDS = 1


@dataclass(frozen=True)
class Finding:
    """One rule violation, located precisely enough to fix without searching."""

    path: str
    line: int
    column: int
    rule: int
    name: str
    message: str
    span: str


def read_allowlist(path: Path = ALLOWLIST_PATH) -> frozenset[str]:
    """Load lowercase terms this repository uses concretely, not as slop."""
    if not path.is_file():
        return frozenset()
    lines = path.read_text(encoding="utf-8").splitlines()
    terms = (line.split("#", 1)[0].strip().lower() for line in lines)
    return frozenset(term for term in terms if term)


def mask_regions(text: str) -> list[str]:
    """Blank out code, frontmatter and verbatim blocks, keeping the line count.

    A verbatim block is upstream text this repository copies byte-identically
    (the OptMem and Akita blocks in AGENTS.md). Rewriting it would break the
    digest check that keeps AGENTS.md and CLAUDE.md in step, so it is exempt.
    """
    lines = text.splitlines()
    masked: list[str] = []
    in_fence = False
    in_verbatim = False
    in_frontmatter = bool(lines) and FRONTMATTER.match(lines[0]) is not None
    for index, line in enumerate(lines):
        in_frontmatter = frontmatter_state(in_frontmatter, index, line)
        in_fence, unfenced = fence_state(in_fence, line)
        in_verbatim, quotable = verbatim_state(in_verbatim, line)
        skip = in_frontmatter or not unfenced or not quotable
        masked.append("" if skip else line)
    return masked


def verbatim_state(active: bool, line: str) -> tuple[bool, bool]:
    """Return the next verbatim state and whether this line should be scanned."""
    if VERBATIM_BEGIN.search(line):
        return True, False
    if VERBATIM_END.search(line):
        return False, False
    return active, not active


def frontmatter_state(active: bool, index: int, line: str) -> bool:
    """Close the frontmatter block at its terminating delimiter."""
    if not active or index == 0:
        return active
    return not FRONTMATTER.match(line)


def fence_state(in_fence: bool, line: str) -> tuple[bool, bool]:
    """Return the next fence state and whether this line should be scanned."""
    if FENCE.match(line):
        return not in_fence, False
    return in_fence, not in_fence


def blank_out(line: str, pattern: re.Pattern[str]) -> str:
    """Replace matches with spaces so later column numbers stay accurate."""
    return pattern.sub(lambda match: " " * len(match.group(0)), line)


def scannable(line: str) -> str:
    """Strip code spans and URLs, which are not prose and carry no rules."""
    return blank_out(blank_out(line, CODE_SPAN), URL)


def allowed(span: str, allowlist: frozenset[str]) -> bool:
    """Report whether this repository uses the matched term concretely."""
    return span.strip().lower() in allowlist


def scan_patterns(path: str, number: int, line: str, allowlist: frozenset[str]) -> Iterator[Finding]:
    """Apply every straightforward pattern rule to one line."""
    for rule in PATTERN_RULES:
        for match in rule.pattern.finditer(line):
            if allowed(match.group(0), allowlist):
                continue
            yield Finding(path, number, match.start() + 1, rule.number, rule.name,
                          rule.message, match.group(0))


def scan_colon(path: str, number: int, line: str) -> Iterator[Finding]:
    """Flag rule 14, a colon used as a mid-sentence connector."""
    if line.lstrip().startswith("|"):
        return
    for match in COLON.finditer(line):
        if not connector_colon(line, match.start()):
            continue
        yield Finding(path, number, match.start() + 1, 14, "connector-colon",
                      "Colon used as a mid-sentence connector. Let the point stand alone.",
                      line[max(0, match.start() - 30):match.start() + 30].strip())


def connector_colon(line: str, index: int) -> bool:
    """Report whether the colon joins two clauses instead of leading a list."""
    tail = line[index + 1:]
    if not tail.strip() or not tail.startswith(" "):
        return False
    following = tail.lstrip()
    if not following[:1].islower():
        return False
    return len(WORD.findall(line[:index])) >= MIN_WORDS_BEFORE_COLON


def scan_heading(path: str, number: int, line: str, allowlist: frozenset[str]) -> Iterator[Finding]:
    """Flag rule 17, a title-case heading where sentence case belongs."""
    match = HEADING.match(line)
    if match is None:
        return
    words = WORD.findall(match.group(2))[1:]
    offenders = [word for word in words
                 if CAPITALIZED.match(word) and word.lower() not in allowlist]
    if len(offenders) <= MAX_TITLE_CASE_WORDS:
        return
    yield Finding(path, number, 1, 17, "title-case-heading",
                  "Title case heading. Use sentence case.", " ".join(offenders))


def scan_emoji(path: str, number: int, line: str) -> Iterator[Finding]:
    """Flag rule 18, a decorative emoji in a heading or a bullet."""
    if not (HEADING.match(line) or BULLET.match(line)):
        return
    for match in EMOJI_PATTERN.finditer(line):
        yield Finding(path, number, match.start() + 1, 18, "decorative-emoji",
                      "Decorative emoji in a heading or bullet. Remove it.",
                      match.group(0))


def scan_line(path: str, number: int, line: str, allowlist: frozenset[str]) -> Iterator[Finding]:
    """Run every rule against one already-masked line."""
    text = scannable(line)
    yield from scan_patterns(path, number, text, allowlist)
    yield from scan_colon(path, number, text)
    yield from scan_heading(path, number, text, allowlist)
    yield from scan_emoji(path, number, line)


def lint_text(text: str, path: str, allowlist: frozenset[str]) -> list[Finding]:
    """Return every finding in one document, in file order."""
    lines = mask_regions(text)
    return [finding
            for number, line in enumerate(lines, start=1)
            for finding in scan_line(path, number, line, allowlist)]


def lint_path(path: Path, allowlist: frozenset[str]) -> list[Finding]:
    """Lint one file on disk."""
    return lint_text(path.read_text(encoding="utf-8"), str(path), allowlist)


def format_finding(finding: Finding) -> str:
    """Render one finding as a clickable, greppable line."""
    return (f"{finding.path}:{finding.line}:{finding.column} "
            f"rule={finding.rule} {finding.name}: {finding.message} "
            f"[{finding.span}]")


def finding_dict(finding: Finding) -> dict[str, object]:
    """Render one finding for machine consumers such as the hooks."""
    return {"path": finding.path, "line": finding.line, "column": finding.column,
            "rule": finding.rule, "name": finding.name, "message": finding.message,
            "span": finding.span}


def report(findings: Sequence[Finding], as_json: bool, stream: TextIO) -> None:
    """Write findings and, when any exist, the judgement items a reader owns."""
    if as_json:
        json.dump([finding_dict(row) for row in findings], stream)
        stream.write("\n")
        return
    for finding in findings:
        stream.write(format_finding(finding) + "\n")
    if findings:
        stream.write("\nReviewer items unslop leaves to judgement:\n")
        stream.writelines(f"  - {item}\n" for item in JUDGEMENT_ITEMS)


def collect(paths: Iterable[str], allowlist: frozenset[str]) -> list[Finding]:
    """Lint every named path."""
    return [finding for name in paths for finding in lint_path(Path(name), allowlist)]


def main(argv: Sequence[str] | None = None, stdin: TextIO = sys.stdin,
         stdout: TextIO = sys.stdout) -> int:
    """Lint the named files, or stdin when `-` is the only argument."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in arguments
    paths = [value for value in arguments if not value.startswith("--")]
    allowlist = read_allowlist()
    if paths == ["-"]:
        findings = lint_text(stdin.read(), "<stdin>", allowlist)
    elif paths:
        findings = collect(paths, allowlist)
    else:
        raise ValueError("unslop_lint expects one or more paths, or '-' for stdin")
    report(findings, as_json, stdout)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
