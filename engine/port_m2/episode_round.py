#!/usr/bin/python3
"""PORT M2 — THE EPISODE-GRAIN PAYMENT-RANKING ROUND DRIVER (D-080.2/.3).

WHAT CHANGED.  Every reader round to date worked at CANDIDATE grain with a
triage keyhole: ~950 candidates a day, a compact index, and deep reads on a
self-selected few.  D-080 rules that out.  The round runs at EPISODE grain —
the program's own CC-M1-12 v2 grouping — with EVERY episode deep-read (full
sheet + on-demand ribbon), and the day's scored task is PAYMENT RANKING: rank
the day's episodes by expected payment, scored on rank-vs-realised.

THE FIVE THINGS THIS MODULE IS
  A. BUILD   the day's episode index under EPISODE_CAUSAL keyed
             (asset, date8, side) — THE SESSION COMPONENT IS MANDATORY.  R81
             measured a 24.8x episode under-count when the key omitted it, and
             that arm is where the reader's margin is taken.
  B. VALIDATE the reader's ranking file (a permutation of the whole day, or an
             explicit ABSTAIN set scored ranked-last and counted).
  C. SCORE   top-k capture (headline k=5), Spearman, NDCG@k, precision@k over
             payers, and realised dollars against the DP ceiling, against four
             mechanical baselines, with session-clustered day-paired inference.
  D. VIEW    the per-episode deep read, RECORDED in an access ledger — a day is
             not scoreable until every one of its episodes has an entry (R02:
             a protocol claim needs a mechanism, not a stamped literal).
  E. BLIND   the build and view paths NEVER import panel_score and never touch
             S14.  Scoring is a separate entry point, run after the ranking
             file is sealed.  `test_builds_fixlane.t10` asserts the import
             property mechanically, in a subprocess.

BLIND SAFETY, MECHANICALLY.  `panel_score` is imported INSIDE `score()` and
nowhere else, so `import episode_round` followed by any build/view call leaves
`panel_score` absent from `sys.modules`.  Nothing on the ranking path can read
an outcome without that import.

CLI
  --build --era E1 --date8 20211020 [--assets SI,HG,NKD]
  --episode SI-20211020-S-E07 --view [--sheet-source render|corpus]
      [--round R] [--caller NAME]
  --validate-ranking --era E1 --date8 20211020 --ranking PATH
  --score --era E1 --ranking 20211020=PATH [--ranking ...] [--outdir DIR]

Protocol doc: design/PORT_M2_EPISODE_ROUND.md
"""
import argparse
import hashlib
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "port_m1")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import m2_common as MC                    # noqa: E402
import era_index as EI                    # noqa: E402
import sections as SEC                    # noqa: E402
import sheets as SH                       # noqa: E402
import tape as TAPE                       # noqa: E402
import ribbon as RIB                      # noqa: E402
import class_census as CLS                # noqa: E402
import episode_v2 as EV                   # noqa: E402
# NOTE: panel_score is deliberately NOT imported here.  See `score()`.

SECTION = "§3 EPISODE-GRAIN PAYMENT-RANKING ROUND (D-080.2/.3)"

OUT_DIR = MC.out_path("episode_round", "_")[:-1]
ACCESS_LEDGER = os.path.join(OUT_DIR, "EPISODE_ACCESS.tsv")


def set_root(path):
    """Point the driver's index + access ledger at another tree.

    A round that wants its own tree (or a test that must not touch the
    committed one) sets it here rather than passing a root through every
    function — the deep-read ledger and the index must always live together or
    the scoreability check would read the wrong ledger.
    """
    global OUT_DIR, ACCESS_LEDGER
    OUT_DIR = os.path.abspath(path)
    ACCESS_LEDGER = os.path.join(OUT_DIR, "EPISODE_ACCESS.tsv")
    os.makedirs(OUT_DIR, exist_ok=True)
    return OUT_DIR

# ------------------------------------------------------ the frozen grouping --
# EPISODE_CAUSAL K* and SPAN_MAX, per (asset, side), copied from
# baseline_replay.py:41-44.  THE COPY IS NOT TRUSTED: `assert_frozen_tables()`
# re-reads the committed episode_v2 receipt below and refuses on any mismatch.
KSTAR = {("SI", -1): 150, ("SI", 1): 180, ("HG", -1): 120, ("HG", 1): 120,
         ("NKD", -1): 150, ("NKD", 1): 150}
SPAN_MAX = {("SI", -1): 588, ("SI", 1): 733, ("HG", -1): 413, ("HG", 1): 412,
            ("NKD", -1): 536, ("NKD", 1): 544}
EPISODE_V2_RECEIPT = ("/workspace/artifacts/cache/port/m1/episodes_v2/"
                      "anti_chaining_guard.tsv")

# ------------------------------------------------------------ scored objects --
KS = (1, 3, 5, 10, 20)                    # declared in advance, all reported
HEADLINE_K = 5                            # pre-registered headline
METRIC_TOPK = "topk_capture"
METRIC_SPEARMAN = "spearman"
METRIC_NDCG = "ndcg"
METRIC_PREC = "precision_payers"
METRIC_DOLLARS = "dollars_topk_usd"
METRIC_CEIL = "capture_vs_dp_ceiling"
METRICS = (METRIC_TOPK, METRIC_SPEARMAN, METRIC_NDCG, METRIC_PREC,
           METRIC_DOLLARS, METRIC_CEIL)

ARM_READER = "READER"
ARM_CHRONO = "CHRONOLOGICAL"
ARM_CLASS = "CLASS_CARD"
ARM_SIZE = "SIZE"
ARM_RANDOM = "RANDOM"
BASELINES = (ARM_CHRONO, ARM_CLASS, ARM_SIZE, ARM_RANDOM)

PERM_SEED = 20260814                      # pinned; the only RNG in this module
N_PERM = 1000

RANKING_COLUMNS = ("rank", "episode_id", "expected_payment_usd", "confidence",
                   "evidence")
ABSTAIN = "ABSTAIN"

EPISODE_COLUMNS = ("episode_id", "era", "asset", "date8", "side", "side_int",
                   "n_members", "first_dec_sec", "last_dec_sec", "span_sec",
                   "rep_cid", "rep_class", "rep_phase", "classes_present",
                   "block", "sheet_path", "ribbon_cmd", "members")

