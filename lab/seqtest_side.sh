#!/usr/bin/env bash
# SEL_WRONG_SIDE FRONT — under full E8 quarantine.
# Select on inner blocks; evaluate on E3-E7 ONLY; E8 is never scored here.
# One change vs the champion: a SIDE VETO on the candidate POOL (not a re-rank).
set -u
P=/usr/bin/python3; E=/workspace/engine/port_m2/seqtest
ER=E3,E4,E5,E6,E7
run(){ echo "### $*" >&2; "$@" || echo "### FAILED: $*" >&2; }

# the treatment
run $P $E/st_lmart.py --run --unit cell --from-era PRE_E1 --search --drop-tf \
    --side-veto --eras $ER --tag LMART_SIDEVETO
# its own shuffled-label control, same configuration
run $P $E/st_lmart.py --run --unit cell --from-era PRE_E1 --search --drop-tf \
    --side-veto --shuffle --eras $ER --tag LMART_SIDEVETO_SHUFFLED

run $P $E/st_sched.py --tags LMART_HP_NOTF,LMART_SIDEVETO,LMART_SIDEVETO_SHUFFLED \
    --eras $ER --out SEQTEST_SIDE_E3E7
for t in LMART_HP_NOTF LMART_SIDEVETO; do
  run $P $E/st_deficit.py --tag "$t" --name "E3E7_$t" --use primary --eras $ER
done
echo "side front complete"
