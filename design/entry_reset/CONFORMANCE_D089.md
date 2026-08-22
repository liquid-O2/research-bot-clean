# D-089 conformance pass — entry reset plan (2026-08-22)

Walk of DIRECTIVES.md (LIVE set per DIRECTIVES_INDEX.md, plus the conditionally-live entries
the plan touches) against `overview.md`. Each entry: satisfied-how, or N/A with the reason.
Violations would block the freeze; none found. Evidence half (D-089-EXTENSION): every design
element is checked against committed findings in the §Evidence-checked table at the end.

| Directive | Status | How |
|---|---|---|
| D-001 one review, one fix pass | satisfied | each phase lands as one batch; `running-consolidated-review` once per batch |
| D-002 orchestrator designs | satisfied | selector, corpus path, replay and folds are designed here; lanes implement only |
| D-003 entries only until certified | satisfied | exits never appear as work or as pricing (D-110) |
| D-004 C++ majority | satisfied | corpus growth goes through the C++ native builder; Python only for fits and probes |
| D-005 lane models | satisfied | lanes, if dispatched, are Opus high / xhigh per D-005 |
| D-006 constructors need spec + red-first | satisfied | SC-RESET-1..5 bind spec→test→receipt; phase 1 seen red twice |
| D-007 corrections become D-entries | satisfied | the goal-round answers became D-110 in the same turn, verbatim in DIRECTIVES_INBOX.md |
| D-008 plain reports | satisfied | unslop + writing-plainly on every user-facing line |
| D-010 numbers need file:line | satisfied | every number in overview.md cites its receipt or command |
| D-012 durable memory | satisfied | STATE.md, CURRENT.md, memo notes updated at each landing |
| D-013 / D-108 hooks | N/A | no hook changes |
| D-014 no turn ends on a finding | satisfied | phase 1 built and receipted in the same session as the diagnosis |
| D-015 no early surrender | satisfied | the goal is not lowered; Q1/Q2 ask the user, the plan measures |
| D-016 low token use | satisfied | phase files are one screen each; tickets carry no code |
| D-017 no weak proxies | satisfied | the promotion metric is exact replay dollars; ρ/AUC are diagnostics placed beside dollars |
| D-018 no bulk on the overlay | satisfied | slices and receipts under /workspace/artifacts |
| D-021 $600/trade minimum | conditionally-live | user demoted to a preference 2026-08-22 (inbox ~09:05Z); the gate reports it |
| D-028 / D-029 autonomy | satisfied | the goal round is answered (D-110); every phase proceeds without further asking |
| D-030 prop-firm MDD < $1,000 | satisfied | gate clause unchanged (SC-RESET-4) |
| D-033 confirmed-extreme entry | satisfied | decision at Δ after formation, never at the extreme prediction |
| D-036 day-complete evaluation | satisfied | every cell of every day in a block is scored; abstention priced at $0 |
| D-040 frozen deterministic taker | satisfied | CatBoost CPU, hash-pinned models; no API model decides |
| D-043 / D-045 / D-048 per-asset rung, thin-era floor | satisfied | ladder rung per asset; per-era curve per half-year |
| D-046 one mini, one position | satisfied | one contract, one position per asset in the replay |
| D-047 MBP-1 ceiling | satisfied | no new data modality |
| D-051 lockstep multi-asset, C++ substrate | satisfied | all three assets in every slice; native builder |
| D-054 mid-sanity | N/A | no change to the mid pipeline |
| D-057 availability-time joins | satisfied | no new context series; existing joins unchanged |
| D-058 walk-forward | satisfied | half-year walk-forward folds; 2025H2 never opened |
| D-060 no paid data | satisfied | none |
| D-062 / D-063 per-asset posture, full session | satisfied | three phases per day, all assets |
| D-070 style-agnostic generation | N/A | generator frozen by user ruling |
| D-074 continuous operation | satisfied | phase 2 is next; phase 3 follows the pilot's arithmetic receipt, no user wait |
| D-077 / D-077-UPDATE news veto | open item | no veto found in replay/teacher/corpus; phase 5 resolves and the receipt says which (map fog item) |
| D-080 law collisions surfaced | satisfied | Q1 surfaces the 80%-capture clause vs the measured bar; D-097's $600/trade clause vs the 2026-08-22 demotion is noted here as a collision for the user |
| D-081 few, large, correct operations | satisfied | six phases; each launch once, receipted |
| D-084 adaptation across eras | satisfied | per-half-year verdict curve 2022H1..2025H1 |
| D-085 model is the scale-certified object | satisfied | phase 3–4 validate walk-forward on every day of every slice |
| D-089 conformance pass | satisfied | this file |
| D-092 raw fidelity for reader decisions | N/A | no reader round; model path only |
| D-094 entry-v2 reset order | satisfied | no neural; old matrix used only for the ruler |
| D-095 exact bottleneck attribution | satisfied | the four-column verdict with shuffle at every boundary; a null closes only the object tested |
| D-097 H2 is confirmation only | satisfied | 2025H2 sealed; note the $600/trade clause inside D-097 now conflicts with the user's 2026-08-22 demotion (collision surfaced, D-080) |
| D-098 / D-103 run-time budgets | satisfied | whole corpus ≈ 1 box-hour (D-110); no chain run in this plan |
| D-100 budget-binding | satisfied | arithmetic per phase; the pilot receipt must prove the one-hour bound before phase 3 launches |
| D-101 / D-102 continuity, merit-first | satisfied | OptMem notes; directives applied on merit |
| D-104 skill routing | satisfied (after correction) | planning skills invoked through the Skill tool on the redo; implementation skills invoked before the phase-1 edit |
| D-105 per-head backends | satisfied | phase-4 fits CPU only, one backend per arm |
| D-106 5+5 seeds | satisfied | phase 4 and 5 |
| D-107 entries first | satisfied | exits out of scope in every form (D-110) |
| D-110 goal rulings | satisfied | rung is the gate; 80% reported; no lever pricing; corpus ≈ 1 box-hour via Δ-grid rows (overview §Corpus build arithmetic) |
| D-109 six-hour cap by speed | satisfied | Δ-grid rows + native builder + walk-free replay; speed by architecture, not thinner evidence |

## Evidence-checked (D-089-EXTENSION)

| Design element | Committed finding it is checked against | Verdict |
|---|---|---|
| Fixed-Δ cell selector | accrual real but weak at 290 s (confirmation_accrual_v2); delay forfeit 92–97% retained | consistent; marked hypothesis that scale lifts ρ |
| θ-skip with θ from prior fold | D7 ruler: skip ≈ all at the 2021 sample | kept because the pool mean is negative at scale too (ruler receipt) |
| No MILP teacher | A7: optimum ≤1 entry per cell; ruler: 0 flat-by-phase-close violations | consistent |
| Native builder at call site | R6 accepted bit-identical on 215 sessions; not wired | consistent |
| Corpus 2022-01..2025-06 | journal 2026-08-18 16:40Z forecast readiness; D-084/D-085 | consistent |
| Sequential hazard deferred | five causal shapes inside 300 s fail at the 2021 sample | fog, not barred (sample-scoped closure) |
| Day-level regime features | cross-asset timing null at tried grains (2021 sample) | enter as features only, marked hypothesis |
