#!/usr/bin/python3
"""E1D2 lawful retrieval wrapper.

retrieve.py's own docstring names the hazard: a STUDY row means "this case
belongs to a study block", and a round may register its rows BEFORE its S14s
are opened (E1D2 did exactly that, as E1D1 did).  The ledger cannot tell the
two states apart, so the round driver must.  This wrapper drops every
2021-07-02 row from the pool, i.e. retrieval sees ONLY history whose outcomes
the reader has already been shown (the warm-up 24 + day 1's 1,039).
"""
import sys
sys.path.insert(0, "/workspace/engine/port_m2")
import used_cases as UC
import retrieve as R

TODAY = 20210702


def main():
    cid = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    entries = UC.read_ledger()
    pool = [e["cid"] for e in entries
            if e.get("mode") == UC.MODE_STUDY and int(e["date8"]) != TODAY]
    q, hits, sc, meta = R.retrieve(cid, k, entries=entries, pool=pool)
    sys.stdout.write(R.table(q, hits, k, meta))


main()
