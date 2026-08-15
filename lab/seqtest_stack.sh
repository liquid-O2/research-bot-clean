#!/usr/bin/env bash
set -u
P=/usr/bin/python3; E=/workspace/engine/port_m2/seqtest; ER=E3,E4,E5,E6,E7
run(){ echo "### $*" >&2; "$@" || echo "### FAILED: $*" >&2; }
run $P $E/st_stack.py --stack --component FM_TABPFN_WINNER --tag STK_TABPFN
run $P $E/st_stack.py --meta --tag META_GATE
run $P $E/st_sched.py --tags STK_TABPFN,META_GATE,LMART_HP_NOTF --eras $ER --out SEQTEST_STACK
run $P $E/st_eratable.py --tag STK_TABPFN --eras $ER --out SEQTEST_ERATABLE_STK_TABPFN.tsv
run $P $E/st_eratable.py --tag META_GATE --eras $ER --out SEQTEST_ERATABLE_META_GATE.tsv
echo "stack+meta complete"
