# Gates: Entry V2 recovery plan

OWNS: .unlazy/entry-v2-recovery-plan/**, design/entry_reset/55-entry-v2-recovery-plan/**

Scope: diagnose why the live entry policy misses the fixed dollar goal and produce an evidence-backed implementation plan without changing product behavior

- [ ] G1: three disjoint exploration reports trace execution, audit evidence, and challenge the open frontier
  EVIDENCE: pending

- [ ] G2: the plan structure, links, evidence pointers, and required sections pass the plan verifier
  CHECK: PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 design/entry_reset/55-entry-v2-recovery-plan/verify_plan.py
  EXPECT: ENTRY V2 PLAN PASS
  CWD: .
  EVIDENCE: pending

- [ ] G3: every plan and contract file has no whitespace errors
  CHECK: /bin/sh -c 'git diff --check -- .unlazy/entry-v2-recovery-plan design/entry_reset/55-entry-v2-recovery-plan && echo "PLAN DIFF PASS"'
  EXPECT: PLAN DIFF PASS
  CWD: .
  EVIDENCE: pending

- [ ] G4: the diagnosis names the present shortfall, the causal data wall, and the information-versus-payoff frontier across allowed confirmation ages
  EVIDENCE: pending

- [ ] G5: the plan protects the sealed corpus, one-read rule, per-comparison nulls, entry-price controls, and two-standard-error verdict rule
  EVIDENCE: pending

- [ ] G6: short confirmation and forward volatility are falsifiable hypotheses among distinct causal paths that can improve within-cell top-two selection
  EVIDENCE: pending

- [ ] G7: each phase ends in a checkable receipt and the last phase decides the exact chronological replay goal
  EVIDENCE: pending

- [ ] G8: the plan contains no product implementation, names every deferred path, and has an independently reviewed decision trail
  EVIDENCE: pending
