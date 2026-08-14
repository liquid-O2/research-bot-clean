#!/usr/bin/python3
"""PORT M2 — the USED-CASE LEDGER + one-way taint guard (D-035.2, spec §3).

    "one-way taint + used-case ledger (session, side, decision_sec) — the
     ledger is a committed TSV"  (spec §3)
    "(1) ONE-WAY TAINT: a session whose outcomes I have SEEN (study) is
     study-tainted FOREVER and never re-enters any blind set; blind-used
     sessions MAY later be promoted to study (one-way door).  (2) USED-CASE
     LEDGER: every (session, side, decision-second) ever shown is recorded"
                                                                    (D-035)

THE LEDGER (committed to git, not to artifacts/: it is a permanent protocol
record, and D-018's bulk rule is about corpora, not this file)
    provenance/port_m2/USED_CASE_LEDGER.tsv
columns: era, block, asset, trade_date, date8, side, decision_sec, cid,
         candidate_class (D-071.2), mode, round, reader, sheets_version,
         spec_sha16, recorded_at

THE GUARD (the part that has teeth)
  * a STUDY entry taints (asset, date8) FOREVER;
  * `check_blind(entries)` REFUSES any blind draw containing a tainted session
    — the refusal is an exception, never a filter: a draw that silently drops
    its tainted members would hide the protocol violation that produced it;
  * the reverse direction is allowed by design (one-way door): a session used
    BLIND may later be promoted to STUDY, and `record` says so explicitly.
  * a repeated (cid, mode) is refused too — the same case shown twice in the
    same mode is a burn the ledger must not silently absorb (D-035.2 "draws
    exclude prior decision seconds").

RED-FIRST: engine/port_m2/test_panel.py carries the mutant — a guard that
filters instead of refusing lets a study-tainted session into a blind draw and
must FAIL the test.

Run:
  used_cases.py record --era E1 --block STUDY --mode STUDY --round R1 \
                       --reader opus-capacity --cids FILE
  used_cases.py check  --mode BLIND --cids FILE
  used_cases.py tainted
"""
import argparse
import datetime as dt
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import era_index as EI                    # noqa: E402

LEDGER = "/workspace/provenance/port_m2/USED_CASE_LEDGER.tsv"
SECTION = "§3 used-case ledger + one-way taint (D-035.2)"

MODE_STUDY = "STUDY"                      # outcomes seen -> taints the session
MODE_BLIND = "BLIND"                      # call committed before unblinding
MODES = (MODE_STUDY, MODE_BLIND)

COLUMNS = ("era", "block", "asset", "trade_date", "date8", "side",
           "decision_sec", "cid", "candidate_class", "mode", "round", "reader",
           "sheets_version", "spec_sha16", "recorded_at")

PARAMS = {
    "spec_section": SECTION,
    "ledger": LEDGER,
    "taint_rule": "STUDY on (asset, date8) taints that session forever; a "
                  "tainted session may never appear in a BLIND draw; "
                  "BLIND -> STUDY promotion is allowed (one-way door)",
    "dedup_rule": "(cid, mode) is unique — the same case is never shown twice "
                  "in the same mode",
}


class TaintRefusal(RuntimeError):
    """Raised when a draw violates the one-way door.  NEVER caught to filter."""


# ------------------------------------------------------------------- io -----
def read_ledger(path=LEDGER):
    out = []
    if not os.path.exists(path):
        return out
    cols = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            out.append(dict(zip(cols, f)))
    return out


