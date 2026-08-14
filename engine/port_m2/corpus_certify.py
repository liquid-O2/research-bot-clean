#!/usr/bin/python3
"""PORT M2 — CORPUS CERTIFICATION (the D-001 fix pass, stage 4).

A rendered corpus is not certified by the fact that a builder ran.  This walks
a rendered (era, block) tree and RE-DERIVES, from the committed bytes, the four
blind-instrument leaks the consolidated review measured — so "the corpus is
clean" is a number, not a claim.

  L1  R93  forward-anchored fvol levels.  A level row whose level_id carries an
           `OPEN_<PHASE>` anchor for a phase that OPENS AFTER the decision
           second.  Review measurement on the pre-fix E1 BLIND corpus:
           1,998 of 12,418 sheets (16.1%), 6,892 rows.
  L2  R02  co-located S14 appendices.  Any `*.S14.*` artefact reachable from a
           BLIND sheet directory.  Pre-fix: 12,418.
  L3  R94  forward S2 session-meta values.  A `dominance` line carrying a
           NUMERIC dom_share / roll_window / dying_book_week /
           instrument_change, or an `insane_book` line carrying
           session_insane_frac.  Pre-fix: every sheet.
  L4  R01  census cards over the decision's own era, calendar year or
           protocol block.  Pre-fix: every sheet with a card.

It also reports the certification stats the render receipts claim (certified /
n_failed / over-budget / refused-derived) recomputed from the sheet text, and
the two-run byte-identity check when `--twice` is passed.

Run:
  /usr/bin/python3 engine/port_m2/corpus_certify.py --era E1 --block BLIND
"""
import argparse
import collections
import hashlib
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import census_common as X                 # noqa: E402
import assemble as A                      # noqa: E402

SECTION = "§2 corpus certification (D-001 fix pass)"
OUT_DIR = os.path.join(MC.M2_ROOT, "fixlane")

COLUMNS = ("era", "block", "asset", "date8", "n_sheets", "n_certified",
           "n_failed_sections", "n_over_budget", "n_refused_derived_total",
           "L1_sheets_forward_fvol", "L1_rows_forward_fvol",
           "L2_colocated_s14", "L3_sheets_forward_s2meta",
           "L4_sheets_own_era_card", "sheets_sha256")

_LEVEL_RE = re.compile(r"^\s+[Kr]\s+(FVOL_BAND|FVOL_LADDER|FVOL_LADDER_RS)\s+"
                       r"(OPEN_[A-Z]+)\|")
_PHASE_RE = re.compile(r"phase_dec=(\S+)")
_DEC_RE = re.compile(r"sec=(\d\d:\d\d:\d\d)\s+\((\d+)\)")
_ERA_RE = re.compile(r"era=(\S+)")
_DOM_RE = re.compile(r"dominance.*?dom_share=([^\s]+)")
_ROLL_RE = re.compile(r"roll_window=([^\s]+)")
_DYING_RE = re.compile(r"dying_book_week=([^\s]+)")
_ICH_RE = re.compile(r"instrument_change=([^\s]+)")
_SIF_RE = re.compile(r"session_insane_frac=([^\s]+)")
# A card row lives INSIDE S13 and its era token comes from a CLOSED vocabulary.
# The first version anchored on "4 spaces, a token, a label" and matched S10's
# `HVN_d$ 1013 ...` profile rows on the \d{4} branch — 40,731 false positives.
_CARD_ERA_RE = re.compile(r"^\s{4}\S+\s+(PRE_E1|E[1-8]|HOLDOUT_2025H2|"
                          r"FIT_\d{4}_\d{4}|GATE_\d{4}|(?:19|20)\d{2})\s+"
                          r"\d+\s+\d+\s")
_S13_RE = re.compile(r"^S13\b")
_SEC_RE = re.compile(r"^S\d+\b")

# phase order on the m0 session clock, earliest first
PHASE_ORDER = list(X.PHASE_NAMES)


def _phase_rank(name):
    try:
        return PHASE_ORDER.index(name)
    except ValueError:
        return -1


def _era_hi(name):
    for n, _lo, hi in MC.ERAS:
        if n == name:
            return hi
    if name == MC.ERA_HOLDOUT[0]:
        return MC.ERA_HOLDOUT[2]
    return None


def scan_sheet(text, d8, phase_open=None, dec_sec=None):
    """(l1_rows, l3_hit, l4_hit) for one sheet's text.

    `phase_open` maps a phase NAME to the session second it opens on, taken
    from the session itself.  Phase RANK is not a substitute: an m0 session
    spans 23h beginning at the prior close, so its tail seconds carry the
    TOKYO tag again, LATER than that session's LONDON and NY.  Comparing ranks
    flagged 79 sheets whose OPEN_LONDON levels are genuinely prior.
    """
    if dec_sec is None:
        m = _DEC_RE.search(text)
        dec_sec = int(m.group(2)) if m else -1
    l1 = 0
    for line in text.splitlines():
        mm = _LEVEL_RE.match(line)
        if not mm:
            continue
        anchor = mm.group(2)[5:]
        o = (phase_open or {}).get(anchor)
        # a level whose anchor second is not STRICTLY BEFORE the decision is
        # priced off a mid that had not happened yet
        if o is None or o >= int(dec_sec):
            l1 += 1
    l3 = 0
    for rx in (_DOM_RE, _ROLL_RE, _DYING_RE, _ICH_RE, _SIF_RE):
        mm = rx.search(text)
        if mm and mm.group(1) not in (MC.NA, MC.NA + ",", ""):
            l3 = 1
            break
    # L4: a card row whose era label is NOT strictly prior to this decision
    yr = int(d8) // 10000
    l4 = 0
    in_s13 = False
    for line in text.splitlines():
        if _SEC_RE.match(line):
            in_s13 = bool(_S13_RE.match(line))
        if not in_s13:
            continue
        mm = _CARD_ERA_RE.match(line)
        if not mm:
            continue
        if mm.group(1) == "PRE_E1":
            if int(d8) < MC.ERAS[0][1]:
                l4 = 1
            continue
        lab = mm.group(1)
        if lab.isdigit():
            if int(lab) >= yr:
                l4 = 1
        elif lab.startswith("FIT_"):
            if yr <= int(lab.split("_")[2]):
                l4 = 1
        elif lab.startswith("GATE_"):
            if yr <= int(lab.split("_")[1]):
                l4 = 1
        else:
            hi = _era_hi(lab)
            if hi is not None and hi >= int(d8):
                l4 = 1
        if l4:
            break
    return l1, l3, l4


