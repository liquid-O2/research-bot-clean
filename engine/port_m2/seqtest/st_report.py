#!/usr/bin/python3
"""PORT M2 SEQTEST — assemble every committed result into the deliverable TSVs.

Reads `artifacts/cache/port/m2/seqtest/results/*.json` (one file per ladder
config, control, pretrain stage and arms table) and writes:

    SEQTEST_CAPACITY.tsv   the length x capacity ladder — the curve that tells
                           a weak model apart from an absent signal
    SEQTEST_ARMS.tsv       every arm on the identical schedule, per era + pooled
    SEQTEST_MOMENT.tsv     the moment layer isolated (episode fixed)
    SEQTEST_HYBRID.tsv     the marginal value of the sequence logits on the
                           frozen m3 matrix
    SEQTEST_LADDER.tsv     per-fold training ledger with GPU wall times
"""
import os

import json

import numpy as np

import st_common as SC
import st_run as R


def _r(v, nd=2):
    return R._r(v, nd)


def capacity_rows(res):
    rows = []
    for o in res:
        if o.get("kind") not in ("ladder", "control", "pretrain", "probe",
                                 "rank"):
            continue
        p = o["pooled"]
        led = o.get("ledger") or []
        secs = [x.get("fit_secs", 0) for x in led]
        pars = led[0].get("params") if led else None
        rows.append([
            ("SHUFFLED_CONTROL" if o.get("shuffled") else
             {"pretrain": "PRETRAINED", "probe": "PROBE", "rank": "LISTWISE"}
             .get(o.get("kind"), "SUPERVISED")),
            o.get("_name", ""), o["arch"], o["rung"], o["L"], pars,
            _r(p.get("capture_oracle"), 4), _r(p.get("co_lo"), 4),
            _r(p.get("co_hi"), 4), _r(p.get("capture_day"), 4),
            _r(p.get("usd_per_session")), _r(p.get("ps_lo")),
            _r(p.get("ps_hi")),
            _r(np.mean([x.get("eval_auc_winner", np.nan) for x in led]), 4)
            if led else "",
            _r(np.mean([x.get("inner_rho", np.nan) for x in led]), 5)
            if led else "",
            _r(np.sum(secs) / 60.0, 1), _r(o.get("wall_secs", 0) / 60.0, 1)])
    rows.sort(key=lambda r: (r[0], r[2], SC.RUNGS.index(r[3])
                             if r[3] in SC.RUNGS else 9, r[4]))
    return rows


def ladder_rows(res):
    rows = []
    for o in res:
        if o.get("kind") not in ("ladder", "control", "pretrain", "probe",
                                 "rank"):
            continue
        tag = "%s_%s_%s_L%d" % ("SHUF" if o.get("shuffled") else
                                {"pretrain": "PRE", "probe": "PROBE",
                                 "rank": "RANK"}.get(o["kind"], "SUP"),
                                o["arch"], o["rung"], o["L"])
        for x in o.get("ledger", []):
            rows.append([tag, x.get("era"), x.get("params"), x.get("n_train"),
                         x.get("n_inner_train"), x.get("n_inner_val"),
                         x.get("n_eval"), x.get("train_days"),
                         x.get("eval_days"), _r(x.get("inner_rho"), 5),
                         x.get("best_epoch"),
                         _r(x.get("eval_auc_winner"), 4),
                         _r(x.get("fit_secs"), 1)])
    return rows


ARM_COLS = ["arm", "era", "n_takes", "n_seated", "usd_per_session", "ps_lo",
            "ps_hi", "usd_per_trade", "pt_lo", "pt_hi", "frac_ge_1000",
            "capture_day", "capture_oracle", "co_lo", "co_hi", "auc_winner"]


def arm_rows(res):
    rows = []
    for o in res:
        if o.get("kind") != "arms":
            continue
        for nm, era, a, u in o["arms"]:
            rows.append([nm, era, a.get("n_takes"), a.get("n_seated"),
                         _r(a.get("usd_per_session")), _r(a.get("ps_lo")),
                         _r(a.get("ps_hi")), _r(a.get("usd_per_trade")),
                         _r(a.get("pt_lo")), _r(a.get("pt_hi")),
                         _r(a.get("frac_ge_1000"), 4),
                         _r(a.get("capture_day"), 4),
                         _r(a.get("capture_oracle"), 4), _r(a.get("co_lo"), 4),
                         _r(a.get("co_hi"), 4), _r(u, 4)])
        for nm, p in sorted(o.get("pooled", {}).items()):
            rows.append([nm, "POOLED_E3-E8", "", "", _r(p.get("usd_per_session")),
                         _r(p.get("ps_lo")), _r(p.get("ps_hi")), "", "", "", "",
                         _r(p.get("capture_day"), 4),
                         _r(p.get("capture_oracle"), 4), _r(p.get("co_lo"), 4),
                         _r(p.get("co_hi"), 4), ""])
    rows.append(["TEACHER_CHANNEL_REFERENCE", "E6_study+blind", 15, 15, "", "",
                 "", 299.0, "", "", "", "", 0.153, -0.022, "", ""])
    return rows


