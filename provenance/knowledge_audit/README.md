# Knowledge migration audit

This directory is the compact, reviewable receipt for the pre-cutover
workspace inventory. The builder classified 238,637 sources into 387,517
segments across the live Codex lineage, recursively discovered historical
local conversation files, documents, research, workflow records, published
runs and cache metadata. The independent verifier re-read 114,605 frozen
content prefixes (about 99 GiB logical scope), quarantined 25 malformed JSONL
fragments, recognized four lawful post-snapshot appends, and reported zero
unclassified sources or segments.

`verification_v1.json` is the independent verdict. `compact/summary.json`,
`compact/build_receipt.json` and `compact/coverage.tsv` describe the census;
the lineage/fragment/duplicate manifests preserve navigation and malformed
record disclosure. The builder, verifier, contract and schemas are included
so the receipt is interpretable without hidden chat context.

The large source inventory, segment inventory, authority manifest and frozen
roster are not Git content. Their exact hashes are in the build receipt and
their bytes are preserved in the encrypted private knowledge-audit vault
listed in `provenance/private_raw_hashes.tsv`. No raw market payload or source
content was copied into this publication. The empty audit proposition output
is not the project claim ledger; curated, evidence-linked active claims live
in `knowledge/propositions.tsv` and `knowledge/evidence.tsv`.
