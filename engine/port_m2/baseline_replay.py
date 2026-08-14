#!/usr/bin/python3
"""PORT M2 — FROZEN MECHANICAL BASELINES (CC-M2-4.1).

    "every scored day is also replayed under frozen zero-intelligence policies
     (EARLIEST-per-episode + value threshold ...).  The reader's headline =
     margin over the best mechanical baseline, day-paired, cluster-robust.
     Judgment must beat rules."

THE POLICY (zero intelligence, no sheet reading at all)
  1. group the day's candidates with EPISODE_CAUSAL — the FROZEN CC-M1-12 v2
     grouping (SAME SESSION AND same side; link iff gap <= K*; anti-chaining
     split at SPAN_MAX), K*/SPAN_MAX READ from the committed episode_v2
     receipts and checked against the frozen pins, never re-fitted here;
  2. keep the EARLIEST member of each episode — that alone is the pure arm
     `BASE_EARLIEST`, which needs no census input at all;
  3. TAKE it iff its D-071 CLASS CENSUS conditional value is >= a threshold.
     The card is READ AT RUN TIME from `class_census.tsv` for the candidate's
     OWN asset and class, restricted to STRICTLY-PRIOR eras (R01: a card whose
     span contains the decision's own future is not an ex-ante statistic), and
     the threshold is swept over the distinct card values ACTUALLY PRESENT.

R05/R81 — WHAT WAS WRONG AND IS NOW FIXED
  * `COND_VALUE` was five HARDCODED E1 numbers.  SHOCK-RESOLUTION and
    CLASS_UNKNOWN were absent and `.get(cls, 0.0)` scored every POST_SHOCK
    candidate at $0.00, so the arm was blind to a whole class by accident, and
    on any era but E1 the ladder was calibrated to a ranking that no longer
    holds.  Cards are now read per (asset, class, prior era); a class with NO
    admissible card is REFUSED, never defaulted, and the refusal count is
    reported.  A CV arm carrying ANY refusal is refused WHOLE: a policy that
    cannot decide every candidate has no day-complete replay.
  * `episodes()` keyed on `(asset, side)` with NO session component and sorted
    by the SESSION second, then handed that concatenated multi-session vector
    to `group_causal`, which is documented "for ONE (session, side)".  Measured
    on the committed E2 BLIND index: 952 episodes at 70.23 cand/episode against
    23,567 at 2.84 — a 24.8x under-count of the arm the reader's headline
    margin is taken over.  The key now carries `date8` and the single-session
    invariant is ASSERTED.

Run:
  baseline_replay.py --index TRIAGE_INDEX.tsv [MORE.tsv ...] --outdir DIR
"""
import argparse
import os
import sys
from collections import OrderedDict

_HERE = os.path.dirname(os.path.abspath(__file__))
for p in (_HERE, os.path.join(os.path.dirname(_HERE), "port_m1")):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np                                            # noqa: E402
import episode_v2 as EV                                       # noqa: E402
import m2_common as MC                                        # noqa: E402
import triage_index as TI                                     # noqa: E402

SECTION = "§CC-M2-4.1 (frozen mechanical baselines)"

# FROZEN, from artifacts/cache/port/m1/episodes_v2/EPISODE_V2_REPORT.md §P2.
# These are PINS, not the source: `episode_pins()` reads the committed receipt
# and REFUSES on any disagreement (the docstring used to claim the receipt was
# read while the numbers were hard-copied).
KSTAR = {("SI", -1): 150, ("SI", 1): 180, ("HG", -1): 120, ("HG", 1): 120,
         ("NKD", -1): 150, ("NKD", 1): 150}
SPAN_MAX = {("SI", -1): 588, ("SI", 1): 733, ("HG", -1): 413, ("HG", 1): 412,
            ("NKD", -1): 536, ("NKD", 1): 544}

M1_EPISODES = os.path.join(os.path.dirname(os.path.dirname(_HERE)),
                           "artifacts/cache/port/m1/episodes_v2")
KSTAR_TSV = os.path.join(M1_EPISODES, "p1_kstar.tsv")
SPAN_TSV = os.path.join(M1_EPISODES, "anti_chaining_guard.tsv")

CLASS_CENSUS = os.path.join(os.path.dirname(os.path.dirname(_HERE)),
                            "artifacts/cache/port/m2/class_census.tsv")