def moment_rows(res):
    rows = []
    for o in res:
        if o.get("kind") != "arms":
            continue
        for m in o.get("moment", []):
            rows.append([m["arm"], m["era"], m["n_episodes"],
                         _r(m["earliest_usd_per_ep"]), _r(m["model_usd_per_ep"]),
                         _r(m["gain_usd_per_ep"]), _r(m["gain_lo"]),
                         _r(m["gain_hi"]),
                         ("" if m.get("gain_p") is None
                          else "%.4g" % float(m["gain_p"])),
                         _r(m["d_frac_ge_1000"], 4), _r(m["dfg_lo"], 4),
                         _r(m["dfg_hi"], 4)])
    return rows


def hybrid_rows(res):
    rows = []
    for o in res:
        if o.get("kind") != "arms":
            continue
        rows += o.get("hybrid", [])
    return rows


def rank_rows(res):
    rows = []
    for o in res:
        if o.get("kind") != "rank":
            continue
        for x in o.get("ledger", []):
            rows.append([o.get("_name", o["arch"]), o.get("trunk"), x["era"],
                         x["loss"],
                         _r(x.get("inner_ndcg3"), 5),
                         _r(x.get("eval_ndcg3"), 5),
                         _r(x.get("eval_ndcg3_random"), 5),
                         _r(x.get("eval_ndcg3_earliest"), 5),
                         x.get("n_groups_train"), x.get("n_groups_eval"),
                         x.get("median_group"), x.get("n_scored_groups"),
                         _r(x.get("fit_secs"), 1),
                         json.dumps(x.get("loss_curve"))])
    return rows


def pretrain_rows():
    """The pretraining quality-gate curves, straight off the trunk receipts."""
    import st_pretrain as P
    curve, summ = [], []
    d = P.TRUNK_DIR
    if not os.path.isdir(d):
        return curve, summ
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        with open(os.path.join(d, f)) as fh:
            o = json.load(fh)
        tag = o.get("tag", f[:-5])
        for row in o.get("val_curve", []):
            step, tr, va, per, secs = row
            curve.append([tag, step, _r(tr, 5), _r(va, 5),
                          _r(va - tr, 5)] +
                         [_r(per.get(a), 5) for a in ("SI", "HG", "NKD")]
                         + [_r(secs, 1)])
        hl = o.get("head_loss_last200", {}) or {}
        hf = o.get("head_loss_first200", {}) or {}
        summ.append([tag, o.get("multi_horizon"), o.get("scope"),
                     o.get("params"), o.get("steps_run"),
                     o.get("truncated"), _r(o.get("wall_sec"), 1),
                     _r(o.get("measured_tokens_per_sec"), 0),
                     _r(o.get("implied_tflops"), 1),
                     _r(o.get("loss_first200"), 4), _r(o.get("loss_last200"), 4),
                     _r(o.get("best_val_next"), 4), _r(o.get("best_val_ppl"), 3),
                     o.get("best_val_step"),
                     _r(o.get("bigram_val_loss"), 4),
                     _r(o.get("bigram_val_ppl"), 3),
                     _r(o.get("unigram_entropy_nats"), 4),
                     o.get("beats_bigram"), o.get("overfit_gate_fired"),
                     json.dumps({k: round(float(v), 5) for k, v in hf.items()}),
                     json.dumps({k: round(float(v), 5) for k, v in hl.items()})])
    return curve, summ


