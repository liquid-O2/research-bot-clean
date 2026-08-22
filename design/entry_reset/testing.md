# Testing (project level for the entry reset)

- Regression battery: `bash tools/run_all_checks.sh --fast` before every launch and before every commit.
- Tool selftests (house single-file-tool law): `python3 tools/probe_rho_ruler.py --selftest`, `python3 tools/probe_cell_selector.py --selftest`, `python3 tools/diff_discretionary_native.py --selftest`, `python3 tools/regate_policy_block.py --selftest`.
- Module tests seen red first: `engine.entry_v2.test_disc_native_harness` (builder selection), `engine.entry_v2.test_cell_pick_replay` (phase 5), `engine.entry_v2.test_tabular_ladder_gate` (existing).
- Evidence tier: the real-path receipts named in each phase file; unit and synthetic tests are regression checks only (AGENTS.md rule 2).
- SC binding: SC-RESET-1..5 ids appear in test names and receipt `prereg` fields so `running-consolidated-review` can grep them.
