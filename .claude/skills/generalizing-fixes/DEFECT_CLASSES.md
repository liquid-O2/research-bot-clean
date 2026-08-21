# Defect-class registry (append-only; checked as a lens in every consolidated review)

Named classes this program has paid for at least once. Every new bug: check if it's an instance of one of these FIRST; every genuinely new class: append it here with its incident.

| Class | Signature | Paid incidents |
|---|---|---|
| side-encoding | string-parsing an integer/typed side; sign conventions crossed at a boundary | confirmation lane: `str(side).startswith("B")` on {-1,+1} → all 8,993 trades short |
| silent-empty | a zero/empty result treated as retry/skip instead of a typed valid outcome | 3x journaled "silent-empty"; bcp-agent's `if not response` re-fire on {"total":0} |
| survivorship-drop | fit/loop silently drops rows/days it cannot process, biasing the sample | M-regression dropped M<=0 days = exactly the buy-heavy days |
| denominator | per-session/per-day divisors inflated or deflated (missing sessions, conditional-on-trading means) | repo-wide audit touched 118 provenance tables; "the bar has no writer" |
| lookahead-seating | selection/seating consumes information from later in the day/run | top_per_cell_score seated the eventual argmax — "the defining adjudication," hit 3x |
| eval-selected-knobs | thresholds/fractions/windows chosen on the eval block's own outcomes | secretary observe-fractions — "swallowed the night" |
| tautological-label | label ordering mechanically equals entry-price/exit-price ordering within group | MFE ~88% tautological; day-end best-pick Spearman 1.0; A_PBAR day-relative |
| mirror-fixture | fixture generated from the same constant/builder the assertion reads | (pre-empted by checking-data-contracts rule 5) |
| resume-width | resume/restart path compares against a different schema source than the builder | action day-store 1793 vs 1764; three rehearsal resume refusals |
| seed-draw-headline | single-seed number quoted as the result | champion $977 → $754±323; A_EV seed-0 |
| stale-doc-read | agent works from inherited/superseded docs or transcripts as current truth | old-select picked apart as current; old transcripts read as new research |
| env-probe-lie | nproc/free/cgroup taken at face value on RunPod | 64-vs-13.6 cores, 1TB-vs-263GiB — recurring; see HARDWARE.md |
| torch-stack-swap | optional install silently replaces the pinned CUDA Torch | 2x; pin cu128 on every install |
| unit-test-as-launch-proof | green unit/synthetic tests presented as chain readiness | AGENTS.md rule 2 exists because of this; 9-plumbing-failure launch |
| gate-not-goal | gate enforces a different grain/law than the contract | portfolio-vs-per-asset PASS; shuffle-can-pass; zero-eligible haircut |
| shared-mutable-lifetime | a handle, buffer, memmap, lock or module-level cache outlives the scope that owns it, or is read/written from two workers with no stated synchronization | EventPack memmap use-after-unmap: holding `.rows` past the `with` SIGSEGVs silently in workers (registered 2026-08-21, sweep owed across `engine/`); journal lock file; 16 workers on a 13.6-core cgroup |
| orphaned-pool | a driver's multiprocessing `spawn_main` workers survive the parent's death as ppid-1 orphans — burning cores against the successor, double-computing, and writing under the pre-crash code | 2026-08-21: all 16 workers of the perfect-actions-crashed driver ran on ~3 nice-0 cores for 1h45m against the resumed chain (load 27→13 on kill); sweep = kill orphans + parse every manifest written in the crash window |
| inert-native-path | a differential/oracle gate passes because the new path never engaged — a stub or silent fallback leaves the old path's bytes on both sides, so the comparison is same-vs-same by construction | 2026-08-21 R6 wave2b: clock families' store differential would pass with lane A's slice kernel still a RED-FIRST stub (caught only by the family-level name-count test); walk-twin's invocation counter and diff_walk_twin's zero-units refusal exist for this class; guard = assert engagement (non-zero displaced/name count or invocation counter) in every differential gate |