ACCESS_COLUMNS = ("seq", "episode_id", "era", "asset", "date8", "rep_cid",
                  "n_members", "mode", "sheet_source", "sheet_sha16",
                  "sheet_tokens", "n_ribbon_cmds", "s14_guard_paths_checked",
                  "round", "caller")

SCORE_COLUMNS = ("era", "date8", "grain", "cluster_key", "arm", "metric", "k",
                 "value", "n_scored", "n_refused", "note")
PAIRED_COLUMNS = ("era", "grain", "metric", "k", "baseline", "n_units",
                  "mean_delta", "se_clustered", "t", "p_raw", "p_holm",
                  "n_won", "n_lost", "verdict", "power_floor_units")

PARAMS = {
    "spec_section": SECTION,
    "directive": "D-080.2 (episode grain, every episode deep-read) + D-080.3 "
                 "(payment ranking as the scored daily objective)",
    "grouping": "EPISODE_CAUSAL (CC-M1-12 v2) keyed (asset, date8, side) — the "
                "SESSION COMPONENT IS MANDATORY (R81: keying on (asset, side) "
                "alone under-counted episodes 24.8x)",
    "kstar_span_source": EPISODE_V2_RECEIPT,
    "representative": "the EARLIEST member — the causal entry, the only member "
                      "a reader could act on at the episode's open",
    "realized_payment": "panel_score.outcome(rep_cid)['cert_close_usd'] — the "
                        "walled close certificate, READ from the frozen "
                        "roster, never re-derived",
    "payer": "panel_score.outcome(rep_cid)['winner_close'] — the D-021 winner "
             "rule as panel_score defines it",
    "ks": list(KS), "headline_k": HEADLINE_K,
    "ndcg_gain": "max(0, realized) — a negative certificate is not a gain; "
                 "declared, not silently clipped inside the metric",
    "baselines": list(BASELINES),
    "random_arm": "exact expectation under a uniform random permutation, plus "
                  "a seeded permutation distribution (seed=%d, n=%d)"
                  % (PERM_SEED, N_PERM),
    "class_card": "class_census conditional_value_usd over STRICTLY-PRIOR era "
                  "labels only (R01)",
    "inference": "cluster = (asset, date8); one unit per cluster, so the "
                 "clustered SE is the CR1 form = the SEM over paired deltas "
                 "(m2_common.mirror_paired); Holm over the baseline set",
    "seed": PERM_SEED,
}


class FrozenTableMismatch(RuntimeError):
    """The copied K*/SPAN_MAX tables disagree with the committed receipt."""


class EpisodeRefusal(RuntimeError):
    """An episode-index invariant failed (session/side purity, membership)."""


class RankingRefusal(ValueError):
    """The reader's ranking file is not a valid ranking of the day."""


class AccessRefusal(RuntimeError):
    """A day whose episodes were not all deep-read cannot be scored."""


# ----------------------------------------------------------- frozen tables ---
def read_receipt_tables(path=EPISODE_V2_RECEIPT):
    """(kstar, span_max) as committed by the episode_v2 program."""
    k, s = {}, {}
    cols = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            d = dict(zip(cols, f))
            key = (d["asset"], int(d["side"]))
            k[key] = int(d["K_star_sec"])
            s[key] = int(d["span_max_sec"])
    return k, s


def assert_frozen_tables(path=EPISODE_V2_RECEIPT):
    """The module constants are a COPY; this is the check that they are right."""
    k, s = read_receipt_tables(path)
    bad = []
    for key in sorted(set(list(KSTAR) + list(k))):
        if KSTAR.get(key) != k.get(key):
            bad.append("K*%s copy=%s receipt=%s" % (key, KSTAR.get(key),
                                                    k.get(key)))
        if SPAN_MAX.get(key) != s.get(key):
            bad.append("SPAN_MAX%s copy=%s receipt=%s" % (key,
                                                          SPAN_MAX.get(key),
                                                          s.get(key)))
    if bad:
        raise FrozenTableMismatch("%s disagrees with %s: %s"
                                  % (__file__, path, "; ".join(bad)))
    return {"receipt": path, "n_keys": len(k),
            "kstar": {"%s|%d" % key: KSTAR[key] for key in sorted(KSTAR)},
            "span_max": {"%s|%d" % key: SPAN_MAX[key]
                         for key in sorted(SPAN_MAX)}}


# ------------------------------------------------------------------ build ----
def era_of_d8(d8):
    return MC.era_of(int(d8))


def index_dir(era):
    return os.path.join(OUT_DIR, era)


def index_path(era, date8):
    return os.path.join(index_dir(era), "EPISODE_INDEX_%s_%08d.tsv"
                        % (era, int(date8)))


def _ribbon_cmd(rep_cid):
    """The episode's causal window, as the exact command line a reader runs."""
    return ("/usr/bin/python3 engine/port_m2/ribbon.py --cid %s --from T-%d "
            "--to T --grain %s"
            % (rep_cid, TAPE.RIBBON_DIGEST_SEC + TAPE.RIBBON_RAW_SEC,
               RIB.GRAIN_BOTH))


def _sheet_path(era, block, asset, d8, cid, mode=MC.MODE_BLIND):
    return MC.out_path("era", era, block, asset, "%08d" % int(d8),
                       "%s.%s.sheet.txt" % (cid, mode))


