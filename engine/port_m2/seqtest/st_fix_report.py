#!/usr/bin/python3
"""PORT M2 FIXPASS2 — THE ONE RE-EVALUATION.

Every arm this workspace has ever committed for this question — the first
pass's and this pass's — scored on the IDENTICAL schedule: `m3_walk`'s
deployable arm verbatim (top-3 per asset-day, D-077-UPDATE news veto, one
position per asset-session, chronological walled phase-close replay), pooled
over E3..E8, CR1 intervals clustered by DAY.  The only thing that differs
between rows is the SCORE.

Two reading forms are reported for every model that has two heads, because the
champion's headline is the PRIMARY form and the sequence stack's is COMPOSED:

  PRIMARY   the champion head alone (`y_retg_rank_phase`)
  COMPOSED  m3_walk's construction: within-(asset,session) percentile of each
            head, rank-summed

Run:  st_fix_report.py --all
"""
import argparse
import glob
import json
import os
import time

import numpy as np

import st_common as SC
import st_run as R
import st_sched as SD
import st_tok2 as TK2
import m3_common as M3

# THE SCHEDULE (coordinator correction, 2026-08-15).  The first pass and the
# first draft of this one scored through a FIXED top-3-per-asset-DAY schedule
# that forfeits 63-65% of its own takes to same-session position collisions —
# on it, perfect foresight lands BELOW the $2,000 bar.  The committed m3
# harness selects (unit, N) on its own inner validation block and lands on the
# (asset, PHASE) CELL at N=1, forfeit 0.1%, foresight $3,344 = 1.67x the bar.
# EVERY row below is seated on the harness's own per-era policy, read out of
# the committed walk.summary.json.  Nothing is refitted; the identical
# out-of-sample score columns are re-seated.
_POLICY = {}


def policy_for(era):
    if not _POLICY:
        _POLICY.update(SD.committed_policy())
    return _POLICY.get(era, ("cell", 1))

OUT = SC.OUT_DIR

# reference arms that are not model scores
REFERENCE = ("FORESIGHT_NONCAUSAL", "BASE_EARLIEST", "RANDOM_SEEDED")


def _load(D, tag):
    z = np.load(os.path.join(R.SCORE_DIR, "%s.npz" % tag))
    champ, win = z["champ"], z["win"]
    z.close()
    return champ, win


def score_form(D, champ, win, ceil, pos, form, test_eras=SC.TEST_ERAS):
    per, parts = [], []
    for era in test_eras:
        ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
        ev = ev[pos[ev] >= 0]
        ev = ev[np.isfinite(champ[ev])]
        if ev.size == 0:
            continue
        s = R.composed(D, champ, win, ev) if form == "composed" else champ
        u, n = policy_for(era)
        a = R.score_arm(D, s, ev, ceil, unit=u, n=n)
        a["era"] = era
        a["policy"] = "%s/%d" % (u, n)
        per.append(a)
        parts.append(a)
    return per, (R.pooled(parts) if parts else None)


def arm_sessions(D, champ, win, ceil, form, test_eras=SC.TEST_ERAS):
    """{session -> realised $} for one arm on the identical schedule."""
    import m3_walk as W
    out = {}
    for era in test_eras:
        ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
        ev = ev[np.isfinite(champ[ev])]
        if ev.size == 0:
            continue
        s = R.composed(D, champ, win, ev) if form == "composed" else champ
        u, n = policy_for(era)
        take = W.topn_takes(D, s, ev, n, deployable=True, unit=u)
        for r in W.replay_rows(D, take):
            out[r["session"]] = float(r["realised"])
    return out


def paired_delta(D, ceil, a_tag, a_form, b_tag, b_form):
    """THE TEST THE VERDICT NEEDS.  Two arms are scored on the SAME sessions, so
    the honest question is not whether their two intervals overlap but whether
    their PAIRED per-session difference is distinguishable from zero.  CR1,
    clustered by DAY, on the same bootstrap the rest of the lane uses."""
    import panel_score as PS
    A = arm_sessions(D, *_load(D, a_tag), ceil, a_form)
    B = arm_sessions(D, *_load(D, b_tag), ceil, b_form)
    keys = sorted(set(A) & set(B))
    d = [A[k] - B[k] for k in keys]
    cl = [int(k.split("|")[1]) for k in keys]
    cm = PS.cluster_mean(d, cl) if d else None
    return {"a": "%s/%s" % (a_tag, a_form), "b": "%s/%s" % (b_tag, b_form),
            "n_sessions": len(keys),
            "delta_usd_per_session": cm["mean"] if cm else None,
            "lo": cm["ci_lo"] if cm else None, "hi": cm["ci_hi"] if cm else None,
            "p": cm.get("p") if cm else None}


