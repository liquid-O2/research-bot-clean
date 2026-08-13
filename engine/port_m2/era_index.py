#!/usr/bin/python3
"""PORT M2 — the PER-ERA CANDIDATE INDEX (spec §3 era/block definitions, D-058).

Gate P-M2b builds the reader's era material.  The index is the COMPLETE,
day-complete enumeration of every v3-roster candidate an era owns, split into
its STUDY and BLIND blocks — it is what makes "no silent subsampling" checkable:
the index is the population, and any render is a receipted subset of it.

BLOCK LAW (spec §3 / D-058 / D-036)
  STUDY = the first ~60% of the era's SESSIONS in chronological order;
  BLIND = the remainder.  Blocks are DAY-COMPLETE: the boundary is a DATE, so a
  session is wholly in one block, and every candidate of an in-block session is
  in the block.  The boundary is computed on the UNION of the three assets'
  session dates, so all three books share one boundary date per era (the reader
  works days, not per-asset calendars, and the taint ledger has one clock).

ELIGIBILITY (identical to the pilot's, spec §4)
  era in E1..E8 (PRE_E1, the 2025H2 holdout and the 2026 seal are excluded) and
  the session must carry its m0 session receipt, its levels_v4 receipt and its
  profile receipt — a candidate whose sheet cannot render is listed with
  eligible=0 rather than dropped, so the index stays a census of the roster.

Output (D-018, under artifacts/cache/port/m2/era/{ERA}/)
  INDEX_{ASSET}.tsv   one row per candidate
  BLOCKS.tsv          one row per (era, asset, block): sessions, dates, counts
  era_index.receipt.json

Run: lab/run.sh port-m2b -- /usr/bin/python3 engine/port_m2/era_index.py E1 E2
"""
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import census_common as X                 # noqa: E402
import assemble as A                      # noqa: E402

SECTION = "§3 era/block definitions (P-M2b index)"
STUDY_FRACTION = 0.60                     # spec §3 "first ~60% of sessions"
BLOCK_STUDY = "STUDY"
BLOCK_BLIND = "BLIND"

PARAMS = {
    "spec_section": SECTION,
    "study_fraction": STUDY_FRACTION,
    "block_rule": "boundary = the ceil(0.60 * n_union_sessions)-th session DATE "
                  "of the era over the UNION of asset session dates; STUDY = "
                  "date <= boundary, BLIND = date > boundary (day-complete)",
    "eligible": "era in E1..E8; m0 session + levels_v4 + profiles receipts "
                "present for the session",
    "population": "every row of m1/generation_v3/union_roster_{ASSET}.npz "
                  "(the ORACLE_FREEZE v3 roster) — nothing is sampled away",
}


def era_dir(era):
    return MC.out_path("era", era, "_")[:-1]


def primary_family(fam_mask):
    """The stratum family = the RAREST tag the candidate carries (the pilot's
    convention, pilot.primary_family — MC.FAMILIES is ordered core-first)."""
    out = "NONE"
    for f in MC.FAMILIES:
        if int(fam_mask) & MC.FAM_BIT[f]:
            out = f
    return out


def era_bounds(era):
    for name, lo, hi in MC.ERAS:
        if name == era:
            return lo, hi
    raise ValueError("unknown era %r (protocol eras are %s)"
                     % (era, [e[0] for e in MC.ERAS]))


def session_dates(asset, era):
    """The asset's roster session dates inside the era, chronological."""
    lo, hi = era_bounds(era)
    d8 = A.roster(asset)["date8"]
    m = (d8 >= lo) & (d8 <= hi)
    return sorted({int(x) for x in d8[m].tolist()})


def boundary_date(era, assets=MC.ASSET_ORDER):
    """The last STUDY date of the era (shared by every asset)."""
    union = sorted({d for a in assets for d in session_dates(a, era)})
    if not union:
        return None, []
    k = int(np.ceil(len(union) * STUDY_FRACTION))
    k = max(1, min(k, len(union)))
    return union[k - 1], union


def receipts_present(asset, d8):
    return (os.path.exists(os.path.join(A.LEVELS_DIR, asset, "%08d.npz" % d8))
            and os.path.exists(os.path.join(A.PROFILES_DIR, asset,
                                            "%08d.npz" % d8))
            and int(d8) in A.session_index(asset))


COLUMNS = ("cid", "asset", "era", "block", "date8", "trade_date", "dec_sec",
           "side", "eligible", "phase_dec", "phase_conf", "conf_sec",
           "primary_family", "families", "rungs", "level_families", "flags",
           "entry_mid", "atr14_usd", "spread_at_decision", "dom_share",
           "phase_close_sec", "sess_close_sec")


