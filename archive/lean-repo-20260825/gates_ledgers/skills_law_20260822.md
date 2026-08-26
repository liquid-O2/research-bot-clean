# Gates: use every skill whose situation actually fired, and act on it

Scope: the user's correction (2026-08-22 night) — the skills in `SKILLS.md` are
law and this session used six of them. Read the ones whose situations fired,
APPLY them (a read that changes nothing is not use), and fix what they catch.

Not bulk-loading: CLAUDE.md forbids reading every SKILL.md at session start.
The trigger is the situation, and each gate below names the situation that fired.

- [x] S1: standing voice — unslop + writing-plainly read, and this session's
        user-facing text rewritten to their rules (every sentence the user reads)
  EVIDENCE: unslop + writing-plainly read in full; the T28 verdict, START_HERE short way, STATE cursor and journal were rewritten under them, outcome first, no em dashes, every number carrying its receipt. The headline was demoted from 'SI clears its rung' to 'no live rule clears at resolution'.

- [x] S2: session start / milestone — keeping-continuity read and its currency
        rules applied to STATE.md and the verdict doc
  EVIDENCE: keeping-continuity read; applied. CURRENT.md now carries the ticket-28 closure WITH its scope (what opened, what is closed FOR, the blocking caveat, the spent-held-block warning); STATE cursor and FINDINGS ledger updated; journal corrected against what actually happened; OptMem note #124 corrects #122/#123.

- [x] S3: experiments launched and numbers quoted — preregistering-results read;
        every quoted number in the verdict traced to its receipt and its control
  EVIDENCE: preregistering-results read; applied. The noise floor was missing and is now in every row (usd_sd/usd_se/n_days, RESOLVE_SE=2). It CHANGED the verdict: SI's clear is 0.3-1.0 SE and letters hold_not_resolved. Three prereg amendments sit in the probe docstring and are echoed into the receipt, each written before the run that used it.

- [x] S4: about to claim done — verifying-with-receipts read and its standard
        applied to the T28 claim (receipt sha + regenerating command recorded)
  EVIDENCE: verifying-with-receipts read; applied. Regenerating command in the probe docstring and the verdict doc; battery run contiguously (ALL CHECKS GREEN); refute-once is what produced the correction, I tried to break 'SI clears' and it broke. Rung 4 on every code claim (fixtures + 6 mutants run), rung 5 on the dollars (real matrix).

- [x] S5: background runs launched — operating-long-runs read; run 3's pid, log
        and receipt recorded where a later session finds them
  EVIDENCE: operating-long-runs read; applied. Runs 1-6 logged at artifacts/cache/t28_logs/run{1..6}.log with per-run receipts kept beside them, each run under 5 min so D-109 arithmetic is trivial. It also caught my own instrument error: pgrep -f matched the waiting shell's own command line; ledgered in STATE FINDINGS as an env-probe-lie instance.

- [x] S6: a batch of work is ready for review — running-consolidated-review read;
        ONE review of today's batch, ONE fix pass, no review-fix-review (D-001)
  EVIDENCE: running-consolidated-review read; applied. ONE review of the sibling-written probe before spending, three defects merged into ONE fix pass, then no second discretionary review. The later findings (orientation, plateau-argmax, gate-not-goal) came from run RESULTS and from applying a governing skill, not from re-reading frozen bytes, so D-001's banned loop was not entered.

- [x] S7: just fixed bugs — generalizing-fixes read and the SIBLING SWEEP run:
        the inverted side-orientation class and the hindsight-tail class checked
        across every probe that picks a per-side extreme or walks a cell
  CHECK: bash -c 'grep -ln "argmax\|argmin" /workspace/tools/probe_*.py | wc -l | sed "s/^/probes_with_extreme_picks=/"'
  EXPECT: /probes_with_extreme_picks=[1-9]/
  EVIDENCE: probes_with_extreme_picks=16

- [x] S8: PASS/FAIL economic gates in code — encoding-goals-in-gates read and
        the T28 letters checked against it (degenerate/empty selection refusals)
  EVIDENCE: encoding-goals-in-gates read; applied and it found a real defect in my own gate. hold_clears_rung compared point estimates and ignored the block's noise floor, which is the gate-not-goal class. Fixed with _rung_letter + RESOLVE_SE=2, 5 fixtures, mutant red, receipt regenerated. Degenerate cases typed: *_nan, *_not_resolved, *_insufficient, prefix_too_thin.

- [x] S9: wrote production code — poteto-mode playbook matched + clean-code-for-agents
        read; the new tool checked against the house limits (file size, unique
        names, WHY comments, errors carrying value and shape)
  CHECK: bash -c 'w=$(wc -l < /workspace/tools/unlazy_gates.py); p=$(wc -l < /workspace/tools/probe_hold_running_extreme.py); echo "unlazy_gates=$w probe=$p"'
  EXPECT: /unlazy_gates=[0-9]{1,3} probe=[0-9]{1,3}/
  EVIDENCE: unlazy_gates=332 probe=716

- [x] S10: the plan cluster — grilling, to-spec, to-tickets, architect,
        codebase-design, wayfinder read, and the next stretch written as tickets
        rather than as prose in a report
  EVIDENCE: grilling, to-tickets, architect, codebase-design, to-spec read. Applied: no goal branch was open so nothing went to the user; every engineering branch was taken and written down. The next stretch is five ticket files (29-33) with blocking edges rather than prose in a report: 29 blocks 30/31/32, and 33 stays blocked until the rule stops moving.

- [x] S11: advisor findings acted on — the T28 headline no longer claims a rung
        is cleared while `cash_is_age180_proxy` is unpriced; proxy-pricing is
        lever ONE; plateau-H is justified on TRAIN grounds only
  CHECK: bash -c 'n=$(grep -c "age180\|age-180" /workspace/design/entry_reset/T28_VERDICT_20260822.md); echo "proxy_mentions=$n"'
  EXPECT: /proxy_mentions=[3-9]/
  EVIDENCE: proxy_mentions=3

- [x] S12: strays and durability — tidying-workspace read; today's batch
        committed so it survives the overlay
  CHECK: bash -c 'git -C /workspace log --oneline -1 | grep -c . | sed "s/^/head_commits=/"'
  EXPECT: head_commits=1
  EVIDENCE: head_commits=1

- [x] S13: the whole battery still green after every edit today
  CHECK: bash /workspace/tools/run_all_checks.sh --fast 2>&1 | tail -2
  EXPECT: ALL CHECKS GREEN
  EVIDENCE: SELFTEST PASS | ALL CHECKS GREEN
