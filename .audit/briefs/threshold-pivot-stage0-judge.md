# Judge Stage 0. Fable only.

`/poteto-mode` Investigation. You are Fable (`claude-fable-5-thinking-max`). Do not inherit Grok. Do not write engine code. Do not start Stage 1.

Read `.audit/threshold-pivot-stage0.json` and the tag files it names. Parent will also have read the bytes. Confirm or reject PASS from the artifact, not from Sol's summary.

Checks.

- Schema is `QRE2G1PIVOTSTAGE01`.
- Selftest and the four mutants are red for the intended reason.
- Determinism guard held against stored candidate TSVs.
- Future-mutation differential held.
- Tags exist for 20210721-20210806. No 2022-2024 tag days.
- Existing candidate and teacher artifacts were not rewritten.
- No tape histograms. No ninth field.

Write `.audit/briefs/threshold-pivot-stage0-judge-out.md` with PASS or REJECT and the cited bytes. REJECT stops the program.
