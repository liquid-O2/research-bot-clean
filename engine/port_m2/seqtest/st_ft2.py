#!/usr/bin/python3
"""PORT M2 FIXPASS2 — F2: REAL TRANSFER.  The frozen probe is retired.

THE CONFOUND THIS REMOVES, named in SEQTEST.md §11: "the transfer failure was
measured through a FROZEN TRUNK, which is the weakest transfer mechanism
available."  The dominant matrix tag R4 (PROBES GOOD, RANKING FLAT) prescribes
"unfreeze more layers with layer-wise LR decay; attention pooling over the
window instead of last-token; longer fine-tune; add B1 day-memory tokens".  All
four are implemented here, each behind a toggle:

  --unfreeze N   the top N transformer blocks (plus the final norm) train; the
                 embeddings and the lower blocks are frozen, so the backward
                 pass costs a fraction of a full one and the fine-tune FITS.
  --lora R       rank-R LoRA adapters on every block's qkv / proj / fc1 / fc2
                 with the base weights frozen — the memory-bound alternative
                 the ruling names, and the only arm in which ALL depths adapt.
  --lldecay G    layer-wise LR decay: block i trains at lr_trunk * G^(depth-1-i),
                 so the top of the trunk moves and the bottom barely does.
  --pool attn    attention pooling over the whole window (a learned query) in
                 place of the frozen probe's [last-token ; mean].
  --daymem       B1: the causal day-memory summary enters as PREPENDED TOKENS
                 (a zero-initialised projection, so the model starts function-
                 identical) as well as in the context block.

The head, the folds, the early stopping, the refit discipline and the scoring
are the lane's, unchanged: `m3_walk`'s deployable arm verbatim, CIs by DAY.

Run:
    st_ft2.py --run --trunk PRE_V2_shared_NEXT --unfreeze 4 --pool attn
"""
import os

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import argparse                             # noqa: E402
import json                                 # noqa: E402
import time                                 # noqa: E402

import numpy as np                          # noqa: E402
import torch                                # noqa: E402
import torch.nn as nn                       # noqa: E402
import torch.nn.functional as F             # noqa: E402

import st_common as SC                      # noqa: E402
import st_aux2 as A2                        # noqa: E402
import st_run as R                          # noqa: E402
import st_pretrain as P                     # noqa: E402
import m3_common as M3                      # noqa: E402

DEV = R.DEV

FT_LR_TRUNK = 3e-5
FT_LR_HEAD = 1e-3
FT_BATCH = 96
FT_STEPS = 1500                    # optimiser steps per fold (declared budget)
FT_EVAL_EVERY = 250
FT_PATIENCE = 2
N_MEM_TOK = 2


# =============================================================== the LoRA ====
class LoRALinear(nn.Module):
    """A frozen base `nn.Linear` plus a trainable rank-R update, zero-
    initialised on B so the wrapped module starts function-identical."""

    def __init__(self, base, r=16, alpha=32.0):
        super(LoRALinear, self).__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad = False
        self.A = nn.Parameter(torch.zeros(r, base.in_features))
        self.B = nn.Parameter(torch.zeros(base.out_features, r))
        nn.init.trunc_normal_(self.A, std=0.02)
        self.scale = float(alpha) / float(r)

    def forward(self, x):
        return self.base(x) + F.linear(F.linear(x, self.A), self.B) * self.scale


def apply_lora(lm, r=16):
    n = 0
    for blk in lm.blocks:
        for nm in ("qkv", "proj", "fc1", "fc2"):
            setattr(blk, nm, LoRALinear(getattr(blk, nm), r=r))
            n += 1
    return n


