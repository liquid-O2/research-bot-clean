#!/usr/bin/python3
"""PORT M2 — PANEL SCORER (spec §3 SCORING, gate P-M2b).

    "SCORING: ported panel_score — lift = mean(cert of takes)/mean(cert of
     skips), winner precision, one-position chronological replay capture;
     mechanical, the only judge."

This is the port of artifacts/cache/campaign/diagnostics/d020_v3/panel_score.py
onto the port substrate: outcomes come from the FROZEN v3 roster
(ORACLE_FREEZE) through c_c_roster.certificates, never from a re-derivation.

WHAT IT COMPUTES (all three, per era, per block, per asset and pooled)
  1. LIFT, on BOTH CC-M1-8 readings — the adoption metric (phase-close walled
     certificate) and its mandatory companion (peak-exit walled certificate):
         lift = mean(cert of TAKEs) / mean(cert of SKIPs)
     Both means are always reported; the ratio is reported only when the SKIP
     mean is positive (a non-positive denominator makes the ratio meaningless,
     never "infinite skill").
  2. WINNER PRECISION = share of TAKEs that are winners, where a winner clears
     the user's bar: cert >= $1,000 (D-021) AND MAE before the peak <= $300
     (D-021's MAE acceptance at that expectancy) AND the $900 wall was never
     hit (a walled candidate is a stop-out, never a winner).  Reported with the
     complementary "winners missed in SKIPs" count — the port's version of the
     old scorer's `winners missed` line.
  3. ONE-POSITION CHRONOLOGICAL REPLAY (D-046/D-036): within a session the
     TAKEs are replayed in decision order with ONE position; a TAKE whose
     decision second is not strictly after the open position's exit second is
     FORFEITED (recorded, not silently dropped).  The realised total is scored
     against the session's DP CEILING — c_c_roster.dp_schedule over EVERY
     candidate of that session — so capture = realised / ceiling.

LEDGER FORMAT (spec §3)
    `id TAKE|SKIP A|B|C evidence{primary: field+value+read, against,
     interaction, novel}`
Two spellings are accepted, both parsed by `parse_ledger`:
  * TSV with a header naming any of cid/call/conf/primary/against/interaction/
    novel (extra columns are carried through untouched);
  * the inline form `cid TAKE A primary: ...; against: ...; novel: ...`.
D-068-CORRECTION: the INTERACTION FIELD IS OPTIONAL.  A single-signal thesis is
a fully valid entry — the parser records `has_interaction` for reporting and
NEVER rejects a call for missing one.  Only `primary` is required (an evidence-
free call is not a thesis).

Run:
  /usr/bin/python3 engine/port_m2/panel_score.py CALLS.tsv [--out DIR]
                                                 [--label NAME]
"""
import argparse
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import c_c_roster as CC                   # noqa: E402
import common as C                        # noqa: E402

SECTION = "§3 SCORING (P-M2b panel_score port)"

CALL_TAKE = "TAKE"
CALL_SKIP = "SKIP"
CALLS = (CALL_TAKE, CALL_SKIP)
CONFS = ("A", "B", "C")

# D-021: the winner bar the program is judged against.
WINNER_CERT_USD = 1000.0
WINNER_MAE_USD = 300.0

EVIDENCE_FIELDS = ("primary", "against", "interaction", "novel")
_INLINE = re.compile(r"^(?P<cid>\S+)\s+(?P<call>TAKE|SKIP)\s+"
                     r"(?P<conf>[ABC])\b\s*(?P<ev>.*)$", re.IGNORECASE)

