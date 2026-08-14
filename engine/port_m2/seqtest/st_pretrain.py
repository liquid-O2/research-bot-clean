#!/usr/bin/python3
"""PORT M2 SEQTEST — self-supervised AUTOREGRESSIVE next-event pretraining, and
the fine-tune that spends the labels.

Implements `design/SEQ_PRETRAIN_DESIGN.md` (+ AMENDMENT 1) exactly:

  * decoder-only transformer, 512d / 12L / 8H / ffn 2048, context 1024 events,
    tied embeddings, learned positions, learned ASSET embedding, ~40M params;
  * objective = cross-entropy on the next composite EVENT TOKEN (§3 vocab);
  * corpora: PRE-A `d8 < 20240101` (the CAUSAL headline, strictly older than
    E6/E7/E8) and PRE-B `d8 < 20250701` (the full pre-holdout corpus, reported
    only with a NON-CAUSAL flag);
  * trunks: SHARED-3 (SI+HG+NKD, asset embedding) and SI-ONLY (A1.1);
  * ONE pass over the corpus (A1.2), 2 epochs the hard cap;
  * a mandatory 5-minute SMOKE that measures tokens/s and writes the wall-time
    arithmetic into the receipt BEFORE the real run; if the measurement puts a
    full pass past the 3h ceiling the corpus is TRUNCATED oldest-first and the
    truncation is reported.

Fine-tuning reuses the lane's anti-overfit stack unchanged: whole-DAY folds, the
walk-forward era ladder, early stopping on the training block's last 20% of
days, and `st_run`'s scoring, which is `m3_walk`'s deployable arm verbatim.

Run:
    st_pretrain.py --smoke
    st_pretrain.py --pretrain --corpus A --scope shared
    st_pretrain.py --finetune --trunk PRE_A_shared [--scratch]
"""
import os

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import argparse                            # noqa: E402
import json                                # noqa: E402
import math                                # noqa: E402
import time                                # noqa: E402

import numpy as np                         # noqa: E402
import torch                               # noqa: E402
import torch.nn as nn                      # noqa: E402
import torch.nn.functional as F            # noqa: E402

import st_common as SC                     # noqa: E402
import st_tok as TK                        # noqa: E402
import st_run as R                         # noqa: E402
import m2_common as MC                     # noqa: E402
import m3_common as M3                     # noqa: E402

DEV = R.DEV

# ---- the frozen model card (design receipt §4) -----------------------------
D_MODEL = 512
DEPTH = 12
HEADS = 8
FFN = 2048
CTX = TK.CTX
PT_BATCH = 128
PT_LR = 3e-4
PT_WARMUP = 200
PT_EPOCHS_MAX = 2
WALL_CEILING_SEC = 3 * 3600
SMOKE_SEC = 300

# ---- fine-tune ------------------------------------------------------------
FT_BATCH = 256
FT_LR_TRUNK = 3e-5
FT_LR_HEAD = 1e-3
FT_EPOCHS = 6
FT_PATIENCE = 2

TRUNK_DIR = os.path.join(SC.CACHE_ROOT, "trunks")


