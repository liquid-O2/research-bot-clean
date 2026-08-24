from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
import sys


@contextmanager
def isolated_hook_imports(directory: Path, siblings: Sequence[str]) -> Iterator[None]:
    """Prevent generic hook module names from leaking between client suites."""
    saved = {name: sys.modules.pop(name) for name in siblings if name in sys.modules}
    original_path = list(sys.path)
    sys.path.insert(0, str(directory))
    try:
        yield
    finally:
        for name in siblings:
            sys.modules.pop(name, None)
        sys.modules.update(saved)
        sys.path[:] = original_path
