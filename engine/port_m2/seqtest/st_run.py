#!/usr/bin/python3
"""PORT M2 SEQTEST — the walk-forward ladder, the controls, and the scoring.

    "does a small sequence model reading RAW EVENTS pick better MOMENTS than
     anything measured — at CANDIDATE grain?"

WHAT IS COMPARED, ON ONE SCHEDULE
  Every model arm is scored through the m3_walk deployable arm VERBATIM —
  `topn_takes` (top-3 per asset-day, D-077-UPDATE news veto ON), `replay_rows`
  (one position per asset-session, chronological, walled phase-close
  certificate), `per_trade_stats`, and the day/oracle DP ceilings.  The only
  thing that differs between arms is the SCORE fed to `topn_takes`.

    SEQ         the raw-event model of this lane (cnn|trf x 1M|10M|50M x L)
    GBT         the m3 feature matrix under xgboost, the harness's own model,
                refitted on the SAME folds (E2..Ek -> E(k+1)) at m3's own
                committed per-era hyper-parameters — no new search
    HYBRID      GBT + the sequence model's two out-of-sample logits as TWO
                extra columns on the frozen matrix (the marginal-value diff)
    BASE_EARLIEST  m3_walk.baseline_takes, the frozen zero-intelligence arm
    RANDOM3     200 seeded draws of three candidates per asset-day
    FORESIGHT3  perfect foresight inside the same top-3 schedule (the shape's
                own ceiling)

  The TEACHER channel is carried as a REFERENCE ROW with its committed numbers
  and its n; it is a 15-take sealed hand record and cannot be replayed on this
  schedule, so it is never presented as an identically-scored arm.

THE FOUR CONTROLS (all mandatory, all receipted)
  shuffled-label   the same ladder with the training block's labels permuted;
                   must score ~0 capture.  RED-FIRST: produced and committed
                   BEFORE the real run.
  duplicate-day    a training day injected into the evaluation block must be
                   REFUSED by `st_common.assert_disjoint_days`.
  non-causal era   an evaluation era at or before the training block must be
                   REFUSED by `st_common.assert_causal_era_order`.
  tensor causality every valid cell of every window must predate its decision
                   second (the seconds-to-decision channel is strictly > 0).

STAGES
  --stage control   red-first: the shuffled ladder + all four probes
  --stage ladder    one or more (arch, rung) configs at one window length
  --stage pretrain  masked-event pretraining + fine-tune, vs scratch
  --stage arms      the deliverable table for a chosen config: arms, moment
                    gain, hybrid marginal
  --stage report    assemble every committed result into the TSVs
"""
import os

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import argparse                            # noqa: E402
import glob                                # noqa: E402
import json                                # noqa: E402
import time                                # noqa: E402

import numpy as np                         # noqa: E402
import torch                               # noqa: E402

import st_common as SC                     # noqa: E402
import st_build as SB                      # noqa: E402
import st_model as SM                      # noqa: E402

import m2_common as MC                     # noqa: E402
import m3_common as M3                     # noqa: E402
import m3_walk as W                        # noqa: E402
import m3_matrix as MX                     # noqa: E402
import panel_score as PS                   # noqa: E402

CACHE = SC.CACHE_ROOT
RES_DIR = os.path.join(CACHE, "results")
SCORE_DIR = os.path.join(CACHE, "scores")
DEV = "cuda" if torch.cuda.is_available() else "cpu"

torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
try:
    torch.use_deterministic_algorithms(True, warn_only=True)
except Exception:                          # noqa: BLE001 — older torch
    pass


def gpu_note():
    if DEV != "cuda":
        return {"device": "cpu"}
    p = torch.cuda.get_device_properties(0)
    return {"device": p.name, "vram_gb": round(p.total_memory / 1e9, 1),
            "torch": torch.__version__, "cuda": torch.version.cuda}


# ============================================================ the fixtures ===
_STATE = {}


def load_all(L):
    """The committed m3 matrix + every seqtest shard at window length L."""
    if _STATE.get("L") == L:
        return _STATE["D"], _STATE["SEQ"], _STATE["pos"]
    t0 = time.time()
    D, _p = W.load_matrix()
    n = D["d8"].size
    pos = np.full(n, -1, dtype=np.int64)
    at = 0
    plan = []
    for asset in MC.ASSET_ORDER:
        for era in SC.UNIVERSE_ERAS:
            base = SC.shard_path(asset, era, L)
            if not os.path.exists(base + ".npy"):
                continue
            m = np.load(base + ".meta.npz")
            ri = m["row_idx"]
            plan.append((asset, era, ri, at))
            pos[ri] = np.arange(at, at + ri.size, dtype=np.int64)
            at += int(ri.size)
    SEQ = np.empty((at, SC.N_CH, L), dtype=np.float16)
    for asset, era, ri, off in plan:
        T = np.load(SC.shard_path(asset, era, L) + ".npy", mmap_mode="r")
        SEQ[off:off + ri.size] = T[:ri.size]
        del T
        SC.hb("loaded %s %s (%d rows, %.0fs)" % (asset, era, ri.size,
                                                 time.time() - t0))
    SC.hb("L=%d tensors %d rows (%.1f GB) in %.0fs"
          % (L, at, SEQ.nbytes / 1e9, time.time() - t0))
    _STATE.update({"L": L, "D": D, "SEQ": SEQ, "pos": pos})
    residency(SEQ, L)
    return D, SEQ, pos


def ceilings_of(D):
    p = os.path.join(CACHE, "ceilings.json")
    if os.path.exists(p):
        with open(p) as fh:
            return {k: tuple(v) for k, v in json.load(fh).items()}
    c = W.dp_ceilings(D)
    with open(p, "w") as fh:
        json.dump({k: list(v) for k, v in c.items()}, fh)
    return c


_ORC = {}


def oracle_of(session):
    if session not in _ORC:
        asset, d8 = session.split("|")
        _ORC[session] = W.oracle_ceiling(asset, int(d8))[0]
    return _ORC[session]


