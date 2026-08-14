#!/usr/bin/python3
"""PORT M2 SEQTEST — the lane's tests.

Every one of these is a *refusal* test or an *identity* test: either a guard
must fire, or a number must reproduce something already committed elsewhere.

Run:  /usr/bin/python3 engine/port_m2/seqtest/test_seqtest.py
"""
import json
import os
import sys
import traceback

import numpy as np

import st_common as SC
import st_build as SB
import st_model as SM

import m3_common as M3                     # noqa: E402
import m2_common as MC                     # noqa: E402

FAIL = []


def check(name, fn):
    try:
        fn()
        print("ok   %s" % name)
    except Exception as e:                  # noqa: BLE001
        FAIL.append((name, e))
        print("FAIL %s: %s" % (name, e))
        traceback.print_exc()


# --------------------------------------------------------------- guards -----
def t_dup_day_refused():
    d8 = np.array([1, 1, 2, 2, 3, 3])
    SC.assert_disjoint_days([0, 1, 2, 3], [4, 5], d8)
    try:
        SC.assert_disjoint_days([0, 1, 2, 3], [3, 4, 5], d8)
    except SC.SeqTestRefusal:
        return
    raise AssertionError("duplicate day was NOT refused")


def t_causal_era_refused():
    era = np.array([1, 1, 2, 2, 3, 3])
    SC.assert_causal_era_order([0, 1, 2, 3], [4, 5], era)
    try:
        SC.assert_causal_era_order([0, 1, 4], [4, 5], era)
    except SC.SeqTestRefusal:
        return
    raise AssertionError("non-causal fold was NOT refused")


def t_inner_split_matches_m3():
    import m3_walk as W
    for n in (12, 40, 129, 384):
        d = np.repeat(np.arange(20210101, 20210101 + n), 3)
        assert SC.inner_split_days(d) == W.inner_split(d), n


def t_cover_clamp():
    cov = [(0, 100), (500, 900), (2000, 2400)]
    assert SC.cover_start_sec(cov, 50) == 0
    assert SC.cover_start_sec(cov, 700) == 500
    assert SC.cover_start_sec(cov, 2400) == 2000
    # a second inside no block falls back to the last block that STARTED
    # before it — never to 0, which would splice unrelated tape
    assert SC.cover_start_sec(cov, 1500) == 500


# ---------------------------------------------------- the tensor identity ---
def _independent_window(asset, d8, dec, L):
    """A deliberately naive, from-scratch recomputation of one window."""
    z = np.load(os.path.join(SC.EVENTS_DIR, asset, "%08d.npz" % d8))
    arr = {k: z[k] for k in z.files}
    z.close()
    with open(os.path.join(SC.EVENTS_DIR, asset, "%08d.json" % d8)) as fh:
        meta = json.load(fh)
    o = int(meta["open_utc"])
    cover = [(int(a), int(b)) for a, b in meta["cover"]]
    ts = arr["ts_ns"]
    cut = (o + int(dec)) * 1_000_000_000
    hi = int(np.searchsorted(ts, cut, side="left"))
    cs = SC.cover_start_sec(cover, int(dec))
    lo0 = int(np.searchsorted(ts, (o + cs) * 1_000_000_000, side="left"))
    a = max(lo0, hi - L)
    out = np.zeros((SC.N_CH, L), dtype=np.float32)
    m = hi - a
    if m <= 0:
        return out
    tick = SC.tick_raw(asset)
    for i, code in enumerate(SC.ACTION_BYTES):
        out[i, L - m:] = (arr["action"][a:hi] == code)
    for i, code in enumerate(SC.SIDE_BYTES):
        out[6 + i, L - m:] = (arr["side"][a:hi] == code)
    px = arr["price"].astype(np.float64)
    mid = 0.5 * (arr["bid_px"] + arr["ask_px"]).astype(np.float64)
    dp = np.zeros(px.size)
    dp[1:] = (px[1:] - px[:-1]) / tick
    dm = np.zeros(px.size)
    dm[1:] = (mid[1:] - mid[:-1]) / tick
    out[9, L - m:] = np.clip(dp[a:hi], -SC.CLIP_TICKS, SC.CLIP_TICKS)
    out[10, L - m:] = np.clip(dm[a:hi], -SC.CLIP_TICKS, SC.CLIP_TICKS)
    out[11, L - m:] = np.clip((px[a:hi] - mid[a:hi]) / tick,
                              -SC.CLIP_TICKS, SC.CLIP_TICKS)
    out[12, L - m:] = np.log1p(arr["size"][a:hi].astype(np.float64))
    gap = np.zeros(px.size)
    gap[1:] = np.clip(np.diff(ts).astype(np.float64), 0, None)
    out[13, L - m:] = np.log1p(gap[a:hi] / 1e3)
    out[14, L - m:] = np.log1p(arr["bid_sz"][a:hi].astype(np.float64))
    out[15, L - m:] = np.log1p(arr["ask_sz"][a:hi].astype(np.float64))
    out[16, L - m:] = np.log1p(arr["bid_ct"][a:hi].astype(np.float64))
    out[17, L - m:] = np.log1p(arr["ask_ct"][a:hi].astype(np.float64))
    out[18, L - m:] = np.clip((arr["ask_px"][a:hi]
                               - arr["bid_px"][a:hi]).astype(np.float64) / tick,
                              -SC.CLIP_SPREAD, SC.CLIP_SPREAD)
    out[19, L - m:] = np.log1p(np.clip((cut - ts[a:hi]).astype(np.float64),
                                       0, None) / 1e9)
    out[20, L - m:] = 1.0
    return out


