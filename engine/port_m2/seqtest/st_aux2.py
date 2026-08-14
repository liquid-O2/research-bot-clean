#!/usr/bin/python3
"""PORT M2 FIXPASS2 — the two BACKLOG objects (F6), built once and shared.

B1 DAY-MEMORY.  `SEQ_STACK_BACKLOG.md`: "prepend compact summaries of the day's
prior episodes + resolutions to the input (within-day autocorrelation;
cell_rank_so_far was a top feature; targets MEMBER-RANKING)".

  THE CAUSALITY RULE, stated because this is exactly where a memory feature
  leaks: a prior candidate contributes to row i's memory ONLY IF it decided
  STRICTLY EARLIER (`dec_sec_j < dec_sec_i`) **and its certificate had already
  CLOSED** (`exit_close_sec_j <= dec_sec_i`).  Both conditions are asserted, not
  assumed — an episode still open at the decision second contributes nothing,
  because its outcome is not yet in the past.  The dollars used are the
  program's own committed `cert_close_usd`, which is a function of tape strictly
  before `exit_close_sec_j`, so every column here is computable at the decision
  second from past tape alone.

B3 WALL-PAIR HARD NEGATIVES.  `SEQ_STACK_BACKLOG.md`: "wall-pairs weighted into
the listwise loss as hard negatives".  A wall pair is the program's committed
object (`info_ceiling.build_pairs` / `creator_census.build_wall_pairs`): same
asset/day/phase cell, OPPOSITE sides, |delta dec_sec| <= K* (SI 180 / HG 120 /
NKD 150 s), entry mids within 0.5 x ATR14, one leg >= +$1,000 and the other
<= -$900.  It is the hardest ranking decision the program has: two candidates a
minute apart at the same price, and one of them is the whole session.

Run:  st_aux2.py --build
"""
import argparse
import json
import os
import time

import numpy as np

import st_common as SC
import st_creator as CR
import m2_common as MC

MEM_COLS = ("dm_n_prior_cand", "dm_n_prior_resolved", "dm_sum_usd",
            "dm_mean_usd", "dm_max_usd", "dm_min_usd", "dm_n_ge1000",
            "dm_n_le_m900", "dm_last_usd", "dm_secs_since_last")
N_MEM = len(MEM_COLS)

MEM_PATH = os.path.join(SC.CACHE_ROOT, "day_memory.npy")
PAIR_PATH = os.path.join(SC.CACHE_ROOT, "wall_pairs_e2e8.npz")

WIN_USD, WALL_USD, VIC = 1000.0, -900.0, 0.5


# ================================================================ B1 =========
def build_day_memory(D):
    """[n_rows, 10] causal within-day memory of RESOLVED prior episodes.

    An episode is collapsed to its EARLIEST member — which is exactly the trade
    the reader takes and what `BASE_EARLIEST` replays — and enters every later
    row of the same asset-day whose decision second is at or after that trade's
    certificate close.  O(n log n): per asset-day, a prefix scan over episodes
    ordered by close time, indexed by `searchsorted(close, dec_sec)`.
    """
    t0 = time.time()
    n = D["d8"].size
    out = np.zeros((n, N_MEM), dtype=np.float32)
    dec = D["dec_sec"].astype(np.int64)
    ex = D["exit_close_sec"].astype(np.float64)
    cc = D["cert_close_usd"].astype(np.float64)
    key = (D["asset_idx"].astype(np.int64) * 100000000
           + D["d8"].astype(np.int64))
    ep = D["ep"]
    order = np.lexsort((dec, key))
    ko = key[order]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [ko.size]
    for a, b in zip(starts, stops):
        idx = order[a:b]
        t = dec[idx]
        # one representative per episode: its earliest row
        eps = ep[idx]
        _u, first = np.unique(eps, return_index=True)
        e_close = ex[idx][first]
        e_val = cc[idx][first]
        o = np.argsort(e_close, kind="stable")
        e_close, e_val = e_close[o], e_val[o]
        k = np.searchsorted(e_close, t, side="right")     # resolved BEFORE t
        cs = np.concatenate([[0.0], np.cumsum(e_val)])
        cn = np.arange(e_close.size + 1, dtype=np.float64)
        cge = np.concatenate([[0.0], np.cumsum(e_val >= WIN_USD)])
        cle = np.concatenate([[0.0], np.cumsum(e_val <= WALL_USD)])
        cmx = np.concatenate([[-np.inf], np.maximum.accumulate(e_val)])
        cmn = np.concatenate([[np.inf], np.minimum.accumulate(e_val)])
        last = np.concatenate([[0.0], e_val])
        lastt = np.concatenate([[np.nan], e_close])
        out[idx, 0] = np.searchsorted(t, t, side="left").astype(np.float32)
        out[idx, 1] = cn[k]
        out[idx, 2] = cs[k]
        out[idx, 3] = np.where(k > 0, cs[k] / np.maximum(cn[k], 1.0), 0.0)
        out[idx, 4] = np.where(k > 0, cmx[k], 0.0)
        out[idx, 5] = np.where(k > 0, cmn[k], 0.0)
        out[idx, 6] = cge[k]
        out[idx, 7] = cle[k]
        out[idx, 8] = last[k]
        out[idx, 9] = np.where(k > 0, t - np.nan_to_num(lastt[k]), 0.0)
        if k.size and int(k.max()) > 0:
            bad = int((np.nan_to_num(lastt[k], nan=-1e18) > t).sum())
            if bad:
                raise SC.SeqTestRefusal(
                    "DAY-MEMORY CAUSALITY: %d rows drew on an unresolved "
                    "episode" % bad)
    SC.hb("day memory built: %d rows, %.1f%% carry a resolved prior episode "
          "(%.0fs)" % (n, 100.0 * float((out[:, 1] > 0).mean()),
                       time.time() - t0))
    return out


