"""check_truth_separation — the STATIC half of APPENDIX C4's process separation.

SPEC: FINAL_PLAN.md APPENDIX C4: "the TRAINER opens an explicit truth allowlist
for loss computation only + static check no truth array is concatenated into
any feature tensor."

WHAT IT CHECKS, without importing or running anything: in each Python source
given to it, any value that came out of a `.truth(...)` call is TAINTED, and a
tainted value may not appear anywhere inside a call that builds a tensor by
concatenation — numpy's concatenate/stack/hstack/vstack/column_stack/append/
c_/r_, or torch's cat/stack/hstack/vstack/column_stack. Taint propagates
through plain assignment, subscripting, tuple unpacking, attribute access and
`.values()`/`.items()`, which is every shape the trainer's loss code will use to
get from `loader.truth([...])` to an array.

WHY STATIC. The runtime guard (decision_tape_loader.assert_no_truth_arrays)
only fires on the code paths a run actually takes. This one reads the whole
file, including the branch that only fires on fold 5 at 3am.

usage: check_truth_separation.py FILE [FILE ...]
exit:  0 clean, 1 a violation was found (each one printed as file:line: message)
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
    }
)
TRUTH_CALL = "truth"


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
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if node.value is not None and self._expression_is_tainted(node.value):
            self._bind(node.target)
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:  # noqa: N802
        if self._expression_is_tainted(node.value):
            self._bind(node.target)
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
        if name in CONCATENATORS:
            for argument in list(node.args) + [keyword.value for keyword in node.keywords]:
                if self._expression_is_tainted(argument):
                    self.violations.append(
                        f"{self.path}:{node.lineno}: a truth array is concatenated into a tensor "
                        f"by {name}()"
                    )
                    break
        self.generic_visit(node)


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
    for name in argv[1:]:
        path = pathlib.Path(name)
        violations.extend(check_source(path, path.read_text(encoding="utf-8")))
    for violation in violations:
        print(violation)
    if violations:
        print(f"FAIL: {len(violations)} truth-into-features violation(s)")
        return 1
    print(f"OK: {len(argv) - 1} file(s) keep truth out of every feature tensor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
