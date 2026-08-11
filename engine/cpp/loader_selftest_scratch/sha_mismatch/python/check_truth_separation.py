"""check_truth_separation — the STATIC half of APPENDIX C4's process separation.

SPEC: FINAL_PLAN.md APPENDIX C4: "the TRAINER opens an explicit truth allowlist
for loss computation only + static check no truth array is concatenated into
any feature tensor."

WHAT IT CHECKS, without importing or running anything.

1. TAINT. In each Python source given to it, any value that came out of a
   `.truth(...)` call is TAINTED, and a tainted value may not reach a tensor
   through any of the SINKS below. Taint propagates through plain assignment,
   subscripting, tuple unpacking, attribute access and `.values()`/`.items()`,
   which is every shape the trainer's loss code will use to get from
   `loader.truth([...])` to an array.

   THE SINKS (widened by the consolidated review, F4/F5 — concatenation was
   never the only way in):
     * CONCATENATION — numpy's concatenate/stack/hstack/vstack/dstack/
       column_stack/row_stack/append, torch's cat/concat/stack/hstack/vstack;
     * SETITEM — `feature_tensor[...] = truth_array`. An in-place write is the
       obvious way to move truth into a tensor without ever calling a
       concatenator, and the original rule could not see it at all;
     * PUT / INSERT — `np.put(x, i, y)`, `x.put(...)`, `np.insert(x, i, y)`,
       `list.insert(...)`: the same write, spelled as a method;
     * `out=` — `np.add(a, b, out=features)` and every ufunc like it write
       their result into a destination the call names. Any call carrying an
       `out=` keyword with a tainted argument ANYWHERE in it is a violation,
       because either the source or the destination is truth.

2. THE CENSUS SCOPE MARKER. `qr::emit::CensusInternalScope` suppresses fd-census
   recording for the census's OWN file access. Used anywhere but inside qr_emit's
   own internals it is a hole in the wall — a builder that opens a truth leaf
   inside that scope is never recorded and never refused. Every file handed to
   this checker, whatever its language, is scanned for the name, and any use
   outside `qr_emit/src/` and `qr_emit/include/` is a violation.

WHY STATIC. The runtime guard (decision_tape_loader.assert_no_truth_arrays)
only fires on the code paths a run actually takes. This one reads the whole
file, including the branch that only fires on fold 5 at 3am.

usage: check_truth_separation.py FILE [FILE ...]
exit:  0 clean, 1 a violation was found (each one printed as file:line: message)

Non-Python files are scanned for check 2 only; only `.py` files are parsed.
"""
from __future__ import annotations

import ast
import pathlib
import sys

CONCATENATORS = frozenset(
    {
        "concatenate",
        "stack",
        "hstack",
        "vstack",
        "dstack",
        "column_stack",
        "row_stack",
        "append",
        "cat",
        "concat",
        # The write-into-a-tensor sinks (review F4/F5): the same move, spelled
        # as a method instead of as a concatenation.
        "put",
        "put_along_axis",
        "insert",
    }
)
TRUTH_CALL = "truth"

#: The census scope marker. Outside qr_emit's own internals it silences the
#: fd census for whatever is opened inside it.
CENSUS_SCOPE = "CensusInternalScope"
#: The only directories allowed to name it — plus THIS file, which has to name
#: it in order to define the rule about it.
CENSUS_SCOPE_OWNERS = (
    "qr_emit/src/",
    "qr_emit/include/",
    "python/check_truth_separation.py",
)

#: THE ONE SUPPRESSION, line-scoped and reason-bearing.
#:
#: The runtime guards (`assert_no_truth_arrays`) can only be tested by BUILDING
#: the forbidden object, so their fixtures are real violations of the static
#: rule and true positives. Silently exempting the test file would hide real
#: findings in it; a line-scoped marker keeps every deliberate violation visible
#: in the diff, greppable, and counted in this checker's own summary line.
#:
#: It suppresses NOTHING outside this file's own static rule: the fd census, the
#: publish-time digest-collision refusal and the runtime guard are three other
#: mechanisms and none of them reads it.
SUPPRESSION = "# truth-separation: guard-fixture"