def build(era, date8, assets=MC.ASSET_ORDER, write=True):
    """The day's episode index.  Returns (episodes, receipt)."""
    MC.verify_spec()
    prov = assert_frozen_tables()
    d8 = int(date8)
    episodes = []
    n_cand = 0
    per_asset = {}
    for asset in sorted(assets):
        rows = [r for r in EI.load_index(era, asset)
                if int(r["date8"]) == d8 and r["eligible"] == "1"]
        n_cand += len(rows)
        n_ep_asset = 0
        for side in (1, -1):
            rs = sorted([r for r in rows if int(r["side"]) == side],
                        key=lambda r: (int(r["dec_sec"]), r["cid"]))
            if not rs:
                continue
            dec = np.array([int(r["dec_sec"]) for r in rs], dtype=np.int64)
            key = (asset, side)
            spans = EV.group_causal(dec, KSTAR[key], SPAN_MAX[key])
            spans = sorted(spans)
            for nn, (lo, hi) in enumerate(spans, start=1):
                mem = rs[lo:hi]
                rep = mem[0]                  # EARLIEST = the causal entry
                eid = "%s-%08d-%s-E%02d" % (asset, d8, MC.SIDE_CHAR[side], nn)
                classes = sorted({m["candidate_class"] for m in mem})
                episodes.append({
                    "episode_id": eid, "era": era, "asset": asset,
                    "date8": d8, "side": MC.SIDE_CHAR[side], "side_int": side,
                    "n_members": len(mem),
                    "first_dec_sec": int(mem[0]["dec_sec"]),
                    "last_dec_sec": int(mem[-1]["dec_sec"]),
                    "span_sec": int(mem[-1]["dec_sec"]) - int(mem[0]["dec_sec"]),
                    "rep_cid": rep["cid"],
                    "rep_class": rep["candidate_class"],
                    "rep_phase": rep["phase_dec"],
                    "classes_present": ",".join(classes),
                    "block": rep["block"],
                    "sheet_path": _sheet_path(era, rep["block"], asset, d8,
                                              rep["cid"]),
                    "ribbon_cmd": _ribbon_cmd(rep["cid"]),
                    "members": ",".join(m["cid"] for m in mem)})
                n_ep_asset += 1
        per_asset[asset] = {"n_candidates": len(rows),
                            "n_episodes": n_ep_asset}
    episodes.sort(key=lambda e: (e["first_dec_sec"], e["episode_id"]))

    # --- the purity assertion, as a CHECKED RECEIPT FIELD ------------------
    viol = []
    n_members_total = 0
    for e in episodes:
        sess, sides = set(), set()
        for cid in e["members"].split(","):
            a, cd8, _cs, cside = MC.parse_cid(cid)
            sess.add((a, cd8))
            sides.add(cside)
            n_members_total += 1
        if len(sess) != 1 or len(sides) != 1:
            viol.append("%s spans sessions=%s sides=%s"
                        % (e["episode_id"], sorted(sess), sorted(sides)))
    if viol:
        raise EpisodeRefusal("EPISODE_CAUSAL purity violated: %s"
                             % "; ".join(viol))
    if n_members_total != n_cand:
        raise EpisodeRefusal(
            "episode membership is not a partition: %d members over %d "
            "candidates" % (n_members_total, n_cand))

    n_ep = len(episodes)
    receipt = {
        "env": MC.env_receipt(PARAMS), "era": era, "date8": d8,
        "assets": sorted(assets),
        "n_episodes": n_ep, "n_candidates": n_cand,
        "episodes_per_day_pooled": n_ep,
        "episodes_per_asset_day_mean": (float(n_ep) / len(per_asset)
                                        if per_asset else float("nan")),
        "candidates_per_episode": (float(n_cand) / n_ep if n_ep else
                                   float("nan")),
        "per_asset": {a: per_asset[a] for a in sorted(per_asset)},
        "d080_reference_episodes_per_day": 180,
        "d080_reference_note": "the '~180 episode decisions/day' figure quoted "
                               "in D-080.2; the measured numbers beside it are "
                               "computed by this build, not asserted",
        "grouping_key": "(asset, date8, side) — session component MANDATORY "
                        "(R81)",
        "kstar_span_provenance": prov,
        "assert_single_session_single_side": {
            "n_episodes_checked": n_ep, "n_violations": 0,
            "n_members_checked": n_members_total},
        "index": index_path(era, d8)}
    if write:
        rows = [[e[c] for c in EPISODE_COLUMNS] for e in episodes]
        MC.write_tsv(index_path(era, d8), SECTION, MC.params_hash(PARAMS),
                     list(EPISODE_COLUMNS), rows,
                     extra=["EPISODE_CAUSAL key = (asset, date8, side); "
                            "K*/SPAN_MAX asserted against %s"
                            % EPISODE_V2_RECEIPT,
                            "chronological by first_dec_sec then episode_id; "
                            "representative = the EARLIEST member"])
        MC.write_json(os.path.join(index_dir(era),
                                   "EPISODE_INDEX_%s_%08d.receipt.json"
                                   % (era, d8)), receipt)
    return episodes, receipt


def load_episodes(era, date8):
    path = index_path(era, date8)
    if not os.path.exists(path):
        raise EpisodeRefusal("no episode index at %s — run --build first"
                             % path)
    out, cols = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            d = dict(zip(cols, f))
            for k in ("date8", "side_int", "n_members", "first_dec_sec",
                      "last_dec_sec", "span_sec"):
                d[k] = int(d[k])
            out.append(d)
    return out