PARAMS = {
    "spec_section": SECTION,
    "lift": "mean(cert of TAKEs)/mean(cert of SKIPs), both CC-M1-8 readings "
            "(phase-close = adoption, peak-exit = companion)",
    "winner": "cert >= $%.0f AND mae_before_argmax <= $%.0f AND not walled"
              % (WINNER_CERT_USD, WINNER_MAE_USD),
    "replay": "one position, chronological within a session, exit at the "
              "certificate's exit second; ceiling = c_c_roster.dp_schedule "
              "over every candidate of the session",
    "interaction_field": "OPTIONAL (D-068-CORRECTION); single-signal theses "
                         "are valid ledger entries",
    "outcomes": "m1/generation_v3 union roster (ORACLE_FREEZE) via "
                "c_c_roster.certificates(wall, cost_rt)",
}


# ------------------------------------------------------------------ parse ---
class LedgerError(ValueError):
    """A malformed ledger line.  Reported with its line number, never skipped
    silently: an unparsed call is a missing call, which changes the score."""


def _split_evidence(text):
    """`primary: ... ; against: ... ; interaction: ... ; novel: ...`"""
    ev = {k: "" for k in EVIDENCE_FIELDS}
    if not text:
        return ev
    t = text.strip()
    if t.startswith("evidence"):
        t = t[len("evidence"):].strip()
    if t.startswith("{") and t.endswith("}"):
        t = t[1:-1]
    # split on the field keywords themselves, so free text may contain ';'
    keys = [(m.start(), m.group(1).lower())
            for m in re.finditer(r"(?i)\b(primary|against|interaction|novel)\s*:",
                                 t)]
    if not keys:
        ev["primary"] = t.strip(" ;|")
        return ev
    for j, (pos, key) in enumerate(keys):
        end = keys[j + 1][0] if j + 1 < len(keys) else len(t)
        val = t[pos:end]
        val = val.split(":", 1)[1] if ":" in val else ""
        ev[key] = val.strip(" ;|\t")
    return ev


def parse_ledger(path):
    """-> [dict(cid, call, conf, primary, against, interaction, novel, line)]"""
    out = []
    cols = None
    with open(path) as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            low = [f.strip().lower() for f in fields]
            if cols is None and "\t" in line and (
                    "cid" in low or "id" in low or "case_id" in low):
                cols = low
                continue
            rec = None
            if cols is not None and "\t" in line:
                d = dict(zip(cols, [f.strip() for f in fields]))
                rec = {"cid": d.get("cid") or d.get("id") or d.get("case_id"),
                       "call": (d.get("call") or "").upper(),
                       "conf": (d.get("conf") or d.get("confidence")
                                or "").upper()}
                for k in EVIDENCE_FIELDS:
                    rec[k] = d.get(k, "")
                if not rec[EVIDENCE_FIELDS[0]] and d.get("evidence"):
                    rec.update(_split_evidence(d["evidence"]))
            else:
                m = _INLINE.match(line.strip())
                if m:
                    rec = {"cid": m.group("cid"), "call": m.group("call").upper(),
                           "conf": m.group("conf").upper()}
                    rec.update(_split_evidence(m.group("ev")))
            if rec is None or not rec.get("cid"):
                raise LedgerError("%s:%d unparseable ledger line: %r"
                                  % (path, lineno, line[:120]))
            if rec["call"] not in CALLS:
                raise LedgerError("%s:%d call must be TAKE or SKIP, got %r"
                                  % (path, lineno, rec["call"]))
            if rec["conf"] not in CONFS:
                raise LedgerError("%s:%d confidence must be A/B/C, got %r"
                                  % (path, lineno, rec["conf"]))
            if not rec["primary"].strip():
                raise LedgerError("%s:%d evidence.primary is required "
                                  "(interaction is NOT — D-068-CORRECTION)"
                                  % (path, lineno))
            MC.parse_cid(rec["cid"])       # raises on a malformed id
            rec["line"] = lineno
            rec["has_interaction"] = 1 if rec["interaction"].strip() else 0
            out.append(rec)
    seen = set()
    for r in out:
        if r["cid"] in seen:
            raise LedgerError("%s: duplicate call for %s (line %d)"
                              % (path, r["cid"], r["line"]))
        seen.add(r["cid"])
    return out


