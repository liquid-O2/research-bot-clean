#!/usr/bin/python3
"""PORT M2 — THE OBSERVED-CLOSE TABLE (D15 / V1.2, the D-001 fix pass).

D15 (CC-M2-12.2) established that the NOMINAL session close is wrong by HOURS
on early-close sessions — HG 2021-07-05's tape stops at 71,354s while every
sheet computes its runway to 82,799s — and `runway_observed` was added to the
triage index for exactly this.  But the OBSERVED close is an end-of-session
fact: `triage_index.py:165-166` correctly masks it under `--as-of`, and the
sheet may never print it.  The V1.2 item was queued and never landed, and
`runway_to_seat` is now the program's central conditioning object (CC-M2-15.1)
with P025/P033 measured on it.

WHAT IS KNOWABLE.  Not this session's observed close — but the DISTRIBUTION of
the shortfall on this asset's STRICTLY PRIOR sessions is.  A reader at 03:00
cannot know when today's tape will stop; it can know that on this asset's last
20 sessions the tape stopped a median of N seconds before the scheduled close.
That is what the sheet prints, and it is computed here once so the render does
not pay 20 session loads per candidate.

Output (one file per asset, deterministic, no wall clock):
  artifacts/cache/port/m2/session_close/OBSERVED_CLOSE_<ASSET>.tsv
    date8  scheduled_close_sec  observed_close_sec  shortfall_sec

Run:
  lab/run.sh port-m2-fixpass-close -- /usr/bin/python3 \
      engine/port_m2/session_close.py
"""
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import census_common as X                 # noqa: E402

SECTION = "§1 S3 runway (D15 / V1.2 observed-close shortfall)"
OUT_DIR = os.path.join(MC.M2_ROOT, "session_close")
COLUMNS = ("date8", "scheduled_close_sec", "observed_close_sec",
           "shortfall_sec")
TRAILING = 20                             # sessions in the trailing window
MIN_TRAILING = 5                          # below this the field is REFUSED

_CACHE = {}


def path_for(asset):
    return os.path.join(OUT_DIR, "OBSERVED_CLOSE_%s.tsv" % asset)


def build(asset):
    """[(d8, scheduled_close_sec, observed_close_sec, shortfall_sec)]."""
    rows = []
    for trade_date, p in X.session_paths(asset, MC.M0_ROOT):
        d8 = MC.d8(trade_date)
        try:
            z = np.load(p, allow_pickle=False)
            meta = json.loads(str(z["meta_json"]))
        except Exception:                 # noqa: BLE001 — recorded, not hidden
            continue
        sched = meta.get("close_utc")
        opn = meta.get("open_utc")
        obs = meta.get("last_two_sided_sec")
        if sched is None or opn is None or obs is None:
            continue
        sc = int(sched) - int(opn)        # scheduled close, in session seconds
        ob = int(obs)
        rows.append([int(d8), sc, ob, sc - ob])
    rows.sort()
    return rows


def load(asset):
    """{d8: shortfall_sec}, cached per process.  {} when the table is absent —
    the sheet then REFUSES the field rather than substituting a nominal."""
    if asset in _CACHE:
        return _CACHE[asset]
    out = {}
    p = path_for(asset)
    if os.path.exists(p):
        with open(p) as fh:
            cols = None
            for line in fh:
                if line.startswith("#"):
                    continue
                f = line.rstrip("\n").split("\t")
                if cols is None:
                    cols = f
                    continue
                out[int(f[0])] = int(f[3])
    _CACHE[asset] = out
    return out


def trailing_shortfall(asset, d8, n=TRAILING):
    """(median shortfall over the n sessions STRICTLY BEFORE d8, n_used).

    Strictly prior: the session being rendered contributes nothing to its own
    expectation.  Returns (nan, n_used) below MIN_TRAILING."""
    tbl = load(asset)
    if not tbl:
        return float("nan"), 0
    prior = sorted(k for k in tbl if k < int(d8))[-int(n):]
    if len(prior) < MIN_TRAILING:
        return float("nan"), len(prior)
    return float(np.median([tbl[k] for k in prior])), len(prior)


def main():
    MC.verify_spec(force=True)
    tot = 0
    for asset in MC.ASSET_ORDER:
        rows = build(asset)
        tot += len(rows)
        MC.write_tsv(path_for(asset), SECTION,
                     MC.params_hash({"trailing": TRAILING,
                                     "min_trailing": MIN_TRAILING}),
                     list(COLUMNS), rows,
                     extra=["shortfall_sec = scheduled_close_sec - "
                            "observed_close_sec (m0 meta last_two_sided_sec); "
                            "an END-OF-SESSION fact, used ONLY through a "
                            "STRICTLY-PRIOR trailing window"])
        MC.hb("session_close %s: %d sessions" % (asset, len(rows)))
    MC.write_json(os.path.join(OUT_DIR, "session_close.receipt.json"),
                  {"env": MC.env_receipt({"trailing": TRAILING}),
                   "n_sessions": tot, "assets": list(MC.ASSET_ORDER)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