# ------------------------------------------------------------ the ranking ---
def read_ranking(path):
    rows, cols = [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = [c.strip() for c in f]
                missing = [c for c in ("rank", "episode_id")
                           if c not in cols]
                if missing:
                    raise RankingRefusal(
                        "ranking file %s has no %s column (columns=%s); the "
                        "schema is %s" % (path, missing, cols,
                                          list(RANKING_COLUMNS)))
                continue
            rows.append(dict(zip(cols, f)))
    if cols is None:
        raise RankingRefusal("ranking file %s is empty" % path)
    return rows


def validate_ranking(episodes, rows):
    """Refusals are VALUES: every failure is collected and named at once."""
    ids = [e["episode_id"] for e in episodes]
    known = set(ids)
    refus = []
    seen = {}
    ranked, abstain = [], []
    for r in rows:
        eid = r["episode_id"].strip()
        seen[eid] = seen.get(eid, 0) + 1
        if eid not in known:
            refus.append("episode_id %s is not in the day's index" % eid)
            continue
        rk = str(r["rank"]).strip().upper()
        if rk == ABSTAIN:
            abstain.append(eid)
            continue
        try:
            ranked.append((int(rk), eid))
        except ValueError:
            refus.append("rank %r for %s is neither an integer nor %s"
                         % (r["rank"], eid, ABSTAIN))
    for eid, n in sorted(seen.items()):
        if n > 1:
            refus.append("episode_id %s appears %d times" % (eid, n))
    missing = sorted(known - set(seen))
    if missing:
        refus.append("%d episodes of the day are absent from the ranking "
                     "(the reader ranks the WHOLE day or declares them "
                     "%s): %s" % (len(missing), ABSTAIN,
                                  ",".join(missing[:20])
                                  + ("..." if len(missing) > 20 else "")))
    got = sorted(r for r, _ in ranked)
    want = list(range(1, len(ranked) + 1))
    if got != want:
        refus.append("ranks are not a permutation of 1..%d (got %s%s)"
                     % (len(ranked), got[:20],
                        "..." if len(got) > 20 else ""))
    if refus:
        raise RankingRefusal("; ".join(refus))
    ranked.sort()
    order = [eid for _r, eid in ranked] + sorted(abstain)
    return {"order": order, "ranked": [eid for _r, eid in ranked],
            "abstain": sorted(abstain), "n_ranked": len(ranked),
            "n_abstain": len(abstain)}


def emit_ranking(era, date8, arm, path):
    """Write a MECHANICAL arm as a ranking file in the reader's own format.

    D-080.3 requires the driver to run against mechanical rankings too, so the
    reader always has baselines to beat and the scorer can be exercised without
    a reader in the loop.
    """
    eps = load_episodes(era, date8)
    order, note = mechanical_order(eps, arm)
    if order is None:
        raise RankingRefusal("arm %s cannot be ordered on %s %d: %s"
                             % (arm, era, date8, note))
    by = {e["episode_id"]: e for e in eps}
    rows = []
    for i, eid in enumerate(order, start=1):
        e = by[eid]
        rows.append([i, eid, "", "C",
                     "primary: mechanical arm %s (%s); n_members=%d "
                     "first_dec_sec=%d class=%s"
                     % (arm, note or "no card note", e["n_members"],
                        e["first_dec_sec"], e["rep_class"])])
    MC.write_tsv(path, SECTION, MC.params_hash(PARAMS),
                 list(RANKING_COLUMNS), rows,
                 extra=["MECHANICAL ranking, arm=%s — not a reader product"
                        % arm])
    return path


# --------------------------------------------------------- the deep view -----
def _read_access(path=None):
    p = path or ACCESS_LEDGER
    rows = []
    if not os.path.exists(p):
        return rows
    cols = None
    with open(p) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def _append_access(rec, path=None):
    p = path or ACCESS_LEDGER
    rows = _read_access(p)
    out = [[r[c] for c in ACCESS_COLUMNS] for r in rows]
    rec = dict(rec)
    rec["seq"] = len(out)
    out.append([str(rec[c]) for c in ACCESS_COLUMNS])
    MC.write_tsv(p, SECTION, MC.params_hash(PARAMS), list(ACCESS_COLUMNS), out,
                 extra=["D-080.2 deep-read ledger: one row per episode view; "
                        "a day is not scoreable until every episode of its "
                        "index appears here (R02)",
                        "seq = row index (deterministic, no wall clock)"])
    return p


def missing_access(era, date8, round_name=None, path=None):
    """Episode ids of the day with NO deep-read entry.  Named, never assumed."""
    eps = load_episodes(era, date8)
    have = set()
    for r in _read_access(path):
        if r.get("era") != era or int(r.get("date8", -1)) != int(date8):
            continue
        if round_name is not None and r.get("round") != round_name:
            continue
        have.add(r["episode_id"])
    return sorted(e["episode_id"] for e in eps
                  if e["episode_id"] not in have)


def view(episode_id, mode=MC.MODE_BLIND, sheet_source="render",
         round_name="-", caller="-", ledger=None, record=True):
    """The per-episode DEEP VIEW: full sheet + member roster + ribbon commands.

    `sheet_source=render` rebuilds the representative's BLIND sheet through
    sheets.build (which never renders S14); `corpus` reads the committed sheet
    file and additionally asserts the corpus directory carries no S14 artefact.
    Every directory this path reads is passed through
    sheets.assert_no_s14_access (R02).
    """
    a, d8, side, _e = _parse_episode_id(episode_id)
    era = era_of_d8(d8)
    eps = [e for e in load_episodes(era, d8) if e["episode_id"] == episode_id]
    if not eps:
        raise EpisodeRefusal("episode %s is not in %s"
                             % (episode_id, index_path(era, d8)))
    e = eps[0]

    guard_dirs = [index_dir(era)]
    if sheet_source == "corpus":
        guard_dirs.append(os.path.dirname(e["sheet_path"]))
    n_guard = SH.assert_no_s14_access(guard_dirs, cids=[e["rep_cid"]])

    if sheet_source == "corpus":
        if not os.path.exists(e["sheet_path"]):
            raise EpisodeRefusal("no committed sheet at %s" % e["sheet_path"])
        with open(e["sheet_path"]) as fh:
            sheet = fh.read()
    else:
        sheet = SH.build(e["rep_cid"], mode).text

    members = e["members"].split(",")
    L = ["EPISODE DEEP VIEW %s (era=%s asset=%s date8=%d side=%s)"
         % (episode_id, era, a, d8, e["side"]),
         MC.row("  episode", "n_members=" + str(e["n_members"]),
                " first_dec_sec=" + str(e["first_dec_sec"]),
                " last_dec_sec=" + str(e["last_dec_sec"]),
                " span_sec=" + str(e["span_sec"]),
                " rep=" + e["rep_cid"],
                " rep_class=" + e["rep_class"],
                " classes=" + e["classes_present"]),
         "  MEMBER ROSTER (chronological; the representative is the EARLIEST)",
         "    n  dec_sec  cid"]
    for i, cid in enumerate(members):
        _a2, _d2, cs, _s2 = MC.parse_cid(cid)
        L.append(MC.row("   ", MC.fint(i + 1, 3), MC.fint(cs, 8), "  " + cid
                        + ("  <- REPRESENTATIVE" if cid == e["rep_cid"] else "")))
    ribbon_cmds = [e["ribbon_cmd"]]
    L.append("  RIBBON (on demand, D-080.4; any causal window, as often as you "
             "like — every call is ledgered)")
    for c in ribbon_cmds:
        L.append("    " + c)
    L.append("  SHEET (%s, mode=%s, source=%s)"
             % (e["rep_cid"], mode, sheet_source))
    L.append(sheet.rstrip("\n"))
    text = "\n".join(L) + "\n"

    sha = hashlib.sha256(sheet.encode("utf-8")).hexdigest()
    rec = {"seq": 0, "episode_id": episode_id, "era": era, "asset": a,
           "date8": d8, "rep_cid": e["rep_cid"], "n_members": e["n_members"],
           "mode": mode, "sheet_source": sheet_source, "sheet_sha16": sha[:16],
           "sheet_tokens": MC.count_tokens(sheet),
           "n_ribbon_cmds": len(ribbon_cmds),
           "s14_guard_paths_checked": n_guard,
           "round": round_name, "caller": caller}
    if record:
        _append_access(rec, ledger)
    return {"text": text, "record": rec, "episode": e}


def _parse_episode_id(eid):
    f = str(eid).split("-")
    if len(f) != 4 or not f[3].startswith("E"):
        raise ValueError("bad episode_id %r (want <ASSET>-<D8>-<L|S>-E<NN>)"
                         % eid)
    return f[0], int(f[1]), MC.CHAR_SIDE[f[2]], int(f[3][1:])


# --------------------------------------------------------------- baselines ---
class _CardShim(object):
    __slots__ = ("d8", "era")


def prior_card_eras(d8):
    """R01 strictly-prior census labels, newest-first.

    `sections._prior_card_eras` owns the rule and is reused verbatim; it
    enumerates MC.ERAS + the holdout only, so the PRE_E1 label that
    class_census emits for pre-2021H2 sessions is appended here (its span ends
    strictly before E1 opens, so it satisfies the same R01 test).
    """
    sh = _CardShim()
    sh.d8 = int(d8)
    sh.era = MC.era_of(int(d8))
    eras, years, _blocks = SEC._prior_card_eras(sh)
    out = list(eras)
    if int(d8) >= MC.ERAS[0][1]:
        out.append("PRE_E1")
    return out, years


def class_card_value(asset, cls, d8):
    """conditional_value_usd from the newest STRICTLY-PRIOR census label."""
    cards = CLS.cards()
    eras, years = prior_card_eras(d8)
    for era in eras + years[:1]:
        c = cards.get((asset, cls, era))
        if c is None:
            continue
        try:
            v = float(c["conditional_value_usd"])
        except (TypeError, ValueError):
            continue
        if np.isfinite(v):
            return v, era
    return None, None


def mechanical_order(episodes, arm):
    """(ordered episode ids, note).  A baseline that cannot be computed is
    REFUSED and named, never silently reordered."""
    if arm == ARM_CHRONO:
        return [e["episode_id"] for e in
                sorted(episodes, key=lambda e: (e["first_dec_sec"],
                                                e["episode_id"]))], ""
    if arm == ARM_SIZE:
        return [e["episode_id"] for e in
                sorted(episodes, key=lambda e: (-e["n_members"],
                                                e["episode_id"]))], ""
    if arm == ARM_CLASS:
        vals, miss, used = {}, [], set()
        for e in episodes:
            v, era = class_card_value(e["asset"], e["rep_class"], e["date8"])
            if v is None:
                miss.append(e["episode_id"])
            else:
                vals[e["episode_id"]] = v
                used.add(era)
        if miss:
            return None, ("REFUSED: no strictly-prior class card (R01) for %d "
                          "of %d episodes (e.g. %s)"
                          % (len(miss), len(episodes), miss[0]))
        return [e["episode_id"] for e in
                sorted(episodes, key=lambda e: (-vals[e["episode_id"]],
                                                e["episode_id"]))], \
            "cards from " + ",".join(sorted(used))
    raise ValueError("no mechanical order for arm %r" % arm)


# ----------------------------------------------------------------- metrics ---
def _rank_avg(v):
    """Average ranks (ties shared), ascending."""
    a = np.asarray(v, dtype=np.float64)
    order = np.argsort(a, kind="stable")
    r = np.empty(a.size, dtype=np.float64)
    i = 0
    while i < a.size:
        j = i
        while j + 1 < a.size and a[order[j + 1]] == a[order[i]]:
            j += 1
        r[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = _rank_avg(x), _rank_avg(y)
    if rx.size < 2 or rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def metrics_for_order(order, real, payer, ceiling):
    """Every declared metric for one arm's ordering over the SCORED set."""
    n = len(order)
    vals = np.array([real[e] for e in order], dtype=np.float64)
    pay = np.array([1.0 if payer[e] else 0.0 for e in order])
    srt = np.sort(vals)[::-1]
    gains = np.maximum(vals, 0.0)
    igains = np.sort(gains)[::-1]
    out = {}
    for k in KS:
        kk = min(k, n)
        if k > n:
            out[(METRIC_TOPK, k)] = MC.REFUSED_TOKEN
            out[(METRIC_NDCG, k)] = MC.REFUSED_TOKEN
            out[(METRIC_PREC, k)] = MC.REFUSED_TOKEN
            out[(METRIC_DOLLARS, k)] = MC.REFUSED_TOKEN
            out[(METRIC_CEIL, k)] = MC.REFUSED_TOKEN
            continue
        num = float(vals[:kk].sum())
        den = float(srt[:kk].sum())
        out[(METRIC_TOPK, k)] = (num / den if den > 0 else MC.REFUSED_TOKEN)
        disc = 1.0 / np.log2(np.arange(kk) + 2.0)
        idcg = float((igains[:kk] * disc).sum())
        out[(METRIC_NDCG, k)] = (float((gains[:kk] * disc).sum()) / idcg
                                 if idcg > 0 else MC.REFUSED_TOKEN)
        out[(METRIC_PREC, k)] = float(pay[:kk].sum()) / kk
        out[(METRIC_DOLLARS, k)] = num
        out[(METRIC_CEIL, k)] = (num / ceiling if ceiling and ceiling > 0
                                 else MC.REFUSED_TOKEN)
    pred = np.array([float(n - i) for i in range(n)])      # rank 1 = best
    out[(METRIC_SPEARMAN, 0)] = spearman(pred, vals)
    return out


def random_exact(order_set, real, payer, ceiling):
    """The EXACT expectation of each metric under a uniform random permutation
    where one exists; NDCG has none, so it is left to the permutation arm."""
    n = len(order_set)
    vals = np.array([real[e] for e in order_set], dtype=np.float64)
    pay = np.array([1.0 if payer[e] else 0.0 for e in order_set])
    srt = np.sort(vals)[::-1]
    mean = float(vals.mean()) if n else float("nan")
    out = {}
    for k in KS:
        if k > n:
            for m in (METRIC_TOPK, METRIC_PREC, METRIC_DOLLARS, METRIC_CEIL,
                      METRIC_NDCG):
                out[(m, k)] = MC.REFUSED_TOKEN
            continue
        den = float(srt[:k].sum())
        out[(METRIC_TOPK, k)] = (k * mean / den if den > 0
                                 else MC.REFUSED_TOKEN)
        out[(METRIC_PREC, k)] = float(pay.mean())
        out[(METRIC_DOLLARS, k)] = k * mean
        out[(METRIC_CEIL, k)] = (k * mean / ceiling if ceiling and ceiling > 0
                                 else MC.REFUSED_TOKEN)
        out[(METRIC_NDCG, k)] = MC.REFUSED_TOKEN     # no closed form -> perm
    out[(METRIC_SPEARMAN, 0)] = 0.0
    return out


def random_permutation_dist(order_set, real, payer, ceiling, seed=PERM_SEED,
                            n_perm=N_PERM):
    """Seeded permutation distribution -> (mean, lo2.5, hi97.5) per metric."""
    rng = np.random.default_rng(seed)
    ids = list(order_set)
    acc = {}
    for _ in range(int(n_perm)):
        perm = [ids[i] for i in rng.permutation(len(ids))]
        m = metrics_for_order(perm, real, payer, ceiling)
        for key, v in m.items():
            if MC.is_refused(v) or (isinstance(v, float)
                                    and not np.isfinite(v)):
                continue
            acc.setdefault(key, []).append(float(v))
    out = {}
    for key in sorted(acc):
        a = np.asarray(acc[key])
        out[key] = (float(a.mean()), float(np.percentile(a, 2.5)),
                    float(np.percentile(a, 97.5)))
    return out


# --------------------------------------------------------------- inference ---
def power_floor_units():
    """The smallest n at which the exact two-sided sign test can reach p<=0.05.

    Computed from the same test the paired arm uses — never a hand-picked
    number.  Below it, cells emit NO_TEST with this floor stated.
    """
    n = 1
    while MC._sign_test_p(n, 0) > 0.05:
        n += 1
        if n > 64:
            break
    return n


def holm(pvals):
    """Holm-Bonferroni adjusted p, input order preserved."""
    idx = sorted(range(len(pvals)), key=lambda i: (pvals[i], i))
    m = len(pvals)
    out = [1.0] * m
    run = 0.0
    for j, i in enumerate(idx):
        v = (m - j) * pvals[i]
        run = max(run, min(1.0, v))
        out[i] = run
    return out


# ------------------------------------------------------------------ score ----
def score(era, rankings, outdir=None, round_name=None, ledger=None,
          require_access=True, metric_grain="CELL"):
    """rankings = {date8: path}.  THE ONLY PLACE panel_score is imported."""
    import panel_score as PS                # noqa: E402 — blind-safety fence

    MC.verify_spec()
    out = outdir or os.path.join(OUT_DIR, era)
    floor = power_floor_units()
    score_rows, refused_rows = [], []
    cell_vals = {}                     # (arm, metric, k) -> {cluster: value}
    day_receipts = []

    for d8 in sorted(int(x) for x in rankings):
        eps = load_episodes(era, d8)
        if require_access:
            miss = missing_access(era, d8, round_name, ledger)
            if miss:
                raise AccessRefusal(
                    "day %d is not scoreable: %d of %d episodes have no "
                    "deep-read entry in %s%s — %s"
                    % (d8, len(miss), len(eps), ledger or ACCESS_LEDGER,
                       (" for round %s" % round_name) if round_name else "",
                       ",".join(miss[:20])
                       + ("..." if len(miss) > 20 else "")))
        rank = validate_ranking(eps, read_ranking(rankings[d8]))

        real, payer, refused = {}, {}, []
        for e in eps:
            try:
                o = PS.outcome(e["rep_cid"])
                v = float(o["cert_close_usd"])
            except Exception as ex:        # noqa: BLE001 — counted, not hidden
                refused.append((e["episode_id"], "outcome refused: %r"
                                % (ex,)))
                continue
            if not np.isfinite(v):
                refused.append((e["episode_id"],
                                "non-finite close certificate"))
                continue
            real[e["episode_id"]] = v
            payer[e["episode_id"]] = int(o["winner_close"])
        for eid, why in refused:
            refused_rows.append([era, d8, eid, why])

        scored = [e for e in eps if e["episode_id"] in real]
        scored_ids = set(e["episode_id"] for e in scored)
        assets = sorted({e["asset"] for e in scored})
        ceiling = 0.0
        for a in assets:
            ceiling += float(PS.dp_ceiling(a, d8, "close")[0])

        arms = {}
        notes = {}
        rdr = [e for e in rank["order"] if e in scored_ids]
        arms[ARM_READER] = rdr
        notes[ARM_READER] = ("ranked=%d abstain=%d (abstains scored ranked-"
                             "last)" % (rank["n_ranked"], rank["n_abstain"]))
        for arm in (ARM_CHRONO, ARM_CLASS, ARM_SIZE):
            order, note = mechanical_order(scored, arm)
            arms[arm] = order
            notes[arm] = note

        # --- DAY grain (the reader's actual task: the whole day at once) ---
        for arm in sorted(arms):
            if arms[arm] is None:
                score_rows.append([era, d8, "DAY", str(d8), arm, "-", 0,
                                   MC.REFUSED_TOKEN, len(scored),
                                   len(refused), notes[arm]])
                continue
            m = metrics_for_order(arms[arm], real, payer, ceiling)
            for (met, k) in sorted(m, key=lambda t: (t[0], t[1])):
                score_rows.append([era, d8, "DAY", str(d8), arm, met, k,
                                   m[(met, k)], len(scored), len(refused),
                                   notes.get(arm, "")])
        rex = random_exact(sorted(scored_ids), real, payer, ceiling)
        for (met, k) in sorted(rex, key=lambda t: (t[0], t[1])):
            score_rows.append([era, d8, "DAY", str(d8), ARM_RANDOM, met, k,
                               rex[(met, k)], len(scored), len(refused),
                               "exact expectation, uniform random permutation"])
        rpd = random_permutation_dist(sorted(scored_ids), real, payer, ceiling)
        for (met, k) in sorted(rpd, key=lambda t: (t[0], t[1])):
            mu, lo, hi = rpd[(met, k)]
            for tag, v in (("_PERM_MEAN", mu), ("_PERM_LO", lo),
                           ("_PERM_HI", hi)):
                score_rows.append([era, d8, "DAY", str(d8),
                                   ARM_RANDOM + tag, met, k, v, len(scored),
                                   len(refused),
                                   "seed=%d n_perm=%d" % (PERM_SEED, N_PERM)])

        # --- CELL grain (asset, date8) = the inference unit ----------------
        for a in assets:
            cs = [e for e in scored if e["asset"] == a]
            cids = set(e["episode_id"] for e in cs)
            ceil_a = float(PS.dp_ceiling(a, d8, "close")[0])
            cluster = "%s|%08d" % (a, d8)
            cell_arms = {ARM_READER: [x for x in arms[ARM_READER]
                                      if x in cids]}
            for arm in (ARM_CHRONO, ARM_CLASS, ARM_SIZE):
                cell_arms[arm] = (None if arms[arm] is None else
                                  [x for x in arms[arm] if x in cids])
            cell_arms[ARM_RANDOM] = None       # exact expectation below
            for arm in sorted(cell_arms):
                if arm == ARM_RANDOM:
                    m = random_exact(sorted(cids), real, payer, ceil_a)
                elif cell_arms[arm] is None:
                    score_rows.append([era, d8, "CELL", cluster, arm, "-", 0,
                                       MC.REFUSED_TOKEN, len(cs),
                                       len(refused), notes.get(arm, "")])
                    continue
                else:
                    m = metrics_for_order(cell_arms[arm], real, payer, ceil_a)
                for (met, k) in sorted(m, key=lambda t: (t[0], t[1])):
                    v = m[(met, k)]
                    score_rows.append([era, d8, "CELL", cluster, arm, met, k,
                                       v, len(cs), len(refused),
                                       notes.get(arm, "")])
                    if not MC.is_refused(v):
                        cell_vals.setdefault((arm, met, k), {})[cluster] = \
                            float(v)

        day_receipts.append({
            "date8": d8, "n_episodes": len(eps), "n_scored": len(scored),
            "n_refused": len(refused), "n_ranked": rank["n_ranked"],
            "n_abstain": rank["n_abstain"], "assets": assets,
            "dp_ceiling_usd": ceiling,
            "ranking": os.path.abspath(rankings[d8])})

    # ------------------------------------------------------- paired tests ---
    paired_rows = []
    keys = sorted({(met, k) for (_a, met, k) in cell_vals})
    for (met, k) in keys:
        rd = cell_vals.get((ARM_READER, met, k), {})
        stats, ps = [], []
        for b in BASELINES:
            bl = cell_vals.get((b, met, k), {})
            common = sorted(set(rd) & set(bl))
            deltas = [rd[c] - bl[c] for c in common]
            st = MC.mirror_paired(deltas, min_sessions=floor)
            stats.append((b, st))
            ps.append(st["p"] if np.isfinite(st["p"]) else 1.0)
        adj = holm(ps)
        for (b, st), pa in zip(stats, adj):
            paired_rows.append([era, "CELL", met, k, b, st["n_sessions"],
                                st["mean_delta"], st["se"], st["t"],
                                st["p"], pa, st["n_won"], st["n_lost"],
                                st["verdict"], floor])

    os.makedirs(out, exist_ok=True)
    phash = MC.params_hash(PARAMS)
    p_score = os.path.join(out, "EPISODE_ROUND_SCORE_%s.tsv" % era)
    MC.write_tsv(p_score, SECTION, phash, list(SCORE_COLUMNS), score_rows,
                 extra=["arm=%s is the reader; %s are the mechanical baselines"
                        % (ARM_READER, ",".join(BASELINES)),
                        "grain DAY = the whole day (the reader's task); grain "
                        "CELL = (asset, date8), the inference unit",
                        "value '%s' = REFUSED (named in the note column), "
                        "never a zero" % MC.REFUSED_TOKEN])
    p_paired = os.path.join(out, "EPISODE_ROUND_PAIRED.tsv")
    MC.write_tsv(p_paired, SECTION, phash, list(PAIRED_COLUMNS), paired_rows,
                 extra=["reader MINUS baseline, paired on the CELL unit "
                        "(asset, date8); one unit per cluster, so the "
                        "clustered SE is the CR1 form = SEM over the deltas",
                        "p_holm = Holm over the %d baselines within each "
                        "(metric, k); verdict NO_TEST below %d units"
                        % (len(BASELINES), floor)])
    p_ref = os.path.join(out, "EPISODE_ROUND_REFUSED.tsv")
    MC.write_tsv(p_ref, SECTION, phash,
                 ["era", "date8", "episode_id", "reason"], refused_rows,
                 extra=["refusal is a VALUE: these episodes are counted and "
                        "named, never scored as zero"])
    receipt = {"env": MC.env_receipt(PARAMS), "era": era,
               "days": day_receipts, "n_days": len(day_receipts),
               "power_floor_units": floor,
               "n_refused_episodes": len(refused_rows),
               "headline": {"metric": METRIC_TOPK, "k": HEADLINE_K,
                            "grain": "DAY"},
               "outputs": {"score": p_score, "paired": p_paired,
                           "refused": p_ref}}
    MC.write_json(os.path.join(out, "episode_round_score.receipt.json"),
                  receipt)
    _write_report(os.path.join(out, "EPISODE_ROUND_REPORT_%s.md" % era), era,
                  score_rows, paired_rows, receipt)
    return {"score_rows": score_rows, "paired_rows": paired_rows,
            "receipt": receipt}


def _fmt(v):
    if MC.is_refused(v):
        return MC.REFUSED_TOKEN
    if isinstance(v, float):
        return MC.NA if not np.isfinite(v) else "%.6f" % v
    return str(v)


def _write_report(path, era, score_rows, paired_rows, receipt):
    """NUMBERS ONLY (D-080.3 / the orchestrator rules).  Every number printed
    here is taken from the rows this run computed (D-010)."""
    L = ["# EPISODE ROUND — %s" % era, "",
         "Grain: EPISODE (EPISODE_CAUSAL, key = (asset, date8, side)).",
         "Objective: PAYMENT RANKING. Headline: %s@k=%d, grain DAY."
         % (METRIC_TOPK, HEADLINE_K),
         "Power floor: %d units (the smallest n at which the exact two-sided "
         "sign test can reach p<=0.05)." % receipt["power_floor_units"], ""]
    L.append("## DAYS")
    L.append("| date8 | n_episodes | n_scored | n_refused | n_ranked | "
             "n_abstain | dp_ceiling_usd |")
    L.append("|---|---|---|---|---|---|---|")
    for d in receipt["days"]:
        L.append("| %d | %d | %d | %d | %d | %d | %.2f |"
                 % (d["date8"], d["n_episodes"], d["n_scored"],
                    d["n_refused"], d["n_ranked"], d["n_abstain"],
                    d["dp_ceiling_usd"]))
    L.append("")
    L.append("## DAY-GRAIN VALUES")
    L.append("| date8 | arm | metric | k | value |")
    L.append("|---|---|---|---|---|")
    for r in score_rows:
        if r[2] != "DAY":
            continue
        L.append("| %s | %s | %s | %s | %s |"
                 % (r[1], r[4], r[5], r[6], _fmt(r[7])))
    L.append("")
    L.append("## PAIRED (reader minus baseline, cluster = (asset, date8))")
    L.append("| metric | k | baseline | n_units | mean_delta | se | p_raw | "
             "p_holm | verdict |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in paired_rows:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                 % (r[2], r[3], r[4], r[5], _fmt(r[6]), _fmt(r[7]),
                    _fmt(r[9]), _fmt(r[10]), r[13]))
    MC.write_text(path, "\n".join(L) + "\n")
    return path


# -------------------------------------------------------------------- CLI ----
def main(argv=None):
    ap = argparse.ArgumentParser(description="episode-grain ranking round")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--view", action="store_true")
    ap.add_argument("--validate-ranking", dest="validate", action="store_true")
    ap.add_argument("--emit-ranking", dest="emit_ranking", default=None,
                    choices=(ARM_CHRONO, ARM_CLASS, ARM_SIZE))
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--era", default=None)
    ap.add_argument("--date8", type=int, default=None)
    ap.add_argument("--assets", default=",".join(MC.ASSET_ORDER))
    ap.add_argument("--episode", default=None)
    ap.add_argument("--sheet-source", dest="sheet_source", default="render",
                    choices=("render", "corpus"))
    ap.add_argument("--mode", default=MC.MODE_BLIND, choices=list(MC.MODES))
    ap.add_argument("--ranking", action="append", default=[],
                    help="PATH (with --validate-ranking / --emit-ranking) or "
                         "DATE8=PATH (with --score)")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--round", dest="round_name", default="-")
    ap.add_argument("--caller", default="-")
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--root", default=None,
                    help="alternative episode_round tree (index + ledger)")
    a = ap.parse_args(argv)

    if a.root:
        set_root(a.root)

    if a.build:
        assets = [x for x in a.assets.split(",") if x]
        eps, rec = build(a.era, a.date8, assets)
        sys.stderr.write(
            "episode_round build %s %d: %d episodes over %d candidates "
            "(%.2f cand/episode; %.1f episodes/asset-day; D-080 reference "
            "~%d/day)\n"
            % (a.era, a.date8, rec["n_episodes"], rec["n_candidates"],
               rec["candidates_per_episode"],
               rec["episodes_per_asset_day_mean"],
               rec["d080_reference_episodes_per_day"]))
        for asset in sorted(rec["per_asset"]):
            v = rec["per_asset"][asset]
            sys.stderr.write("  %-4s n_candidates=%d n_episodes=%d\n"
                             % (asset, v["n_candidates"], v["n_episodes"]))
        sys.stdout.write(rec["index"] + "\n")
        return 0

    if a.view:
        if not a.episode:
            sys.stderr.write("--view needs --episode\n")
            return 2
        try:
            v = view(a.episode, mode=a.mode, sheet_source=a.sheet_source,
                     round_name=a.round_name, caller=a.caller,
                     ledger=a.ledger)
        except (SH.S14AccessRefusal, EpisodeRefusal, MC.LeakRefusal) as e:
            # a refused view is a VALUE: named, exit-coded, and NOT ledgered —
            # so the day stays unscoreable until the episode is really read
            sys.stderr.write("REFUSED %s: %s\n" % (type(e).__name__, e))
            return 3
        sys.stdout.write(v["text"])
        return 0

    if a.emit_ranking:
        p = emit_ranking(a.era, a.date8, a.emit_ranking,
                         a.ranking[0] if a.ranking else
                         os.path.join(index_dir(a.era),
                                      "EPISODE_RANKING_%s_%08d.tsv"
                                      % (a.era, a.date8)))
        sys.stdout.write(p + "\n")
        return 0

    if a.validate:
        eps = load_episodes(a.era, a.date8)
        try:
            r = validate_ranking(eps, read_ranking(a.ranking[0]))
        except RankingRefusal as e:
            sys.stderr.write("RANKING REFUSED: %s\n" % e)
            return 3
        sys.stderr.write("ranking OK: n_ranked=%d n_abstain=%d over %d "
                         "episodes\n" % (r["n_ranked"], r["n_abstain"],
                                         len(eps)))
        return 0

    if a.score:
        rk = {}
        for item in a.ranking:
            d, _sep, p = item.partition("=")
            if not p:
                sys.stderr.write("--score wants --ranking DATE8=PATH\n")
                return 2
            rk[int(d)] = p
        try:
            res = score(a.era, rk, outdir=a.outdir,
                        round_name=(None if a.round_name == "-"
                                    else a.round_name),
                        ledger=a.ledger)
        except (AccessRefusal, RankingRefusal) as e:
            sys.stderr.write("REFUSED %s: %s\n" % (type(e).__name__, e))
            return 3
        sys.stderr.write("scored %d day(s) -> %s\n"
                         % (res["receipt"]["n_days"],
                            res["receipt"]["outputs"]["score"]))
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