_MEM = {}


def day_memory(D, rebuild=False):
    if "M" in _MEM:
        return _MEM["M"]
    if os.path.exists(MEM_PATH) and not rebuild:
        M = np.load(MEM_PATH)
        if M.shape == (D["d8"].size, N_MEM):
            _MEM["M"] = M
            return M
    M = build_day_memory(D)
    np.save(MEM_PATH, M)
    _MEM["M"] = M
    return M


def mem_norm(M, rows):
    """Train-only standardisation of the memory block (log1p on the counts and
    a signed log on the dollars, so a $19k session does not dominate)."""
    Z = np.sign(M) * np.log1p(np.abs(M))
    mu = Z[rows].mean(0)
    sd = np.maximum(Z[rows].std(0), 1e-3)
    return Z.astype(np.float32), mu.astype(np.float32), sd.astype(np.float32)


# ================================================================ B3 =========
def build_wall_pairs(D, rows=None):
    """The committed wall-pair definition, on matrix rows E2..E8."""
    import common as C
    import baseline_replay as BR
    kst, _spn = BR.episode_pins(check=True)
    KST = {a: max(kst[(a, 1)], kst[(a, -1)]) for a in C.ASSET_ORDER}
    mid = CR.entry_mid(D)
    j = D["names"].index("atr_usd")
    atr = D["X"][:, j].astype(np.float64)
    cert = D["cert_close_usd"].astype(np.float64)
    ok = (D["cert_refused"] == 0) & np.isfinite(mid)
    if rows is not None:
        m = np.zeros(D["d8"].size, dtype=bool)
        m[np.asarray(rows, dtype=np.int64)] = True
        ok = ok & m
    key = (D["asset_idx"].astype(np.int64) * 1000000000
           + D["d8"].astype(np.int64)) * 10 + D["phase_dec"].astype(np.int64)
    idx = np.nonzero(ok)[0]
    o = np.argsort(key[idx], kind="stable")
    idx = idx[o]
    ko = key[idx]
    starts = [0] + (np.flatnonzero(ko[1:] != ko[:-1]) + 1).tolist()
    stops = starts[1:] + [ko.size]
    pw, pl = [], []
    for a, b in zip(starts, stops):
        s = idx[a:b]
        if s.size < 2:
            continue
        w = s[cert[s] >= WIN_USD]
        l = s[cert[s] <= WALL_USD]
        if w.size == 0 or l.size == 0:
            continue
        K = KST[C.ASSET_ORDER[int(D["asset_idx"][s[0]])]]
        for x in w.tolist():
            for y in l.tolist():
                if D["side"][x] == D["side"][y]:
                    continue
                if abs(int(D["dec_sec"][x]) - int(D["dec_sec"][y])) > K:
                    continue
                aa = np.nanmean([atr[x], atr[y]])
                if not np.isfinite(aa) or aa <= 0:
                    continue
                if abs(float(mid[x]) - float(mid[y])) > VIC * aa:
                    continue
                pw.append(x)
                pl.append(y)
    return np.asarray(pw, dtype=np.int64), np.asarray(pl, dtype=np.int64)


_WP = {}


def wall_pairs(D, rebuild=False):
    if "w" in _WP:
        return _WP["w"], _WP["l"]
    if os.path.exists(PAIR_PATH) and not rebuild:
        z = np.load(PAIR_PATH)
        _WP["w"], _WP["l"] = z["w"], z["l"]
        z.close()
        return _WP["w"], _WP["l"]
    t0 = time.time()
    rows = np.nonzero(np.isin(D["era_idx"],
                              [SC.ERA_IDX[e] for e in SC.UNIVERSE_ERAS]))[0]
    w, l = build_wall_pairs(D, rows)
    np.savez(PAIR_PATH, w=w, l=l)
    SC.hb("wall pairs E2..E8: %d pairs, %d distinct winner legs, %d loser legs "
          "(%.0fs)" % (w.size, np.unique(w).size, np.unique(l).size,
                       time.time() - t0))
    _WP["w"], _WP["l"] = w, l
    return w, l


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    a = ap.parse_args()
    if a.build:
        import m3_walk as W
        D, _p = W.load_matrix()
        M = day_memory(D, rebuild=True)
        w, l = wall_pairs(D, rebuild=True)
        print(json.dumps({
            "memory_rows": int(M.shape[0]), "memory_cols": list(MEM_COLS),
            "frac_with_resolved_prior": round(float((M[:, 1] > 0).mean()), 4),
            "mean_n_prior_resolved": round(float(M[:, 1].mean()), 3),
            "wall_pairs": int(w.size),
            "wall_pair_winner_legs": int(np.unique(w).size),
            "wall_pair_loser_legs": int(np.unique(l).size)}, indent=1))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