# ================================================================ the net ====
class FTNet(nn.Module):
    def __init__(self, lm, n_ctx, mode="fused", pool="lastmean", d=512, p=0.1,
                 n_mem=0):
        super(FTNet, self).__init__()
        self.lm = lm
        self.mode = mode
        self.pool = pool
        self.n_mem = int(n_mem)
        dim = 0
        if pool == "attn":
            self.q = nn.Parameter(torch.zeros(1, 1, d))
            nn.init.trunc_normal_(self.q, std=0.02)
        if mode in ("seq", "fused"):
            dim += 2 * d
        if mode in ("ctx", "fused"):
            self.ctx_mlp = nn.Sequential(nn.Linear(2 * int(n_ctx), 512),
                                         nn.GELU(), nn.Dropout(p),
                                         nn.Linear(512, 256), nn.GELU())
            dim += 256
        if self.n_mem:
            # B1: the day-memory summary as PREPENDED TOKENS.  Zero-initialised
            # projection => identical function at step 0.
            self.mem_proj = nn.Linear(A2.N_MEM, d * N_MEM_TOK)
            nn.init.zeros_(self.mem_proj.weight)
            nn.init.zeros_(self.mem_proj.bias)
            self.mem_pos = nn.Parameter(torch.zeros(1, N_MEM_TOK, d))
            nn.init.trunc_normal_(self.mem_pos, std=0.02)
        self.head = nn.Sequential(nn.Linear(dim, d), nn.GELU(), nn.Dropout(p),
                                  nn.Linear(d, 2))

    def encode(self, x, a, mem=None):
        lm = self.lm
        h = lm.tok(x) + lm.pos[:, :x.shape[1], :] + lm.asset(a)[:, None, :]
        if self.n_mem and mem is not None:
            m = self.mem_proj(mem).view(x.shape[0], N_MEM_TOK, -1) \
                + self.mem_pos
            h = torch.cat([m, h], 1)
        for b in lm.blocks:
            h = b(h)
        h = lm.nf(h)
        if self.pool == "attn":
            w = torch.softmax((h @ self.q.transpose(1, 2)).squeeze(-1)
                              / (h.shape[-1] ** 0.5), dim=1)
            return torch.cat([h[:, -1, :], (h * w.unsqueeze(-1)).sum(1)], -1)
        return torch.cat([h[:, -1, :], h.mean(1)], -1)

    def forward(self, x, a, c=None, mem=None):
        parts = []
        if self.mode in ("seq", "fused"):
            parts.append(self.encode(x, a, mem))
        if self.mode in ("ctx", "fused"):
            parts.append(self.ctx_mlp(c))
        return self.head(torch.cat(parts, -1) if len(parts) > 1 else parts[0])


def build(trunk_tag, n_ctx, mode="fused", pool="lastmean", unfreeze=4, lora=0,
          daymem=False, scratch=False):
    torch.manual_seed(SC.SEED)
    if scratch or trunk_tag.startswith("RANDOM"):
        lm = P.EventLM(vocab=P.VOCAB(), n_assets=3)
        info = {"tag": trunk_tag, "note": "untrained trunk, identical shape",
                "tokenizer": P.TOKVER()}
    else:
        ck = torch.load(os.path.join(P.TRUNK_DIR, "%s.pt" % trunk_tag),
                        map_location="cpu")
        lm = P.EventLM(vocab=int(ck.get("vocab", P.VOCAB())),
                       n_assets=ck["n_assets"], side=bool(ck.get("side")),
                       multi=bool(ck.get("multi")))
        lm.load_state_dict(ck["state"])
        info = ck["info"]
        if int(ck.get("vocab", P.VOCAB())) != P.VOCAB():
            raise SC.SeqTestRefusal(
                "trunk vocab %d != tokenizer vocab %d — the fine-tune would "
                "read a different alphabet from the one it was trained on"
                % (int(ck.get("vocab", 0)), P.VOCAB()))
    if lora > 0:
        for p_ in lm.parameters():
            p_.requires_grad = False
        n_wrapped = apply_lora(lm, r=int(lora))
        SC.hb("LoRA r=%d on %d projections (all %d blocks)"
              % (lora, n_wrapped, len(lm.blocks)))
    else:
        for p_ in lm.parameters():
            p_.requires_grad = False
        depth = len(lm.blocks)
        for i in range(max(depth - int(unfreeze), 0), depth):
            for p_ in lm.blocks[i].parameters():
                p_.requires_grad = True
        for p_ in lm.nf.parameters():
            p_.requires_grad = True
    m = FTNet(lm, n_ctx, mode=mode, pool=pool,
              n_mem=(A2.N_MEM if daymem else 0)).to(DEV)
    return m, info