CHAMPION = ("LMART_HP_NOTF", "primary")   # SEQTEST.md §18, $1,174.01/session


def write_paired(D, ceil, pairs, name="SEQTEST2_PAIRED.tsv"):
    rows = []
    for a_tag, a_form, b_tag, b_form in pairs:
        r = paired_delta(D, ceil, a_tag, a_form, b_tag, b_form)
        rows.append([r["a"], r["b"], r["n_sessions"],
                     R._r(r["delta_usd_per_session"]), R._r(r["lo"]),
                     R._r(r["hi"]),
                     ("%.3g" % r["p"]) if r["p"] is not None else "",
                     "BEATS" if (r["lo"] or 0) > 0 else
                     ("LOSES" if (r["hi"] or 0) < 0 else "INDISTINGUISHABLE")])
        SC.hb("paired %s - %s = %+.2f/session [%+.2f, %+.2f] p=%s"
              % (r["a"], r["b"], r["delta_usd_per_session"] or 0.0,
                 r["lo"] or 0.0, r["hi"] or 0.0, r["p"]))
    return R.write_tsv(name, ["arm_a", "arm_b", "n_sessions",
                              "delta_usd_per_session", "lo", "hi", "p",
                              "verdict"], rows,
                       extra=["THE PAIRED TEST.  Both arms are seated on the "
                              "SAME sessions under the HARNESS'S OWN per-era "
                              "policy, so the difference is measured per "
                              "session and bootstrapped with clusters = DAY "
                              "(CR1) — not read off two overlapping marginal "
                              "intervals.",
                              "verdict=BEATS means the 95% interval of the "
                              "paired difference is entirely above zero.",
                              "The reference arm is the committed champion "
                              "LMART_CELL_ALLDATA (cell-grouped LambdaMART on "
                              "the full prior history, $935.97/session pooled, "
                              "SEQTEST.md §14)."])


def result_meta():
    meta = {}
    for p in sorted(glob.glob(os.path.join(R.RES_DIR, "*.json"))):
        with open(p) as fh:
            o = json.load(fh)
        meta[os.path.basename(p)[:-5]] = o
    return meta


def arms_table(D, ceil, pos, tags=None):
    meta = result_meta()
    rows = []
    tags = tags or sorted(os.path.basename(p)[:-4] for p in
                          glob.glob(os.path.join(R.SCORE_DIR, "*.npz")))
    for tag in tags:
        champ, win = _load(D, tag)
        same = np.array_equal(np.nan_to_num(champ, nan=-1e30),
                              np.nan_to_num(win, nan=-1e30))
        m = meta.get(tag, {})
        forms = ["composed"] if not same else ["primary"]
        if not same:
            forms = ["primary", "composed"]
        for form in forms:
            t0 = time.time()
            per, pool = score_form(D, champ, win, ceil, pos, form)
            if pool is None:
                continue
            upt = [a["usd_per_trade"] for a in per
                   if a["usd_per_trade"] is not None]
            rows.append({
                "arm": tag, "form": form,
                "kind": m.get("kind", ""), "arch": m.get("arch", ""),
                "trunk": m.get("trunk", ""), "tokenizer": m.get("tokenizer", ""),
                "n_sessions": pool["n_sessions"],
                "usd_per_session": pool["usd_per_session"],
                "ps_lo": pool["ps_lo"], "ps_hi": pool["ps_hi"],
                "usd_per_trade": float(np.mean(upt)) if upt else None,
                "capture_oracle": pool["capture_oracle"],
                "co_lo": pool["co_lo"], "co_hi": pool["co_hi"],
                "capture_day": pool["capture_day"],
                "per_era": {a["era"]: a["capture_oracle"] for a in per},
                "policy": "m3_committed (%s)"
                          % ",".join(sorted({a["policy"] for a in per})),
                "secs": round(time.time() - t0, 1)})
            SC.hb("arm %-34s %-8s cap=%.4f [%.4f,%.4f] $%.2f/session"
                  % (tag, form, pool["capture_oracle"] or float("nan"),
                     pool["co_lo"] or float("nan"),
                     pool["co_hi"] or float("nan"),
                     pool["usd_per_session"] or float("nan")))
    return rows


