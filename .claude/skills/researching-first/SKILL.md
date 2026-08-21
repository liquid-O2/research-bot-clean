---
name: researching-first
description: Use before building any nontrivial new component, when adding a dependency, or when a problem smells like one other fields have already solved.
---

# Researching First

Adapted from bigpowers `research-first`; composes with the house cross-domain-sweep method.

## Overview
Look before build. Minimum outcome: **adopt / extend / compose / build** — with evidence. "Build" must justify why the others failed.

## Recipe
0. **Refuted-lane check**: grep `design/REFUTED/` and `/workspace/CURRENT.md` §Closed Questions for the CONCEPT (not just the keyword). If the idea was closed, either respect the closure or state explicitly why this attempt falls OUTSIDE its recorded scope. Never file "already built" or a mere deferral there — only genuine refutations with scope.
1. **This repo first**: an earlier tool, engine module, or quarantined script may already do it (grep tools/, engine/, design/).
2. **Vendored/local source next**: read the actual dependency source under the venv or engine/cpp vendor dirs before writing integration code — API shapes from source, not memory.
3. **Literature/web**: for method questions, run a cross-domain sweep (the house pattern: EVT declustering, NMS, Hawkes etc. came from exactly this) — named techniques, adopt/skip verdict per technique.
4. **Record Prior Art** in the design doc: name, source, fit verdict, why.

| Verdict | Action |
|---|---|
| adopt | Use as-is; link it; no new code |
| extend | Wrap or configure the existing thing |
| compose | Chain existing modules |
| build | New code — with the failure evidence for the other three |

## Common mistakes
| Mistake | Reality |
|---|---|
| Web-searching before grepping the repo | The repo has 100+ tools; most wheels exist here already. |
| Adopting a library from its README | Read the source for the exact behavior you rely on. |
| Sweep without verdicts | A list of papers is not research; adopt/skip per technique is. |
