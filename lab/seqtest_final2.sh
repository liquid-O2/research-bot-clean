#!/usr/bin/env bash
# FINAL FRONT — iteration 2: PER-ERA POLICY REFINEMENT.  The champion inherited
# m3's committed (unit, N), selected for m3's POINTWISE scores.  This selects it
# on the INNER VALIDATION BLOCK with this arm's own scores.  One change.
set -u
P=/usr/bin/python3; E=/workspace/engine/port_m2/seqtest; ER=E3,E4,E5,E6,E7
S=/workspace/artifacts/cache/port/m2/seqtest/scores
run(){ echo "### $*" >&2; "$@" || echo "### FAILED: $*" >&2; }
run $P $E/st_lmart.py --run --unit cell --from-era PRE_E1 --search --drop-tf \
    --policy-select --eras $ER --tag F2_POLSEL
run $P $E/st_lmart.py --run --unit cell --from-era PRE_E1 --search --drop-tf \
    --policy-select --shuffle --eras $ER --tag F2_POLSEL_SHUF
run $P $E/st_eratable.py --tag F2_POLSEL --eras $ER \
    --policy $S/F2_POLSEL.policy.json --out SEQTEST_ERATABLE_F2_POLSEL.tsv
run $P $E/st_eratable.py --tag F2_POLSEL_SHUF --eras $ER \
    --policy $S/F2_POLSEL_SHUF.policy.json --out SEQTEST_ERATABLE_F2_SHUF.tsv
echo "final iteration 2 complete"