def t_tensor_identity():
    """The shard must equal an independent recomputation, to float16."""
    z = np.load(os.path.join(M3.MATRIX_DIR, "matrix.npz"), allow_pickle=False)
    d8, ai, era, dec = z["d8"], z["asset_idx"], z["era_idx"], z["dec_sec"]
    z.close()
    n_checked = 0
    for L in SC.SEQ_LENS:
        for asset in MC.ASSET_ORDER:
            base = SC.shard_path(asset, "E6", L)
            if not os.path.exists(base + ".npy"):
                continue
            T, ri, _ne = SB.load_shard(asset, "E6", L)
            for k in (0, ri.size // 3, ri.size - 1):
                row = int(ri[k])
                want = _independent_window(asset, int(d8[row]),
                                           int(dec[row]), L)
                got = np.asarray(T[k], dtype=np.float32)
                mx = float(np.max(np.abs(want.astype(np.float16)
                                         .astype(np.float32) - got)))
                assert mx == 0.0, "%s L=%d row %d: max abs diff %g" % (
                    asset, L, row, mx)
                n_checked += 1
            del T
    assert n_checked >= 3, "no shards were available to check"


def t_tensor_causality():
    """No valid cell may sit at or after its decision second."""
    for L in SC.SEQ_LENS:
        base = SC.shard_path("SI", "E6", L)
        if not os.path.exists(base + ".npy"):
            continue
        T, ri, _ne = SB.load_shard("SI", "E6", L)
        blk = np.asarray(T[:2000], dtype=np.float32)
        m = blk[:, SC.CH_VALID, :] > 0.5
        assert int((m & (blk[:, SC.CH_TTD, :] <= 0.0)).sum()) == 0, L
        # padding is exactly zero everywhere
        assert float(np.abs(blk * (~m)[:, None, :]).max()) == 0.0, L
        del T


def t_shard_rows_are_matrix_rows():
    z = np.load(os.path.join(M3.MATRIX_DIR, "matrix.npz"), allow_pickle=False)
    era, ai = z["era_idx"], z["asset_idx"]
    z.close()
    for asset in MC.ASSET_ORDER:
        base = SC.shard_path(asset, "E6", SC.SEQ_LENS[0])
        if not os.path.exists(base + ".npy"):
            continue
        _T, ri, _ne = SB.load_shard(asset, "E6", SC.SEQ_LENS[0])
        assert np.unique(era[ri]).tolist() == [SC.ERA_IDX["E6"]]
        assert np.unique(ai[ri]).tolist() == [MC.ASSET_ORDER.index(asset)]
        assert np.unique(ri).size == ri.size, "duplicate row indices"


# ---------------------------------------------------------------- models ----
def t_capacity_ladder():
    import torch
    for arch in SC.ARCHS:
        for rung in SC.RUNGS:
            for L in SC.SEQ_LENS:
                m, n = SM.make(arch, rung, L)
                tgt = SC.RUNG_TARGET[rung]
                assert 0.4 * tgt <= n <= 1.6 * tgt, (arch, rung, L, n)
                x = torch.zeros(2, SC.N_CH, L)
                out = m(x)
                assert tuple(out.shape) == (2, 2), (arch, rung, L, out.shape)


def t_pretrain_head_shapes():
    import torch
    for L in SC.SEQ_LENS:
        m, _n = SM.make("trf", "1M", L)
        patch = SC.TRF_PATCH[L]
        ntok = L // patch
        x = torch.randn(2, SC.N_CH, L)
        x[:, SC.CH_VALID, :] = 1.0
        mask = torch.rand(2, ntok) < 0.5
        p = m.forward_masked(x, mask)
        assert tuple(p.shape) == (2, ntok, patch * (len(SC.NORM_CH) + 9)), \
            (L, p.shape)
        loss = SM.pretrain_loss(p, x, mask, patch)
        assert np.isfinite(float(loss.item()))


# --------------------------------------------------------------- scoring ----
def t_schedule_is_m3_verbatim():
    """`score_arm` must call m3_walk's own selection and replay, and reproduce
    them exactly when driven with the same score."""
    import st_run as R
    import m3_walk as W
    D, _p = W.load_matrix()
    ev = np.nonzero(D["era_idx"] == SC.ERA_IDX["E6"])[0][:60000]
    rs = np.random.RandomState(7)
    s = rs.rand(D["d8"].size)
    take = W.topn_takes(D, s, ev, SC.SCHEDULE_N, deployable=True,
                        unit=SC.SCHEDULE_UNIT)
    rows = W.replay_rows(D, take)
    want = sum(r["realised"] for r in rows)
    ceil = {r["session"]: (1.0, 1, 1) for r in rows}
    got = R.score_arm(D, s, ev, ceil)
    assert got["n_takes"] == int(take.size)
    assert abs(sum(got["_realised"]) - want) < 1e-6
    seats = [j for r in rows for j in r["seats"]]
    assert got["n_seated"] == len(seats)


def main():
    check("duplicate-day guard refuses", t_dup_day_refused)
    check("non-causal era guard refuses", t_causal_era_refused)
    check("inner split == m3_walk.inner_split", t_inner_split_matches_m3)
    check("cover clamp", t_cover_clamp)
    check("shard rows are matrix rows", t_shard_rows_are_matrix_rows)
    check("tensor == independent recomputation", t_tensor_identity)
    check("tensor causality + zero padding", t_tensor_causality)
    check("capacity ladder shapes/params", t_capacity_ladder)
    check("masked-event head shapes", t_pretrain_head_shapes)
    check("schedule is m3_walk verbatim", t_schedule_is_m3_verbatim)
    print("\n%d checks, %d failures" % (10, len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