REFUSED = MC.REFUSED_TOKEN
PURE_ARM = "BASE_EARLIEST"


class BaselineRefusal(RuntimeError):
    """A mechanical arm that cannot be built.  Never a silent default."""


# ------------------------------------------------------------------- pins ---
def _read_tsv(path):
    rows = []
    with open(path) as fh:
        hdr = None
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            f = ln.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f
                continue
            rows.append(dict(zip(hdr, f)))
    if hdr is None:
        raise BaselineRefusal("%s carries no header" % path)
    return rows


def episode_pins(check=True):
    """(KSTAR, SPAN_MAX) READ from the committed episode_v2 receipts.

    R83-MINOR: the module claimed to read the receipt and hard-copied the
    numbers instead.  The pins above are kept as the frozen declaration and
    this function REFUSES on any disagreement with the receipt on disk.
    """
    kst, spn = {}, {}
    for r in _read_tsv(KSTAR_TSV):
        kst[(r["asset"], int(r["side"]))] = int(r["K_star_sec"])
    for r in _read_tsv(SPAN_TSV):
        spn[(r["asset"], int(r["side"]))] = int(float(r["span_max_sec"]))
    if check:
        bad = [k for k in sorted(set(KSTAR) | set(kst))
               if KSTAR.get(k) != kst.get(k)]
        bad += [k for k in sorted(set(SPAN_MAX) | set(spn))
                if SPAN_MAX.get(k) != spn.get(k)]
        if bad:
            raise BaselineRefusal(
                "episode pins disagree with the committed receipt on %s — the "
                "frozen grouping moved and the arm is refused" % (bad,))
    return kst, spn


# --------------------------------------------------------------- episodes ---
def _side(tok):
    """R45: one spelling of the side contract, and it REFUSES on an unknown
    token instead of silently mapping it to SHORT."""
    t = str(tok).strip().upper()
    if t in ("1", "+1"):
        return 1
    if t == "-1":
        return -1
    if t.startswith("L"):
        return 1
    if t.startswith("S"):
        return -1
    raise BaselineRefusal("unrecognised side token %r" % (tok,))


# R26/D16: the two index shapes in the stack spell the same two fields
# differently (the triage index says `sec`/`cls`, the era index says
# `dec_sec`/`candidate_class`).  One accessor, and it RAISES on an absent
# column rather than returning a default.
ROW_ALIASES = {"sec": ("sec", "dec_sec"),
               "cls": ("cls", "candidate_class"),
               "date8": ("date8",),
               "asset": ("asset",),
               "side": ("side",),
               "cid": ("cid",)}


def col(r, key):
    for k in ROW_ALIASES[key]:
        v = r.get(k)
        if v is not None and str(v).strip() != "":
            return v
    raise BaselineRefusal("index row %s carries no %s column (tried %s)"
                          % (r.get("cid"), key, "/".join(ROW_ALIASES[key])))


def episodes(rows):
    """{(asset, date8, side): [[cid, ...], ...]} under EPISODE_CAUSAL.

    R81: the key carries the SESSION.  `group_causal` returns member ranges
    "for ONE (session, side)" and `r["sec"]` is the SESSION second, so a key
    without `date8` concatenates every day's seconds into one vector and the
    gap rule links across midnight.
    """
    by = {}
    for r in rows:
        by.setdefault((col(r, "asset"), int(col(r, "date8")),
                       _side(col(r, "side"))), []).append(r)
    out = {}
    for key, rs in by.items():
        asset, d8, side = key
        # THE SINGLE-SESSION INVARIANT, asserted rather than assumed: this is
        # the guard R81 was missing.  `group_causal` links on `sec`, which is
        # the SESSION second — a member vector drawn from two sessions links
        # across midnight and the anti-chaining span is meaningless.
        d8s = {int(col(r, "date8")) for r in rs}
        if d8s != {d8}:
            raise BaselineRefusal(
                "EPISODE_CAUSAL was handed %d sessions (%s) for one "
                "(asset, side) group on %s/%s — group_causal is defined for "
                "ONE (session, side)" % (len(d8s), sorted(d8s), asset, side))
        rs.sort(key=lambda r: (int(col(r, "sec")), r["cid"]))
        dec = np.array([int(col(r, "sec")) for r in rs], dtype=np.int64)
        spans = EV.group_causal(dec, KSTAR[(asset, side)],
                                SPAN_MAX[(asset, side)])
        out[key] = [[rs[i]["cid"] for i in range(lo, hi)] for lo, hi in spans]
    return out


