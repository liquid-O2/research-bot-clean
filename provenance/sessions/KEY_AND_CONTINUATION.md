# Private key and continuation

The transcript vault is AES-256 symmetric GPG encrypted. Its current key file
is outside Git at:

`/home/claude/.russell-private-keys/vault_20260810T144841Z.key`

Only the key SHA-256 is recorded in Git. The user must copy the key to a
separate password manager or offline secret store before the old environment
is retired. Losing both the local key and that backup makes the raw vault
unrecoverable.

The initial and final Codex manifests freeze exact byte cutoffs. The final
continuation was captured at `2026-08-10T15:55:59Z`; every initial source
prefix was rehashed byte-identically before the readable transcript was
regenerated. `CONTINUATION_PROOF.tsv` carries the per-source old/new cutoff,
appended-byte count, and both hashes. Both encrypted archives remain in the
private vault; neither was overwritten.

Codex JSONL sources remain technically live after the final cutoff, so later
conversation is a new continuation rather than part of the frozen clean-room
snapshot. The readable Git transcript is complete through the declared final
cutoff, while exact raw bytes remain encrypted.