def write_ledger(entries, path=LEDGER):
    """Deterministic rewrite: sorted, fixed columns, LF only."""
    # entries arrive both from make_entries (typed) and from read_ledger
    # (strings); normalise to text first so the sort key is total and the file
    # is byte-identical whichever way an entry got here.
    rows = [[("" if e.get(c) is None else str(e.get(c, ""))) for c in COLUMNS]
            for e in entries]

    def _key(r):
        return (r[2], int(r[4]), int(r[6]), int(r[5]), r[9], r[10])
    rows.sort(key=_key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    MC.write_tsv(path, SECTION, MC.params_hash(PARAMS), list(COLUMNS), rows,
                 extra=["D-035.2 USED-CASE LEDGER — every (session, side, "
                        "decision_sec) ever shown to a reader",
                        "ONE-WAY TAINT: a STUDY row taints (asset, date8) "
                        "forever; that session may never enter a BLIND draw"])
    return path


def tainted_sessions(entries=None):
    """{(asset, date8)} tainted by any STUDY entry."""
    entries = read_ledger() if entries is None else entries
    return {(e["asset"], int(e["date8"])) for e in entries
            if e["mode"] == MODE_STUDY}


def shown(entries=None):
    """{(cid, mode)} already burned."""
    entries = read_ledger() if entries is None else entries
    return {(e["cid"], e["mode"]) for e in entries}


# ---------------------------------------------------------------- guards ----
def check_blind(cids, entries=None):
    """REFUSE a blind draw that touches a study-tainted session.

    Returns the checked list unchanged when the draw is lawful; raises
    TaintRefusal otherwise.  It never returns a FILTERED list — that would turn
    a protocol violation into a silent subsample.
    """
    tainted = tainted_sessions(entries)
    bad = []
    for cid in cids:
        asset, d8, _sec, _side = MC.parse_cid(cid)
        if (asset, d8) in tainted:
            bad.append(cid)
    if bad:
        raise TaintRefusal(
            "D-035 one-way taint: %d candidate(s) sit in STUDY-tainted "
            "sessions and may never enter a blind draw: %s"
            % (len(bad), ", ".join(sorted(bad)[:5])
               + (" ..." if len(bad) > 5 else "")))
    return list(cids)


def check_new(cids, mode, entries=None):
    """Refuse a re-show of the same (cid, mode)."""
    burned = shown(entries)
    dup = [c for c in cids if (c, mode) in burned]
    if dup:
        raise TaintRefusal("used-case ledger: %d candidate(s) already shown in "
                           "%s mode: %s" % (len(dup), mode,
                                            ", ".join(sorted(dup)[:5])))
    return list(cids)


# ---------------------------------------------------------------- record ----
def make_entries(cids, era, block, mode, rnd, reader, recorded_at=None):
    if mode not in MODES:
        raise ValueError("mode %r" % mode)
    at = recorded_at or dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for cid in cids:
        asset, d8, sec, side = MC.parse_cid(cid)
        r = A.roster(asset)
        i = r["_index"].get((d8, sec, side))
        if i is None:
            raise ValueError("candidate %s is not in the v3 roster" % cid)
        cls, _driver, _o = MC.class_of(int(r["fam_mask"][i]))
        out.append({"era": era or MC.era_of(d8), "block": block,
                    "asset": asset, "trade_date": MC.d8_to_date(d8).isoformat(),
                    "date8": d8, "side": side, "decision_sec": sec, "cid": cid,
                    "candidate_class": cls, "mode": mode, "round": rnd,
                    "reader": reader,
                    "sheets_version": MC.SHEETS_VERSION,
                    "spec_sha16": MC.SPEC_SHA16, "recorded_at": at})
    return out


def record(cids, era, block, mode, rnd, reader, recorded_at=None,
           path=LEDGER):
    """Guard, then append.  Refusals happen BEFORE anything is written."""
    entries = read_ledger(path)
    check_new(cids, mode, entries)
    if mode == MODE_BLIND:
        check_blind(cids, entries)        # the one-way door
    new = make_entries(cids, era, block, mode, rnd, reader, recorded_at)
    write_ledger(entries + new, path)
    return new


# --------------------------------------------------- the seal-path hook -----
# CC-M2-17.4 (BINDING): "seal tooling auto-calls used_cases record (the day-5
# gap class dies)".
#
# THE GAP CLASS.  Every E1 study day is sealed by an `e1dN_seal.py` that
# APPENDS the day's calls to provenance/port_m2/E1_STUDY_LEDGER.tsv.  Recording
# those same cids in the USED-CASE LEDGER was a SEPARATE manual step, so the
# day-5 lane sealed 2021-07-07 and never recorded it: a day-complete STUDY
# session sat outside the taint register and could have been drawn BLIND.  It
# was found on day 6 and backfilled by hand (commit 7b822f1).  A step that has
# to be remembered is a step that will be forgotten, so the seal now performs
# it: `record_seal` is called by every seal's main() with the exact cid list it
# just wrote.
#
# WHY THIS ONE IS IDEMPOTENT AND `record` IS NOT.  `record` refuses a repeated
# (cid, mode) because a reader being shown the same case twice is a burn.  A
# SEAL is not a showing — it is a deterministic re-emission of a day that has
# already been read, and re-running it (to regenerate the arms file, to fix a
# column) must not explode and must not double-write.  So `record_seal` splits
# the cids into the already-registered and the new, records only the new, and
# RETURNS BOTH COUNTS so the seal can print them.  It never filters silently:
# the BLIND one-way-door check still runs on the new ones, and a taint refusal
# still raises.
def record_seal(cids, era, block, mode, rnd, reader, recorded_at=None,
                path=LEDGER):
    """Idempotent used-case record for a seal.  -> (new_entries, n_already).

    Raises TaintRefusal exactly as `record` does — a seal that would put a
    study-tainted session into a BLIND block is a protocol violation and stops
    the seal.
    """
    if mode not in MODES:
        raise ValueError("mode %r" % mode)
    seen = []
    for c in cids:                        # order-preserving dedup within call
        if c not in seen:
            seen.append(c)
    entries = read_ledger(path)
    burned = shown(entries)
    fresh = [c for c in seen if (c, mode) not in burned]
    n_already = len(seen) - len(fresh)
    if not fresh:
        return [], n_already
    if mode == MODE_BLIND:
        check_blind(fresh, entries)       # the one-way door, unchanged
    new = make_entries(fresh, era, block, mode, rnd, reader, recorded_at)
    write_ledger(entries + new, path)
    MC.hb("used_cases record_seal: +%d entries (%s/%s/%s), %d already on the "
          "ledger -> %s" % (len(new), era, mode, rnd, n_already, path))
    return new, n_already


# ------------------------------------------------------------------ cli -----
def _cids_from(args):
    if args.cids:
        with open(args.cids) as fh:
            return [ln.strip() for ln in fh
                    if ln.strip() and not ln.startswith("#")]
    if args.era and args.block:
        out = []
        for asset in (args.assets or list(MC.ASSET_ORDER)):
            for r in EI.load_index(args.era, asset):
                if r["block"] == args.block and r["eligible"] == "1":
                    out.append(r["cid"])
        return out
    raise SystemExit("need --cids FILE (or --era/--block to take a whole block)")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("record", "check"):
        q = sub.add_parser(name)
        q.add_argument("--era")
        q.add_argument("--block")
        q.add_argument("--assets", nargs="+")
        q.add_argument("--mode", required=True, choices=MODES)
        q.add_argument("--round", default="")
        q.add_argument("--reader", default="")
        q.add_argument("--cids")
        q.add_argument("--recorded-at", default=None)
    sub.add_parser("tainted")
    a = p.parse_args()
    MC.verify_spec(force=True)
    if a.cmd == "tainted":
        for asset, d8 in sorted(tainted_sessions()):
            sys.stdout.write("%s\t%d\n" % (asset, d8))
        return 0
    cids = _cids_from(a)
    if a.cmd == "check":
        if a.mode == MODE_BLIND:
            check_blind(cids)
        check_new(cids, a.mode)
        MC.hb("used_cases check: %d candidates lawful in %s" % (len(cids),
                                                                a.mode))
        return 0
    new = record(cids, a.era, a.block, a.mode, a.round, a.reader,
                 a.recorded_at)
    MC.hb("used_cases record: +%d entries (%s/%s) -> %s"
          % (len(new), a.mode, a.round, LEDGER))
    return 0


if __name__ == "__main__":
    sys.exit(main())