# ================================================================== model ====
class Block(nn.Module):
    def __init__(self, d=D_MODEL, h=HEADS, ffn=FFN, p=0.0):
        super(Block, self).__init__()
        self.n1 = nn.LayerNorm(d)
        self.qkv = nn.Linear(d, 3 * d)
        self.proj = nn.Linear(d, d)
        self.n2 = nn.LayerNorm(d)
        self.fc1 = nn.Linear(d, ffn)
        self.fc2 = nn.Linear(ffn, d)
        self.h = h
        self.d = d

    def forward(self, x):
        B, T, C = x.shape
        y = self.n1(x)
        q, k, v = self.qkv(y).split(C, dim=2)
        q = q.view(B, T, self.h, C // self.h).transpose(1, 2)
        k = k.view(B, T, self.h, C // self.h).transpose(1, 2)
        v = v.view(B, T, self.h, C // self.h).transpose(1, 2)
        y = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        x = x + self.proj(y)
        x = x + self.fc2(F.gelu(self.fc1(self.n2(x))))
        return x


N_SIDE = 10                                # st_aux.N_IN (clock + level channels)
N_HORIZON_TGT = 8                          # st_aux.N_TGT (h60 then h300)
CPC_OFFSETS = (64, 256)


class EventLM(nn.Module):
    """The shared backbone.  `n_assets=1` is the SI-ONLY trunk of A1.1.

    `side=True` adds the AMENDMENT 4 per-event input channels (session/phase
    clock + level-relative distances) through a ZERO-INITIALISED projection, so
    a side-enabled model is function-identical to a token-only one at
    initialisation and the two trunks stay comparable.
    """

    def __init__(self, vocab=TK.VOCAB, d=D_MODEL, depth=DEPTH, h=HEADS,
                 ffn=FFN, ctx=CTX, n_assets=3, side=False, multi=False):
        super(EventLM, self).__init__()
        self.tok = nn.Embedding(vocab, d)
        self.pos = nn.Parameter(torch.zeros(1, ctx, d))
        nn.init.trunc_normal_(self.pos, std=0.02)
        self.asset = nn.Embedding(max(n_assets, 1), d)
        nn.init.zeros_(self.asset.weight)
        self.side = side
        if side:
            self.side_proj = nn.Linear(N_SIDE, d)
            nn.init.zeros_(self.side_proj.weight)
            nn.init.zeros_(self.side_proj.bias)
        self.blocks = nn.ModuleList([Block(d, h, ffn) for _ in range(depth)])
        self.nf = nn.LayerNorm(d)
        self.lm = nn.Linear(d, vocab, bias=False)
        self.lm.weight = self.tok.weight          # tied
        self.multi = multi
        if multi:
            self.h_head = nn.Sequential(nn.Linear(d, d), nn.GELU(),
                                        nn.Linear(d, N_HORIZON_TGT))
            self.cpc = nn.ModuleList([nn.Linear(d, d, bias=False)
                                      for _ in CPC_OFFSETS])
        self.ctx = ctx

    def trunk(self, x, a, sd=None):
        h = self.tok(x) + self.pos[:, :x.shape[1], :] + self.asset(a)[:, None, :]
        if self.side and sd is not None:
            h = h + self.side_proj(sd)
        for b in self.blocks:
            h = b(h)
        return self.nf(h)

    def forward(self, x, a, sd=None):
        return self.lm(self.trunk(x, a, sd))


class EventHead(nn.Module):
    """THE FUSED HEAD (design receipt AMENDMENT 2).

        obs = [pooled pretrained sequence embedding] (+) [the m3 matrix's
               context feature vector at the decision second]

    `mode` selects the declared three-row ablation:
        "seq"    the pooled sequence embedding alone
        "ctx"    the context features alone, through the same MLP
        "fused"  both, concatenated — the interaction row
    The context branch is a small MLP so that CTX_ONLY is a real model and not
    a linear probe, and so FUSED's advantage cannot be an artefact of capacity.
    """

    def __init__(self, lm, n_ctx=0, d=D_MODEL, p=0.1, mode="fused"):
        super(EventHead, self).__init__()
        self.lm = lm
        self.mode = mode
        self.n_ctx = int(n_ctx)
        dim = 0
        if mode in ("seq", "fused"):
            dim += 2 * d
        if mode in ("ctx", "fused"):
            self.ctx_mlp = nn.Sequential(nn.Linear(2 * self.n_ctx, 512),
                                         nn.GELU(), nn.Dropout(p),
                                         nn.Linear(512, 256), nn.GELU())
            dim += 256
        self.head = nn.Sequential(nn.Linear(dim, d), nn.GELU(),
                                  nn.Dropout(p), nn.Linear(d, 2))

    def forward(self, x, a, c=None):
        parts = []
        if self.mode in ("seq", "fused"):
            h = self.lm.trunk(x, a)
            parts.append(torch.cat([h[:, -1, :], h.mean(1)], -1))
        if self.mode in ("ctx", "fused"):
            parts.append(self.ctx_mlp(c))
        return self.head(torch.cat(parts, -1) if len(parts) > 1 else parts[0])


def n_params(m):
    return int(sum(p.numel() for p in m.parameters()))


# =============================================================== pretrain ====
def _corpus(corpus, scope, multi=False, split=False):
    max_d8 = 20240101 if corpus == "A" else 20250701
    assets = MC.ASSET_ORDER if scope == "shared" else ("SI",)
    T, S, A = TK.load_pretrain_corpus(max_d8, assets=assets)
    IN = TG = None
    if multi:
        import st_aux as AX
        IN, TG = AX.load_aux(max_d8, assets=assets)
        if IN.shape[0] != T.size:
            raise SC.SeqTestRefusal(
                "aux stream %d != token stream %d" % (IN.shape[0], T.size))
    return T, S, A, max_d8, assets, IN, TG


def split_chunks(max_d8, assets, S, A):
    """Whole-DAY held-out split of the pretraining corpus itself."""
    vd = val_day_set(max_d8, assets)
    bounds, day_of = [], []
    at = 0
    for a_i, asset in enumerate(assets):
        d = os.path.join(TK.TOK_DIR, asset)
        for f in sorted(os.listdir(d)):
            if not f.endswith(".npz") or int(f[:-4]) >= int(max_d8):
                continue
            z = np.load(os.path.join(d, f))
            n = int(z["tok"].size)
            z.close()
            bounds.append((at, at + n, int(f[:-4])))
            at += n
    lo = np.array([b[0] for b in bounds], dtype=np.int64)
    day = np.array([b[2] for b in bounds], dtype=np.int64)
    k = np.searchsorted(lo, S, side="right") - 1
    is_val = np.isin(day[np.clip(k, 0, day.size - 1)],
                     np.array(sorted(vd), dtype=np.int64))
    return (~is_val), is_val, len(vd)


def balanced_sampler(A, n_assets, seed=SC.SEED):
    """ASSET-BALANCED batch sampling (A4.3): SI is ~44% of the cached events,
    so a uniform draw would make the shared trunk an SI model with accents."""
    pools = [np.nonzero(A == k)[0] for k in range(n_assets)]
    pools = [p for p in pools if p.size]
    rng = np.random.RandomState(int(seed))

    def draw(bs):
        per = max(1, bs // len(pools))
        out = np.concatenate([rng.choice(p, size=per, replace=False)
                              for p in pools])
        if out.size < bs:
            out = np.concatenate([out, rng.choice(pools[0],
                                                  size=bs - out.size)])
        return out[:bs]
    return draw


W_NEXT, W_H60, W_H300, W_CPC = 1.0, 0.30, 0.30, 0.20

# ---- THE PRETRAIN QUALITY GATES (coordinator amendment, 2026-08-16) --------
# A held-out-DAY validation split of the pretraining objective itself: whole
# days, all assets, never trained on.  Selection is by VAL (and the downstream
# benchmark), never by train loss; two consecutive rises in val stop the run and
# the best-val checkpoint is restored.
VAL_EVERY = 400                            # steps between evaluations
VAL_CHUNKS = 3000                          # held-out chunks scored per eval
VAL_DAY_STRIDE = 11                        # every 11th trade date is held out
VAL_PATIENCE = 2
VAL_BAND = 0.35                            # |val - train| must stay inside this


def val_day_set(max_d8, assets=MC.ASSET_ORDER):
    """Every VAL_DAY_STRIDE-th cached trade date, ALL assets — whole days."""
    days = set()
    for asset in assets:
        d = os.path.join(TK.TOK_DIR, asset)
        for f in sorted(os.listdir(d)):
            if f.endswith(".npz") and int(f[:-4]) < int(max_d8):
                days.add(int(f[:-4]))
    ds = sorted(days)
    return set(ds[::VAL_DAY_STRIDE])


def bigram_val_loss(T, S_tr, S_va, vocab=TK.VOCAB, chunk=40_000_000):
    """The 'did it actually learn structure' floor: a Laplace-smoothed bigram
    fitted on the TRAINING chunks, scored on the held-out ones."""
    cnt = np.zeros(vocab * vocab, dtype=np.int32)
    def stream(S):
        for a in range(0, S.size, 4096):
            st = S[a:a + 4096]
            for s0 in st.tolist():
                yield T[s0:s0 + CTX].astype(np.int64)
    buf = []
    tot = 0
    for w in stream(S_tr):
        buf.append(w[:-1] * vocab + w[1:])
        tot += w.size
        if tot > chunk:
            cnt += np.bincount(np.concatenate(buf),
                               minlength=vocab * vocab).astype(np.int32)
            buf, tot = [], 0
    if buf:
        cnt += np.bincount(np.concatenate(buf),
                           minlength=vocab * vocab).astype(np.int32)
    M = cnt.reshape(vocab, vocab).astype(np.float64) + 1.0
    logp = np.log(M) - np.log(M.sum(1, keepdims=True))
    ll, n = 0.0, 0
    for w in stream(S_va):
        ll += float(logp[w[:-1], w[1:]].sum())
        n += w.size - 1
    return float(-ll / max(n, 1))


def _batch(T, S, A, idx, IN=None, TG=None):
    if IN is not None and IN.shape[0] != T.size:
        raise SC.SeqTestRefusal("aux rows %d != token rows %d"
                                % (IN.shape[0], T.size))
    st = S[idx]
    x = np.empty((idx.size, CTX), dtype=np.int64)
    sd = tg = None
    if IN is not None:
        sd = np.empty((idx.size, CTX, IN.shape[1]), dtype=np.float32)
        tg = np.empty((idx.size, CTX, TG.shape[1]), dtype=np.float32)
    for i, s in enumerate(st.tolist()):
        x[i] = T[s:s + CTX]
        if IN is not None:
            sd[i] = IN[s:s + CTX]
            tg[i] = TG[s:s + CTX]
    out = [torch.from_numpy(x).to(DEV, non_blocking=True),
           torch.from_numpy(A[idx].astype(np.int64)).to(DEV)]
    out.append(None if sd is None else torch.from_numpy(sd).to(DEV))
    out.append(None if tg is None else torch.from_numpy(tg).to(DEV))
    return out


def _step(model, opt, T, S, A, idx, IN=None, TG=None):
    """The weighted objective of design receipt AMENDMENT 3."""
    x, a, sd, tg = _batch(T, S, A, idx, IN, TG)
    parts = {}
    with torch.autocast("cuda", dtype=torch.bfloat16, enabled=(DEV == "cuda")):
        h = model.trunk(x[:, :-1], a, None if sd is None else sd[:, :-1])
        logits = model.lm(h)
    loss = F.cross_entropy(logits.float().reshape(-1, TK.VOCAB),
                           x[:, 1:].reshape(-1))
    parts["next"] = float(loss.item())
    if getattr(model, "multi", False) and tg is not None:
        p = model.h_head(h.float())
        t = tg[:, :-1, :]
        m = torch.isfinite(t)
        for k, (lo, w, nm) in enumerate(((0, W_H60, "h60"),
                                         (4, W_H300, "h300"))):
            pk = p[:, :, lo:lo + 4]
            tk = t[:, :, lo:lo + 4]
            mk = m[:, :, lo:lo + 4]
            if mk.any():
                l = F.smooth_l1_loss(pk[mk], torch.nan_to_num(tk)[mk])
                loss = loss + w * l
                parts[nm] = float(l.item())
        # CPC: predict the model's OWN representation N events ahead
        z = F.normalize(h.float(), dim=-1)
        for k, off in enumerate(CPC_OFFSETS):
            if h.shape[1] <= off + 8:
                continue
            q = F.normalize(model.cpc[k](h[:, :-off, :].float()), dim=-1)
            tgt = z[:, off:, :].detach()
            step = max(1, q.shape[1] // 32)
            qs = q[:, ::step, :].reshape(-1, q.shape[-1])
            ts_ = tgt[:, ::step, :].reshape(-1, tgt.shape[-1])
            sim = qs @ ts_.t() / 0.1
            lab = torch.arange(qs.shape[0], device=qs.device)
            l = F.cross_entropy(sim, lab)
            loss = loss + W_CPC * l
            parts["cpc%d" % off] = float(l.item())
    opt.zero_grad(set_to_none=True)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    opt.step()
    parts["total"] = float(loss.item())
    return parts


@torch.no_grad()
def eval_val(model, T, S, A, IN, TG, idx, n_assets, bs=64):
    """Held-out-day loss of the pretraining objective, overall and PER ASSET."""
    model.eval()
    tot = {"n": 0, "ll": 0.0}
    per = {k: {"n": 0, "ll": 0.0} for k in range(n_assets)}
    for a in range(0, idx.size, bs):
        sel = np.sort(idx[a:a + bs])
        x, av, sd, _tg = _batch(T, S, A, sel, IN, TG)
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=(DEV == "cuda")):
            h = model.trunk(x[:, :-1], av, None if sd is None else sd[:, :-1])
            lg = model.lm(h)
        ce = F.cross_entropy(lg.float().reshape(-1, TK.VOCAB),
                             x[:, 1:].reshape(-1), reduction="none")
        ce = ce.view(x.shape[0], -1).mean(1).cpu().numpy()
        for j, k in enumerate(A[sel].tolist()):
            per[int(k)]["n"] += 1
            per[int(k)]["ll"] += float(ce[j])
        tot["n"] += ce.size
        tot["ll"] += float(ce.sum())
    model.train()
    return (tot["ll"] / max(tot["n"], 1),
            {MC.ASSET_ORDER[k]: (v["ll"] / v["n"]) for k, v in per.items()
             if v["n"]})


def smoke(corpus="A", scope="shared", secs=SMOKE_SEC, multi=False,
          preloaded=None):
    """THE MANDATORY MEASUREMENT.  Tokens/s on this GPU, and the wall-time
    arithmetic the design receipt says must exist before the real run."""
    T, S, A, max_d8, assets, IN, TG = preloaded or _corpus(corpus, scope, multi)
    torch.manual_seed(SC.SEED)
    model = EventLM(n_assets=len(assets), side=multi, multi=multi).to(DEV)
    npar = n_params(model)
    opt = torch.optim.AdamW(model.parameters(), lr=PT_LR, weight_decay=0.01)
    rng = np.random.RandomState(SC.SEED)
    t0 = time.time()
    n_tok, steps, losses = 0, 0, []
    while time.time() - t0 < secs:
        idx = rng.randint(0, S.size, size=PT_BATCH)
        losses.append(_step(model, opt, T, S, A, idx, IN, TG)["total"])
        n_tok += PT_BATCH * (CTX - 1)
        steps += 1
        if steps % 50 == 0:
            SC.hb("smoke step %d loss=%.4f %.0f tok/s"
                  % (steps, float(np.mean(losses[-50:])),
                     n_tok / (time.time() - t0)))
    dt = time.time() - t0
    tps = n_tok / dt
    total = int(S.size) * (CTX - 1)
    out = {"corpus": corpus, "scope": scope, "max_d8": max_d8,
           "multi_horizon": bool(multi),
           "assets": list(assets), "params": npar,
           "n_chunks": int(S.size), "corpus_tokens": total,
           "measured_tokens_per_sec": round(tps, 1),
           "measured_steps_per_sec": round(steps / dt, 3),
           "implied_full_pass_sec": round(total / tps, 1),
           "implied_full_pass_hours": round(total / tps / 3600.0, 3),
           "flops_6NT": 6.0 * npar * total,
           "implied_tflops": round(6.0 * npar * tps / 1e12, 1),
           "ceiling_sec": WALL_CEILING_SEC,
           "fits_ceiling": bool(total / tps <= WALL_CEILING_SEC),
           "smoke_secs": round(dt, 1), "smoke_steps": steps,
           "loss_first50": float(np.mean(losses[:50])),
           "loss_last50": float(np.mean(losses[-50:]))}
    SC.hb("SMOKE %s/%s: %.0f tok/s, %.1f TFLOP/s, full pass %.2f h, fits=%s"
          % (corpus, scope, tps, out["implied_tflops"],
             out["implied_full_pass_hours"], out["fits_ceiling"]))
    del model, opt
    if DEV == "cuda":
        torch.cuda.empty_cache()
    return out


def pretrain(corpus="A", scope="shared", budget_sec=None, epochs=1,
             multi=False):
    os.makedirs(TRUNK_DIR, exist_ok=True)
    tag = "PRE_V_%s%s" % (scope, "_MULTI" if multi else "_NEXT")
    pre = _corpus(corpus, scope, multi)
    sm = smoke(corpus, scope, multi=multi, preloaded=pre)
    T, S, A, max_d8, assets, IN, TG = pre
    tr_m, va_m, n_val_days = split_chunks(max_d8, assets, S, A)
    S_all, A_all = S, A
    S_va, A_va = S[va_m], A[va_m]
    S, A = S[tr_m], A[tr_m]
    rs = np.random.RandomState(SC.SEED)
    va_idx = np.sort(rs.choice(S_va.size, size=min(VAL_CHUNKS, S_va.size),
                               replace=False))
    SC.hb("val split: %d held-out DAYS, %d/%d chunks held out"
          % (n_val_days, S_va.size, S_all.size))
    draw = balanced_sampler(A, len(assets))
    torch.manual_seed(SC.SEED)
    model = EventLM(n_assets=len(assets), side=multi, multi=multi).to(DEV)
    opt = torch.optim.AdamW(model.parameters(), lr=PT_LR, weight_decay=0.01)
    total_steps = int(min(int(epochs), PT_EPOCHS_MAX) * S.size / PT_BATCH)
    budget = budget_sec or WALL_CEILING_SEC
    # TRUNCATION RULE (design receipt S4): never overrun the ceiling; cut the
    # corpus OLDEST-FIRST and say so.
    est = total_steps / max(sm["measured_steps_per_sec"], 1e-9)
    truncated = False
    if est > budget:
        keep = int(budget * sm["measured_steps_per_sec"] * PT_BATCH)
        keep = max(keep, PT_BATCH * 100)
        order = np.argsort(S, kind="stable")   # chunk order == calendar order
        S = S[order][-keep:]
        A = A[order][-keep:]
        # THE SAMPLER IS REBUILT ON THE TRUNCATED ARRAYS.  It indexes S/A
        # POSITIONALLY, so a sampler built before the cut would hand back
        # out-of-range positions (observed: IndexError 653401 vs size 651059).
        draw = balanced_sampler(A, len(assets))
        total_steps = int(S.size / PT_BATCH)
        truncated = True
        SC.hb("TRUNCATED oldest-first to %d chunks (%d steps) to hold the "
              "%.1fh ceiling" % (S.size, total_steps, budget / 3600.0))
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=PT_LR, total_steps=max(total_steps, 2),
        pct_start=min(0.05, PT_WARMUP / max(total_steps, 1)), anneal_strategy="cos")
    t0 = time.time()
    losses, curve, heads, vcurve = [], [], {}, []
    best_val, best_step, val_bad, best_state = np.inf, 0, 0, None
    if S.size != A.size:
        raise SC.SeqTestRefusal("chunk/asset length mismatch %d != %d"
                                % (S.size, A.size))
    for step in range(total_steps):
        idx = np.sort(draw(PT_BATCH))
        if idx.max() >= S.size:
            raise SC.SeqTestRefusal(
                "sampler index %d out of range for %d chunks — the sampler and "
                "the corpus disagree" % (int(idx.max()), int(S.size)))
        parts = _step(model, opt, T, S, A, idx, IN, TG)
        losses.append(parts["total"])
        for k2, v2 in parts.items():
            heads.setdefault(k2, []).append(v2)
        sched.step()
        if (step + 1) % VAL_EVERY == 0 or step + 1 == total_steps:
            vl, vper = eval_val(model, T, S_va, A_va, IN, TG, va_idx,
                                len(assets))
            trl = float(np.mean(heads["next"][-VAL_EVERY:]))
            vcurve.append([step + 1, round(trl, 5), round(vl, 5),
                           {k2: round(v2, 5) for k2, v2 in vper.items()},
                           round(time.time() - t0, 1)])
            SC.hb("VAL %s step %d train_next=%.4f val_next=%.4f per_asset=%s"
                  % (tag, step + 1, trl, vl,
                     {k2: round(v2, 4) for k2, v2 in vper.items()}))
            if vl < best_val:
                best_val, best_step, val_bad = vl, step + 1, 0
                best_state = {k2: v2.detach().cpu().clone()
                              for k2, v2 in model.state_dict().items()}
            else:
                val_bad += 1
                if val_bad >= VAL_PATIENCE:
                    SC.hb("OVERFIT GATE FIRED at step %d: val rose on %d "
                          "consecutive evals; reverting to the best-val "
                          "checkpoint at step %d" % (step + 1, val_bad,
                                                     best_step))
                    break
        if (step + 1) % 200 == 0:
            m = float(np.mean(losses[-200:]))
            curve.append([step + 1, round(m, 5),
                          {k2: round(float(np.mean(v2[-200:])), 5)
                           for k2, v2 in heads.items()},
                          round(time.time() - t0, 1)])
            SC.hb("pretrain %s step %d/%d loss=%.4f ppl=%.1f %.0f tok/s "
                  "(%.0fs)" % (tag, step + 1, total_steps, m, math.exp(m),
                               (step + 1) * PT_BATCH * (CTX - 1)
                               / (time.time() - t0), time.time() - t0))
        if time.time() - t0 > budget:
            SC.hb("pretrain %s: wall ceiling hit at step %d" % (tag, step + 1))
            break
    info = dict(sm)
    if best_state is not None:
        model.load_state_dict({k2: v2.to(DEV) for k2, v2 in best_state.items()})
    bg = bigram_val_loss(T, S[::max(1, S.size // 6000)], S_va[va_idx])
    info.update({"tag": tag, "multi_horizon": bool(multi),
                 "val_curve": vcurve, "n_val_days": n_val_days,
                 "n_val_chunks": int(S_va.size),
                 "best_val_next": (None if not np.isfinite(best_val)
                                   else float(best_val)),
                 "best_val_step": int(best_step),
                 "best_val_ppl": (None if not np.isfinite(best_val)
                                  else float(math.exp(best_val))),
                 "bigram_val_loss": bg, "bigram_val_ppl": float(math.exp(bg)),
                 "beats_bigram": bool(np.isfinite(best_val) and best_val < bg),
                 "overfit_gate_fired": bool(val_bad >= VAL_PATIENCE),
                 "val_band": VAL_BAND,
                 "head_loss_last200": {k2: float(np.mean(v2[-200:]))
                                       for k2, v2 in heads.items()},
                 "head_loss_first200": {k2: float(np.mean(v2[:200]))
                                        for k2, v2 in heads.items()},
                 "steps_run": len(losses),
                 "epochs_requested": int(epochs), "truncated": truncated,
                 "wall_sec": round(time.time() - t0, 1),
                 "loss_first200": float(np.mean(losses[:200])),
                 "loss_last200": float(np.mean(losses[-200:])),
                 "ppl_last200": float(math.exp(np.mean(losses[-200:]))),
                 "curve": curve})
    with open(os.path.join(SC.CACHE_ROOT, "token_counts.npy"), "rb") as fh:
        pass
    cnt = np.load(os.path.join(SC.CACHE_ROOT, "token_counts.npy"))
    p = cnt.astype(np.float64) / max(cnt.sum(), 1)
    nz = p[p > 0]
    info["unigram_entropy_nats"] = float(-(nz * np.log(nz)).sum())
    info["beats_unigram"] = bool(info["loss_last200"]
                                 < info["unigram_entropy_nats"])
    torch.save({"state": model.state_dict(), "n_assets": len(assets),
                "side": bool(multi), "multi": bool(multi), "info": info},
               os.path.join(TRUNK_DIR, "%s.pt" % tag))
    with open(os.path.join(TRUNK_DIR, "%s.json" % tag), "w") as fh:
        json.dump(info, fh, indent=1, default=str)
    SC.hb("PRETRAIN %s done: loss %.4f -> %.4f (unigram %.4f), %.0fs"
          % (tag, info["loss_first200"], info["loss_last200"],
             info["unigram_entropy_nats"], info["wall_sec"]))
    del model, opt
    if DEV == "cuda":
        torch.cuda.empty_cache()
    return info


# =============================================================== finetune ====
_FT = {}


def load_ft():
    if "X" in _FT:
        return _FT
    import m3_walk as W
    D, _p = W.load_matrix()
    X, rows = TK.load_cand_tokens()
    pos = np.full(D["d8"].size, -1, dtype=np.int64)
    pos[rows] = np.arange(rows.size, dtype=np.int64)
    _FT.update({"D": D, "X": X, "pos": pos,
                "asset": D["asset_idx"].astype(np.int64),
                "C": D["X"], "ctx_names": list(D["names"])})
    SC.hb("finetune corpus: %d candidate token windows (%.2f GB) + %d context "
          "features" % (X.shape[0], X.nbytes / 1e9, D["X"].shape[1]))
    return _FT


def ctx_stats(C, rows):
    """Train-only standardisation of the context block, with a typed-missing
    indicator per feature (AMENDMENT 2)."""
    B = C[rows]
    fin = np.isfinite(B)
    mu = np.where(fin.any(0), np.nanmean(np.where(fin, B, np.nan), axis=0), 0.0)
    sd = np.where(fin.any(0), np.nanstd(np.where(fin, B, np.nan), axis=0), 1.0)
    sd = np.where(np.isfinite(sd) & (sd > 1e-6), sd, 1.0)
    return mu.astype(np.float32), sd.astype(np.float32)


def ctx_batch(C, rows, mu, sd):
    B = C[rows]
    m = np.isfinite(B)
    Z = (np.where(m, B, mu[None, :]) - mu[None, :]) / sd[None, :]
    return torch.from_numpy(np.concatenate(
        [np.clip(Z, -8.0, 8.0), (~m).astype(np.float32)], axis=1)
        .astype(np.float32)).to(DEV)


def _ft_batch(X, pos, asset, rows):
    x = torch.from_numpy(X[pos[rows]].astype(np.int64)).to(DEV)
    a = torch.from_numpy(asset[rows]).to(DEV)
    return x, a


def _ft_predict(model, X, pos, asset, rows, C=None, mu=None, sd=None, bs=512):
    model.eval()
    out = np.zeros((rows.size, 2), dtype=np.float64)
    with torch.no_grad():
        for i in range(0, rows.size, bs):
            r = rows[i:i + bs]
            x, a = _ft_batch(X, pos, asset, r)
            c = ctx_batch(C, r, mu, sd) if model.mode != "seq" else None
            with torch.autocast("cuda", dtype=torch.bfloat16,
                                enabled=(DEV == "cuda")):
                o = model(x, a, c)
            out[i:i + bs] = o.float().cpu().numpy()
    return out[:, 0], out[:, 1]


def _make_ft(trunk_tag, scratch, n_assets, n_ctx, mode):
    torch.manual_seed(SC.SEED)
    lm = EventLM(n_assets=n_assets)
    loaded = None
    if not scratch and mode != "ctx":
        ck = torch.load(os.path.join(TRUNK_DIR, "%s.pt" % trunk_tag),
                        map_location="cpu")
        lm = EventLM(n_assets=ck["n_assets"])
        lm.load_state_dict(ck["state"])
        loaded = ck["info"]
    return EventHead(lm, n_ctx=n_ctx, mode=mode).to(DEV), loaded


def _ft_fold(m, X, pos, asset, itr, iva, y_c, y_w, tag, max_epochs,
             C=None, mu=None, sd=None):
    opt = torch.optim.AdamW(
        [{"params": m.lm.parameters(), "lr": FT_LR_TRUNK},
         {"params": m.head.parameters(), "lr": FT_LR_HEAD}],
        weight_decay=SC.WEIGHT_DECAY)
    rng = np.random.RandomState(SC.SEED)
    best, best_ep, bad, best_state = -np.inf, 0, 0, None
    hist = []
    for ep in range(1, int(max_epochs) + 1):
        m.train()
        order = rng.permutation(itr.size)
        t0 = time.time()
        for a in range(0, itr.size, FT_BATCH):
            r = itr[np.sort(order[a:a + FT_BATCH])]
            if r.size < 8:
                continue
            x, av = _ft_batch(X, pos, asset, r)
            c = ctx_batch(C, r, mu, sd) if m.mode != "seq" else None
            with torch.autocast("cuda", dtype=torch.bfloat16,
                                enabled=(DEV == "cuda")):
                out = m(x, av, c)
            loss = F.mse_loss(out[:, 0].float(),
                              torch.from_numpy(y_c[r]).to(DEV).float()) \
                + SC.WINNER_LOSS_W * F.binary_cross_entropy_with_logits(
                    out[:, 1].float(), torch.from_numpy(y_w[r]).to(DEV).float())
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
            opt.step()
        dt = time.time() - t0
        if iva is not None and iva.size:
            pc, _pw = _ft_predict(m, X, pos, asset, iva, C, mu, sd)
            rho = M3._rho(pc, y_c[iva])
        else:
            rho = float(ep)
        hist.append([ep, round(float(rho), 5), round(dt, 1)])
        SC.hb("%s ep%d rho=%.4f %.0fs (%.0f rows/s)"
              % (tag, ep, rho, dt, itr.size / max(dt, 1e-6)))
        if np.isfinite(rho) and rho > best:
            best, best_ep, bad = float(rho), ep, 0
            best_state = {k: v.detach().clone() for k, v in
                          m.state_dict().items()}
        else:
            bad += 1
            if bad >= FT_PATIENCE:
                break
    if best_state is not None:
        m.load_state_dict(best_state)
    return m, {"inner_rho": best, "best_epoch": best_ep, "epoch_hist": hist}


def finetune(trunk_tag, scratch=False, test_eras=SC.TEST_ERAS, tag=None,
             mode="fused", assets=None):
    ft = load_ft()
    D, X, pos, asset = ft["D"], ft["X"], ft["pos"], ft["asset"]
    C = ft["C"]
    n_ctx = int(C.shape[1])
    ceil = R.ceilings_of(D)
    n = D["d8"].size
    champ = np.full(n, np.nan)
    win = np.full(n, np.nan)
    y_c0, y_w0 = D["y_retg_rank_phase"], D["y_winner"]
    ledger = []
    name = tag or ("FT_%s_%s%s" % (trunk_tag, mode.upper(),
                                   "_SCRATCH" if scratch else ""))
    keep_assets = None if not assets else \
        [MC.ASSET_ORDER.index(x) for x in assets]
    for era in test_eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era)
        tr = tr[(pos[tr] >= 0) & np.isfinite(y_c0[tr])]
        ev = ev[pos[ev] >= 0]
        if keep_assets is not None:
            tr = tr[np.isin(asset[tr], keep_assets)]
            ev = ev[np.isin(asset[ev], keep_assets)]
        cut = SC.inner_split_days(D["d8"][tr])
        itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
        y_c = y_c0.astype(np.float64)
        y_w = y_w0.astype(np.float64)
        mu, sd = ctx_stats(C, tr)
        m, loaded = _make_ft(trunk_tag, scratch, 3, n_ctx, mode)
        m, info = _ft_fold(m, X, pos, asset, itr, iva, y_c, y_w,
                           "%s/%s" % (name, era), FT_EPOCHS, C, mu, sd)
        m2, _l = _make_ft(trunk_tag, scratch, 3, n_ctx, mode)
        m2, _i2 = _ft_fold(m2, X, pos, asset, tr, None, y_c, y_w,
                           "%s/%s refit" % (name, era), info["best_epoch"],
                           C, mu, sd)
        pc, pw = _ft_predict(m2, X, pos, asset, ev, C, mu, sd)
        champ[ev], win[ev] = pc, pw
        info.update({"era": era, "n_train": int(tr.size), "n_eval": int(ev.size),
                     "n_inner_train": int(itr.size), "n_inner_val": int(iva.size),
                     "train_days": int(np.unique(D["d8"][tr]).size),
                     "eval_days": int(np.unique(D["d8"][ev]).size),
                     "params": n_params(m2),
                     "eval_auc_winner": round(R.auc(y_w0[ev], pw), 4),
                     "fit_secs": round(time.time() - t0, 1),
                     "pretrain_info": (loaded or {}).get("tag")})
        ledger.append(info)
        SC.hb("FT %s %s: rho=%.4f auc=%.4f (%.0fs)"
              % (name, era, info["inner_rho"], info["eval_auc_winner"],
                 info["fit_secs"]))
        del m, m2
        if DEV == "cuda":
            torch.cuda.empty_cache()
    per, pool = R.eval_scores(D, champ, win, ceil, pos, test_eras=test_eras)
    R.save_result(name, {"kind": "pretrain" if not scratch else "ladder",
                         "arch": "eventlm-%s" % mode, "rung": "40M",
                         "L": TK.CTX, "assets": (assets or "ALL"),
                         "pretrained": (not scratch and mode != "ctx"),
                         "trunk": trunk_tag,
                         "per_era": [R._strip(a) for a in per], "pooled": pool,
                         "ledger": ledger, "gpu": R.gpu_note()})
    np.savez(os.path.join(R._sdir(), "%s.npz" % name), champ=champ, win=win)
    SC.hb("%s pooled capture_oracle=%.4f [%.4f,%.4f]"
          % (name, pool["capture_oracle"] or float("nan"),
             pool["co_lo"] or float("nan"), pool["co_hi"] or float("nan")))
    return pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--embed", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--pretrain", action="store_true")
    ap.add_argument("--finetune", action="store_true")
    ap.add_argument("--corpus", default="A", choices=("A", "B"))
    ap.add_argument("--scope", default="shared", choices=("shared", "si"))
    ap.add_argument("--budget", type=float, default=WALL_CEILING_SEC)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--multi", action="store_true")
    ap.add_argument("--trunk", default="PRE_A_shared")
    ap.add_argument("--scratch", action="store_true")
    ap.add_argument("--eras", default=",".join(SC.TEST_ERAS))
    ap.add_argument("--mode", default="fused")
    ap.add_argument("--assets", default="")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    if a.embed:
        embed_all(a.trunk)
    elif a.probe:
        for mode in (a.mode.split(",") if a.mode else ["fused"]):
            probe(a.trunk, mode=mode, test_eras=tuple(a.eras.split(",")),
                  assets=(tuple(a.assets.split(",")) if a.assets else None),
                  tag=a.tag)
    elif a.smoke:
        out = smoke(a.corpus, a.scope, multi=a.multi)
        print(json.dumps(out, indent=1))
    elif a.pretrain:
        pretrain(a.corpus, a.scope, budget_sec=a.budget, epochs=a.epochs,
                 multi=a.multi)
    elif a.finetune:
        finetune(a.trunk, scratch=a.scratch,
                 test_eras=tuple(a.eras.split(",")), tag=a.tag, mode=a.mode,
                 assets=(tuple(a.assets.split(",")) if a.assets else None))
    else:
        ap.print_help()




# ============================================== the FROZEN-TRUNK PROBE =======
# The end-to-end fine-tune of a 40M-parameter trunk over 1024-token windows costs
# ~250 GFLOP per row per step, which puts the full three-row ablation x two
# trunks x six folds far outside the lane's wall-clock ceiling.  The standard
# protocol at that point is the FROZEN-TRUNK PROBE: run the trunk ONCE over every
# candidate window, cache the pooled representation, and train the (small) head
# on the cache.  It is the same comparison — pretrained representation versus a
# randomly-initialised one of identical shape — and it is what the coordinator's
# "frozen / lightly-tuned backbone" wording anticipates for the policy stage.
EMB_DIR = os.path.join(SC.CACHE_ROOT, "emb")


def embed_all(trunk_tag, bs=256):
    """One forward pass of the trunk over every candidate window; cache the
    pooled [last-token ; mean] representation as float16."""
    os.makedirs(EMB_DIR, exist_ok=True)
    p = os.path.join(EMB_DIR, "%s.npy" % trunk_tag)
    if os.path.exists(p):
        return np.load(p, mmap_mode="r")
    ft = load_ft()
    X, asset = ft["X"], ft["asset"]
    rows_all = np.nonzero(ft["pos"] >= 0)[0]
    order = np.argsort(ft["pos"][rows_all])
    rows_all = rows_all[order]
    side = False
    if trunk_tag == "RANDOM":
        torch.manual_seed(SC.SEED)
        lm = EventLM(n_assets=3)
        info = {"tag": "RANDOM", "note": "untrained trunk, identical shape"}
    else:
        ck = torch.load(os.path.join(TRUNK_DIR, "%s.pt" % trunk_tag),
                        map_location="cpu")
        side = bool(ck.get("side", False))
        lm = EventLM(n_assets=ck["n_assets"], side=side,
                     multi=bool(ck.get("multi", False)))
        lm.load_state_dict(ck["state"])
        info = ck["info"]
    SIDE = None
    if side:
        import st_aux as AX
        sw, srows = AX.load_cand_aux()
        spos = np.full(ft["pos"].size, -1, dtype=np.int64)
        spos[srows] = np.arange(srows.size, dtype=np.int64)
        SIDE = (sw, spos)
        SC.hb("embed %s: side channels %s" % (trunk_tag, (sw.shape,)))
    lm = lm.to(DEV).eval()
    out = np.zeros((X.shape[0], 2 * D_MODEL), dtype=np.float16)
    t0 = time.time()
    with torch.no_grad():
        for i in range(0, rows_all.size, bs):
            r = rows_all[i:i + bs]
            x, a = _ft_batch(X, ft["pos"], asset, r)
            if lm.asset.num_embeddings == 1:
                a = torch.zeros_like(a)      # the SI-ONLY trunk has one row
            sd = None
            if SIDE is not None:
                sd = torch.from_numpy(
                    SIDE[0][SIDE[1][r]].astype(np.float32)).to(DEV)
            with torch.autocast("cuda", dtype=torch.bfloat16,
                                enabled=(DEV == "cuda")):
                h = lm.trunk(x, a, sd)
                z = torch.cat([h[:, -1, :], h.mean(1)], -1)
            out[ft["pos"][r]] = z.float().cpu().numpy().astype(np.float16)
            if (i // bs) % 400 == 0:
                SC.hb("embed %s %d/%d (%.0fs)"
                      % (trunk_tag, i, rows_all.size, time.time() - t0))
    np.save(p, out)
    with open(os.path.join(EMB_DIR, "%s.json" % trunk_tag), "w") as fh:
        json.dump({"trunk": trunk_tag, "rows": int(X.shape[0]),
                   "dim": 2 * D_MODEL, "secs": round(time.time() - t0, 1),
                   "pretrain": info}, fh, indent=1, default=str)
    SC.hb("embedded %s: %d rows x %d (%.0fs)"
          % (trunk_tag, X.shape[0], 2 * D_MODEL, time.time() - t0))
    del lm
    if DEV == "cuda":
        torch.cuda.empty_cache()
    return np.load(p, mmap_mode="r")


class ProbeHead(nn.Module):
    """The three declared ablation rows over a cached trunk representation."""

    def __init__(self, n_emb, n_ctx, mode="fused", d=512, p=0.1):
        super(ProbeHead, self).__init__()
        self.mode = mode
        dim = 0
        if mode in ("seq", "fused"):
            self.emb_mlp = nn.Sequential(nn.Linear(n_emb, d), nn.GELU(),
                                         nn.Dropout(p), nn.Linear(d, 256),
                                         nn.GELU())
            dim += 256
        if mode in ("ctx", "fused"):
            self.ctx_mlp = nn.Sequential(nn.Linear(2 * n_ctx, d), nn.GELU(),
                                         nn.Dropout(p), nn.Linear(d, 256),
                                         nn.GELU())
            dim += 256
        self.head = nn.Sequential(nn.Linear(dim, 256), nn.GELU(),
                                  nn.Dropout(p), nn.Linear(256, 2))

    def forward(self, e, c):
        parts = []
        if self.mode in ("seq", "fused"):
            parts.append(self.emb_mlp(e))
        if self.mode in ("ctx", "fused"):
            parts.append(self.ctx_mlp(c))
        return self.head(torch.cat(parts, -1) if len(parts) > 1 else parts[0])


PROBE_EPOCHS = 12
PROBE_BATCH = 2048
PROBE_LR = 1e-3


def _probe_fold(mode, E, C, emu, esd, cmu, csd, itr, iva, y_c, y_w, tag,
                max_epochs, pos):
    torch.manual_seed(SC.SEED)
    m = ProbeHead(E.shape[1], C.shape[1], mode=mode).to(DEV)
    opt = torch.optim.AdamW(m.parameters(), lr=PROBE_LR,
                            weight_decay=SC.WEIGHT_DECAY)
    rng = np.random.RandomState(SC.SEED)
    best, best_ep, bad, best_state = -np.inf, 0, 0, None

    def batch(rows):
        e = torch.from_numpy(
            ((E[pos[rows]].astype(np.float32) - emu) / esd)).to(DEV)
        c = ctx_batch(C, rows, cmu, csd)
        return e, c

    for ep in range(1, int(max_epochs) + 1):
        m.train()
        order = rng.permutation(itr.size)
        t0 = time.time()
        for a in range(0, itr.size, PROBE_BATCH):
            r = itr[np.sort(order[a:a + PROBE_BATCH])]
            if r.size < 16:
                continue
            e, c = batch(r)
            out = m(e, c)
            loss = F.mse_loss(out[:, 0], torch.from_numpy(y_c[r]).to(DEV).float()) \
                + SC.WINNER_LOSS_W * F.binary_cross_entropy_with_logits(
                    out[:, 1], torch.from_numpy(y_w[r]).to(DEV).float())
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
        if iva is not None and iva.size:
            m.eval()
            with torch.no_grad():
                pc = np.concatenate([m(*batch(iva[i:i + 8192]))[:, 0]
                                     .float().cpu().numpy()
                                     for i in range(0, iva.size, 8192)])
            rho = M3._rho(pc, y_c[iva])
        else:
            rho = float(ep)
        SC.hb("%s %s ep%d rho=%.4f (%.0fs)" % (tag, mode, ep, rho,
                                               time.time() - t0))
        if np.isfinite(rho) and rho > best:
            best, best_ep, bad = float(rho), ep, 0
            best_state = {k: v.detach().clone() for k, v in
                          m.state_dict().items()}
        else:
            bad += 1
            if bad >= 3:
                break
    if best_state is not None:
        m.load_state_dict(best_state)
    return m, {"inner_rho": best, "best_epoch": best_ep}


def probe(trunk_tag, mode="fused", test_eras=SC.TEST_ERAS, tag=None,
          assets=None):
    ft = load_ft()
    D, pos, C = ft["D"], ft["pos"], ft["C"]
    E = np.asarray(embed_all(trunk_tag))
    ceil = R.ceilings_of(D)
    n = D["d8"].size
    champ = np.full(n, np.nan)
    win = np.full(n, np.nan)
    y_c0, y_w0 = D["y_retg_rank_phase"], D["y_winner"]
    y_c = y_c0.astype(np.float64)
    y_w = y_w0.astype(np.float64)
    name = tag or ("PROBE_%s_%s%s" % (trunk_tag, mode.upper(),
                                      "_" + "".join(assets) if assets else ""))
    keep = None if not assets else [MC.ASSET_ORDER.index(x) for x in assets]
    ledger = []
    for era in test_eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era)
        tr = tr[(pos[tr] >= 0) & np.isfinite(y_c0[tr])]
        ev = ev[pos[ev] >= 0]
        if keep is not None:
            tr = tr[np.isin(ft["asset"][tr], keep)]
            ev = ev[np.isin(ft["asset"][ev], keep)]
        cut = SC.inner_split_days(D["d8"][tr])
        itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
        sub = E[pos[itr]].astype(np.float32)
        emu = sub.mean(0)
        esd = np.maximum(sub.std(0), 1e-3)
        cmu, csd = ctx_stats(C, itr)
        m, info = _probe_fold(mode, E, C, emu, esd, cmu, csd, itr, iva, y_c,
                              y_w, "%s/%s" % (name, era), PROBE_EPOCHS, pos)
        sub = E[pos[tr]].astype(np.float32)
        emu = sub.mean(0)
        esd = np.maximum(sub.std(0), 1e-3)
        cmu, csd = ctx_stats(C, tr)
        m, _i = _probe_fold(mode, E, C, emu, esd, cmu, csd, tr, None, y_c, y_w,
                            "%s/%s refit" % (name, era), info["best_epoch"],
                            pos)
        m.eval()
        with torch.no_grad():
            out = np.concatenate([
                m(torch.from_numpy(((E[pos[ev[i:i + 8192]]].astype(np.float32)
                                     - emu) / esd)).to(DEV),
                  ctx_batch(C, ev[i:i + 8192], cmu, csd)).float().cpu().numpy()
                for i in range(0, ev.size, 8192)])
        champ[ev], win[ev] = out[:, 0], out[:, 1]
        info.update({"era": era, "n_train": int(tr.size), "n_eval": int(ev.size),
                     "n_inner_train": int(itr.size), "n_inner_val": int(iva.size),
                     "train_days": int(np.unique(D["d8"][tr]).size),
                     "eval_days": int(np.unique(D["d8"][ev]).size),
                     "params": int(sum(p.numel() for p in m.parameters())),
                     "eval_auc_winner": round(R.auc(y_w0[ev], win[ev]), 4),
                     "fit_secs": round(time.time() - t0, 1)})
        ledger.append(info)
    per, pool = R.eval_scores(D, champ, win, ceil, pos, test_eras=test_eras)
    R.save_result(name, {"kind": "probe", "arch": "eventlm-probe-%s" % mode,
                         "rung": "40M-frozen", "L": TK.CTX, "trunk": trunk_tag,
                         "mode": mode, "assets": (list(assets) if assets
                                                  else "ALL"),
                         "pretrained": (trunk_tag != "RANDOM"),
                         "per_era": [R._strip(a) for a in per], "pooled": pool,
                         "ledger": ledger, "gpu": R.gpu_note()})
    np.savez(os.path.join(R._sdir(), "%s.npz" % name), champ=champ, win=win)
    SC.hb("%s pooled capture_oracle=%.4f [%.4f,%.4f]"
          % (name, pool["capture_oracle"] or float("nan"),
             pool["co_lo"] or float("nan"), pool["co_hi"] or float("nan")))
    return pool


if __name__ == "__main__":
    main()
