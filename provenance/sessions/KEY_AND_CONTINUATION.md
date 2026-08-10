# Private key and continuation

The transcript vault is AES-256 symmetric GPG encrypted. Its current key file
is outside Git at:

`/home/claude/.russell-private-keys/vault_20260810T144841Z.key`

Only the key SHA-256 is recorded in Git. The user must copy the key to a
separate password manager or offline secret store before the old environment
is retired. Losing both the local key and that backup makes the raw vault
unrecoverable.

Codex JSONL sources were live at capture time. The prefix manifest freezes
each exact cutoff and marks it continuing. Before final workspace cutover,
capture one continuation vault and prove that every earlier file prefix is
byte-identical; do not overwrite this archive.

