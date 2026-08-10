# Knowledge-source inventory audit

Status: `PASS_ZERO_UNCLASSIFIED` for the frozen source/segment inventory.

This publication is metadata-only. It copied no transcript text, research-paper
body, raw market payload, secret, or other source content. Content-bearing
sources are represented by fixed byte-prefix SHA-256 values; restricted and
data-wall sources are metadata-only.

## Frozen publication

- Publication: `/workspace/data/cleanroom_work/knowledge_audit/publication_v1`
- Snapshot ID: `d939f0856c4f9ca9ea949149cd3a9c69531e36c5de41c9a78ebe6a7553f39385`
- Build receipt SHA-256: `c735d096375c555062d10ac12b6de0ca801d64b507d4839f8da2e5e2ddda7ccb`
- Independent verification receipt: `/workspace/data/cleanroom_work/knowledge_audit/verification_v1.json`
- Verification receipt SHA-256: `32a0e6bb4578ec02f0eae3f20b72be59fd46571893aa6d865a6491e93a17d2ad`
- Verifier SHA-256: `768aca48886c6d556c0c3974453e8af9407704ce0a427ecbf4a7f34d3b4202f0`

## Census

- Sources: 238,637
- Segments: 387,517
- Exact Codex lineage sources: 40
- Recursive historical Claude workspace sources: 655
- Authority candidates: 69,287
- Malformed JSONL fragments: 25 (24 malformed physical records and one
  unterminated tail), all quarantined by source and byte range
- Sources without segments: 0
- Unclassified sources/segments: 0
- Independently reverified content prefixes: 114,605
- Sources appended after the frozen prefix: 4; all four retained the exact
  frozen prefix and require a later continuation capture before cutover

## Principal machine-readable outputs

- `source_inventory.jsonl`: `16e38ba1aab7c39aeee0b95d4f21307cba11f1de18e81a4ef0c1582b57d7e176`
- `segments.jsonl`: `c6b69f197deb840e14b91787c15d34948e1744a636fecc0218beb7a85f7b2594`
- `codex_lineage_manifest.jsonl`: `81fd962e48c838c53f4a5ab7d442247668084a518fd01e655d7f0a1fce97a245`
- `claude_history_manifest.jsonl`: `b25cf85e86206ea6859e988ad56598f731ffdb932103a0769c7e0a0880dcf464`
- `authority_manifest.jsonl`: `1bd93ede0073d0a1c1c66d21f0fea3b39da0fe6ab9884c6f83a95bd32e5979b2`
- `jsonl_fragments.jsonl`: `b1f8bc5f82cafb1b44ea329f4be140b9d1df90cf0297d123492a181e68ba6141`
- `coverage.tsv`: `5c9bc286163983afda764ab7af4000b65bb2e6493a11198d60fe27e35a8af110`

## Scope boundary

The proposition and evidence-link files are deliberately empty. This audit
proves exhaustive source classification, segment foreign-key closure,
privacy/license disposition, malformed-fragment quarantine, and operational
gates that reject unsupported propositions. It does **not** claim that
semantic proposition extraction or evidence adjudication is complete. The
clean repository must still bind its active empirical propositions to exact
admissible evidence before cutover.
