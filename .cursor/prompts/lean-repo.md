---
name: lean-repo
description: Find unused code and delete it. Reshape what still runs using the full principle index.
---

# Lean live code

`/poteto-mode`. Read the Principles index in full. Open every leaf whose trigger matches. Codebase-design is one leaf, not the only one. Listing names is not applying them.

The work is **code**. Markdown onboarding is already done. Deleting more markdown, skills, or `.cursor/` does not count. Do not touch `.cursor/`.

## Anti-pattern

Codex `01a034f0`. Catalog receipt, then an 865k-file scanner. A markdown-only diff is the same failure in reverse. Do not use plan-flow, implement-flow, unlazy, or method_guard.

## Goal

The live code tree should be as small as it can be without losing what still runs. Few code files and folders. Data, artifacts, caches, raw, and provenance can stay huge. Do not walk those trees.

You find what is live. Follow the running product from how a session actually works here, then follow imports and tests. Do not take a file list from this brief. Unused means no live caller, no live test, no live entry path. Delete unused code. Empty folders go with it. "Might be useful later" is not a keep.

Then reshape what remains. Every principle whose trigger matches binds: subtract, laziness, reader load, domain model, depth, types, boundaries, migrate-then-delete, prove it, sequence verifiable units. Deep modules. Small interface. Do not replace one god file with twenty pass-through files.

`python3 -m unittest` on tests you touch. pytest is not installed.

## Cadence

One-pass. Discover the dead set, delete it as one batch, prove. Then one live reshape if time remains. Prove. Stop.

Pin behavior before you move structure. Name which principle changed which decision.

## Done

Failure: only docs changed, or unused code left because it might be useful.

Done when unused code you found is gone with proof, or a remaining live module is smaller and deeper and its tests still pass. `.cursor/` untouched.

Reply with what you found live, what you deleted and why, which principles changed a decision, and the test command.

Do not open a PR.
