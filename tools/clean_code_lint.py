#!/usr/bin/env python3
"""Check Python against the checkable half of the Akita block in AGENTS.md.

The contract caps files at 500 lines and functions at 4 to 20, asks for two
levels of nesting, explicit types, and exception messages that carry the
offending value. Those are decidable, so they are decided here.

The half that needs a reader stays with `code-review`: whether a comment records
a why, whether a dependency is injected, whether a name is specific. This tool
reports those as reviewer items rather than pretending to judge them.

Default scope is the current diff, which is what the Akita rule itself asks for:
audit the final diff, not the tree.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Iterator, Sequence, TextIO

# Length and nesting are production-code rules. A test method holds one whole
# scenario, and splitting it to fit a cap separates a fixture from its use,
# which makes the test worse rather than better. Types and exception messages
# still apply everywhere, because those help a reader in any file.
SHAPE_EXEMPT = ("tests/", "test_", "_test.py", "/fixtures/")
MAX_FILE_LINES = 500
MAX_FUNCTION_LINES = 20
MAX_NESTING = 2
NESTING_NODES = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)
VAGUE_TYPES = {"Any"}
# Control flow, not error reporting: these carry no offending value by design.
CONTROL_EXCEPTIONS = {"SystemExit", "StopIteration", "StopAsyncIteration", "KeyboardInterrupt"}
REVIEWER_ITEMS = (
    "Comments record a why, not a what, and survive the refactor.",
    "Dependencies arrive through a parameter, not a global or an import.",
    "Names are specific enough to return few matches when grepped.",
    "Every new function has a test, and every fix has a regression test.",
)


@dataclass(frozen=True)
class Finding:
    """One rule violation, located where it can be fixed."""

    path: str
    line: int
    rule: str
    message: str


def changed_files(reference: str) -> list[Path]:
    """Return the Python files this diff touches."""
    result = subprocess.run(("git", "diff", "--name-only", "--diff-filter=d", reference),
                            capture_output=True, text=True, check=False)
    names = [row.strip() for row in result.stdout.splitlines() if row.strip().endswith(".py")]
    return [Path(name) for name in names if Path(name).is_file()]


def collect_files(targets: Sequence[str]) -> list[Path]:
    """Expand paths and directories into the Python files to check."""
    files: list[Path] = []
    for name in targets:
        path = Path(name)
        files.extend(sorted(path.rglob("*.py")) if path.is_dir() else [path])
    return [path for path in files if path.is_file() and path.suffix == ".py"]


def body_span(node: ast.AST) -> int:
    """Return how many lines a definition occupies."""
    end = getattr(node, "end_lineno", None)
    start = getattr(node, "lineno", None)
    return (end - start + 1) if end and start else 0


def is_definition(node: ast.AST) -> bool:
    """Report whether a node defines a function."""
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))


def docstring_lines(node: ast.AST) -> int:
    """Return how many lines a definition spends on its docstring."""
    body = getattr(node, "body", [])
    if not body or not isinstance(body[0], ast.Expr):
        return 0
    value = body[0].value
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        return 0
    return body_span(body[0])


def code_lines(node: ast.AST) -> int:
    """Return a definition's line count, excluding its docstring."""
    return body_span(node) - docstring_lines(node)


def check_length(path: Path, node: ast.AST) -> Iterator[Finding]:
    """Flag a function over the twenty line cap, docstring excluded."""
    lines = code_lines(node)
    if lines <= MAX_FUNCTION_LINES:
        return
    name = getattr(node, "name", "?")
    yield Finding(str(path), node.lineno, "function-too-long",
                  f"{name} is {lines} code lines, over the {MAX_FUNCTION_LINES} line cap. "
                  "Split it by responsibility.")


def depth_of(node: ast.AST, depth: int = 0) -> int:
    """Return the deepest nesting level inside one function body."""
    deepest = depth
    for child in ast.iter_child_nodes(node):
        if is_definition(child) or isinstance(child, ast.ClassDef):
            continue
        step = depth + 1 if isinstance(child, NESTING_NODES) else depth
        deepest = max(deepest, depth_of(child, step))
    return deepest


def check_nesting(path: Path, node: ast.AST) -> Iterator[Finding]:
    """Flag a function nested deeper than two levels."""
    depth = depth_of(node)
    if depth <= MAX_NESTING:
        return
    yield Finding(str(path), node.lineno, "nesting-too-deep",
                  f"{getattr(node, 'name', '?')} nests {depth} levels, over {MAX_NESTING}. "
                  "Use an early return.")


def annotation_name(annotation: ast.expr | None) -> str:
    """Return a readable name for one annotation."""
    return ast.unparse(annotation) if annotation is not None else ""


