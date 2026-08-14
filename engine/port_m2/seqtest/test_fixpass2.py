#!/usr/bin/python3
"""PORT M2 FIXPASS2 — the fix pass's own tests.

Same discipline as `test_seqtest.py`: every check is either a REFUSAL test (a
guard must fire) or an IDENTITY test (a number must reproduce something already
committed elsewhere).  The fix pass adds five new instruments — a second
tokenizer, a creator-feature join, a day-memory block, a wall-pair set and a
partial fine-tune — and none of them may be read before these pass.

Run:  /usr/bin/python3 engine/port_m2/seqtest/test_fixpass2.py
"""
import json
import os
import sys
import traceback

import numpy as np

import st_common as SC
import st_tok2 as TK2
import st_aux2 as A2
import st_creator as CR
import m2_common as MC

FAIL = []
_D = {}


def D():
    if "D" not in _D:
        import m3_walk as W
        _D["D"] = W.load_matrix()[0]
    return _D["D"]


def check(name, fn):
    try:
        fn()
        print("ok   %s" % name)
    except Exception as e:                  # noqa: BLE001
        FAIL.append((name, e))
        print("FAIL %s: %s" % (name, e))
        traceback.print_exc()


# ------------------------------------------------------- F1: the tokenizer --
def t_tok2_identity():
    """The cached V2 token stream equals an independent from-scratch
    recomputation, for one session per asset."""
    cuts = TK2.load_cuts()
    for asset in MC.ASSET_ORDER:
        d = os.path.join(TK2.TOK_DIR, asset)
        f = sorted(x for x in os.listdir(d) if x.endswith(".npz"))[17]
        z = np.load(os.path.join(d, f))
        cached = z["tok"]
        z.close()
        p = os.path.join(SC.EVENTS_DIR, asset, f)
        z = np.load(p)
        arr = {k: z[k] for k in z.files}
        z.close()
        fresh = TK2.tokenize_day(asset, arr, cuts[asset])
        if not np.array_equal(cached, fresh):
            raise AssertionError("%s %s: %d/%d tokens differ"
                                 % (asset, f, int((cached != fresh).sum()),
                                    cached.size))


def t_tok2_occupancy():
    """THE REPAIR ITSELF: no price bucket may exceed ~40% of the corpus."""
    rows = TK2.occupancy_rows()
    px = [r for r in rows if r[0] == "px_bucket"]
    mx = max(float(r[3]) for r in px)
    if mx > 0.40:
        raise AssertionError("largest px_bucket is %.4f of all events (> 0.40)"
                             % mx)
    if abs(sum(float(r[3]) for r in px) - 1.0) > 1e-4:
        raise AssertionError("px_bucket masses do not sum to 1")
    print("       largest px_bucket = %.4f (V1 dmid_bucket was 0.9331)" % mx)


def t_tok2_vocab_range():
    """No cached token may fall outside the declared vocabulary."""
    cnt = np.load(TK2.COUNTS_PATH)
    if cnt.size != TK2.VOCAB_EVENTS:
        raise AssertionError("counts %d != vocab %d" % (cnt.size,
                                                        TK2.VOCAB_EVENTS))
    X, rows = TK2.load_cand_tokens()
    lo, hi = int(X.min()), int(X.max())
    if lo < 0 or hi > TK2.PAD:
        raise AssertionError("candidate tokens out of range [%d, %d]" % (lo, hi))


def t_tok2_cuts_causal():
    """The per-asset cuts are fitted on PRE-A only — never on evaluation tape."""
    with open(TK2.CUTS_PATH) as fh:
        c = json.load(fh)
    if int(c["fit_max_d8"]) != 20240101:
        raise AssertionError("cuts fitted past the PRE-A boundary: %s"
                             % c["fit_max_d8"])


# --------------------------------------------------- F5: the creator join ---
def t_creator_reproduces_census():
    """The E2..E8 detector re-run must reproduce the COMMITTED E2..E6 census
    cache exactly on the rows they share — same code, same params, same bytes."""
    old = "/workspace/artifacts/cache/port/m2/creator/detect.npz"
    if not os.path.exists(old) or not os.path.exists(CR.DETECT):
        raise AssertionError("a detector cache is missing")
    a = np.load(old, allow_pickle=False)
    b = np.load(CR.DETECT, allow_pickle=False)
    ia = {str(c): i for i, c in enumerate(a["cid"].tolist())}
    ib = {str(c): i for i, c in enumerate(b["cid"].tolist())}
    na = [str(x) for x in a["det_names"].tolist()]
    nb = [str(x) for x in b["det_names"].tolist()]
    common = sorted(set(ia) & set(ib))
    if len(common) < 800000:
        raise AssertionError("only %d shared rows" % len(common))
    rs = np.random.RandomState(SC.SEED)
    sel = [common[i] for i in rs.choice(len(common), size=20000,
                                        replace=False)]
    ra = np.array([ia[c] for c in sel])
    rb = np.array([ib[c] for c in sel])
    for nm in CR.SURVIVORS:
        ca = a["D"][ra, na.index(nm)]
        cb = b["D"][rb, nb.index(nm)]
        if not np.array_equal(ca, cb):
            raise AssertionError("%s differs on %d/20000 shared rows"
                                 % (nm, int((ca != cb).sum())))
    a.close()
    b.close()


