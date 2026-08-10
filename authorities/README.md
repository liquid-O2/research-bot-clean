# Authorities

`REGISTRY.tsv` is the active logical authority map. Raw files and large
generated outputs remain external to Git. Empty or `PENDING_EXPORT` hashes are
blockers, not invitations to trust a path.

Before scientific execution, `tests/contracts` must resolve every required
authority, verify its hash/schema/scope and prove that no forbidden 2026 or
RTY payload can be opened.