def random_arm(D, ev, ceil, unit, n, draws=SC.N_RANDOM_DRAWS):
    """The seeded random-selection reference, on the harness's own policy."""
    rs = np.random.RandomState(SC.SEED)
    caps, pss, pts = [], [], []
    for _ in range(draws):
        a = R.score_arm(D, rs.rand(D["d8"].size), ev, ceil, unit=unit, n=n)
        caps.append(a["capture_oracle"] or 0.0)
        pss.append(a["usd_per_session"] or 0.0)
        pts.append(a["usd_per_trade"] or 0.0)
    return {"capture_oracle": float(np.mean(caps)),
            "co_lo": float(np.percentile(caps, 2.5)),
            "co_hi": float(np.percentile(caps, 97.5)),
            "usd_per_session": float(np.mean(pss)),
            "usd_per_trade": float(np.mean(pts)),
            "capture_day": None, "ps_lo": None, "ps_hi": None,
            "n_takes": None, "n_seated": None, "_realised": [], "_cl": [],
            "_den_c": [], "_den_o": []}


def reference_rows(D, ceil):
    """FORESIGHT3 / BASE_EARLIEST / RANDOM3 on the same schedule."""
    pos = np.zeros(D["d8"].size, dtype=np.int64)
    out = []
    parts = {k: [] for k in REFERENCE}
    for era in SC.TEST_ERAS:
        ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
        u, n = policy_for(era)
        for k, v in (("FORESIGHT_NONCAUSAL",
                      R.score_arm(D, D["cert_close_usd"], ev, ceil, unit=u,
                                  n=n)),
                     ("BASE_EARLIEST", R.base_earliest(D, ev, ceil)),
                     ("RANDOM_SEEDED", random_arm(D, ev, ceil, u, n))):
            v["era"] = era
            parts[k].append(v)
    for k in ("FORESIGHT_NONCAUSAL", "BASE_EARLIEST"):
        pool = R.pooled(parts[k])
        upt = [a["usd_per_trade"] for a in parts[k]
               if a.get("usd_per_trade") is not None]
        out.append({"arm": k, "form": "reference", "kind": "reference",
                    "arch": "", "trunk": "", "tokenizer": "",
                    "n_sessions": pool["n_sessions"],
                    "usd_per_session": pool["usd_per_session"],
                    "ps_lo": pool["ps_lo"], "ps_hi": pool["ps_hi"],
                    "usd_per_trade": float(np.mean(upt)) if upt else None,
                    "capture_oracle": pool["capture_oracle"],
                    "co_lo": pool["co_lo"], "co_hi": pool["co_hi"],
                    "capture_day": pool["capture_day"],
                    "per_era": {a["era"]: a["capture_oracle"]
                                for a in parts[k]}, "secs": 0})
    c = [a["capture_oracle"] for a in parts["RANDOM_SEEDED"]]
    out.append({"arm": "RANDOM_SEEDED", "form": "reference", "kind": "reference",
                "arch": "200 seeded draws", "trunk": "", "tokenizer": "",
                "n_sessions": None,
                "usd_per_session": float(np.mean(
                    [a["usd_per_session"] for a in parts["RANDOM_SEEDED"]])),
                "ps_lo": None, "ps_hi": None,
                "usd_per_trade": float(np.mean(
                    [a["usd_per_trade"] for a in parts["RANDOM_SEEDED"]])),
                "capture_oracle": float(np.mean(c)),
                "co_lo": float(np.min(c)), "co_hi": float(np.max(c)),
                "capture_day": None,
                "per_era": {a["era"]: a["capture_oracle"]
                            for a in parts["RANDOM_SEEDED"]}, "secs": 0})
    return out


