# Gates: use every skill whose situation actually fired, and act on it

Scope: the user's correction (2026-08-22 night) — the skills in `SKILLS.md` are
law and this session used six of them. Read the ones whose situations fired,
APPLY them (a read that changes nothing is not use), and fix what they catch.

Not bulk-loading: CLAUDE.md forbids reading every SKILL.md at session start.
The trigger is the situation, and each gate below names the situation that fired.

- [ ] S1: standing voice — unslop + writing-plainly read, and this session's
        user-facing text rewritten to their rules (every sentence the user reads)
  EVIDENCE: pending

- [ ] S2: session start / milestone — keeping-continuity read and its currency
        rules applied to STATE.md and the verdict doc
  EVIDENCE: pending

- [ ] S3: experiments launched and numbers quoted — preregistering-results read;
        every quoted number in the verdict traced to its receipt and its control
  EVIDENCE: pending

- [ ] S4: about to claim done — verifying-with-receipts read and its standard
        applied to the T28 claim (receipt sha + regenerating command recorded)
  EVIDENCE: pending

- [ ] S5: background runs launched — operating-long-runs read; run 3's pid, log
        and receipt recorded where a later session finds them
  EVIDENCE: pending

- [ ] S6: a batch of work is ready for review — running-consolidated-review read;
        ONE review of today's batch, ONE fix pass, no review-fix-review (D-001)
  EVIDENCE: pending

- [ ] S7: just fixed bugs — generalizing-fixes read and the SIBLING SWEEP run:
        the inverted side-orientation class and the hindsight-tail class checked
        across every probe that picks a per-side extreme or walks a cell
  CHECK: bash -c 'grep -ln "argmax\|argmin" /workspace/tools/probe_*.py | wc -l | sed "s/^/probes_with_extreme_picks=/"'
  EXPECT: /probes_with_extreme_picks=[1-9]/
  EVIDENCE: pending

- [ ] S8: PASS/FAIL economic gates in code — encoding-goals-in-gates read and
        the T28 letters checked against it (degenerate/empty selection refusals)
  EVIDENCE: pending

- [ ] S9: wrote production code — poteto-mode playbook matched + clean-code-for-agents
        read; the new tool checked against the house limits (file size, unique
        names, WHY comments, errors carrying value and shape)
  CHECK: bash -c 'w=$(wc -l < /workspace/tools/unlazy_gates.py); p=$(wc -l < /workspace/tools/probe_hold_running_extreme.py); echo "unlazy_gates=$w probe=$p"'
  EXPECT: /unlazy_gates=[0-9]{1,3} probe=[0-9]{1,3}/
  EVIDENCE: pending

- [ ] S10: the plan cluster — grilling, to-spec, to-tickets, architect,
        codebase-design, wayfinder read, and the next stretch written as tickets
        rather than as prose in a report
  EVIDENCE: pending

- [ ] S11: advisor findings acted on — the T28 headline no longer claims a rung
        is cleared while `cash_is_age180_proxy` is unpriced; proxy-pricing is
        lever ONE; plateau-H is justified on TRAIN grounds only
  CHECK: bash -c 'n=$(grep -c "age180\|age-180" /workspace/design/entry_reset/T28_VERDICT_20260822.md); echo "proxy_mentions=$n"'
  EXPECT: /proxy_mentions=[3-9]/
  EVIDENCE: pending

- [ ] S12: strays and durability — tidying-workspace read; today's batch
        committed so it survives the overlay
  CHECK: bash -c 'git -C /workspace log --oneline -1 | grep -c . | sed "s/^/head_commits=/"'
  EXPECT: head_commits=1
  EVIDENCE: pending

- [ ] S13: the whole battery still green after every edit today
  CHECK: bash /workspace/tools/run_all_checks.sh --fast 2>&1 | tail -2
  EXPECT: ALL CHECKS GREEN
  EVIDENCE: pending