def earliest_cids(rows):
    """{cid} — the EARLIEST member of each (session, side) episode."""
    idx = {r["cid"]: r for r in rows}
    out = set()
    n_ep = 0
    for _key, groups in episodes(rows).items():
        n_ep += len(groups)
        for g in groups:
            out.add(min(g, key=lambda c: (int(col(idx[c], "sec")), c)))
    return out, n_ep


# ------------------------------------------------------------ class cards ---
def prior_card_eras(d8):
    """The era labels a card for a decision on `d8` may be computed over.

    MIRRORS `sections._prior_card_eras` (R01): a card is admissible only if its
    whole span ENDED strictly before the decision date.  For E1 that set is
    EMPTY — the protocol's first era has no strictly-prior era — and the card is
    REFUSED rather than back-filled from the future.  PRE_E1 is deliberately
    excluded for the same reason the sheet builder excludes it: it is out of
    protocol scope and is not one of `m2_common.ERAS`.
    """
    d8 = int(d8)
    eras = [n for (n, _lo, hi) in MC.ERAS if hi < d8]
    if MC.ERA_HOLDOUT[2] < d8:
        eras.append(MC.ERA_HOLDOUT[0])
    return list(reversed(eras))             # newest admissible era first


_CARDS = {}


def class_cards(path=None):
    """{(asset, class, era): conditional_value_usd} from the class census."""
    p = path or CLASS_CENSUS
    if p in _CARDS:
        return _CARDS[p]
    if not os.path.exists(p):
        raise BaselineRefusal(
            "%s does not exist: the class-card arm reads its values at run "
            "time and REFUSES rather than falling back to a hardcoded table"
            % p)
    cards = {}
    for r in _read_tsv(p):
        try:
            v = float(r["conditional_value_usd"])
        except (KeyError, ValueError):
            continue
        cards[(r["asset"], r["class"], r["era"])] = v
    _CARDS[p] = cards
    return cards


def card_value(cards, asset, cls, d8):
    """The strictly-prior conditional-value card, or REFUSED.

    -> (value_or_REFUSED, era_used_or_None).  The NEWEST admissible era wins:
    it is the closest ex-ante estimate of the population being traded.
    """
    for era in prior_card_eras(d8):
        v = cards.get((asset, cls, era))
        if v is not None:
            return float(v), era
    return REFUSED, None