# ============================================================== the ladder ===
def fold_rows(D, test_era, from_era="E2"):
    """train <from_era>..Ek -> test E(k+1).  Whole eras, whole days, never
    random.  `from_era="PRE_E1"` reproduces the committed m3 ladder's own
    training block (everything strictly earlier, warm-up tape included)."""
    k = SC.ERA_IDX[test_era]
    lo = -99 if from_era == "PRE_E1" else SC.ERA_IDX[from_era]
    tr = np.nonzero((D["era_idx"] >= lo) & (D["era_idx"] < k))[0]
    ev = np.nonzero(D["era_idx"] == k)[0]
    SC.assert_causal_era_order(tr, ev, D["era_idx"], tag=test_era)
    SC.assert_disjoint_days(tr, ev, D["d8"], tag=test_era)
    return tr, ev


def norm_stats(SEQ, pos, rows, cap=20_000, chunk=2048):
    """Per-channel mean/std fitted on TRAINING rows ONLY (deterministic stride
    subsample, masked to the VALID part of the window).  Two streaming passes,
    so the statistic never needs the whole block resident."""
    r = rows[pos[rows] >= 0]
    step = max(1, int(np.ceil(r.size / float(cap))))
    p = np.sort(pos[r[::step]])
    s1 = torch.zeros(SC.N_CH, dtype=torch.float64, device=DEV)
    s2 = torch.zeros(SC.N_CH, dtype=torch.float64, device=DEV)
    cnt = torch.zeros((), dtype=torch.float64, device=DEV)
    res = _RESIDENT.get("t")
    for a in range(0, p.size, chunk):
        q = p[a:a + chunk]
        if res is not None:
            blk = res.index_select(0, torch.from_numpy(q).to(DEV)).double()
        else:
            blk = torch.from_numpy(SEQ[q]).to(DEV).double()
        m = (blk[:, SC.CH_VALID, :] > 0.5).double()
        cnt += m.sum()
        s1 += (blk * m.unsqueeze(1)).sum(dim=(0, 2))
        s2 += ((blk ** 2) * m.unsqueeze(1)).sum(dim=(0, 2))
        del blk
    denom = torch.clamp(cnt, min=1.0)
    mu = torch.zeros(SC.N_CH, device=DEV)
    sd = torch.ones(SC.N_CH, device=DEV)
    for c in SC.NORM_CH:
        mm = s1[c] / denom
        ss = torch.sqrt(torch.clamp(s2[c] / denom - mm * mm, min=1e-12))
        mu[c] = mm.float()
        sd[c] = torch.clamp(ss.float(), min=1e-3)
    if DEV == "cuda":
        torch.cuda.empty_cache()
    return mu, sd


GPU_RESIDENT_CAP_GB = 60.0
_RESIDENT = {}


def residency(SEQ, L):
    """Put the whole tensor set in VRAM when it fits — the RTX PRO 6000 has
    97 GB, which holds L=256 (12 GB) and L=1024 (48 GB) outright.  L=4096
    (191 GB) stays in host RAM and is gathered per batch."""
    if _RESIDENT.get("L") == L:
        return _RESIDENT.get("t")
    _RESIDENT.clear()
    t = None
    if DEV == "cuda" and SEQ.nbytes / 1e9 <= GPU_RESIDENT_CAP_GB:
        try:
            t0 = time.time()
            t = torch.from_numpy(SEQ).to(DEV)
            SC.hb("tensors resident in VRAM (%.1f GB, %.0fs)"
                  % (SEQ.nbytes / 1e9, time.time() - t0))
        except RuntimeError as e:           # noqa: BLE001 — fall back to host
            SC.hb("VRAM residency refused (%s); gathering from host" % e)
            t = None
    _RESIDENT.update({"L": L, "t": t})
    return t


def _to_gpu(SEQ, pos, rows, mu, sd):
    res = _RESIDENT.get("t")
    if res is not None:
        idx = torch.from_numpy(pos[rows]).to(DEV)
        x = res.index_select(0, idx).float()
    else:
        x = torch.from_numpy(SEQ[pos[rows]]).to(DEV, non_blocking=True).float()
    v = x[:, SC.CH_VALID:SC.CH_VALID + 1, :]
    x = (x - mu[None, :, None]) / sd[None, :, None]
    return x * v                            # every padded cell stays exactly 0


def predict(model, SEQ, pos, rows, mu, sd, bs=2048):
    model.eval()
    out = np.zeros((rows.size, 2), dtype=np.float64)
    with torch.no_grad():
        for a in range(0, rows.size, bs):
            r = rows[a:a + bs]
            with torch.autocast("cuda", dtype=torch.bfloat16,
                                enabled=(DEV == "cuda")):
                o = model(_to_gpu(SEQ, pos, r, mu, sd))
            out[a:a + bs] = o.float().cpu().numpy()
    return out[:, 0], out[:, 1]


