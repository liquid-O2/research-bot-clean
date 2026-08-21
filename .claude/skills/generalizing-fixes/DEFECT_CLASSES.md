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