def parameters(node: ast.AST) -> list[ast.arg]:
    """Return every named parameter a definition takes."""
    arguments = getattr(node, "args", None)
    if arguments is None:
        return []
    named = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    return [argument for argument in named if argument.arg not in {"self", "cls"}]


def check_types(path: Path, node: ast.AST) -> Iterator[Finding]:
    """Flag a missing or vague annotation on a function."""
    name = getattr(node, "name", "?")
    for argument in parameters(node):
        yield from untyped(path, node, name, argument)
    if getattr(node, "returns", None) is None:
        yield Finding(str(path), node.lineno, "missing-return-type",
                      f"{name} has no return annotation.")


def untyped(path: Path, node: ast.AST, name: str, argument: ast.arg) -> Iterator[Finding]:
    """Flag one parameter with no annotation, or a vague one."""
    if argument.annotation is None:
        yield Finding(str(path), node.lineno, "missing-parameter-type",
                      f"{name}({argument.arg}) has no type annotation.")
        return
    rendered = annotation_name(argument.annotation)
    if rendered in VAGUE_TYPES:
        yield Finding(str(path), node.lineno, "vague-type",
                      f"{name}({argument.arg}) is typed {rendered}. Name the real shape.")


def raise_has_value(node: ast.Raise) -> bool:
    """Report whether a raised exception interpolates the offending value."""
    exception = node.exc
    if exception is None:
        return True
    if not isinstance(exception, ast.Call):
        return False
    if getattr(exception.func, "id", "") in CONTROL_EXCEPTIONS:
        return True
    if not exception.args:
        return False
    return any(isinstance(argument, (ast.JoinedStr, ast.BinOp, ast.Name, ast.Call))
               for argument in exception.args)


def check_raises(path: Path, tree: ast.AST) -> Iterator[Finding]:
    """Flag an exception message that names no value."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and not raise_has_value(node):
            yield Finding(str(path), node.lineno, "opaque-exception",
                          "Exception message carries no offending value or expected shape.")


def check_file_length(path: Path, source: str) -> Iterator[Finding]:
    """Flag a file over the line cap."""
    lines = len(source.splitlines())
    if lines <= MAX_FILE_LINES:
        return
    yield Finding(str(path), 1, "file-too-long",
                  f"{lines} lines, over the {MAX_FILE_LINES} line cap. "
                  "Split it by responsibility.")


def definition_findings(path: Path, tree: ast.AST, exempt: bool = False) -> list[Finding]:
    """Return every per-function finding in one parsed file."""
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if is_definition(node):
            findings.extend(node_findings(path, node, exempt))
    return findings


def node_findings(path: Path, node: ast.AST, exempt: bool) -> list[Finding]:
    """Return the findings for one definition, honouring the shape exemption."""
    findings = list(check_types(path, node))
    if exempt:
        return findings
    return [*check_length(path, node), *check_nesting(path, node), *findings]


def shape_exempt(path: Path) -> bool:
    """Report whether the length and nesting caps apply to this file."""
    name = path.as_posix()
    return any(marker in name or path.name.startswith("test_") for marker in SHAPE_EXEMPT)


def lint_file(path: Path) -> list[Finding]:
    """Return every finding in one Python file."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [Finding(str(path), error.lineno or 1, "syntax-error", str(error))]
    findings = [*check_raises(path, tree), *definition_findings(path, tree, shape_exempt(path))]
    if not shape_exempt(path):
        findings.extend(check_file_length(path, source))
    return sorted(findings, key=lambda row: (row.path, row.line))


def report(findings: Sequence[Finding], stdout: TextIO) -> int:
    """Print findings and the items a reader still owns."""
    for finding in findings:
        stdout.write(f"{finding.path}:{finding.line} {finding.rule}: {finding.message}\n")
    if not findings:
        stdout.write("CLEAN CODE PASS\n")
        return 0
    stdout.write(f"\nCLEAN CODE FAIL {len(findings)} findings\n")
    stdout.write("Reviewer items the Akita block leaves to a reader:\n")
    stdout.writelines(f"  - {item}\n" for item in REVIEWER_ITEMS)
    return 1


def resolve_targets(arguments: Sequence[str]) -> list[Path]:
    """Return the files to check, defaulting to the current diff."""
    if arguments and arguments[0] == "--diff":
        return changed_files(arguments[1] if len(arguments) > 1 else "HEAD")
    return collect_files(arguments)


def main(argv: Sequence[str] | None = None, stdout: TextIO = sys.stdout) -> int:
    """Lint the named files, or the current diff when none are named."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    targets = resolve_targets(arguments or ["--diff"])
    findings = [row for path in targets for row in lint_file(path)]
    return report(findings, stdout)


if __name__ == "__main__":
    raise SystemExit(main())
