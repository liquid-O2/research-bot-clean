---
name: principle-codebase-design
description: "Apply when designing or changing a module interface, placing a seam, or judging whether a module is deep. Deep modules hide a lot of behaviour behind a small interface."
disable-model-invocation: true
---

# Codebase design

Design **deep modules**: a lot of behaviour behind a small interface, placed at a clean seam, testable through that interface.

## Glossary

Use these terms exactly.

**Module**: anything with an interface and an implementation. A function, class, package, or slice. Not "unit", "component", or "service".

**Interface**: everything a caller must know: types, invariants, ordering, error modes, config, performance. Not only the type signature.

**Implementation**: what sits behind the interface.

**Depth**: leverage at the interface. Deep means lots of behaviour per unit of interface the caller learns. Shallow means the interface is nearly as complex as the body.

**Seam** (Michael Feathers): a place where you can change behaviour without editing at that place. Where the interface lives.

**Adapter**: a concrete thing that satisfies an interface at a seam.

**Leverage**: what callers get from depth. One implementation pays back across N call sites.

**Locality**: what maintainers get. Change, bugs, and tests concentrate in one place.

## Rules

- Depth is a property of the interface, not line count in the body. Padding the implementation does not make a module deep. Do not split a module to satisfy a file-length cap if the split is a pass-through. Design the seam first. Length is a later shape check (Akita).
- **The deletion test.** Delete the module. If complexity vanishes, it was a pass-through. If complexity reappears across N callers, it was earning its keep.
- The interface is the test surface. Callers and tests cross the same seam.
- One adapter is a hypothetical seam. Two adapters make a real one. Do not add a seam until something actually varies across it.
- Accept dependencies, do not create them inside the module. Return results rather than mutating caller state when that choice is open.
- Small implementation functions stay private behind the interface. A long file is a smell to revisit the seam, not a license to slice into 499-line pass-throughs.

When the interface itself is open, design it twice: two radically different shapes, then pick on depth, locality, and seam placement. See [DESIGN-IT-TWICE.md](DESIGN-IT-TWICE.md). For deepening an existing cluster, see [DEEPENING.md](DEEPENING.md).