def train_model(SEQ, pos, itr, iva, y_c, y_w, arch, rung, L, mu, sd, tag,
                max_epochs, init_state=None):
    model, npar = SM.make(arch, rung, L)
    if init_state is not None:
        missing = model.load_state_dict(init_state, strict=False)
        SC.hb("%s: pretrained init loaded (missing %d)"
              % (tag, len(missing.missing_keys)))
    model = model.to(DEV)
    opt = torch.optim.AdamW(model.parameters(), lr=SC.LR_BY_ARCH[arch],
                            weight_decay=SC.WEIGHT_DECAY)
    rng = np.random.RandomState(SC.SEED)
    bs = SC.BATCH_BY_LEN[L]
    best, best_ep, bad, best_state = -np.inf, 0, 0, None
    hist = []
    for ep in range(1, int(max_epochs) + 1):
        model.train()
        order = rng.permutation(itr.size)
        t0 = time.time()
        for a in range(0, itr.size, bs):
            r = itr[np.sort(order[a:a + bs])]
            if r.size < 8:
                continue
            with torch.autocast("cuda", dtype=torch.bfloat16,
                                enabled=(DEV == "cuda")):
                out = model(_to_gpu(SEQ, pos, r, mu, sd))
            loss = SM.loss_fn(out,
                              torch.from_numpy(y_c[r]).to(DEV).float(),
                              torch.from_numpy(y_w[r]).to(DEV).float())
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        dt = time.time() - t0
        if iva is not None and iva.size:
            pc, _pw = predict(model, SEQ, pos, iva, mu, sd)
            rho = M3._rho(pc, y_c[iva])
        else:
            rho = float(ep)
        hist.append([ep, round(float(rho), 5), round(dt, 1)])
        SC.hb("%s ep%d rho=%.4f %.0fs (%.0f rows/s)"
              % (tag, ep, rho, dt, itr.size / max(dt, 1e-6)))
        if np.isfinite(rho) and rho > best:
            best, best_ep, bad = float(rho), ep, 0
            best_state = {k: v.detach().clone()
                          for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= SC.PATIENCE:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, {"arch": arch, "rung": rung, "L": L, "params": npar,
                   "inner_rho": best, "best_epoch": int(best_ep),
                   "epoch_hist": hist}


def run_ladder(D, SEQ, pos, L, arch, rung, shuffled=False, tag="",
               test_eras=SC.TEST_ERAS, init_state=None):
    n = D["d8"].size
    champ = np.full(n, np.nan)
    win = np.full(n, np.nan)
    y_c0 = D["y_retg_rank_phase"]
    y_w0 = D["y_winner"]
    ledger = []
    for era in test_eras:
        t0 = time.time()
        tr, ev = fold_rows(D, era)
        tr = tr[(pos[tr] >= 0) & np.isfinite(y_c0[tr])]
        ev = ev[pos[ev] >= 0]
        cut = SC.inner_split_days(D["d8"][tr])
        itr = tr[D["d8"][tr] <= cut]
        iva = tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
        y_c = y_c0.astype(np.float64).copy()
        y_w = y_w0.astype(np.float64).copy()
        if shuffled:
            rs = np.random.RandomState(SC.SEED + SC.ERA_IDX[era])
            perm = rs.permutation(tr.size)
            y_c[tr] = y_c0[tr][perm]
            y_w[tr] = y_w0[tr][perm]
        mu, sd = norm_stats(SEQ, pos, itr)
        _m, info = train_model(SEQ, pos, itr, iva, y_c, y_w, arch, rung, L,
                               mu, sd, "%s/%s" % (tag, era), SC.MAX_EPOCHS,
                               init_state=init_state)
        # THE REFIT, m3's own discipline: from scratch on the WHOLE training
        # block, for the epoch count the inner block chose.  Normalisation is
        # refitted on the whole training block — still TRAIN ONLY.
        mu, sd = norm_stats(SEQ, pos, tr)
        model, _i = train_model(SEQ, pos, tr, None, y_c, y_w, arch, rung, L,
                                mu, sd, "%s/%s refit" % (tag, era),
                                info["best_epoch"], init_state=init_state)
        pc, pw = predict(model, SEQ, pos, ev, mu, sd)
        champ[ev] = pc
        win[ev] = pw
        info.update({"era": era, "n_train": int(tr.size),
                     "n_inner_train": int(itr.size), "n_inner_val": int(iva.size),
                     "n_eval": int(ev.size),
                     "train_days": int(np.unique(D["d8"][tr]).size),
                     "eval_days": int(np.unique(D["d8"][ev]).size),
                     "fit_secs": round(time.time() - t0, 1),
                     "eval_auc_winner": round(auc(y_w0[ev], pw), 4)})
        ledger.append(info)
        SC.hb("LADDER %s %s: rho=%.4f auc=%.4f %.0fs"
              % (tag, era, info["inner_rho"], info["eval_auc_winner"],
                 info["fit_secs"]))
        del model, _m
        if DEV == "cuda":
            torch.cuda.empty_cache()
    return champ, win, ledger


# =============================================================== scoring =====
def auc(y, s):
    y = np.asarray(y, dtype=np.float64)
    s = np.asarray(s, dtype=np.float64)
    ok = np.isfinite(y) & np.isfinite(s)
    y, s = y[ok], s[ok]
    if y.size == 0 or y.min() == y.max():
        return float("nan")
    r = MX._rank_pct(s) * s.size
    n1 = float((y > 0.5).sum())
    n0 = float(y.size - n1)
    if n0 <= 0 or n1 <= 0:
        return float("nan")
    return float((r[y > 0.5].sum() - n1 * (n1 + 1) / 2.0) / (n0 * n1))


def composed(D, champ, win, ev):
    """m3_walk's COMPOSED construction, verbatim: within-(asset, session)
    percentile of each head, rank-SUMMED."""
    return W._unit_pct(D, champ, ev) + W._unit_pct(D, win, ev)


def score_arm(D, score, ev, ceilings, unit=SC.SCHEDULE_UNIT, n=SC.SCHEDULE_N,
              deployable=True):
    take = W.topn_takes(D, score, ev, n, deployable=deployable, unit=unit)
    rows = W.replay_rows(D, take)
    seats = [j for r in rows for j in r["seats"]]
    y, cl, den_c, den_o = [], [], [], []
    for r in rows:
        y.append(r["realised"])
        cl.append(int(r["session"].split("|")[1]))       # cluster = the DAY
        den_c.append(ceilings.get(r["session"], (0.0, 0, 0))[0])
        den_o.append(oracle_of(r["session"]))
    cm = PS.cluster_mean(y, cl) if y else None
    cap = PS.cluster_ratio(y, den_c, cl) if y else None
    orc = PS.cluster_ratio(y, den_o, cl) if y else None
    pt = W.per_trade_stats(D, seats)
    s = np.asarray(seats, dtype=np.int64)
    tm = PS.cluster_mean(D["cert_close_usd"][s],
                         [int(k.split("|")[1])
                          for k in D["session"][s].tolist()]) if s.size else None
    return {"n_takes": int(take.size), "n_sessions": len(rows),
            "n_seated": int(s.size),
            "usd_per_session": cm["mean"] if cm else None,
            "ps_lo": cm["ci_lo"] if cm else None,
            "ps_hi": cm["ci_hi"] if cm else None,
            "usd_per_trade": pt.get("expectancy_usd"),
            "pt_lo": tm["ci_lo"] if tm else None,
            "pt_hi": tm["ci_hi"] if tm else None,
            "frac_ge_1000": pt.get("frac_ge_1000"),
            "capture_day": cap["ratio"] if cap else None,
            "cd_lo": cap["ci_lo"] if cap else None,
            "cd_hi": cap["ci_hi"] if cap else None,
            "capture_oracle": orc["ratio"] if orc else None,
            "co_lo": orc["ci_lo"] if orc else None,
            "co_hi": orc["ci_hi"] if orc else None,
            "_realised": y, "_cl": cl, "_den_c": den_c, "_den_o": den_o,
            "_seats": seats}


def pooled(parts):
    """Pooled-over-eras reading, still clustered by DAY."""
    y = [v for p in parts for v in p["_realised"]]
    cl = [v for p in parts for v in p["_cl"]]
    dc = [v for p in parts for v in p["_den_c"]]
    do = [v for p in parts for v in p["_den_o"]]
    cm = PS.cluster_mean(y, cl) if y else None
    cap = PS.cluster_ratio(y, dc, cl) if y else None
    orc = PS.cluster_ratio(y, do, cl) if y else None
    return {"n_sessions": len(y),
            "usd_per_session": cm["mean"] if cm else None,
            "ps_lo": cm["ci_lo"] if cm else None,
            "ps_hi": cm["ci_hi"] if cm else None,
            "capture_day": cap["ratio"] if cap else None,
            "cd_lo": cap["ci_lo"] if cap else None,
            "cd_hi": cap["ci_hi"] if cap else None,
            "capture_oracle": orc["ratio"] if orc else None,
            "co_lo": orc["ci_lo"] if orc else None,
            "co_hi": orc["ci_hi"] if orc else None}


def eval_scores(D, champ, win, ceil, pos, test_eras=SC.TEST_ERAS):
    """Per-era + pooled reading of one (champ, winner) score pair."""
    per, parts = [], []
    for era in test_eras:
        ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
        ev = ev[pos[ev] >= 0]
        comp = composed(D, champ, win, ev)
        a = score_arm(D, comp, ev, ceil)
        a["era"] = era
        a["auc_winner"] = auc(D["y_winner"][ev], win[ev])
        per.append(a)
        parts.append(a)
    return per, pooled(parts)


# ================================================== the moment-layer test ====
def moment_gain(D, score, ev, tag, era):
    """THE MOMENT LAYER ISOLATED.  Episode FIXED (the frozen `ep`), the only
    choice is WHICH SECOND inside it: the model's argmax vs the EARLIEST
    actable member — which is what the reader takes and what BASE_EARLIEST
    replays."""
    ev = np.asarray(ev, dtype=np.int64)
    j = D["names"].index("in_news_window")
    ev = ev[D["X"][ev, j] < 0.5]
    order = np.lexsort((D["dec_sec"][ev], D["ep"][ev]))
    e = ev[order]
    k = D["ep"][e]
    starts = [0] + (np.flatnonzero(k[1:] != k[:-1]) + 1).tolist()
    stops = starts[1:] + [k.size]
    d_close, d_win, cl, v_e, v_m = [], [], [], [], []
    for a, b in zip(starts, stops):
        if b - a < 2:
            continue
        idx = e[a:b]
        s = score[idx]
        if not np.isfinite(s).any():
            continue
        earl = idx[0]
        pick = idx[int(np.nanargmax(s))]
        d_close.append(float(D["cert_close_usd"][pick]
                             - D["cert_close_usd"][earl]))
        d_win.append(float(D["cert_close_usd"][pick] >= 1000.0)
                     - float(D["cert_close_usd"][earl] >= 1000.0))
        v_e.append(float(D["cert_close_usd"][earl]))
        v_m.append(float(D["cert_close_usd"][pick]))
        cl.append(int(D["d8"][earl]))
    cm = PS.cluster_mean(d_close, cl) if d_close else None
    cw = PS.cluster_mean(d_win, cl) if d_win else None
    return {"arm": tag, "era": era, "n_episodes": len(d_close),
            "earliest_usd_per_ep": float(np.mean(v_e)) if v_e else None,
            "model_usd_per_ep": float(np.mean(v_m)) if v_m else None,
            "gain_usd_per_ep": cm["mean"] if cm else None,
            "gain_lo": cm["ci_lo"] if cm else None,
            "gain_hi": cm["ci_hi"] if cm else None,
            "gain_p": cm["p"] if cm else None,
            "d_frac_ge_1000": cw["mean"] if cw else None,
            "dfg_lo": cw["ci_lo"] if cw else None,
            "dfg_hi": cw["ci_hi"] if cw else None}


# ================================================================== GBT ======
_HP = None


def committed_hp(era, target):
    global _HP
    if _HP is None:
        with open(os.path.join(M3.WALK_DIR, "walk.summary.json")) as fh:
            s = json.load(fh)
        _HP = {}
        for e in s["eras"]:
            for t, v in (e.get("targets") or {}).items():
                if v.get("status") == "OK":
                    _HP[(e["era"], t)] = (v["hp"], int(v["rounds"]))
    hp, rounds = _HP[(era, target)]
    cfg = {"objective": "reg:squarederror", "tree_method": "hist",
           "subsample": 0.8, "seed": SC.SEED, "nthread": 8}
    cfg.update(hp)
    return cfg, rounds


def gbt_scores(D, era, extra=None, tag="GBT"):
    """The m3 GBT on the SAME fold, at m3's committed per-era HP (no search)."""
    import xgboost as xgb
    tr, ev = fold_rows(D, era)
    X = D["X"] if extra is None else np.hstack([D["X"], extra])
    names = list(D["names"]) + ([] if extra is None
                                else ["seq_champ_hat", "seq_winner_hat"])
    out = {}
    for target in ("y_retg_rank_phase", "y_winner"):
        y = D[target]
        f = tr[np.isfinite(y[tr])]
        cfg, rounds = committed_hp(era, target)
        t0 = time.time()
        b = xgb.train(cfg, xgb.DMatrix(X[f], label=y[f], feature_names=names),
                      rounds)
        s = np.full(D["d8"].size, np.nan)
        s[ev] = b.predict(xgb.DMatrix(X[ev], feature_names=names))
        out[target] = s
        SC.hb("%s %s %s: %d rows, %d rounds (%.0fs)"
              % (tag, era, target, f.size, rounds, time.time() - t0))
        if extra is not None and target == "y_retg_rank_phase":
            g = b.get_score(importance_type="gain")
            tot = sum(g.values()) or 1.0
            out["_seq_gain_share"] = (g.get("seq_champ_hat", 0.0)
                                      + g.get("seq_winner_hat", 0.0)) / tot
    return out, ev


# =============================================================== pretrain ====
def pretrain_trf(D, SEQ, pos, L, rung, train_eras, steps=SC.PRETRAIN_STEPS):
    """SELF-SUPERVISED MASKED-EVENT PRETRAINING on the UNLABELLED stream.

    Only rows from the training eras are used — the same walk-forward wall the
    supervised ladder obeys.  No label of any kind enters this stage.
    """
    rows = np.nonzero(np.isin(D["era_idx"],
                              [SC.ERA_IDX[e] for e in train_eras]))[0]
    rows = rows[pos[rows] >= 0]
    mu, sd = norm_stats(SEQ, pos, rows)
    model, npar = SM.make("trf", rung, L)
    model = model.to(DEV)
    opt = torch.optim.AdamW(model.parameters(), lr=SC.PRETRAIN_LR,
                            weight_decay=SC.WEIGHT_DECAY)
    rng = np.random.RandomState(SC.SEED)
    bs = SC.PRETRAIN_BATCH[L]
    patch = SC.TRF_PATCH[L]
    ntok = L // patch
    t0 = time.time()
    losses = []
    for it in range(int(steps)):
        r = np.sort(rng.choice(rows, size=bs, replace=False))
        x = _to_gpu(SEQ, pos, r, mu, sd)
        m = torch.rand(bs, ntok, device=DEV) < SC.PRETRAIN_MASK_FRAC
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=(DEV == "cuda")):
            p = model.forward_masked(x, m)
        loss = SM.pretrain_loss(p, x, m, patch)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        losses.append(float(loss.item()))
        if (it + 1) % 500 == 0:
            SC.hb("pretrain %s L=%d step %d/%d loss=%.4f (%.0fs)"
                  % (rung, L, it + 1, steps, float(np.mean(losses[-500:])),
                     time.time() - t0))
    state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()
             if not k.startswith("head.") and not k.startswith("dec.")}
    info = {"rung": rung, "L": L, "steps": int(steps), "params": npar,
            "n_rows_seen": int(bs * steps), "n_pool_rows": int(rows.size),
            "loss_first500": float(np.mean(losses[:500])),
            "loss_last500": float(np.mean(losses[-500:])),
            "secs": round(time.time() - t0, 1),
            "train_eras": list(train_eras)}
    del model
    if DEV == "cuda":
        torch.cuda.empty_cache()
    return state, info