def main():
    res = R.load_results()
    pc, ps = pretrain_rows()
    R.write_tsv("SEQTEST_PRETRAIN_CURVE.tsv",
                ["trunk", "step", "train_next", "val_next", "val_minus_train",
                 "val_SI", "val_HG", "val_NKD", "secs"], pc,
                extra=["THE PRETRAIN QUALITY GATE: a HELD-OUT-DAY split of the "
                       "pretraining objective itself (whole days, all assets, "
                       "never trained on).",
                       "The overfit gate stops the run and reverts to the "
                       "best-val checkpoint if val rises on two consecutive "
                       "evaluations; checkpoint selection is by VAL, never by "
                       "train loss.",
                       "Per-asset columns exist because a backbone that only "
                       "learned SI fails the shared-arm reading (matrix "
                       "signature R5)."])
    R.write_tsv("SEQTEST_PRETRAIN.tsv",
                ["trunk", "multi_horizon", "scope", "params", "steps_run",
                 "truncated", "wall_sec", "tokens_per_sec", "tflops",
                 "loss_first200", "loss_last200", "best_val_next",
                 "best_val_ppl", "best_val_step", "bigram_val_loss",
                 "bigram_val_ppl", "unigram_entropy", "beats_bigram",
                 "overfit_gate_fired", "head_loss_first200",
                 "head_loss_last200"], ps,
                extra=["One row per pretrained trunk.  `bigram_val_ppl` is the "
                       "'did it actually learn structure' floor: a "
                       "Laplace-smoothed bigram fitted on the training chunks "
                       "and scored on the held-out days.",
                       "`head_loss_*` carries every head of the multi-horizon "
                       "objective (next / h60 / h300 / cpc64 / cpc256)."])
    R.write_tsv("SEQTEST_RANKING.tsv",
                ["arch", "trunk", "era", "loss_selected", "inner_ndcg3",
                 "eval_ndcg3", "eval_ndcg3_random", "eval_ndcg3_earliest",
                 "n_groups_train", "n_groups_eval", "median_group_size",
                 "n_scored_groups", "fit_secs", "loss_curve"],
                rank_rows(res),
                extra=["THE MEMBER-RANKING HEAD: listwise over GROUPS = "
                       "(asset, day, CLASS), target = the certificate dollars.",
                       "`loss_selected` is chosen on the training block's "
                       "inner-validation days by NDCG@3 and nowhere else; "
                       "`loss_curve` carries both candidates' inner scores.",
                       "NDCG@3 gain = max(cert_close_usd, 0); the random and "
                       "earliest-member columns are the two references the "
                       "ranker has to beat to be worth anything."])
    R.write_tsv("SEQTEST_CAPACITY.tsv",
                ["mode", "run", "arch", "rung", "seq_len", "params",
                 "capture_oracle", "co_lo", "co_hi", "capture_day",
                 "usd_per_session", "ps_lo", "ps_hi", "mean_auc_winner",
                 "mean_inner_rho", "train_minutes", "wall_minutes"],
                capacity_rows(res),
                extra=["THE PRE-REGISTERED LADDER: window length x capacity, "
                       "every cell a full walk-forward run of six whole-day "
                       "folds (train E2..Ek -> test E(k+1)).",
                       "Pooled over E3..E8 (E8 = the GATE-2025H1 echo), scored "
                       "through the identical top-3/asset-day schedule, CIs "
                       "CR1 clustered by DAY.",
                       "A rung is climbed only while honest capture improves; "
                       "the whole curve is printed so a weak model and an "
                       "absent signal are told apart by the shape."])
    R.write_tsv("SEQTEST_LADDER.tsv",
                ["config", "era", "params", "n_train", "n_inner_train",
                 "n_inner_val", "n_eval", "train_days", "eval_days",
                 "inner_rho", "best_epoch", "eval_auc_winner", "fit_secs"],
                ladder_rows(res),
                extra=["Per-fold training ledger.  `fit_secs` is the wall time "
                       "of the fold (inner-selection run + full-block refit + "
                       "scoring) on the RTX PRO 6000."])
    R.write_tsv("SEQTEST_ARMS.tsv", ARM_COLS, arm_rows(res),
                extra=["Every arm scored through the m3_walk DEPLOYABLE arm "
                       "VERBATIM: top-3 per asset-day, D-077-UPDATE news veto "
                       "ON, one-position chronological walled phase-close "
                       "replay.  Only the SCORE differs.",
                       "CIs are CR1, clustered by DAY.  FORESIGHT3_NONCAUSAL is "
                       "the schedule's own ceiling and is not a result.",
                       "TEACHER_CHANNEL_REFERENCE is NOT identically scored: 15 "
                       "sealed hand takes over E6 study/blind days, +$299/trade, "
                       "~40-47% precision, capture 0.153 (round 1, n=22 takes) "
                       "and -0.022 (round 2, n=3) — provenance JOURNAL "
                       "2026-08-15 22:00Z and INFO_CEILING.md S2."])
    R.write_tsv("SEQTEST_MOMENT.tsv",
                ["arm", "era", "n_episodes", "earliest_usd_per_ep",
                 "model_usd_per_ep", "gain_usd_per_ep", "gain_lo", "gain_hi",
                 "gain_p", "d_frac_ge_1000", "dfg_lo", "dfg_hi"],
                moment_rows(res),
                extra=["THE MOMENT LAYER ISOLATED: episode FIXED (the frozen "
                       "`ep`), the only choice is which SECOND inside it — the "
                       "model's argmax vs the EARLIEST actable member, which is "
                       "what the reader takes and what BASE_EARLIEST replays.",
                       "Multi-candidate episodes only, D-077 veto applied, CIs "
                       "CR1 clustered by DAY."])
    R.write_tsv("SEQTEST_HYBRID.tsv",
                ["era", "n_train_rows_with_seq_score", "capture_oracle_GBT",
                 "capture_oracle_HYBRID", "delta_capture", "usd_per_trade_GBT",
                 "usd_per_trade_HYBRID", "delta_usd_per_trade",
                 "seq_cols_gain_share"],
                hybrid_rows(res),
                extra=["THE MARGINAL VALUE OF THE SEQUENCE MODEL ON THE FROZEN "
                       "MATRIX: the same GBT, the same fold, the same committed "
                       "hyper-parameters, plus TWO columns — the sequence "
                       "model's out-of-sample champion and winner logits.",
                       "E3's training block is E2 alone, which has no "
                       "out-of-sample sequence score, so its seq columns are "
                       "entirely typed-missing in training — flagged, not "
                       "hidden."])


if __name__ == "__main__":
    main()