def param_groups(m, lldecay=0.75, lr_trunk=FT_LR_TRUNK, lr_head=FT_LR_HEAD):
    """LAYER-WISE LR DECAY: block i at lr_trunk * lldecay^(depth-1-i)."""
    depth = len(m.lm.blocks)
    seen = set()
    groups = []
    for i, blk in enumerate(m.lm.blocks):
        ps = [p for p in blk.parameters() if p.requires_grad]
        if not ps:
            continue
        for p in ps:
            seen.add(id(p))
        groups.append({"params": ps,
                       "lr": lr_trunk * (lldecay ** (depth - 1 - i))})
    rest_trunk = [p for p in m.lm.parameters()
                  if p.requires_grad and id(p) not in seen]
    if rest_trunk:
        groups.append({"params": rest_trunk, "lr": lr_trunk})
        for p in rest_trunk:
            seen.add(id(p))
    head = [p for n, p in m.named_parameters()
            if p.requires_grad and id(p) not in seen]
    groups.append({"params": head, "lr": lr_head})
    n_tr = sum(p.numel() for g in groups for p in g["params"])
    return groups, n_tr


# ================================================================ the loop ===
def _batch(ft, C, MEMZ, cmu, csd, mmu, msd, rows, mode, daymem):
    X, pos, asset = ft["X"], ft["pos"], ft["asset"]
    x = torch.from_numpy(X[pos[rows]].astype(np.int64)).to(DEV)
    a = torch.from_numpy(asset[rows]).to(DEV)
    c = P.ctx_batch(C, rows, cmu, csd) if mode != "seq" else None
    mem = None
    if daymem:
        mem = torch.from_numpy(((MEMZ[rows] - mmu) / msd)
                               .astype(np.float32)).to(DEV)
    return x, a, c, mem


def predict(m, ft, C, MEMZ, cmu, csd, mmu, msd, rows, mode, daymem, bs=256):
    m.eval()
    out = np.zeros((rows.size, 2), dtype=np.float64)
    with torch.no_grad():
        for i in range(0, rows.size, bs):
            r = rows[i:i + bs]
            x, a, c, mem = _batch(ft, C, MEMZ, cmu, csd, mmu, msd, r, mode,
                                  daymem)
            with torch.autocast("cuda", dtype=torch.bfloat16,
                                enabled=(DEV == "cuda")):
                o = m(x, a, c, mem)
            out[i:i + bs] = o.float().cpu().numpy()
    return out[:, 0], out[:, 1]