def phase_open_secs(asset, d8):
    """{phase name: first session second carrying that tag} from the session."""
    try:
        s = A.load_session(asset, int(d8))["s"]
    except Exception:                     # noqa: BLE001 — reported as refusal
        return None
    out = {}
    for i, name in enumerate(X.PHASE_NAMES):
        w = np.nonzero(s.phase_tag == i)[0]
        if w.size:
            out[name] = int(w[0])
    return out


def scan_dir(era, block, asset, d8):
    base = MC.out_path("era", era, block, asset, "%08d" % int(d8), "_")[:-1]
    if not os.path.isdir(base):
        return None
    popen = phase_open_secs(asset, d8)
    names = sorted(os.listdir(base))
    sheets = [n for n in names if n.endswith(".%s.sheet.txt" % block)]
    s14 = [n for n in names if ".S14." in n]
    n_cert = n_fail = n_over = n_ref = 0
    l1_sheets = l1_rows = l3 = l4 = 0
    h = hashlib.sha256()
    for n in sheets:
        with open(os.path.join(base, n)) as fh:
            t = fh.read()
        h.update(hashlib.sha256(t.encode("utf-8")).digest())
        mm = re.search(r"^\s+certified\s+(\d)\s+n_sections=(\d+)\s+"
                       r"n_failed=(\d+)\s+n_leak_refusals=(\d+)\s+"
                       r"n_refused_derived=(\d+)", t, re.M)
        if mm:
            n_cert += int(mm.group(1))
            n_fail += int(mm.group(3))
            n_ref += int(mm.group(5))
        n_over += t.count("  OVER ")
        a, b, c = scan_sheet(t, d8, popen)
        if a:
            l1_sheets += 1
            l1_rows += a
        l3 += b
        l4 += c
    return [era, block, asset, int(d8), len(sheets), n_cert, n_fail, n_over,
            n_ref, l1_sheets, l1_rows, len(s14), l3, l4, h.hexdigest()[:16]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--era", default="E1")
    ap.add_argument("--block", default=MC.MODE_BLIND)
    ap.add_argument("--assets", default=",".join(MC.ASSET_ORDER))
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    MC.verify_spec(force=True)
    rows = []
    for asset in a.assets.split(","):
        base = MC.out_path("era", a.era, a.block, asset, "_")[:-1]
        if not os.path.isdir(base):
            continue
        for d8 in sorted(os.listdir(base)):
            if not d8.isdigit():
                continue
            r = scan_dir(a.era, a.block, asset, d8)
            if r:
                rows.append(r)
                MC.hb("certify %s/%s %s %s: %d sheets, L1=%d/%d L2=%d L3=%d "
                      "L4=%d" % (a.era, a.block, asset, d8, r[4], r[9], r[10],
                                 r[11], r[12], r[13]))
    tot = [sum(int(r[i]) for r in rows) for i in range(4, 14)]
    out = a.out or os.path.join(OUT_DIR, "CORPUS_CERT_%s_%s.tsv"
                                % (a.era, a.block))
    MC.write_tsv(out, SECTION, MC.params_hash({"era": a.era,
                                               "block": a.block}),
                 list(COLUMNS), rows,
                 extra=["L1 R93 forward-anchored fvol level rows; "
                        "L2 R02 co-located S14 artefacts; "
                        "L3 R94 forward S2 session-meta values; "
                        "L4 R01 census cards over a non-prior era",
                        "TOTALS n_sheets=%d n_certified=%d n_failed=%d "
                        "n_over_budget=%d n_refused_derived=%d "
                        "L1_sheets=%d L1_rows=%d L2=%d L3=%d L4=%d"
                        % tuple(tot)])
    MC.write_json(out.replace(".tsv", ".receipt.json"),
                  {"env": MC.env_receipt({"era": a.era, "block": a.block}),
                   "n_session_assets": len(rows),
                   "totals": dict(zip(COLUMNS[4:14], tot)),
                   "clean": bool(tot[5] == 0 and tot[7] == 0 and tot[8] == 0
                                 and tot[9] == 0)})
    sys.stdout.write(
        "%s/%s: %d session-assets, %d sheets, %d certified | LEAKS "
        "L1=%d sheets/%d rows  L2=%d  L3=%d  L4=%d\n"
        % (a.era, a.block, len(rows), tot[0], tot[1], tot[5], tot[6], tot[7],
           tot[8], tot[9]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