# --------------------------------------------------------------- outcomes ---
_OUT = {}


def outcome(cid):
    """Both CC-M1-8 certificates + the winner inputs for one candidate."""
    if cid in _OUT:
        return _OUT[cid]
    asset, d8, ds, side = MC.parse_cid(cid)
    r = A.roster(asset)
    i = r["_index"][(d8, ds, side)]
    date = MC.d8_to_date(d8)
    cost = A.cost_map().get((asset, date.isoformat()), float("nan"))
    cost = float(cost) if np.isfinite(cost) else C.FEES_RT
    wall = float(A.walls()[asset]["wall_usd"])
    peak, close = CC.certificates(r, i, wall, cost)
    t_wall, mfe_w, argmax_sec, walled = CC._skel_query(r, i, wall)
    o = {"cid": cid, "asset": asset, "date8": d8, "trade_date": date,
         "dec_sec": ds, "side": side, "row": int(i),
         "era": MC.era_of(d8),
         "cert_close_usd": float(close[0]), "exit_close_sec": int(close[2]),
         "cert_peak_usd": float(peak[0]), "exit_peak_sec": int(peak[2]),
         "peak_seated": int(bool(peak[3])),
         "mae_before_argmax": float(r["mae_before_argmax"][i]),
         "walled": int(bool(walled)), "wall_usd": wall, "cost_rt": cost}
    for m, cert in (("close", o["cert_close_usd"]), ("peak", o["cert_peak_usd"])):
        o["winner_" + m] = int(cert >= WINNER_CERT_USD
                               and o["mae_before_argmax"] <= WINNER_MAE_USD
                               and not o["walled"])
    _OUT[cid] = o
    return o


def dp_ceiling(asset, d8, metric="close"):
    """The one-position DP ceiling over EVERY candidate of the session."""
    key = ("dp", asset, int(d8), metric)
    if key in _OUT:
        return _OUT[key]
    r = A.roster(asset)
    date = MC.d8_to_date(int(d8))
    cost = A.cost_map().get((asset, date.isoformat()), float("nan"))
    cost = float(cost) if np.isfinite(cost) else C.FEES_RT
    wall = float(A.walls()[asset]["wall_usd"])
    idx = np.nonzero(r["date8"] == int(d8))[0]
    items = []
    for i in idx.tolist():
        peak, close = CC.certificates(r, i, wall, cost)
        val, dec, exit_sec, _ = close if metric == "close" else peak
        items.append((dec, exit_sec, val, dec, int(r["iid"][i]), i))
    total, chosen = CC.dp_schedule(items)
    _OUT[key] = (float(total), len(chosen), len(idx))
    return _OUT[key]


# ---------------------------------------------------------------- scoring ---
def replay(records, metric="close"):
    """One-position chronological replay of the TAKEs, per session.

    -> (per-session rows, totals).  A TAKE that cannot be seated (the position
    from an earlier TAKE is still open) is FORFEITED and counted.
    """
    by = {}
    for rec in records:
        if rec["call"] != CALL_TAKE:
            continue
        o = rec["outcome"]
        by.setdefault((o["asset"], o["date8"]), []).append(o)
    rows = []
    for (asset, d8) in sorted(by):
        seq = sorted(by[(asset, d8)], key=lambda o: (o["dec_sec"], -o["side"]))
        open_until = -1
        realised = 0.0
        n_seat = n_forfeit = 0
        for o in seq:
            if o["dec_sec"] <= open_until:
                n_forfeit += 1
                continue
            cert = o["cert_close_usd"] if metric == "close" else o["cert_peak_usd"]
            exit_sec = (o["exit_close_sec"] if metric == "close"
                        else o["exit_peak_sec"])
            realised += cert
            open_until = exit_sec
            n_seat += 1
        ceiling, n_dp, n_cand = dp_ceiling(asset, d8, metric)
        rows.append({"asset": asset, "date8": d8, "era": MC.era_of(d8),
                     "n_takes": len(seq), "n_seated": n_seat,
                     "n_forfeited": n_forfeit, "realised_usd": realised,
                     "dp_ceiling_usd": ceiling, "dp_n_seated": n_dp,
                     "n_candidates": n_cand,
                     "capture": (realised / ceiling) if ceiling > 0 else None})
    tot_r = sum(x["realised_usd"] for x in rows)
    tot_c = sum(x["dp_ceiling_usd"] for x in rows)
    totals = {"n_sessions": len(rows),
              "realised_usd": tot_r, "dp_ceiling_usd": tot_c,
              "capture": (tot_r / tot_c) if tot_c > 0 else None,
              "realised_per_session": (tot_r / len(rows)) if rows else 0.0,
              "n_seated": sum(x["n_seated"] for x in rows),
              "n_forfeited": sum(x["n_forfeited"] for x in rows)}
    return rows, totals