# ----------------------------------------------------------------- arms -----
def build_arms(rows, cards=None):
    """-> (arms, info).

    `arms`  OrderedDict name -> {cid: "TAKE"|"SKIP"}.  A CV arm that had to
            refuse ANY candidate is NOT emitted (it appears in
            info["refused_arms"] with its reason) — a policy that cannot decide
            every candidate has no day-complete replay, and a refused quantity
            is never a number.
    `info`  the receipt: episode count, thresholds swept, per-class card used,
            refusal count and the refused (asset, class, era-set) triples.
    """
    cards = class_cards() if cards is None else cards
    earliest, n_ep = earliest_cids(rows)
    resolved, refused = {}, {}
    for r in rows:
        key = (col(r, "asset"), col(r, "cls"), int(col(r, "date8")))
        if key in resolved or key in refused:
            continue
        v, era = card_value(cards, col(r, "asset"), col(r, "cls"),
                            int(col(r, "date8")))
        if MC.is_refused(v):
            refused[key] = prior_card_eras(int(col(r, "date8")))
        else:
            resolved[key] = (v, era)
    n_refused_rows = sum(
        1 for r in rows
        if (col(r, "asset"), col(r, "cls"), int(col(r, "date8"))) in refused)

    arms = OrderedDict()
    # the PURE arm: no census input at all, so it is always buildable and is
    # the honest mechanical comparator when the cards are refused.
    arms[PURE_ARM] = {r["cid"]: ("TAKE" if r["cid"] in earliest else "SKIP")
                      for r in rows}
    thresholds = sorted({v for v, _e in resolved.values()})
    names = {}
    for th in thresholds:
        base = "BASE_EARLIEST_CV%d" % int(round(th))
        name, k = base, 1
        while name in names:               # two distinct values, one rounding
            k += 1
            name = "%s_%d" % (base, k)
        names[name] = th
    refused_arms = {}
    if refused and not names:
        # every card in the universe is refused, so the whole CV family is
        # unbuildable and only the PURE arm stands.  Recorded under a name so
        # the gate's arm set shows a REFUSAL rather than a silent absence.
        refused_arms["BASE_EARLIEST_CV*"] = (
            "no strictly-prior class card exists for ANY (asset, class) in "
            "this universe (%d triples, %d of %d rows) — R01/R05: an E1 "
            "decision has no admissible prior era"
            % (len(refused), n_refused_rows, len(rows)))
    for name, th in names.items():
        if refused:
            refused_arms[name] = (
                "%d of %d rows carry no strictly-prior class card (R01/R05)"
                % (n_refused_rows, len(rows)))
            continue
        arms[name] = {
            r["cid"]: ("TAKE" if (r["cid"] in earliest
                                  and resolved[(col(r, "asset"), col(r, "cls"),
                                                int(col(r, "date8")))][0] >= th)
                       else "SKIP")
            for r in rows}
    info = {"n_rows": len(rows), "n_episodes": n_ep, "n_earliest": len(earliest),
            "cand_per_episode": (len(rows) / float(n_ep)) if n_ep else None,
            "thresholds": names,
            "cards_used": {"%s|%s|%d" % k: {"value": v, "era": e}
                           for k, (v, e) in sorted(resolved.items())},
            "n_card_refusals": len(refused),
            "n_rows_card_refused": n_refused_rows,
            "card_refusals": {"%s|%s|%d" % k: v for k, v in sorted(refused.items())},
            "refused_arms": refused_arms}
    return arms, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, nargs="+")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--class-census", default=None)
    a = ap.parse_args()
    episode_pins()                          # refuses if the grouping moved
    rows = []
    for p in a.index:                       # R26: the CANONICAL reader, never
        rs, _stamps = TI.read_index(p)      # readlines()[1:]
        rows += rs
    seen = set()
    for r in rows:
        if r["cid"] in seen:
            raise BaselineRefusal("duplicate cid %s across the given indices"
                                  % r["cid"])
        seen.add(r["cid"])
    arms, info = build_arms(rows, class_cards(a.class_census))
    sys.stderr.write("EPISODE_CAUSAL: %d episodes over %d candidates "
                     "(%.2f cand/episode, %d session-sides)\n"
                     % (info["n_episodes"], info["n_rows"],
                        info["cand_per_episode"] or 0.0,
                        len(episodes(rows))))
    os.makedirs(a.outdir, exist_ok=True)
    for name, cmap in arms.items():
        path = os.path.join(a.outdir, name + ".tsv")
        n = 0
        with open(path, "w", newline="\n") as fh:
            fh.write("cid\tcall\tconf\tprimary\n")
            for r in rows:
                call = cmap[r["cid"]]
                n += (call == "TAKE")
                th = info["thresholds"].get(name)
                card = info["cards_used"].get(
                    "%s|%s|%d" % (col(r, "asset"), col(r, "cls"),
                                  int(col(r, "date8"))))
                fh.write("%s\t%s\tC\tprimary: frozen mechanical policy — "
                         "EARLIEST member of its EPISODE_CAUSAL group "
                         "(session %d, K*=%ds)%s\n"
                         % (r["cid"], call, int(col(r, "date8")),
                            KSTAR[(col(r, "asset"), _side(col(r, "side")))],
                            "" if th is None else
                            (" and class card cond_value$=%.2f (era %s) vs "
                             "threshold $%.2f"
                             % (card["value"], card["era"], th))))
        sys.stderr.write("  %s: %d TAKE -> %s\n" % (name, n, path))
    for name, why in sorted(info["refused_arms"].items()):
        sys.stderr.write("  %s: REFUSED — %s\n" % (name, why))
    MC.write_json(os.path.join(a.outdir, "baseline_replay.receipt.json"),
                  {"env": MC.env_receipt({"spec_section": SECTION}),
                   "indices": [os.path.abspath(p) for p in a.index],
                   "arms": list(arms), **info})
    return 0


if __name__ == "__main__":
    sys.exit(main())
