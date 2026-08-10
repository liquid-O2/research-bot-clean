# Contract tests

The repository-level verifier checks clean-room structure, transcript
provenance, authority hashes, branch law, payload exclusion, large blobs,
symlinks and common credential patterns.

Rust production contract tests live with their crates. Tests that require
mounted 2022–2025 authorities are compiled during cleanup but are not run
until their exact payload gate is active. No test may open 2026 or RTY market
payload.