# ================================================================ results ====
def save_result(tag, obj):
    os.makedirs(RES_DIR, exist_ok=True)
    with open(os.path.join(RES_DIR, "%s.json" % tag), "w") as fh:
        json.dump(obj, fh, indent=1, default=str)
    SC.hb("saved result %s" % tag)


def load_results():
    out = []
    for p in sorted(glob.glob(os.path.join(RES_DIR, "*.json"))):
        with open(p) as fh:
            o = json.load(fh)
        o["_name"] = os.path.basename(p)[:-5]
        out.append(o)
    return out


def _r(v, nd=2):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ""
    return round(float(v), nd)


def write_tsv(name, columns, rows, extra=()):
    p = os.path.join(SC.OUT_DIR, name)
    with open(p, "w") as fh:
        fh.write("# PORT M2 %s (lane=%s; seed=%d; device=%s)\n"
                 % (SC.SECTION, SC.LANE, SC.SEED, gpu_note().get("device")))
        for e in extra:
            fh.write("# %s\n" % e)
        fh.write("\t".join(columns) + "\n")
        for r in rows:
            fh.write("\t".join("" if v is None else str(v) for v in r) + "\n")
    SC.hb("wrote %s (%d rows)" % (p, len(rows)))
    return p


# ================================================================ stages =====
def stage_control(L, arch, rung):
    D, SEQ, pos = load_all(L)
    ceil = ceilings_of(D)
    probes = []
    tr, ev = fold_rows(D, "E6")
    bad_day = int(D["d8"][tr][0])
    ev_bad = np.concatenate([ev, tr[D["d8"][tr] == bad_day]])
    try:
        SC.assert_disjoint_days(tr, ev_bad, D["d8"], tag="PROBE")
        probes.append(["duplicate_day", "NOT_CAUGHT", "FAIL", ""])
    except SC.SeqTestRefusal as e:
        probes.append(["duplicate_day", "REFUSED", "PASS", str(e)[:200]])
    try:
        SC.assert_disjoint_days(tr, ev, D["d8"], tag="CLEAN")
        probes.append(["duplicate_day_clean_fold", "ACCEPTED", "PASS", ""])
    except SC.SeqTestRefusal as e:
        probes.append(["duplicate_day_clean_fold", "REFUSED", "FAIL",
                       str(e)[:200]])
    try:
        SC.assert_causal_era_order(np.concatenate([tr, ev[:10]]), ev,
                                   D["era_idx"], tag="PROBE")
        probes.append(["non_causal_era", "NOT_CAUGHT", "FAIL", ""])
    except SC.SeqTestRefusal as e:
        probes.append(["non_causal_era", "REFUSED", "PASS", str(e)[:200]])
    probes.append(list(tensor_causality_probe(SEQ, pos)))

    champ, win, ledger = run_ladder(D, SEQ, pos, L, arch, rung, shuffled=True,
                                    tag="SHUFFLED")
    per, pool = eval_scores(D, champ, win, ceil, pos)
    save_result("CONTROL_shuffled_%s_%s_L%d" % (arch, rung, L),
                {"kind": "control", "arch": arch, "rung": rung, "L": L,
                 "shuffled": True, "per_era": [_strip(a) for a in per],
                 "pooled": pool, "ledger": ledger, "probes": probes,
                 "gpu": gpu_note()})
    np.savez(os.path.join(_sdir(), "SHUFFLED_%s_%s_L%d.npz" % (arch, rung, L)),
             champ=champ, win=win)
    rec = M3.env_receipt(SC.PARAMS)
    rec.update({"stage": "CONTROL_RED_FIRST", "probes": probes,
                "pooled_shuffled": pool, "gpu": gpu_note()})
    with open(os.path.join(CACHE, "control.receipt.json"), "w") as fh:
        json.dump(rec, fh, indent=1, sort_keys=True, default=str)
    write_tsv("SEQTEST_PROBES.tsv", ["probe", "outcome", "verdict", "message"],
              probes, extra=["Leak probes fired BEFORE the real run "
                             "(red-first)."])
    write_tsv("SEQTEST_CONTROL.tsv",
              ["arm", "era", "n_takes", "n_seated", "usd_per_session",
               "usd_per_trade", "capture_day", "capture_oracle", "co_lo",
               "co_hi", "auc_winner"],
              [["SEQ_SHUFFLED_%s_%s_L%d" % (arch, rung, L), a["era"],
                a["n_takes"], a["n_seated"], _r(a["usd_per_session"]),
                _r(a["usd_per_trade"]), _r(a["capture_day"], 4),
                _r(a["capture_oracle"], 4), _r(a["co_lo"], 4),
                _r(a["co_hi"], 4), _r(a["auc_winner"], 4)] for a in per]
              + [["SEQ_SHUFFLED_POOLED", "E3-E8", "", "",
                  _r(pool["usd_per_session"]), "", _r(pool["capture_day"], 4),
                  _r(pool["capture_oracle"], 4), _r(pool["co_lo"], 4),
                  _r(pool["co_hi"], 4), ""]],
              extra=["RED-FIRST shuffled-label control: the training block's "
                     "labels are permuted; every number must be "
                     "indistinguishable from chance.",
                     "Identical schedule: top-3/asset-day, D-077 veto, "
                     "phase-close replay, CIs clustered by DAY."])
    return probes, pool