def write_arms(rows, name="SEQTEST2_ARMS.tsv"):
    rows = sorted(rows, key=lambda r: -(r["capture_oracle"] or -9))
    cols = ["arm", "form", "kind", "arch", "trunk", "tokenizer", "policy",
            "n_sessions",
            "usd_per_session", "ps_lo", "ps_hi", "usd_per_trade",
            "capture_oracle", "co_lo", "co_hi", "capture_day"] \
        + list(SC.TEST_ERAS)
    out = []
    for r in rows:
        out.append([r["arm"], r["form"], r["kind"], r["arch"], r["trunk"],
                    r["tokenizer"], r.get("policy", "m3_committed"),
                    r["n_sessions"],
                    R._r(r["usd_per_session"]), R._r(r["ps_lo"]),
                    R._r(r["ps_hi"]), R._r(r["usd_per_trade"]),
                    R._r(r["capture_oracle"], 4), R._r(r["co_lo"], 4),
                    R._r(r["co_hi"], 4), R._r(r["capture_day"], 4)]
                   + [R._r(r["per_era"].get(e), 4) for e in SC.TEST_ERAS])
    return R.write_tsv(name, cols, out, extra=[
        "THE ONE RE-EVALUATION (fix pass 2).  Every arm on the IDENTICAL "
        "schedule: the schedule the M3 HARNESS ITSELF selects per era on its "
        "own inner validation block (the (asset,PHASE) CELL at N=1), read out "
        "of the committed walk.summary.json, with the D-077-UPDATE veto and "
        "the one-position chronological walled phase-close replay.",
        "The fixed top-3-per-asset-DAY schedule used by the first pass "
        "forfeits 63-65% of its takes and is NOT used here "
        "(provenance/port_m2/SEQTEST_SCHEDULE_ALERT.md).",
        "capture_oracle is pooled over E3..E8 with CR1 intervals clustered by "
        "DAY; the per-era columns are the same statistic per fold.",
        "form=primary is the champion head alone; form=composed is m3_walk's "
        "rank-sum of the two heads.  A single-head arm (a ranker) has one row."])


def write_pretrain(name="SEQTEST2_PRETRAIN.tsv"):
    import st_pretrain as P
    rows = []
    for p in sorted(glob.glob(os.path.join(P.TRUNK_DIR, "*.json"))):
        with open(p) as fh:
            i = json.load(fh)
        rows.append([i.get("tag"), i.get("tokenizer", "v1"),
                     i.get("vocab", 3152), i.get("multi_horizon"),
                     i.get("cpc_weight", 0.20 if i.get("multi_horizon")
                           else 0.0),
                     i.get("steps_run"), i.get("wall_sec"),
                     R._r(i.get("best_val_next"), 4),
                     R._r(i.get("best_val_ppl"), 2),
                     R._r(i.get("bigram_val_loss"), 4),
                     R._r(i.get("unigram_entropy_nats"), 4),
                     i.get("beats_bigram"), i.get("overfit_gate_fired"),
                     i.get("truncated"),
                     json.dumps(i.get("head_loss_last200", {}))])
    return R.write_tsv(name, ["trunk", "tokenizer", "vocab", "multi_horizon",
                              "cpc_weight", "steps", "wall_sec",
                              "val_next", "val_ppl", "bigram_floor",
                              "unigram_floor", "beats_bigram",
                              "overfit_gate_fired", "truncated",
                              "head_loss_last200"], rows,
                       extra=["Every trunk this lane has trained, V1 and the "
                              "F1-repaired V2 grid, with its own gates.",
                              "The floors are RECOMPUTED per vocabulary: a V2 "
                              "perplexity against a V1 floor would not be a "
                              "comparison."])


def write_ranking(name="SEQTEST2_RANKING.tsv"):
    meta = result_meta()
    rows = []
    for tag, m in sorted(meta.items()):
        if m.get("kind") not in ("rank", "rank2"):
            continue
        for L in m.get("ledger", []):
            rows.append([tag, m.get("group", "class"), m.get("mode"),
                         m.get("trunk"), m.get("hardneg", 0),
                         m.get("daymem", False), m.get("use_creator", False),
                         L.get("era"), L.get("loss"),
                         R._r(L.get("eval_ndcg3_day",
                                    L.get("eval_ndcg3")), 4),
                         R._r(L.get("eval_ndcg3_class",
                                    L.get("eval_ndcg3")), 4),
                         R._r(L.get("eval_ndcg3_random_day",
                                    L.get("eval_ndcg3_random")), 4),
                         R._r(L.get("eval_ndcg3_random_class",
                                    L.get("eval_ndcg3_random")), 4),
                         R._r(L.get("eval_ndcg3_earliest_day",
                                    L.get("eval_ndcg3_earliest")), 4),
                         L.get("n_groups_eval"), L.get("n_eval")])
        p = m.get("pooled") or {}
        rows.append([tag, m.get("group", "class"), m.get("mode"),
                     m.get("trunk"), m.get("hardneg", 0),
                     m.get("daymem", False), m.get("use_creator", False),
                     "POOLED", "", "", "", "", "", "",
                     R._r(p.get("capture_oracle"), 4),
                     R._r(p.get("usd_per_session"))])
    return R.write_tsv(name, ["arm", "group", "mode", "trunk", "hardneg",
                              "daymem", "creator26", "era", "loss",
                              "ndcg3_day", "ndcg3_class", "ndcg3_random_day",
                              "ndcg3_random_class", "ndcg3_earliest_day",
                              "n_groups_eval", "n_eval"], rows,
                       extra=["F3: the DEPLOY-MATCHED objective.  group=day is "
                              "the schedule's own selection unit (score all "
                              "candidates of an asset-day, take 3 across it); "
                              "group=class is the first pass's "
                              "(asset,day,class) form, carried as the matched "
                              "control.",
                              "The POOLED row's last two columns are "
                              "capture_oracle and $/session, not NDCG."])