def index_rows(asset, era, bdate):
    """Every roster candidate of (asset, era), sorted (date8, dec_sec, side)."""
    lo, hi = era_bounds(era)
    r = A.roster(asset)
    d8 = r["date8"]
    m = np.nonzero((d8 >= lo) & (d8 <= hi))[0]
    order = m[np.lexsort((r["side"][m], r["dec_sec"][m], r["date8"][m]))]
    ok = {}
    rows = []
    for i in order.tolist():
        d = int(d8[i])
        if d not in ok:
            ok[d] = receipts_present(asset, d)
        ds = int(r["dec_sec"][i])
        side = int(r["side"][i])
        rows.append([
            MC.make_cid(asset, d, ds, side), asset, era,
            BLOCK_STUDY if d <= bdate else BLOCK_BLIND,
            d, MC.d8_to_date(d).isoformat(), ds, side, 1 if ok[d] else 0,
            X.PHASE_NAMES[int(r["phase_dec"][i])],
            X.PHASE_NAMES[int(r["phase_conf"][i])],
            int(r["conf_sec"][i]),
            primary_family(int(r["fam_mask"][i])),
            ",".join(MC.fam_names(int(r["fam_mask"][i]))),
            ",".join(MC.rung_names(int(r["rung_mask"][i]))),
            ",".join(MC.level_fam_names(int(r["level_fam_mask"][i]))) or "none",
            ",".join(MC.bits_to_names(int(r["flags"][i]), MC.FLAG_NAMES))
            or "none",
            float(r["entry_mid"][i]), float(r["atr14_usd"][i]),
            float(r["spread_at_decision"][i]), float(r["dom_share"][i]),
            int(r["phase_close_sec"][i]), int(r["sess_close_sec"][i])])
    return rows


def build(eras, assets=MC.ASSET_ORDER):
    MC.verify_spec()
    phash = MC.params_hash(PARAMS)
    blocks = []
    totals = {}
    for era in eras:
        bdate, union = boundary_date(era, assets)
        out = era_dir(era)
        for asset in assets:
            rows = index_rows(asset, era, bdate)
            MC.write_tsv(os.path.join(out, "INDEX_%s.tsv" % asset), SECTION,
                         phash, list(COLUMNS), rows,
                         extra=["era=%s boundary_date=%s (STUDY <= boundary)"
                                % (era, bdate),
                                "COMPLETE population of the v3 roster for this "
                                "era — no sampling, no filtering"])
            for blk in (BLOCK_STUDY, BLOCK_BLIND):
                sel = [r for r in rows if r[3] == blk]
                el = [r for r in sel if r[8] == 1]
                ds = sorted({r[4] for r in sel})
                dse = sorted({r[4] for r in el})
                blocks.append([era, asset, blk, len(ds), len(dse), len(sel),
                               len(el),
                               min(ds) if ds else None, max(ds) if ds else None,
                               bdate])
                totals[(era, blk)] = totals.get((era, blk), 0) + len(el)
            MC.hb("era_index %s %s: %d candidates" % (era, asset, len(rows)))
    MC.write_tsv(MC.out_path("era", "BLOCKS.tsv"), SECTION, phash,
                 ["era", "asset", "block", "n_sessions", "n_sessions_eligible",
                  "n_candidates", "n_candidates_eligible", "first_date8",
                  "last_date8", "boundary_date8"], blocks,
                 extra=["block boundary is a DATE shared by all assets "
                        "(day-complete, D-036)"])
    receipt = {"env": MC.env_receipt(PARAMS), "eras": list(eras),
               "assets": list(assets),
               "totals_eligible_by_block":
                   {"%s/%s" % k: v for k, v in sorted(totals.items())},
               "out_root": MC.out_path("era", "_")[:-1]}
    MC.write_json(MC.out_path("era", "era_index.receipt.json"), receipt)
    return blocks, totals


def load_index(era, asset):
    """[dict] rows of INDEX_{ASSET}.tsv (the renderer's work list)."""
    path = os.path.join(era_dir(era), "INDEX_%s.tsv" % asset)
    out = []
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


def main():
    eras = [a for a in sys.argv[1:] if not a.startswith("-")] or ["E1", "E2"]
    t0 = time.time()
    blocks, totals = build(eras)
    for k in sorted(totals):
        MC.hb("era_index total %s/%s eligible candidates = %d"
              % (k[0], k[1], totals[k]))
    MC.hb("era_index: %d block rows, %.1fs" % (len(blocks), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
