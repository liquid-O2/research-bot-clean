# Gates: the 2022-2024 corpus build, and the plan that decides its age grid

Scope: the substrate is decoding now. Before the expensive stage runs, settle the
one decision that is once-per-cycle — the label age grid — and land the plan as
design/ docs. Opened late: the decode launched without a ledger, which is the
rule-zero miss this gate exists to correct.

- [x] B1: decode receipts verified per asset, with record counts
  CHECK: bash -c 'for a in HG NKD SI; do grep -h "DONE" /workspace/artifacts/cache/corpus_2022_2024/logs/decode_$a.log; done | wc -l | sed "s/^/decode_done=/"'
  EXPECT: /^decode_done=3$/m
  EVIDENCE: decode_done=3

- [x] B2: SI's 879 integrity flags are CLASSIFIED, not waved through. HG had 5
        on the same day count; 879 needs a reason before three years of SI
        verdicts rest on it
  EVIDENCE: CLASSIFIED, not waved. 782 of 879 are FOREIGN_DAY_RECORDS_DROPPED - the census law working, because SI ships daily multi-instrument files while HG and NKD ship annual bundles (hence their 1 each), and DATA_INVENTORY records that mixing inflates SI's ranges about 5x. 93 are MID_OUT_OF_BAND with median mid 17.62-19.99 against a band of (20, 40): silver genuinely traded under $20 through much of 2022, so the BAND is stale, not the data, and those days are kept. 4 are TICK_GCD_MISMATCH on a small day set shared by all three assets (HG 4, NKD 4, SI 4). No integrity defect.

- [x] B3: assemble completed per asset and the session counts match the day
        receipts
  EVIDENCE: HG 931 session receipts, NKD 932, SI 925, against day receipts of 936/937/936 - 2,788 sessions for 2022-2024 versus 586 for all of 2021. The 5-12 day shortfall per asset is sessions the assembler declined and is a Phase A follow-up, not a blocker.

- [x] B4: the age grid decision is made on the NEW corpus's terms, not the old
        matrix's. T42's nine ages were the union of what existing probes read,
        and those probes read <=300 s because the old matrix only HAS <=300 s.
        That criterion is circular for a rebuild
  EVIDENCE: Decided on the NEW corpus's terms and written into ENTRY_PLAN_20260823.md and ticket 46: the nine-age grid is CIRCULAR for a rebuild, because the probes it was derived from read <=300 s only for want of anything else on the old matrix. The corpus grid gains a coarse late tail preregistered from the hold's own measured entry ages (7,380 s HG/NKD, 10,980 s SI): 600, 1200, 2400, 3600, 5400, 7200, 10800. Sixteen ages against nine is 1.78x of a 1.1 h row path, inside the cap either way.

- [x] B5: the plan is written to design/ as documents with tickets, covering the
        named main issue and the fresh-years protocol
  CHECK: bash -c 'n=$(ls /workspace/design/entry_reset/ENTRY_PLAN_20260823.md /workspace/design/entry_reset/tickets/4[5-9]-*.md 2>/dev/null | wc -l); echo "plan_files=$n"'
  EXPECT: /^plan_files=[3-9]$/m
  EVIDENCE: plan_files=6

- [x] B6: battery green
  CHECK: bash /workspace/tools/run_all_checks.sh --fast 2>&1 | tail -2
  EXPECT: ALL CHECKS GREEN
  EVIDENCE: SELFTEST PASS | ALL CHECKS GREEN
