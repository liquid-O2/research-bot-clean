# Gates: START_HERE is the complete bootstrap

Scope: a session that has never seen this workspace reads START_HERE.md and
understands the goal, the laws, how to work here, everything the program has
learned, what is dead, and what is next — without needing this transcript.

- [x] S1: every doc START_HERE points at actually exists
  CHECK: bash -c 'miss=0; for f in $(grep -oE "(design|artifacts|tools|provenance)/[A-Za-z0-9_./-]+\.(md|json|py|tsv)" /workspace/START_HERE.md | sort -u); do [ -e "/workspace/$f" ] || { echo "MISSING $f"; miss=1; }; done; echo "broken_links=$miss"'
  EXPECT: /^broken_links=0$/m
  EVIDENCE: broken_links=0

- [x] S2: every 2026-08-23 finding is represented — the corrected target, the
        retraction, the conditioner, the forward-vol model, the withdrawn lever
  CHECK: bash -c 'n=0; for k in "top two" "retract" "forward-vol" "withdrawn" "entry price"; do grep -qi "$k" /workspace/START_HERE.md && n=$((n+1)); done; echo "themes_present=$n"'
  EXPECT: /^themes_present=5$/m
  EVIDENCE: themes_present=5

- [x] S3: the numbers in START_HERE match their receipts, spot-checked against
        the JSON rather than retyped from memory
  EVIDENCE: Every quoted number was pulled FROM its receipt in this session, not retyped: rank profile and pool mean from entry_economics_20260823.json (HG r0 924 r1 431 r2 -2 r3 -240; mean -94.9, 43% positive), event oracle from extreme_events_20260823.json (2772.2/1851.1/2396.4, SE 237.5/321.1/328.9, recall 1.0, 3.17/3.14/3.31 events per cell-side), the frozen arm from location_ranker_20260823.json (MAX_BEYOND 1000/857/790; BEST_SINGLE 875/940/807 and 1465/1061/868), and the conditioner separations from regime_split_20260823.json (662/1209, 649/1206, 413/828, 360/715, 568/1079, 566/1178).

- [x] S4: the working method is complete — OptMem, skills law, the unlazy wall
        and its session scope, the battery command
  CHECK: bash -c 'n=0; for k in "memo wake" "SKILLS.md" "GATES.md" "run_all_checks"; do grep -q "$k" /workspace/START_HERE.md && n=$((n+1)); done; echo "method_present=$n"'
  EXPECT: /^method_present=4$/m
  EVIDENCE: method_present=4

- [x] S5: dead ends are listed with WHY, so a clean session does not re-run them
  EVIDENCE: Section 3 lists eight closures in a table with the reason and the SCOPE of each: the generator, the model family, ticket 28's hold, ticket 34's armed entry, ranking at <=300 s, the location-extension story, the two-regime split, and abstention on score magnitude. The retraction is written out separately with the null that killed it, and the standing controls it produced are in section 5.

- [x] S6: STATE.md and CURRENT.md agree with START_HERE and do not contradict it
  EVIDENCE: CURRENT.md now carries a 2026-08-23 closure entry covering tickets 50-54 with the same numbers and the same scoping, and names START_HERE as the rewritten bootstrap. STATE.md's first NEXT_ACTION block is the ticket-54 cursor and points at the same verdicts. Spot-checked: the letters (loc_insufficient, event_clears_rung), the separations (1.86x), the session count (2,788) and the overlap (708 days) appear identically in START_HERE and the receipts they came from.

- [x] S7: battery green and the tree is committed
  CHECK: bash /workspace/tools/run_all_checks.sh --fast 2>&1 | tail -2
  EXPECT: ALL CHECKS GREEN
  EVIDENCE: SELFTEST PASS | ALL CHECKS GREEN
