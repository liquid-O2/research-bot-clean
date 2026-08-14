#!/usr/bin/python3
"""PORT M2 SEQTEST — the TWO pre-registered architectures and their capacity
ladder.

    cnn   a stride-2 1D convolutional stack, kernel PINNED at 5
    trf   a conv patch-embed + transformer encoder stack

Three rungs each: ~1M / ~10M / ~50M parameters.  A rung is climbed ONLY while
honest day-fold walk-forward capture improves (`st_common.PARAMS`
["capacity_rule"]); the whole ladder is reported so a weak model and an absent
signal are told apart by the CURVE and not by assumption.

Both heads are always present:
    head 0  the atlas champion `y_retg_rank_phase`   (squared error)
    head 1  the D-021 walled-winner flag `y_winner`  (logistic)

The transformer additionally exposes a MASKED-EVENT decoder used by the
self-supervised pretraining stage, which reconstructs the masked positions'
continuous channels and classifies their action/side bytes.  Pretraining sees
only the unlabelled event stream.
"""
import math

import numpy as np
import torch
import torch.nn as nn

import st_common as SC


# ==================================================================== CNN ====
class SeqCNN(nn.Module):
    def __init__(self, cin=SC.N_CH, k=SC.CNN_KERNEL, widths=(128, 192, 256, 320),
                 head_dim=256, dropout=SC.DROPOUT, stem_stride=1):
        super(SeqCNN, self).__init__()
        pad = k // 2
        s = int(stem_stride)
        blocks, prev = [], cin
        if s > 1:
            ks = 2 * s + 1
            blocks.append(nn.Sequential(
                nn.Conv1d(cin, widths[0], ks, stride=s, padding=ks // 2),
                nn.BatchNorm1d(widths[0]), nn.ReLU()))
            prev = widths[0]
        for w in widths:
            blocks.append(nn.Sequential(
                nn.Conv1d(prev, w, k, stride=2, padding=pad),
                nn.BatchNorm1d(w), nn.ReLU()))
            prev = w
        self.blocks = nn.Sequential(*blocks)
        self.head = nn.Sequential(
            nn.Linear(prev * 2, head_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(head_dim, 2))

    def forward(self, x):
        h = self.blocks(x)
        h = torch.cat([h.mean(-1), h.amax(-1)], -1)
        return self.head(h)


# ============================================================ TRANSFORMER ====
class SeqTRF(nn.Module):
    def __init__(self, cin=SC.N_CH, L=256, patch=4, dim=144, depth=4, heads=4,
                 dropout=SC.DROPOUT):
        super(SeqTRF, self).__init__()
        self.patch = int(patch)
        self.embed = nn.Conv1d(cin, dim, kernel_size=patch, stride=patch)
        ntok = int(L // patch)
        self.pos = nn.Parameter(torch.zeros(1, ntok, dim))
        nn.init.trunc_normal_(self.pos, std=0.02)
        layer = nn.TransformerEncoderLayer(
            d_model=dim, nhead=heads, dim_feedforward=4 * dim,
            dropout=dropout, activation="gelu", batch_first=True,
            norm_first=True)
        self.enc = nn.TransformerEncoder(layer, num_layers=depth)
        self.norm = nn.LayerNorm(dim)
        self.head = nn.Sequential(nn.Linear(dim * 2, dim), nn.GELU(),
                                  nn.Dropout(dropout), nn.Linear(dim, 2))
        # the masked-event decoder (pretraining only): 11 continuous channels
        # reconstructed, plus the action and side bytes classified
        self.dec = nn.Linear(dim, patch * (len(SC.NORM_CH) + 6 + 3))
        self.dim, self.depth = dim, depth

    def tokens(self, x):
        h = self.embed(x).transpose(1, 2)
        return h + self.pos[:, :h.shape[1], :]

    def forward(self, x):
        h = self.norm(self.enc(self.tokens(x)))
        h = torch.cat([h.mean(1), h.amax(1)], -1)
        return self.head(h)

    def forward_masked(self, x, mask_tok):
        """`mask_tok` [B, ntok] bool — those tokens are zeroed before the
        encoder and their content is reconstructed from context."""
        h = self.tokens(x)
        h = h * (~mask_tok).unsqueeze(-1).to(h.dtype)
        h = self.norm(self.enc(h))
        return self.dec(h)


# ============================================================== factory ======
def make(arch, rung, L, seed=SC.SEED):
    torch.manual_seed(int(seed))
    np.random.seed(int(seed) % (2 ** 32 - 1))
    if arch == "cnn":
        m = SeqCNN(k=SC.CNN_KERNEL, widths=SC.CNN_WIDTHS[rung],
                   head_dim=SC.CNN_HEAD[rung],
                   stem_stride=SC.CNN_STEM_STRIDE[L])
    elif arch == "trf":
        m = SeqTRF(L=L, patch=SC.TRF_PATCH[L], dim=SC.TRF_DIM[rung],
                   depth=SC.TRF_DEPTH[rung], heads=SC.TRF_HEADS[rung])
    else:
        raise SC.SeqTestRefusal("unknown architecture %r" % (arch,))
    n = sum(p.numel() for p in m.parameters())
    return m, int(n)


def loss_fn(out, y_champ, y_win):
    mse = nn.functional.mse_loss(out[:, 0].float(), y_champ)
    bce = nn.functional.binary_cross_entropy_with_logits(out[:, 1].float(),
                                                         y_win)
    return mse + SC.WINNER_LOSS_W * bce


def pretrain_loss(pred, x, mask_tok, patch):
    """Masked-event objective: reconstruct the continuous channels (Huber) and
    classify the action / side bytes (cross-entropy) of the masked positions."""
    B, T, _ = pred.shape
    nc = len(SC.NORM_CH)
    pred = pred.view(B, T, patch, nc + 9)
    xs = x.transpose(1, 2).reshape(B, T, patch, SC.N_CH)
    m = mask_tok.unsqueeze(-1).unsqueeze(-1)
    valid = (xs[..., SC.CH_VALID:SC.CH_VALID + 1] > 0.5) & m
    if valid.sum() == 0:
        return pred.sum() * 0.0
    tgt = xs[..., list(SC.NORM_CH)]
    hub = nn.functional.smooth_l1_loss(pred[..., :nc].float() * valid,
                                       tgt.float() * valid, reduction="sum")
    hub = hub / (valid.sum() * nc)
    act_t = xs[..., 0:6].argmax(-1)
    sid_t = xs[..., 6:9].argmax(-1)
    v = valid.squeeze(-1)
    ce = (nn.functional.cross_entropy(
              pred[..., nc:nc + 6].float().reshape(-1, 6), act_t.reshape(-1),
              reduction="none").reshape(act_t.shape) * v).sum() \
        / v.sum().clamp(min=1)
    ce = ce + (nn.functional.cross_entropy(
                   pred[..., nc + 6:nc + 9].float().reshape(-1, 3),
                   sid_t.reshape(-1), reduction="none").reshape(sid_t.shape)
               * v).sum() / v.sum().clamp(min=1)
    return hub + 0.5 * ce


def describe():
    rows = []
    for arch in SC.ARCHS:
        for rung in SC.RUNGS:
            for L in SC.SEQ_LENS:
                if arch == "cnn" and L != SC.SEQ_LENS[0]:
                    pass
                _m, n = make(arch, rung, L)
                rows.append((arch, rung, L, n))
    return rows


if __name__ == "__main__":
    for r in describe():
        print("%-4s %-4s L=%-5d params=%d" % r)