def _fit(m, ft, C, MEMZ, cmu, csd, mmu, msd, itr, iva, y_c, y_w, mode, daymem,
         steps, tag, lldecay, eval_every=FT_EVAL_EVERY):
    groups, n_tr = param_groups(m, lldecay)
    opt = torch.optim.AdamW(groups, weight_decay=SC.WEIGHT_DECAY)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=[g["lr"] for g in groups], total_steps=max(int(steps), 2),
        pct_start=0.1, anneal_strategy="cos")
    rng = np.random.RandomState(SC.SEED)
    best, best_step, bad, best_state = -np.inf, 0, 0, None
    hist = []
    t0 = time.time()
    m.train()
    for st in range(1, int(steps) + 1):
        r = itr[np.sort(rng.randint(0, itr.size, size=FT_BATCH))]
        x, a, c, mem = _batch(ft, C, MEMZ, cmu, csd, mmu, msd, r, mode, daymem)
        with torch.autocast("cuda", dtype=torch.bfloat16,
                            enabled=(DEV == "cuda")):
            out = m(x, a, c, mem)
        loss = F.mse_loss(out[:, 0].float(),
                          torch.from_numpy(y_c[r]).to(DEV).float()) \
            + SC.WINNER_LOSS_W * F.binary_cross_entropy_with_logits(
                out[:, 1].float(), torch.from_numpy(y_w[r]).to(DEV).float())
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_([p for g in opt.param_groups
                                        for p in g["params"]], 1.0)
        opt.step()
        sched.step()
        if iva is not None and iva.size and (st % eval_every == 0
                                             or st == int(steps)):
            pc, _pw = predict(m, ft, C, MEMZ, cmu, csd, mmu, msd, iva, mode,
                              daymem)
            rho = M3._rho(pc, y_c[iva])
            hist.append([st, round(float(rho), 5), round(time.time() - t0, 1)])
            SC.hb("%s step %d/%d rho=%.4f (%.0fs, %.0f rows/s)"
                  % (tag, st, steps, rho, time.time() - t0,
                     st * FT_BATCH / max(time.time() - t0, 1e-6)))
            m.train()
            if np.isfinite(rho) and rho > best:
                best, best_step, bad = float(rho), st, 0
                best_state = {k: v.detach().clone()
                              for k, v in m.state_dict().items()}
            else:
                bad += 1
                if bad >= FT_PATIENCE:
                    SC.hb("%s early stop at step %d (best %d)"
                          % (tag, st, best_step))
                    break
    if best_state is not None:
        m.load_state_dict(best_state)
    return m, {"inner_rho": best, "best_step": best_step, "hist": hist,
               "n_trainable": int(n_tr),
               "steps_run": int(hist[-1][0]) if hist else int(steps),
               "secs": round(time.time() - t0, 1)}


