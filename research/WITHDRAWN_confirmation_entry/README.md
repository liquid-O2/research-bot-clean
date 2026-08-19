# WITHDRAWN 2026-08-19 — DO NOT RUN
Both scripts carry the side-parser bug (str(side).startswith("B") vs integer
{-1,+1} sides => all trades simulated SHORT) and the M-regression
survivorship filter (M<=0 days silently dropped => short-friendly universe).
Every number they produced is withdrawn (journal ~22:30Z). Kept only as the
incident record. The corrected instrument lives in the max-effort audit's
scratchpad (strat/rebuild_v2.py) and, authoritatively, in the engine chain.
