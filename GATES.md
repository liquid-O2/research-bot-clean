# Gates: ticket 29 — price the age-180 cash proxy

Scope: replace every ticket-28 dollar figure with cash taken at the moment the
hold rule ACTUALLY enters, or letter exactly why that cannot be built and what
the bound is. Until this lands no ticket-28 number is an economic result and
tickets 30-33 are not worth running.

Spec: `design/entry_reset/tickets/29-price-entry-time-label.md`.
Law unchanged: rung $2,000 HG / $1,500 NKD and SI; <=12 entries per
portfolio-day; MDD < $1,000; generator frozen; exits deferred; 2025H2 sealed;
2021 kills but never promotes.

- [ ] P1: the y label's construction is established from the outcome-builder
        SOURCE, not assumed — in particular whether its exit is anchored to the
        entry moment (a later entry moves the exit too, so only a fresh label is
        honest) or to a fixed clock (a drift correction is then meaningful)
  EVIDENCE: pending

- [ ] P2: the maximum series age the authoritative data can label is measured,
        not guessed — this decides whether an H = 120-180 min entry is
        labelable at all from what exists on this box
  EVIDENCE: pending

- [ ] P3: the Stage B walk emits its pick list (day, cell, series, formation
        time, fire time, entered age) to the receipt, so the picks are
        addressable by anything downstream
  CHECK: python3 -c "import json;d=json.load(open('/workspace/artifacts/entry_v2/tabular_recovery/diagnostics/hold_running_extreme_20260822.json'));p=d['assets']['HG']['stage_b']['train'].get('picks');print('picks='+str(len(p) if p else 0),'keys='+(','.join(sorted(p[0])) if p else 'NONE'))"
  EXPECT: /picks=[1-9][0-9]* keys=.*entered_age_sec/
  EVIDENCE: pending

- [ ] P4: the distribution of entered age is published per asset and block —
        this is the size of the gap the proxy is hiding
  CHECK: python3 -c "import json;d=json.load(open('/workspace/artifacts/entry_v2/tabular_recovery/diagnostics/hold_running_extreme_20260822.json'));s=d['assets']['SI']['stage_b']['train'];print('median_entered_age_sec='+str(s.get('entered_age_median_sec')))"
  EXPECT: /median_entered_age_sec=[0-9]/
  EVIDENCE: pending

- [ ] P5: a red-first fixture proves the pricing path cashes a planted pick at
        its REAL entry value, and REFUSES (never silently falls back to the
        180 s value) when no real-entry label exists for that pick
  CHECK: python3 /workspace/tools/probe_hold_running_extreme.py --selftest 2>&1 | tail -1
  EXPECT: selftest OK
  EVIDENCE: pending

- [ ] P6: the verdict is one of exactly two, and it is written down: either
        real-entry cash per asset and block with its per-day SE beside the proxy
        cash, or a typed refusal naming what data would be needed
  EVIDENCE: pending

- [ ] P7: START_HERE, STATE, CURRENT and the T28 verdict carry the outcome, and
        `cash_is_age180_proxy` is either removed, re-scoped, or explicitly kept
        with its measured bound
  CHECK: bash -c 'n=$(grep -lc "entered_age\|entry-time cash\|age180" /workspace/START_HERE.md /workspace/STATE.md /workspace/design/entry_reset/T28_VERDICT_20260822.md 2>/dev/null | wc -l); echo "verdict_files=$n"'
  EXPECT: /verdict_files=3/
  EVIDENCE: pending

- [ ] P8: battery green
  CHECK: bash /workspace/tools/run_all_checks.sh --fast 2>&1 | tail -2
  EXPECT: ALL CHECKS GREEN
  EVIDENCE: pending
