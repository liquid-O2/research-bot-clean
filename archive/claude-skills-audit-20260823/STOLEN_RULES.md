# Rules worth stealing from bigpowers (extracted, not adopted)

Directive-grade lines harvested by the 2026-08-21 audit. Candidates for future D-entries or CLAUDE.md; sources cited so wording can be re-verified. None are active law until the user ratifies.

1. **"A gate that cannot run must not claim it did."** (wire-ci — exits distinct-nonzero rather than pretending it gated.) Generalizes to every skipped/degraded check; fits the receipts culture.
2. **Single-contiguous-run verdict.** (verify-work) At least one gate must be a real shell verdict captured from ONE contiguous run; evidence from multiple runs must never be merged into one verdict.
3. **Every PASS must survive one refutation attempt.** (gate-trace) Before recording a pass, actively try to break it once.
4. **Three independent facts** before a keep/merge decision. (release-branch) No single-source verdicts.
5. **Failing-ledger:** never pre-mark a checklist item as passing; items start failed and are flipped only by evidence. (plan-work)
6. **Zoom-out mandate:** state a module's purpose, callers, and contracts before editing it. (plan-work)
7. **Multiple-interpretations gate:** if a spec line admits two readings, name both and pick one in writing before coding. (plan-work)
8. **"Reason for Depth"** — every new abstraction/indirection must state why inline code wouldn't do; otherwise inline it. (plan-work / APOSD)
9. **Deletion test** for names/abstractions: if deleting it changes nothing observable, delete it. (deepen-architecture/LANGUAGE.md)
10. **Defect-class sweep:** after fixing a bug, name the class, grep for siblings, record match_count in the receipt. (validate-fix/REFERENCE-generalize-fix.md)
11. **Positive/negative fixture pairs** for every detector/scanner — a red-first fixture AND a false-positive guard fixture. (security-review; extends D-017's red-first law with the FP half.)
12. **Two-commit RED/GREEN isolation:** test commit and implementation commit separable, so the red state is provable from history. (develop-tdd)
13. **Subagent brief template + depth tiers** (delegate-task): context/constraints/deliverable/verify sections; depth of review scaled to blast radius.
14. **Dangerous-git knowledge list** (guard-git REFERENCE — knowledge only, never its blocking hooks per D-013): force-push, `reset --hard`, `clean -f`, `branch -D`, `checkout/restore .` are the destroy-work commands; treat as ask-first.
15. **Honest-metric retraction pattern** (release-branch REFERENCE): agent-self-reported, wall-clock-contaminated metrics get retracted in writing, with the contamination named — rhymes with this repo's incorruptible-labels finding.

## Upstream additions (2026-08-21, second pass — Karpathy/Pocock/Akita/pstack)

16. **Surgical changes** (Karpathy): every changed line traces to the request; clean only your own orphans; mention, don't delete, pre-existing dead code. → CLAUDE.md coding conduct.
17. **Frontier-round grilling** (Pocock `grilling`): ask the whole frontier of currently-answerable questions per round, numbered, each with a recommended answer; dependent questions wait. → stress-testing-plans.
18. **Tight-red-signal-first debugging** (Pocock `diagnosing-bugs`): a pass/fail signal that goes red on THIS bug is the skill; bisection and hypotheses merely consume it. → verifying-with-receipts ladder.
19. **Seam minimization** (Pocock `to-spec`): test at the highest existing seam; ideal new-seam count is one. → designing-it-twice.
20. **Durable briefs** (Pocock `triage`): briefs describe interfaces and behavior, never file paths/line numbers (they stale); testable acceptance criteria; explicit out-of-scope. → subagent brief practice.
21. **Invocation-cost model** (Pocock `writing-for-agents`): a model-invoked skill's description is permanent per-session context load — keep descriptions tight; rarely-used skills can be user-invoked at zero context cost.
22. **Code shape = agent infrastructure** (Akita): unique grep-able names (<5 hits), files fit one read, typed signatures, WHY-comments with provenance, one-command tests. → shaping-code-for-agents skill + CLAUDE.md conduct.
23. **Cheap-first verification ladder** (house synthesis for the trading project): fixture → 1-day slice → full run; climb only on green; full runs only at zero predicted refusals.
24. **Unslop** (pstack): cut puffery and -ing tails; have opinions; specificity over vibes. → writing-plainly.