def run(trunk="PRE_V2_shared_NEXT", mode="fused", pool="attn", unfreeze=4,
        lora=0, lldecay=0.75, daymem=False, scratch=False, steps=FT_STEPS,
        test_eras=SC.TEST_ERAS, tag=None, tokver="v2", from_era="E2"):
    P.use_tokenizer(tokver)
    ft = P.load_ft()
    D, pos = ft["D"], ft["pos"]
    C = D["X"]
    n_ctx = int(C.shape[1])
    MEMZ = mmu = msd = None
    if daymem:
        M = A2.day_memory(D)
        MEMZ = (np.sign(M) * np.log1p(np.abs(M))).astype(np.float32)
    ceil = R.ceilings_of(D)
    n = D["d8"].size
    champ = np.full(n, np.nan)
    win = np.full(n, np.nan)
    y_c0, y_w0 = D["y_retg_rank_phase"], D["y_winner"]
    y_c = y_c0.astype(np.float64)
    y_w = y_w0.astype(np.float64)
    name = tag or ("FT2_%s_%s%s%s%s"
                   % (trunk, mode.upper(),
                      "_LORA%d" % lora if lora else "_TOP%d" % unfreeze,
                      "_ATTN" if pool == "attn" else "",
                      "_MEM" if daymem else "")
                   + ("_ALLDATA" if from_era == "PRE_E1" else ""))
    ledger = []
    for era in test_eras:
        t0 = time.time()
        tr, ev = R.fold_rows(D, era, from_era=from_era)
        tr = tr[(pos[tr] >= 0) & np.isfinite(y_c0[tr])]
        ev = ev[pos[ev] >= 0]
        cut = SC.inner_split_days(D["d8"][tr])
        itr, iva = tr[D["d8"][tr] <= cut], tr[D["d8"][tr] > cut]
        SC.assert_disjoint_days(itr, iva, D["d8"], tag="%s inner" % era)
        cmu, csd = P.ctx_stats(C, itr)
        if daymem:
            mmu = MEMZ[itr].mean(0)
            msd = np.maximum(MEMZ[itr].std(0), 1e-3)
        m, info0 = build(trunk, n_ctx, mode, pool, unfreeze, lora, daymem,
                         scratch)
        m, info = _fit(m, ft, C, MEMZ, cmu, csd, mmu, msd, itr, iva, y_c, y_w,
                       mode, daymem, steps, "%s/%s" % (name, era), lldecay)
        del m
        if DEV == "cuda":
            torch.cuda.empty_cache()
        # THE REFIT, the lane's discipline: from the same initialisation, on the
        # WHOLE training block, for the step count the inner block chose.
        cmu, csd = P.ctx_stats(C, tr)
        if daymem:
            mmu = MEMZ[tr].mean(0)
            msd = np.maximum(MEMZ[tr].std(0), 1e-3)
        m2, _i0 = build(trunk, n_ctx, mode, pool, unfreeze, lora, daymem,
                        scratch)
        m2, _i = _fit(m2, ft, C, MEMZ, cmu, csd, mmu, msd, tr, None, y_c, y_w,
                      mode, daymem, max(info["best_step"], FT_EVAL_EVERY),
                      "%s/%s refit" % (name, era), lldecay)
        pc, pw = predict(m2, ft, C, MEMZ, cmu, csd, mmu, msd, ev, mode, daymem)
        champ[ev], win[ev] = pc, pw
        info.update({"era": era, "n_train": int(tr.size), "n_eval": int(ev.size),
                     "n_inner_train": int(itr.size), "n_inner_val": int(iva.size),
                     "train_days": int(np.unique(D["d8"][tr]).size),
                     "eval_days": int(np.unique(D["d8"][ev]).size),
                     "eval_auc_winner": round(R.auc(y_w0[ev], pw), 4),
                     "fit_secs": round(time.time() - t0, 1)})
        ledger.append(info)
        SC.hb("FT2 %s %s: rho=%.4f auc=%.4f trainable=%d (%.0fs)"
              % (name, era, info["inner_rho"], info["eval_auc_winner"],
                 info["n_trainable"], info["fit_secs"]))
        del m2
        if DEV == "cuda":
            torch.cuda.empty_cache()
    per, pool_ = R.eval_scores(D, champ, win, ceil, pos, test_eras=test_eras)
    R.save_result(name, {
        "kind": "ft2", "arch": "eventlm-ft-%s" % mode, "rung": "40M",
        "L": P.CTX, "trunk": trunk, "mode": mode, "pooling": pool,
        "unfreeze_top": int(unfreeze), "lora_rank": int(lora),
        "lldecay": lldecay, "daymem": bool(daymem), "steps_budget": int(steps),
        "from_era": from_era,
        "tokenizer": P.TOKVER(), "vocab": P.VOCAB(),
        "pretrained": (not scratch and not trunk.startswith("RANDOM")),
        "per_era": [R._strip(a) for a in per], "pooled": pool_,
        "ledger": ledger, "gpu": R.gpu_note()})
    np.savez(os.path.join(R._sdir(), "%s.npz" % name), champ=champ, win=win)
    SC.hb("%s pooled capture_oracle=%.4f [%.4f,%.4f] $%.2f/session"
          % (name, pool_["capture_oracle"] or float("nan"),
             pool_["co_lo"] or float("nan"), pool_["co_hi"] or float("nan"),
             pool_["usd_per_session"] or float("nan")))
    return pool_


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--trunk", default="PRE_V2_shared_NEXT")
    ap.add_argument("--mode", default="fused")
    ap.add_argument("--pool", default="attn")
    ap.add_argument("--unfreeze", type=int, default=4)
    ap.add_argument("--lora", type=int, default=0)
    ap.add_argument("--lldecay", type=float, default=0.75)
    ap.add_argument("--daymem", action="store_true")
    ap.add_argument("--scratch", action="store_true")
    ap.add_argument("--steps", type=int, default=FT_STEPS)
    ap.add_argument("--tokver", default="v2")
    ap.add_argument("--from-era", default="E2")
    ap.add_argument("--eras", default=",".join(SC.TEST_ERAS))
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    if a.run:
        run(a.trunk, mode=a.mode, pool=a.pool, unfreeze=a.unfreeze,
            lora=a.lora, lldecay=a.lldecay, daymem=a.daymem,
            scratch=a.scratch, steps=a.steps, tokver=a.tokver,
            from_era=a.from_era,
            test_eras=tuple(x for x in a.eras.split(",") if x), tag=a.tag)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
