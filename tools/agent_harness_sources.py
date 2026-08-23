"""Pinned source definitions for the Codex agent harness installer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


WORKSPACE = Path("/workspace")
HOME = Path("/home/algo")
VENDOR_ROOT = WORKSPACE / "vendor/agent-sources"
OPT_MEM = HOME / ".optmem/memo"


@dataclass(frozen=True)
class SourcePin:
    name: str
    commit: str
    origin: str
    pristine: Path | None
    selection: str
    relative_files: tuple[str, ...] = ()

    @property
    def installed(self) -> Path:
        """Resolve the installed pin path. Example: PINS[0].installed."""
        if self.name == "optmem":
            return OPT_MEM
        return VENDOR_ROOT / self.name / self.commit


PINS = (
    SourcePin("pstack", "46125561306434d8a1d7745d540d8932ab0cd2a2",
              "https://github.com/cursor/plugins", Path("/tmp/harness-pstack-pristine-20260823"), "full"),
    SourcePin("pocock", "5b15a47f2d7150f545fbcacbfe381787fc0230dc",
              "https://github.com/mattpocock/skills", Path("/tmp/harness-pocock-pristine-20260823"), "full"),
    SourcePin("unlazy", "754d9a68109e39b836cc72a39fb9a823f9d6b613",
              "https://github.com/Leonxlnx/unlazy", Path("/tmp/harness-unlazy-pristine-754d9a6"), "full"),
    SourcePin("akita", "bbd8e681c14c0f57b2e5ea63e4d1c0043a6890da",
              "https://github.com/akitaonrails/akitaonrails.github.io", Path("/tmp/harness-akita-pristine-bbd8e68"),
              "akita-article-and-license", ("README.md", "content/2026/04/20/clean-code-para-agentes-de-ia/index.en.md")),
    SourcePin("karpathy", "2c606141936f1eeef17fa3043a72095b4765b9c2",
              "https://github.com/multica-ai/andrej-karpathy-skills", Path("/tmp/harness-karpathy-pristine-2c60614"), "full"),
    SourcePin("bigpowers", "c0209032fb978d730a416167cd8f1e91e411650b",
              "https://github.com/danielvm-git/bigpowers", Path("/tmp/harness-bigpowers-pristine-c020903"),
              "ousterhout-subset", ("LICENSE", "skills/deepen-architecture/SKILL.md",
              "skills/deepen-architecture/DEEPENING.md", "skills/deepen-architecture/INTERFACE-DESIGN.md",
              "skills/deepen-architecture/LANGUAGE.md", "skills/design-interface/SKILL.md",
              "skills/develop-tdd/deep-modules.md", "skills/develop-tdd/refactoring.md",
              "docs/PRINCIPLES.md", "docs/references/ousterhout.md")),
    SourcePin("optmem", "1fb164cf39028047781f72ac3bb1e5a691c1dcb0",
              "https://github.com/VictorTaelin/OptMem", None, "installed-binary"),
)

PINNED_PSTACK_NODE_MODULES = next(
    pin.installed for pin in PINS if pin.name == "pstack") / "pstack/skills/poteto-mode/scripts/node_modules"


def pinned_runtime_error(path: Path = PINNED_PSTACK_NODE_MODULES) -> str | None:
    """Reject mutable bytes in a pin. Example: pinned_runtime_error()."""
    if not os.path.lexists(path):
        return None
    return f"pinned runtime offending={path}; expected absent mutable runtime"