def write_champion(name="SEQTEST2_CHAMPION.tsv"):
    meta = result_meta()
    rows = []
    for tag, m in sorted(meta.items()):
        if m.get("kind") != "champion":
            continue
        p = m.get("pooled") or {}
        gs = [L.get("gain_share_creator_y_retg_rank_phase")
              for L in m.get("ledger", []) if
              L.get("gain_share_creator_y_retg_rank_phase") is not None]
        rows.append([tag, m.get("n_features"), m.get("label"),
                     m.get("label_winner_n"), m.get("label_winner_rate"),
                     R._r(np.mean(gs), 4) if gs else "",
                     R._r(p.get("capture_oracle"), 4), R._r(p.get("co_lo"), 4),
                     R._r(p.get("co_hi"), 4), R._r(p.get("usd_per_session")),
                     json.dumps(m.get("mae_cap_usd", {}))])
    return R.write_tsv(name, ["arm", "n_features", "label", "winner_set_size",
                              "winner_rate", "creator_gain_share",
                              "capture_oracle_composed", "co_lo", "co_hi",
                              "usd_per_session", "mae_cap_usd"], rows,
                       extra=["F5: the CHAMPION UPGRADES.  +26 census-surviving "
                              "creator detectors as matrix columns, and the "
                              "D-021 MAE-cap label variant (18-tick dip q75: "
                              "SI/NKD $450, HG $225) as an alternative TARGET "
                              "COLUMN — never a contract change (D-029).",
                              "The dollars are the same replayed certificate "
                              "dollars for every row, so the label variant is "
                              "scored on exactly the same money."])


def write_transfer(name="SEQTEST2_TRANSFER.tsv"):
    meta = result_meta()
    rows = []
    for tag, m in sorted(meta.items()):
        if m.get("kind") not in ("ft2", "probe"):
            continue
        p = m.get("pooled") or {}
        L = m.get("ledger", [])
        rows.append([tag, m.get("kind"), m.get("trunk"),
                     m.get("tokenizer", "v1"), m.get("mode"),
                     m.get("pooling", "lastmean"),
                     m.get("unfreeze_top", 0), m.get("lora_rank", 0),
                     m.get("lldecay", ""), m.get("daymem", False),
                     int(np.mean([x.get("n_trainable", 0) for x in L]))
                     if L and "n_trainable" in L[0] else "",
                     R._r(np.mean([x.get("inner_rho", np.nan) for x in L]), 4)
                     if L else "",
                     R._r(np.mean([x.get("eval_auc_winner", np.nan)
                                   for x in L]), 4) if L else "",
                     R._r(p.get("capture_oracle"), 4), R._r(p.get("co_lo"), 4),
                     R._r(p.get("co_hi"), 4), R._r(p.get("usd_per_session"))])
    return R.write_tsv(name, ["arm", "kind", "trunk", "tokenizer", "mode",
                              "pooling", "unfreeze_top", "lora_rank",
                              "lldecay", "daymem", "n_trainable_params",
                              "mean_inner_rho", "mean_eval_auc_winner",
                              "capture_oracle", "co_lo", "co_hi",
                              "usd_per_session"], rows,
                       extra=["F2: REAL TRANSFER.  kind=probe is the FROZEN "
                              "trunk (the first pass's mechanism, and the "
                              "named confound on the R4 tag); kind=ft2 is the "
                              "partial fine-tune / LoRA that replaces it.",
                              "A frozen row and a fine-tuned row on the SAME "
                              "trunk isolate the transfer mechanism; a V1 row "
                              "and a V2 row on the same mechanism isolate the "
                              "tokenizer repair."])