def t_creator_coverage():
    """Every E2..E8 matrix row must carry the columns; nothing outside may."""
    d = D()
    A, cols, cov = CR.creator_columns(d)
    if len(cols) != 26:
        raise AssertionError("expected 26 columns, got %d" % len(cols))
    inside = np.isin(d["era_idx"], [SC.ERA_IDX[e] for e in SC.UNIVERSE_ERAS])
    if not bool(cov[inside].all()):
        raise AssertionError("%d E2..E8 rows uncovered"
                             % int((~cov[inside]).sum()))
    if bool(cov[~inside].any()):
        raise AssertionError("rows outside E2..E8 are covered")
    if np.isfinite(A[~cov]).any():
        raise AssertionError("uncovered rows are not typed-missing")


# ---------------------------------------------------- F6/B1: day memory -----
def t_daymem_causality():
    """BRUTE FORCE, on 40 asset-days: the vectorised memory must equal the
    definition computed the slow, obvious way — and never touch an episode
    whose certificate had not closed."""
    d = D()
    M = A2.day_memory(d)
    key = (d["asset_idx"].astype(np.int64) * 100000000
           + d["d8"].astype(np.int64))
    rs = np.random.RandomState(SC.SEED)
    uk = np.unique(key)
    for k in uk[rs.choice(uk.size, size=40, replace=False)].tolist():
        idx = np.nonzero(key == k)[0]
        idx = idx[np.argsort(d["dec_sec"][idx], kind="stable")]
        t = d["dec_sec"][idx].astype(np.int64)
        eps = d["ep"][idx]
        _u, first = np.unique(eps, return_index=True)
        ec = d["exit_close_sec"][idx][first].astype(np.float64)
        ev = d["cert_close_usd"][idx][first].astype(np.float64)
        for j in range(0, idx.size, max(1, idx.size // 20)):
            m = ec <= t[j]
            if float(M[idx[j], 1]) != float(m.sum()):
                raise AssertionError("n_prior_resolved mismatch on %d" % k)
            if m.any() and abs(float(M[idx[j], 2]) - float(ev[m].sum())) > 1.0:
                raise AssertionError("sum_usd mismatch on %d" % k)
            if m.any() and float(ec[m].max()) > t[j]:
                raise AssertionError("LEAK: unresolved episode in the memory")


def t_daymem_zero_at_open():
    """The first candidate of a session can have no memory at all."""
    d = D()
    M = A2.day_memory(d)
    key = (d["asset_idx"].astype(np.int64) * 100000000
           + d["d8"].astype(np.int64))
    order = np.lexsort((d["dec_sec"], key))
    ko = key[order]
    firsts = order[np.concatenate([[0], np.flatnonzero(ko[1:] != ko[:-1]) + 1])]
    if float(np.abs(M[firsts, 1:]).max()) != 0.0:
        raise AssertionError("the session's FIRST candidate carries memory")


# --------------------------------------------------- F6/B3: wall pairs ------
def t_wall_pairs_definition():
    """Every pair must satisfy the committed definition."""
    import common as C
    import baseline_replay as BR
    d = D()
    w, l = A2.wall_pairs(d)
    if w.size == 0:
        raise AssertionError("no wall pairs")
    kst, _s = BR.episode_pins(check=True)
    K = {i: max(kst[(a, 1)], kst[(a, -1)])
         for i, a in enumerate(C.ASSET_ORDER)}
    cc = d["cert_close_usd"]
    if not bool((cc[w] >= 1000.0).all()):
        raise AssertionError("a winner leg is below +$1,000")
    if not bool((cc[l] <= -900.0).all()):
        raise AssertionError("a loser leg is above -$900")
    if bool((d["side"][w] == d["side"][l]).any()):
        raise AssertionError("a pair is same-side")
    for f in ("asset_idx", "d8", "phase_dec"):
        if bool((d[f][w] != d[f][l]).any()):
            raise AssertionError("a pair crosses %s" % f)
    dt = np.abs(d["dec_sec"][w].astype(np.int64)
                - d["dec_sec"][l].astype(np.int64))
    kk = np.array([K[int(i)] for i in d["asset_idx"][w].tolist()])
    if bool((dt > kk).any()):
        raise AssertionError("a pair exceeds K*")


# ------------------------------------------- F3: the deployment group unit --
def t_day_groups_are_the_schedule_unit():
    """`build_groups(..., 'day')` must partition exactly the rows the deployed
    schedule chooses from, per (asset, session)."""
    import st_rank2 as RK2
    import st_rank as RK
    import m3_walk as W
    d = D()
    klass, _n = RK.class_index(d)
    ev = np.nonzero(d["era_idx"] == SC.ERA_IDX["E6"])[0]
    j = d["names"].index("in_news_window")
    ev_r = ev[d["X"][ev, j] < 0.5]
    g = RK2.build_groups(d, ev_r, klass, "day")
    flat = np.concatenate(g) if g else np.zeros(0, dtype=np.int64)
    if flat.size != np.unique(flat).size:
        raise AssertionError("day groups overlap")
    take = W.topn_takes(d, np.arange(float(d["d8"].size)), ev_r, 3,
                        deployable=True, unit="session")
    if not bool(np.isin(take, flat).all()):
        raise AssertionError("the schedule can seat a row no day group holds")


# -------------------------------------------------- F5: the label variant ---
def t_maecap_label():
    import st_champ as CH
    d = D()
    y0, c0 = CH.label_variant(d, "d021")
    y1, c1 = CH.label_variant(d, "maecap")
    if not np.array_equal(y0, d["y_winner"].astype(np.float64)):
        raise AssertionError("the d021 branch does not reproduce y_winner")
    import common as C
    for i, a in enumerate(MC.ASSET_ORDER):
        m = d["asset_idx"] == i
        want = 18.0 * float(C.ASSETS[a]["tick_usd"])
        if not np.allclose(c1[m], want):
            raise AssertionError("%s cap %.1f != %.1f" % (a, c1[m][0], want))
    # the variant is looser wherever the cap rose and tighter where it fell
    loose = (c1 > c0) & (y0 > 0)
    if bool((y1[loose] < y0[loose]).any()):
        raise AssertionError("a D-021 winner was dropped where the cap ROSE")


# ------------------------------------------------- F2: the transfer model ---
def t_ft2_zero_init_and_grads():
    """The day-memory projection is zero-initialised (so the model starts
    function-identical), and only the intended parameters train."""
    import torch
    import st_ft2 as F2
    import st_pretrain as P
    P.use_tokenizer("v2")
    m, _i = F2.build("RANDOM_V2", n_ctx=202, mode="fused", pool="attn",
                     unfreeze=4, lora=0, daymem=True, scratch=True)
    if float(m.mem_proj.weight.abs().max()) != 0.0:
        raise AssertionError("mem_proj is not zero-initialised")
    depth = len(m.lm.blocks)
    for i in range(depth - 4):
        if any(p.requires_grad for p in m.lm.blocks[i].parameters()):
            raise AssertionError("block %d should be frozen" % i)
    for i in range(depth - 4, depth):
        if not all(p.requires_grad for p in m.lm.blocks[i].parameters()):
            raise AssertionError("block %d should be trainable" % i)
    if m.lm.tok.weight.requires_grad:
        raise AssertionError("the embedding table should be frozen")
    groups, n_tr = F2.param_groups(m, 0.75)
    lrs = [g["lr"] for g in groups[:-1]]
    if len(lrs) > 1 and not all(lrs[i] < lrs[i + 1] + 1e-12
                                for i in range(len(lrs) - 1)):
        raise AssertionError("layer-wise LR decay is not increasing with depth")
    if any(not p.requires_grad for g in groups for p in g["params"]):
        raise AssertionError("a frozen parameter entered the optimiser")
    # LoRA: base frozen, adapters trainable, zero-initialised B
    m2, _i2 = F2.build("RANDOM_V2", n_ctx=202, mode="fused", pool="attn",
                       unfreeze=0, lora=8, daymem=False, scratch=True)
    blk = m2.lm.blocks[0]
    if float(blk.qkv.B.abs().max()) != 0.0:
        raise AssertionError("LoRA B is not zero-initialised")
    if any(p.requires_grad for p in blk.qkv.base.parameters()):
        raise AssertionError("the LoRA base weight is trainable")
    if not blk.qkv.A.requires_grad:
        raise AssertionError("the LoRA adapter is frozen")


def main():
    check("tok-v2 cached stream == independent recomputation", t_tok2_identity)
    check("tok-v2 no price bucket over 40%", t_tok2_occupancy)
    check("tok-v2 tokens inside the declared vocabulary", t_tok2_vocab_range)
    check("tok-v2 cuts fitted on PRE-A only", t_tok2_cuts_causal)
    check("creator E2..E8 reproduces the committed census",
          t_creator_reproduces_census)
    check("creator columns cover exactly E2..E8", t_creator_coverage)
    check("day memory == the brute-force definition (no leak)",
          t_daymem_causality)
    check("day memory is empty at the session open", t_daymem_zero_at_open)
    check("wall pairs satisfy the committed definition",
          t_wall_pairs_definition)
    check("day groups are the schedule's selection unit",
          t_day_groups_are_the_schedule_unit)
    check("MAE-cap label variant", t_maecap_label)
    check("fine-tune freezing / LoRA / layer-wise LR", t_ft2_zero_init_and_grads)
    print("\n%d checks, %d failures" % (12, len(FAIL)))
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