class _TaintScanner(ast.NodeVisitor):
    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        self.tainted: set[str] = set()
        self.violations: list[str] = []

    # --- taint introduction and propagation --------------------------------

    @staticmethod
    def _is_truth_call(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == TRUTH_CALL
        )

    def _expression_is_tainted(self, node: ast.AST) -> bool:
        for inner in ast.walk(node):
            if self._is_truth_call(inner):
                return True
            if isinstance(inner, ast.Name) and inner.id in self.tainted:
                return True
        return False

    def _bind(self, target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            self.tainted.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                self._bind(element)
        elif isinstance(target, ast.Starred):
            self._bind(target.value)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802 (ast API)
        if self._expression_is_tainted(node.value):
            for target in node.targets:
                self._bind(target)
            # SETITEM: `feature_tensor[i] = truth_array`. Binding a NAME is taint
            # propagation; writing through a SUBSCRIPT or an ATTRIBUTE is a write
            # INTO an existing tensor, which is the thing the rule forbids.
            for target in node.targets:
                if isinstance(target, (ast.Subscript, ast.Attribute)):
                    self.violations.append(
                        f"{self.path}:{node.lineno}: a truth array is written into a tensor "
                        f"by setitem"
                    )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if node.value is not None and self._expression_is_tainted(node.value):
            self._bind(node.target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        if self._expression_is_tainted(node.value):
            self._bind(node.target)
            if isinstance(node.target, (ast.Subscript, ast.Attribute)):
                self.violations.append(
                    f"{self.path}:{node.lineno}: a truth array is written into a tensor "
                    f"by setitem"
                )
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802
        if self._expression_is_tainted(node.iter):
            self._bind(node.target)
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:  # noqa: N802
        for item in node.items:
            if item.optional_vars is not None and self._expression_is_tainted(item.context_expr):
                self._bind(item.optional_vars)
        self.generic_visit(node)

    # --- the rule ----------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        name = None
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        arguments = list(node.args) + [keyword.value for keyword in node.keywords]
        if name in CONCATENATORS:
            for argument in arguments:
                if self._expression_is_tainted(argument):
                    self.violations.append(
                        f"{self.path}:{node.lineno}: a truth array is concatenated into a tensor "
                        f"by {name}()"
                    )
                    break
        # `out=`: the call names its own destination. Either the destination or
        # an operand being truth puts truth into a tensor, so a tainted argument
        # ANYWHERE in such a call is the violation.
        elif any(keyword.arg == "out" for keyword in node.keywords):
            for argument in arguments:
                if self._expression_is_tainted(argument):
                    self.violations.append(
                        f"{self.path}:{node.lineno}: a truth array reaches a tensor through the "
                        f"out= destination of {name}()"
                    )
                    break
        self.generic_visit(node)


def check_census_scope(path: pathlib.Path, text: str) -> list[str]:
    """Check 2: `CensusInternalScope` outside qr_emit's own internals.

    Textual on purpose. The marker is C++, the files that may legitimately use
    it are two directories, and the question — "does this file name it?" — needs
    no parse. A checker that only understood Python could not ask it at all.
    """
    normalised = str(path).replace("\\", "/")
    if any(owner in normalised for owner in CENSUS_SCOPE_OWNERS):
        return []
    violations: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if CENSUS_SCOPE in line:
            violations.append(
                f"{path}:{number}: {CENSUS_SCOPE} is used outside qr_emit's own internals; "
                f"it suppresses fd-census recording for everything opened inside it"
            )
    return violations


def apply_suppressions(text: str, violations: list[str]) -> tuple[list[str], int]:
    """Drops violations whose own source line carries the declared marker.

    Returns (kept, dropped_count). The count is printed, so a suppression can
    never be invisible.
    """
    lines = text.splitlines()
    kept: list[str] = []
    dropped = 0
    for violation in violations:
        parts = violation.split(":", 2)
        number = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        source = lines[number - 1] if 1 <= number <= len(lines) else ""
        if SUPPRESSION in source:
            dropped += 1
            continue
        kept.append(violation)
    return kept, dropped


def check_source(path: pathlib.Path, text: str) -> list[str]:
    tree = ast.parse(text, filename=str(path))
    # Two passes: taint can be introduced after its first textual use inside a
    # function that runs later, so the binding pass runs to a fixed point first.
    scanner = _TaintScanner(path)
    for _ in range(3):
        before = set(scanner.tainted)
        scanner.violations = []
        scanner.visit(tree)
        if scanner.tainted == before:
            break
    return scanner.violations


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    violations: list[str] = []
    suppressed = 0
    for name in argv[1:]:
        path = pathlib.Path(name)
        text = path.read_text(encoding="utf-8")
        found = check_census_scope(path, text)
        if path.suffix == ".py":
            found.extend(check_source(path, text))
        kept, dropped = apply_suppressions(text, found)
        violations.extend(kept)
        suppressed += dropped
    for violation in violations:
        print(violation)
    if violations:
        print(f"FAIL: {len(violations)} truth-into-features violation(s)")
        return 1
    print(
        f"OK: {len(argv) - 1} file(s) keep truth out of every feature tensor "
        f"({suppressed} declared guard-fixture line(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