def _mean(v):
    return float(np.mean(v)) if len(v) else None


def score_group(records):
    """The three metrics over one group of scored records."""
    takes = [r["outcome"] for r in records if r["call"] == CALL_TAKE]
    skips = [r["outcome"] for r in records if r["call"] == CALL_SKIP]
    out = {"n_calls": len(records), "n_takes": len(takes), "n_skips": len(skips),
           "take_rate": (len(takes) / len(records)) if records else None,
           "n_with_interaction": sum(r["has_interaction"] for r in records)}
    for m in ("close", "peak"):
        k = "cert_%s_usd" % m
        t = [o[k] for o in takes]
        s = [o[k] for o in skips]
        mt, ms = _mean(t), _mean(s)
        out["mean_take_%s_usd" % m] = mt
        out["mean_skip_%s_usd" % m] = ms
        # a ratio against a non-positive denominator is not a lift
        out["lift_%s" % m] = (mt / ms) if (ms is not None and ms > 0
                                           and mt is not None) else None
        nw = sum(o["winner_" + m] for o in takes)
        out["n_winner_takes_%s" % m] = nw
        out["winner_precision_%s" % m] = (nw / len(takes)) if takes else None
        out["n_winners_missed_in_skips_%s" % m] = sum(o["winner_" + m]
                                                      for o in skips)
        out["worst_take_mae_usd"] = (max((o["mae_before_argmax"] for o in takes),
                                         default=0.0))
        out["n_walled_takes"] = sum(o["walled"] for o in takes)
    for m in ("close", "peak"):
        _, tot = replay(records, m)
        out["replay_%s" % m] = tot
    return out


def score(records):
    """Attach outcomes, then score pooled / per era / per block / per asset."""
    for rec in records:
        rec["outcome"] = outcome(rec["cid"])
        rec["era"] = rec["outcome"]["era"]
        rec["asset"] = rec["outcome"]["asset"]
    groups = {"POOLED": records}
    for key in ("era", "asset"):
        for rec in records:
            groups.setdefault("%s=%s" % (key, rec[key]), []).append(rec)
    if any(r.get("block") for r in records):
        for rec in records:
            groups.setdefault("block=%s" % rec.get("block", "?"), []).append(rec)
    return {g: score_group(rs) for g, rs in sorted(groups.items())}


# ----------------------------------------------------------------- output ---
CALL_COLUMNS = ("cid", "asset", "era", "trade_date", "dec_sec", "side", "call",
                "conf", "has_interaction", "cert_close_usd", "cert_peak_usd",
                "mae_before_argmax", "walled", "winner_close", "winner_peak",
                "primary", "against", "interaction", "novel")