def _sdir():
    os.makedirs(SCORE_DIR, exist_ok=True)
    return SCORE_DIR


def _strip(a):
    return {k: v for k, v in a.items() if not k.startswith("_")}


def tensor_causality_probe(SEQ, pos, n=5000):
    """Every event in a tensor must predate its decision second: channel 19 is
    log1p(seconds to the decision), so `> 0` on every VALID cell is exactly the
    causal statement."""
    rows = np.nonzero(pos >= 0)[0]
    step = max(1, rows.size // n)
    blk = SEQ[np.sort(pos[rows[::step]])].astype(np.float32)
    m = blk[:, SC.CH_VALID, :] > 0.5
    bad = int((m & (blk[:, SC.CH_TTD, :] <= 0.0)).sum())
    return ("tensor_causality",
            "%d/%d valid cells at or after the decision second"
            % (bad, int(m.sum())), "PASS" if bad == 0 else "FAIL",
            "channel %d = log1p(seconds to decision) > 0 on every valid cell"
            % SC.CH_TTD)


def stage_ladder(L, configs, pretrained=None):
    D, SEQ, pos = load_all(L)
    ceil = ceilings_of(D)
    for arch, rung in configs:
        tag = "LADDER_%s_%s_L%d%s" % (arch, rung, L,
                                      "_PRE" if pretrained else "")
        if os.path.exists(os.path.join(RES_DIR, "%s.json" % tag)):
            SC.hb("skip %s (already committed)" % tag)
            continue
        t0 = time.time()
        champ, win, ledger = run_ladder(D, SEQ, pos, L, arch, rung,
                                        shuffled=False, tag=tag,
                                        init_state=pretrained)
        per, pool = eval_scores(D, champ, win, ceil, pos)
        save_result(tag, {"kind": "ladder", "arch": arch, "rung": rung, "L": L,
                          "pretrained": bool(pretrained),
                          "per_era": [_strip(a) for a in per], "pooled": pool,
                          "ledger": ledger, "gpu": gpu_note(),
                          "wall_secs": round(time.time() - t0, 1)})
        np.savez(os.path.join(_sdir(), "%s.npz" % tag), champ=champ, win=win)
        SC.hb("%s pooled capture_oracle=%.4f [%.4f,%.4f] (%.0fs)"
              % (tag, pool["capture_oracle"] or float("nan"),
                 pool["co_lo"] or float("nan"), pool["co_hi"] or float("nan"),
                 time.time() - t0))


def stage_pretrain(L, rung):
    """Masked-event pretraining is WALK-FORWARD too: one pretrained trunk per
    fold, built ONLY from that fold's training eras."""
    D, SEQ, pos = load_all(L)
    ceil = ceilings_of(D)
    n = D["d8"].size
    champ = np.full(n, np.nan)
    win = np.full(n, np.nan)
    ledger, pinfo = [], []
    for era in SC.TEST_ERAS:
        train_eras = [e for e in SC.UNIVERSE_ERAS
                      if SC.ERA_IDX[e] < SC.ERA_IDX[era]]
        state, pi = pretrain_trf(D, SEQ, pos, L, rung, train_eras)
        pinfo.append(pi)
        c, w, lg = run_ladder(D, SEQ, pos, L, "trf", rung, shuffled=False,
                              tag="PRETRAIN_%s_L%d" % (rung, L),
                              test_eras=[era], init_state=state)
        ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
        ev = ev[pos[ev] >= 0]
        champ[ev] = c[ev]
        win[ev] = w[ev]
        ledger += lg
    per, pool = eval_scores(D, champ, win, ceil, pos)
    tag = "PRETRAIN_trf_%s_L%d" % (rung, L)
    save_result(tag, {"kind": "pretrain", "arch": "trf", "rung": rung, "L": L,
                      "pretrained": True, "per_era": [_strip(a) for a in per],
                      "pooled": pool, "ledger": ledger, "pretrain": pinfo,
                      "gpu": gpu_note()})
    np.savez(os.path.join(_sdir(), "%s.npz" % tag), champ=champ, win=win)
    SC.hb("%s pooled capture_oracle=%.4f" % (tag, pool["capture_oracle"] or 0))


def stage_gbt_scores():
    """Save the GBT arm's own out-of-sample scores so the SAME deficit-ledger
    command can decompose it beside the sequence arms."""
    D, _p = W.load_matrix()
    n = D["d8"].size
    champ = np.full(n, np.nan)
    win = np.full(n, np.nan)
    for era in SC.TEST_ERAS:
        g, ev = gbt_scores(D, era, extra=None, tag="GBTSCORES")
        champ[ev] = g["y_retg_rank_phase"][ev]
        win[ev] = g["y_winner"][ev]
    np.savez(os.path.join(_sdir(), "GBT_M3FEATURES.npz"), champ=champ, win=win)
    SC.hb("saved GBT_M3FEATURES scores (%d rows)"
          % int(np.isfinite(champ).sum()))


def stage_arms(L, arch, rung, tag=None):
    """THE DELIVERABLE: every arm on the identical schedule, the moment gain,
    and the hybrid marginal."""
    D, SEQ, pos = load_all(L)
    ceil = ceilings_of(D)
    src = tag or ("LADDER_%s_%s_L%d" % (arch, rung, L))
    z = np.load(os.path.join(SCORE_DIR, "%s.npz" % src))
    champ, win = z["champ"], z["win"]
    arms, moms, hybs = [], [], []
    parts = {}
    for era in SC.TEST_ERAS:
        ev = np.nonzero(D["era_idx"] == SC.ERA_IDX[era])[0]
        ev = ev[pos[ev] >= 0]
        yw = D["y_winner"][ev]
        seq_comp = composed(D, champ, win, ev)
        a = score_arm(D, seq_comp, ev, ceil)
        arms.append(("SEQ_COMPOSED", era, a, auc(yw, win[ev])))
        parts.setdefault("SEQ_COMPOSED", []).append(a)
        a1 = score_arm(D, champ, ev, ceil)
        arms.append(("SEQ_PRIMARY", era, a1, auc(yw, champ[ev])))
        parts.setdefault("SEQ_PRIMARY", []).append(a1)

        g, _ = gbt_scores(D, era, extra=None, tag="GBT")
        gc, gw = g["y_retg_rank_phase"], g["y_winner"]
        gcomp = composed(D, gc, gw, ev)
        b = score_arm(D, gcomp, ev, ceil)
        arms.append(("GBT_COMPOSED", era, b, auc(yw, gw[ev])))
        parts.setdefault("GBT_COMPOSED", []).append(b)
        b1 = score_arm(D, gc, ev, ceil)
        arms.append(("GBT_PRIMARY", era, b1, auc(yw, gc[ev])))
        parts.setdefault("GBT_PRIMARY", []).append(b1)

        extra = np.column_stack([champ, win]).astype(np.float32)
        h, _ = gbt_scores(D, era, extra=extra, tag="HYBRID")
        hcomp = composed(D, h["y_retg_rank_phase"], h["y_winner"], ev)
        c = score_arm(D, hcomp, ev, ceil)
        arms.append(("HYBRID_COMPOSED", era, c, auc(yw, h["y_winner"][ev])))
        parts.setdefault("HYBRID_COMPOSED", []).append(c)
        tr, _e = fold_rows(D, era)
        hybs.append([era, int(np.isfinite(champ[tr]).sum()),
                     _r(b["capture_oracle"], 4), _r(c["capture_oracle"], 4),
                     _r((c["capture_oracle"] or 0) - (b["capture_oracle"] or 0), 4),
                     _r(b["usd_per_trade"]), _r(c["usd_per_trade"]),
                     _r((c["usd_per_trade"] or 0) - (b["usd_per_trade"] or 0)),
                     _r(h.get("_seq_gain_share"), 4)])

        be = base_earliest(D, ev, ceil)
        arms.append(("BASE_EARLIEST", era, be, None))
        parts.setdefault("BASE_EARLIEST", []).append(be)
        r3 = random3(D, ev, ceil)
        arms.append(("RANDOM3", era, r3, None))
        fs = score_arm(D, D["cert_close_usd"], ev, ceil)
        arms.append(("FORESIGHT3_NONCAUSAL", era, fs, None))
        parts.setdefault("FORESIGHT3_NONCAUSAL", []).append(fs)

        for nm, sc in (("SEQ_COMPOSED", seq_comp), ("SEQ_PRIMARY", champ),
                       ("GBT_COMPOSED", gcomp),
                       ("FORESIGHT_NONCAUSAL", D["cert_close_usd"])):
            moms.append(moment_gain(D, sc, ev, nm, era))
        SC.hb("ARMS %s done" % era)

    save_result("ARMS_%s" % src,
                {"kind": "arms", "src": src, "arch": arch, "rung": rung,
                 "L": L,
                 "arms": [[nm, era, _strip(a),
                           (None if u is None else round(float(u), 4))]
                          for nm, era, a, u in arms],
                 "pooled": {k: pooled(v) for k, v in parts.items()},
                 "moment": moms, "hybrid": hybs, "gpu": gpu_note()})


def base_earliest(D, ev, ceilings):
    take = W.baseline_takes(D, ev, deployable=True)
    rows = W.replay_rows(D, take)
    seats = [j for r in rows for j in r["seats"]]
    y = [r["realised"] for r in rows]
    cl = [int(r["session"].split("|")[1]) for r in rows]
    dc = [ceilings.get(r["session"], (0.0, 0, 0))[0] for r in rows]
    do = [oracle_of(r["session"]) for r in rows]
    cm = PS.cluster_mean(y, cl) if rows else None
    cap = PS.cluster_ratio(y, dc, cl) if rows else None
    orc = PS.cluster_ratio(y, do, cl) if rows else None
    pt = W.per_trade_stats(D, seats)
    return {"n_takes": int(take.size), "n_sessions": len(rows),
            "n_seated": len(seats),
            "usd_per_session": cm["mean"] if cm else None,
            "ps_lo": cm["ci_lo"] if cm else None,
            "ps_hi": cm["ci_hi"] if cm else None,
            "usd_per_trade": pt.get("expectancy_usd"),
            "frac_ge_1000": pt.get("frac_ge_1000"),
            "capture_day": cap["ratio"] if cap else None,
            "capture_oracle": orc["ratio"] if orc else None,
            "co_lo": orc["ci_lo"] if orc else None,
            "co_hi": orc["ci_hi"] if orc else None,
            "_realised": y, "_cl": cl, "_den_c": dc, "_den_o": do,
            "_seats": seats}


def random3(D, ev, ceilings, draws=SC.N_RANDOM_DRAWS):
    rs = np.random.RandomState(SC.SEED)
    caps, pss, pts = [], [], []
    for _ in range(draws):
        a = score_arm(D, rs.rand(D["d8"].size), ev, ceilings)
        caps.append(a["capture_oracle"] or 0.0)
        pss.append(a["usd_per_session"] or 0.0)
        pts.append(a["usd_per_trade"] or 0.0)
    return {"capture_oracle": float(np.mean(caps)),
            "co_lo": float(np.percentile(caps, 2.5)),
            "co_hi": float(np.percentile(caps, 97.5)),
            "usd_per_session": float(np.mean(pss)),
            "usd_per_trade": float(np.mean(pts)), "draws": int(draws),
            "n_takes": None, "n_seated": None}


def stage_export(src, L=None):
    """Hand the model's out-of-sample score column to the frontier lane's plane:
    one TSV keyed by `cid`, the m3 matrix's candidate id."""
    import m3_walk as W
    D, _p = W.load_matrix()
    z = np.load(os.path.join(SCORE_DIR, "%s.npz" % src))
    champ, win = z["champ"], z["win"]
    ok = np.nonzero(np.isfinite(champ))[0]
    comp = np.full(D["d8"].size, np.nan)
    for era in SC.TEST_ERAS:
        ev = np.nonzero((D["era_idx"] == SC.ERA_IDX[era])
                        & np.isfinite(champ))[0]
        if ev.size:
            comp[ev] = composed(D, champ, win, ev)[ev]
    rows = [[str(D["cid"][i]), str(D["asset"][i]), int(D["d8"][i]),
             int(D["dec_sec"][i]), int(D["side"][i]),
             M3.ERA_NAMES[int(D["era_idx"][i])],
             _r(champ[i], 6), _r(win[i], 6), _r(comp[i], 6)]
            for i in ok.tolist()]
    write_tsv("SEQTEST_SCORES_%s.tsv" % src,
              ["cid", "asset", "d8", "dec_sec", "side", "era",
               "seq_champ_hat", "seq_winner_logit", "seq_composed_pct"], rows,
              extra=["OUT-OF-SAMPLE sequence-model scores for the frontier "
                     "lane's plane, keyed by the m3 matrix `cid`.",
                     "Every row was scored by a model trained ONLY on strictly "
                     "earlier eras (train E2..Ek -> test E(k+1)); no row here "
                     "was seen in its own model's training block.",
                     "seq_composed_pct = the m3 COMPOSED construction: "
                     "within-(asset,session) percentile of each head, summed.",
                     "source config: %s" % src])
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True,
                    choices=("control", "ladder", "pretrain", "arms",
                             "gbtscores", "export", "report"))
    ap.add_argument("--len", type=int, default=256)
    ap.add_argument("--arch", default="cnn")
    ap.add_argument("--rung", default="1M")
    ap.add_argument("--configs", default="")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(RES_DIR, exist_ok=True)
    SC.hb("stage=%s L=%d gpu=%s" % (a.stage, a.len, gpu_note()))
    if a.stage == "control":
        stage_control(a.len, a.arch, a.rung)
    elif a.stage == "ladder":
        cfg = [tuple(c.split(":")) for c in a.configs.split(",") if c] \
            or [(a.arch, a.rung)]
        stage_ladder(a.len, cfg)
    elif a.stage == "pretrain":
        stage_pretrain(a.len, a.rung)
    elif a.stage == "arms":
        stage_arms(a.len, a.arch, a.rung, tag=a.tag)
    elif a.stage == "gbtscores":
        stage_gbt_scores()
    elif a.stage == "export":
        stage_export(a.tag or ("LADDER_%s_%s_L%d" % (a.arch, a.rung, a.len)))
    elif a.stage == "report":
        import st_report
        st_report.main()


if __name__ == "__main__":
    main()