def write_moment(D, tags, name="SEQTEST2_MOMENT.tsv"):
    """THE MOMENT LAYER, re-isolated for the fix pass's arms: the episode is
    held FIXED and the only choice is which second inside it — the arm's argmax
    against the EARLIEST actable member, which is what the reader takes."""
    rows = []
    for tag, form in tags:
        champ, win = _load(D, tag)
        for era in SC.TEST_ERAS:
            ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
            ev = ev[np.isfinite(champ[ev])]
            if ev.size == 0:
                continue
            s = R.composed(D, champ, win, ev) if form == "composed" else champ
            m = R.moment_gain(D, s, ev, tag, era)
            rows.append([tag, form, era, m["n_episodes"],
                         R._r(m["earliest_usd_per_ep"]),
                         R._r(m["model_usd_per_ep"]),
                         R._r(m["gain_usd_per_ep"]), R._r(m["gain_lo"]),
                         R._r(m["gain_hi"]),
                         ("%.3g" % m["gain_p"]) if m["gain_p"] is not None
                         else ""])
            SC.hb("moment %s %s %s: %+.2f/ep" % (tag, form, era,
                                                 m["gain_usd_per_ep"] or 0.0))
    # the non-causal ceiling, on the same episodes
    for era in SC.TEST_ERAS:
        ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
        m = R.moment_gain(D, D["cert_close_usd"], ev, "FORESIGHT", era)
        rows.append(["FORESIGHT_NONCAUSAL", "ceiling", era, m["n_episodes"],
                     R._r(m["earliest_usd_per_ep"]),
                     R._r(m["model_usd_per_ep"]), R._r(m["gain_usd_per_ep"]),
                     R._r(m["gain_lo"]), R._r(m["gain_hi"]), ""])
    return R.write_tsv(name, ["arm", "form", "era", "n_episodes",
                              "earliest_usd_per_ep", "model_usd_per_ep",
                              "gain_usd_per_ep", "gain_lo", "gain_hi",
                              "gain_p"], rows,
                       extra=["The episode is FIXED (the frozen `ep`); the only "
                              "choice is which second inside it.  "
                              "Multi-member episodes only, D-077 veto applied, "
                              "CIs clustered by DAY."])


def write_occupancy(name="SEQTEST2_TOKEN_OCCUPANCY.tsv"):
    with open(TK2.CUTS_PATH) as fh:
        cuts = json.load(fh)
    return R.write_tsv(name, ["field", "bucket", "n_events", "mass_fraction",
                              "n_vocab_cells"], TK2.occupancy_rows(),
                       extra=["F1: the R1/R6 REPAIR, measured.  The first "
                              "pass's price axis put 93.31% of 1.43B events in "
                              "ONE bucket; this vocabulary's largest price "
                              "bucket is reported above.",
                              "The mechanism: the L1 mid moves in HALF ticks "
                              "and the V1 bucketing was cut in whole ticks.",
                              "per-asset cuts (fitted on d8<20240101 ONLY): "
                              + json.dumps({a: v["qhi"] for a, v
                                            in cuts["assets"].items()}),
                              cuts["rule"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--arms", action="store_true")
    ap.add_argument("--tables", action="store_true")
    ap.add_argument("--moment", default="")
    ap.add_argument("--paired", default="")
    a = ap.parse_args()
    import m3_walk as W
    if a.all or a.tables:
        write_occupancy()
        write_pretrain()
        write_champion()
        write_ranking()
        write_transfer()
    if a.all or a.arms:
        D, _p = W.load_matrix()
        ceil = R.ceilings_of(D)
        pos = np.zeros(D["d8"].size, dtype=np.int64)
        rows = arms_table(D, ceil, pos) + reference_rows(D, ceil)
        with open(os.path.join(SC.CACHE_ROOT, "fixpass2_arms.json"), "w") as fh:
            json.dump(rows, fh, indent=1, default=str)
        write_arms(rows)
    if a.paired:
        D, _p = W.load_matrix()
        ceil = R.ceilings_of(D)
        base = a.paired.split("|")[0]
        bt, bf = base.split(":")
        pairs = [tuple(x.split(":")) + (bt, bf)
                 for x in a.paired.split("|")[1].split(",") if x]
        write_paired(D, ceil, pairs)
    if a.moment:
        D, _p = W.load_matrix()
        tags = [tuple(x.split(":")) if ":" in x else (x, "composed")
                for x in a.moment.split(",") if x]
        write_moment(D, tags)
    if not (a.all or a.arms or a.tables or a.moment):
        ap.print_help()


if __name__ == "__main__":
    main()