def write_report(records, groups, out_dir, label):
    phash = MC.params_hash(PARAMS)
    rows = []
    for r in sorted(records, key=lambda r: (r["asset"], r["outcome"]["date8"],
                                            r["outcome"]["dec_sec"])):
        o = r["outcome"]
        rows.append([r["cid"], o["asset"], o["era"], o["trade_date"].isoformat(),
                     o["dec_sec"], o["side"], r["call"], r["conf"],
                     r["has_interaction"], o["cert_close_usd"],
                     o["cert_peak_usd"], o["mae_before_argmax"], o["walled"],
                     o["winner_close"], o["winner_peak"],
                     r["primary"], r["against"], r["interaction"], r["novel"]])
    MC.write_tsv(os.path.join(out_dir, "PANEL_CALLS_%s.tsv" % label), SECTION,
                 phash, list(CALL_COLUMNS), rows,
                 extra=["one row per scored call; certificates from the frozen "
                        "v3 roster via c_c_roster.certificates"])
    srows = []
    for g in sorted(groups):
        s = groups[g]
        srows.append([g, s["n_calls"], s["n_takes"], s["n_skips"],
                      s["n_with_interaction"],
                      s["mean_take_close_usd"], s["mean_skip_close_usd"],
                      s["lift_close"], s["winner_precision_close"],
                      s["n_winners_missed_in_skips_close"],
                      s["mean_take_peak_usd"], s["mean_skip_peak_usd"],
                      s["lift_peak"], s["winner_precision_peak"],
                      s["replay_close"]["realised_usd"],
                      s["replay_close"]["dp_ceiling_usd"],
                      s["replay_close"]["capture"],
                      s["replay_close"]["realised_per_session"],
                      s["replay_close"]["n_forfeited"]])
    MC.write_tsv(os.path.join(out_dir, "PANEL_SCORE_%s.tsv" % label), SECTION,
                 phash,
                 ["group", "n_calls", "n_takes", "n_skips", "n_with_interaction",
                  "mean_take_close_usd", "mean_skip_close_usd", "lift_close",
                  "winner_precision_close", "winners_missed_in_skips_close",
                  "mean_take_peak_usd", "mean_skip_peak_usd", "lift_peak",
                  "winner_precision_peak", "replay_realised_usd",
                  "replay_dp_ceiling_usd", "replay_capture",
                  "replay_usd_per_session", "replay_forfeited"], srows,
                 extra=["CC-M1-8: close = adoption metric, peak = companion"])
    MC.write_json(os.path.join(out_dir, "panel_score_%s.receipt.json" % label),
                  {"env": MC.env_receipt(PARAMS), "label": label,
                   "n_calls": len(records), "groups": groups})
    return groups


def render_table(groups):
    L = ["group                 calls  take  skip | mean_take$ mean_skip$  lift"
         " | winprec | replay$   dp$    capture"]
    for g in sorted(groups):
        s = groups[g]
        r = s["replay_close"]
        L.append("%-20s %6d %5d %5d | %10.0f %10.0f %5s | %6s  | %8.0f %8.0f %7s"
                 % (g[:20], s["n_calls"], s["n_takes"], s["n_skips"],
                    s["mean_take_close_usd"] or 0.0,
                    s["mean_skip_close_usd"] or 0.0,
                    "%.2f" % s["lift_close"] if s["lift_close"] else "NA",
                    "%.2f" % s["winner_precision_close"]
                    if s["winner_precision_close"] is not None else "NA",
                    r["realised_usd"], r["dp_ceiling_usd"],
                    "%.3f" % r["capture"] if r["capture"] is not None else "NA"))
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ledger")
    p.add_argument("--out", default=MC.out_path("panel", "_")[:-1])
    p.add_argument("--label", default=None)
    a = p.parse_args()
    MC.verify_spec(force=True)
    label = a.label or os.path.basename(a.ledger).split(".")[0]
    records = parse_ledger(a.ledger)
    groups = score(records)
    write_report(records, groups, a.out, label)
    sys.stdout.write(render_table(groups) + "\n")
    MC.hb("panel_score %s: %d calls scored -> %s" % (label, len(records), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
