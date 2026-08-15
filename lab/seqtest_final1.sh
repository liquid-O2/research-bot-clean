#!/usr/bin/env bash
# FINAL FRONT — iteration 1: OBJECTIVE ALIGNMENT (ndcg@1, matching top-1-per-cell
# deployment) vs the champion's ndcg@3.  One change.  E8 blind.
set -u
P=/usr/bin/python3; E=/workspace/engine/port_m2/seqtest; ER=E3,E4,E5,E6,E7
run(){ echo "### $*" >&2; "$@" || echo "### FAILED: $*" >&2; }
run $P $E/st_lmart.py --run --unit cell --from-era PRE_E1 --search --drop-tf \
    --topk 1 --eras $ER --tag F1_NDCG1
run $P $E/st_lmart.py --run --unit cell --from-era PRE_E1 --search --drop-tf \
    --topk 1 --shuffle --eras $ER --tag F1_NDCG1_SHUF
run $P $E/st_sched.py --tags LMART_HP_NOTF,F1_NDCG1,F1_NDCG1_SHUF --eras $ER \
    --out SEQTEST_FINAL1
run $P $E/st_eratable.py --tag F1_NDCG1 --eras $ER --out SEQTEST_ERATABLE_F1_NDCG1.tsv
run $P $E/st_deficit.py --tag F1_NDCG1 --name E3E7_F1_NDCG1 --use primary --eras $ER
echo "final iteration 1 complete"
