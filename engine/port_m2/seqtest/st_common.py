#!/usr/bin/python3
"""PORT M2 SEQTEST — shared constants, the channel spec, and the guards.

THE QUESTION (user-authorised measurement lane, 2026-08-16):

    does a small sequence model reading RAW EVENTS pick better MOMENTS than
    anything measured, at CANDIDATE grain — the layer M3 already shows beats
    episode grain?

Everything here is PRE-REGISTERED.  The channel list, the three window lengths,
the two architectures, the three capacity rungs, the fold construction, the
normalisation rule and the three leak probes are frozen in this file and its
`PARAMS` dict before a single real number is produced; the shuffled-label
control is run and its receipt committed BEFORE the real run (red-first).

NO FEATURISATION.  The tensor is the raw MBP-1 event record stream: the action
byte, the side byte, the record price, the size, the inter-event gap, the L1
book (size AND order count on both sides), and the time to the decision.  No
cue, no statistic, no window aggregate — those are exactly what INFO_CEILING
measured, and the point of this lane is to measure what they threw away.

AMENDMENTS (coordinator, 2026-08-16, binding — recorded here because a
pre-registration that is quietly edited is not one):
  A1  the machine has an idle RTX PRO 6000 (Blackwell, 97 GB).  Training moves
      to the GPU; the window-length ablation becomes {256, 1024, 4096}; all of
      E2->E6 plus the GATE echo are run rather than any reduced scope.
  A2  the fixed-size rule is replaced by a CAPACITY LADDER at ~1M / ~10M / ~50M
      parameters, climbed only while honest walk-forward capture improves.
  A3  a small TRANSFORMER joins the CNN — exactly two architectures, both
      declared here before any result.  The original kernel-9 CNN variant is
      RETIRED to keep the architecture count at two; the CNN kernel is pinned
      at 5.  No LSTM.
  A4  if the supervised ladder shows any signal, a self-supervised
      MASKED-EVENT pretraining stage runs on the unlabelled stream and is
      reported as its own pretrained-vs-scratch row.
  The anti-overfit stack is UNCHANGED at every rung: whole-day folds,
  walk-forward era splits, train-only normalisation, the red-first shuffled
  control, and the leak probes.
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("/workspace/engine/port_m3", "/workspace/engine/port_m2",
           "/workspace/engine/port_m1b", "/workspace/engine/port_m1",
           "/workspace/engine/port_m0", "/workspace/artifacts/cache/pylibs"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import common as C                        # noqa: E402
import m2_common as MC                    # noqa: E402
import m3_common as M3                    # noqa: E402

SECTION = "M2.SEQ raw-event sequence model at candidate grain"
LANE = "port-m2-seqtest"

SEED = M3.SEED                            # 20260813, the pinned program seed

# ------------------------------------------------------------------ paths ---
EVENTS_DIR = os.path.join(MC.M2_ROOT, "events")
CACHE_ROOT = os.path.join(MC.M2_ROOT, "seqtest")
SHARD_DIR = os.path.join(CACHE_ROOT, "shards")
OUT_DIR = "/workspace/provenance/port_m2"

# ------------------------------------------------------------ the tensor ----
SEQ_LENS = (256, 1024, 4096)              # the pre-registered length ablation
SEQ_LEN_MAX = max(SEQ_LENS)
CHANNELS = (
    "act_A", "act_C", "act_M", "act_T", "act_F", "act_R",     # 0-5 one-hot
    "side_B", "side_A", "side_N",                             # 6-8 one-hot
    "dpx_ticks", "dmid_ticks", "px_minus_mid_ticks",          # 9-11
    "log_size", "log_gap_us",                                 # 12-13
    "log_bid_sz", "log_ask_sz", "log_bid_ct", "log_ask_ct",   # 14-17
    "spread_ticks", "log_secs_to_decision",                   # 18-19
    "valid",                                                  # 20 pad mask
)
N_CH = len(CHANNELS)
CH_TTD = 19                               # log seconds-to-decision
CH_VALID = 20                             # the pad mask
NORM_CH = tuple(range(9, 20))             # one-hots and the mask stay raw
CLIP_TICKS = 20.0
CLIP_SPREAD = 50.0

ACTION_BYTES = tuple(ord(c) for c in "ACMTFR")
SIDE_BYTES = (ord("B"), ord("A"), ord("N"))

# ------------------------------------------------------------- the folds ----
# THE LADDER: train E2..Ek -> test E(k+1).  E1 and the PRE_E1 warm-up tape are
# NOT in the training block.  Never random, never same-era.  E8 is the
# harness's GATE-2025H1 echo and is the last rung.
UNIVERSE_ERAS = ("E2", "E3", "E4", "E5", "E6", "E7", "E8")
TEST_ERAS = ("E3", "E4", "E5", "E6", "E7", "E8")
GATE_ERA = "E8"
ERA_IDX = {name: i for i, (name, _a, _b) in enumerate(MC.ERAS)}

INNER_FRACTION = 0.2                      # s4_confirm._inner_split, verbatim

# ------------------------------------------------------------- the models ---
# TWO architectures.  THREE capacity rungs.  Nothing else is searched.
ARCHS = ("cnn", "trf")
RUNGS = ("1M", "10M", "50M")
RUNG_TARGET = {"1M": 1e6, "10M": 1e7, "50M": 5e7}

# CNN: stride-2 convolutional stack, kernel PINNED at 5 (amendment A3).
CNN_KERNEL = 5
CNN_WIDTHS = {"1M":  (128, 192, 256, 320),
              "10M": (448, 640, 896, 1152),
              "50M": (1024, 1408, 1920, 2432)}
CNN_HEAD = {"1M": 256, "10M": 512, "50M": 768}
# THE STEM: a single strided convolution that brings ANY window length down to
# 256 positions before the shared stack, so the length ablation is not also a
# compute ablation — {256, 1024, 4096} cost the same per row after the stem.
CNN_STEM_STRIDE = {256: 1, 1024: 4, 4096: 16}

# TRANSFORMER: conv patch-embed -> encoder stack.  Tokens are held near 64-256
# so attention stays affordable at L=4096.
TRF_DEPTH = {"1M": 4, "10M": 6, "50M": 8}
TRF_DIM = {"1M": 144, "10M": 384, "50M": 720}
TRF_HEADS = {"1M": 4, "10M": 6, "50M": 8}
TRF_PATCH = {256: 4, 1024: 8, 4096: 32}   # -> 64 / 128 / 128 tokens

DROPOUT = 0.1
BATCH_BY_LEN = {256: 1024, 1024: 512, 4096: 256}
LR_BY_ARCH = {"cnn": 2e-3, "trf": 6e-4}
WEIGHT_DECAY = 1e-4
MAX_EPOCHS = 10
PATIENCE = 3
WINNER_LOSS_W = 0.25

# ------------------------------------------------------ the pretrain stage --
PRETRAIN_MASK_FRAC = 0.15
PRETRAIN_STEPS = 6000
PRETRAIN_BATCH = {256: 1024, 1024: 512, 4096: 256}
PRETRAIN_LR = 3e-4

# ------------------------------------------------------------ the scoring ---
# The m3_walk deployable arm, VERBATIM: top-N per selection unit, the D-077
# news veto, one-position chronological phase-close replay.  The headline
# schedule is the brief's TOP-3 PER ASSET-DAY, applied identically to every arm
# so the comparison is apples-to-apples.
SCHEDULE_UNIT = "session"
SCHEDULE_N = 3
N_RANDOM_DRAWS = 200


class SeqTestRefusal(RuntimeError):
    """A guard fired.  Never downgraded to a warning, never silently filtered."""


def hb(msg):
    import time as _t
    sys.stderr.write("[seqtest %s] %s\n"
                     % (_t.strftime("%H:%M:%S"), msg))
    sys.stderr.flush()


# ================================================================= guards ====
def assert_disjoint_days(train_idx, test_idx, d8, tag=""):
    """THE DUPLICATE-DAY GUARD.

    A whole-DAY fold means no calendar day may appear on both sides of a split.
    This is the guard the duplicate-day leak probe is fired against: inject a
    training day into the test block and this must REFUSE.
    """
    tr = np.unique(np.asarray(d8)[np.asarray(train_idx, dtype=np.int64)])
    te = np.unique(np.asarray(d8)[np.asarray(test_idx, dtype=np.int64)])
    both = np.intersect1d(tr, te)
    if both.size:
        raise SeqTestRefusal(
            "DUPLICATE-DAY LEAK%s: %d day(s) appear in BOTH the training and "
            "the evaluation block (first 5: %s)"
            % ((" [%s]" % tag) if tag else "", int(both.size),
               both[:5].tolist()))
    return True


def assert_causal_era_order(train_idx, test_idx, era_idx, tag=""):
    """Walk-forward, never random: every training row is from a STRICTLY
    earlier era than every evaluation row."""
    tr = np.asarray(era_idx)[np.asarray(train_idx, dtype=np.int64)]
    te = np.asarray(era_idx)[np.asarray(test_idx, dtype=np.int64)]
    if tr.size and te.size and int(tr.max()) >= int(te.min()):
        raise SeqTestRefusal(
            "NON-CAUSAL FOLD%s: max train era %d >= min eval era %d"
            % ((" [%s]" % tag) if tag else "", int(tr.max()), int(te.min())))
    return True


def inner_split_days(d8_train):
    """s4_confirm._inner_split / m3_walk.inner_split, verbatim: the training
    block's last 20% of DAYS become the inner validation block."""
    u = np.unique(np.asarray(d8_train))
    if u.size < 10:
        return None
    cut = u[int(round(u.size * (1.0 - INNER_FRACTION))) - 1]
    return int(cut)


# ------------------------------------------------------- the cover clamp ----
def cover_start_sec(cover, dec_sec):
    """The start of the CONTIGUOUS cached block that contains `dec_sec`.

    `tape.extract` caches the UNION of per-candidate [dec-692, dec+1] windows,
    so the arrays are a concatenation of blocks: record 0 of a block follows the
    LAST record of the previous block, which is a different part of the session.
    Reading N events backwards must therefore stop at the block boundary or it
    silently splices two unrelated stretches of tape together.  This returns
    that boundary; `st_build` clamps every window to it and pads the rest, and
    the per-shard fill statistics report how often the clamp binds.
    """
    lo = 0
    for a, b in cover:
        if a <= dec_sec <= b + 1:
            return int(a)
        if b < dec_sec:
            lo = int(a)
    return lo


def tick_raw(asset):
    return float(C.ASSETS[asset]["tick_raw"])


def shard_path(asset, era, L):
    return os.path.join(SHARD_DIR, "L%d" % int(L), "SEQ_%s_%s" % (asset, era))


PARAMS = {
    "spec_section": SECTION,
    "question": ("does a small sequence model reading RAW EVENTS pick better "
                 "MOMENTS than anything measured, at CANDIDATE grain"),
    "seq_lens": list(SEQ_LENS),
    "channels": list(CHANNELS),
    "channel_note": ("raw record fields only — action byte one-hot, side byte "
                     "one-hot, record price delta / mid delta / price-minus-mid "
                     "in ticks, log size, log inter-event gap, log L1 size and "
                     "ORDER COUNT both sides, spread in ticks, log seconds to "
                     "the decision second, and a pad-validity mask.  No cue, no "
                     "window statistic, no featurisation."),
    "causality": ("events with ts_event STRICTLY BEFORE (open_utc + dec_sec) "
                  "seconds; the window is additionally clamped to the start of "
                  "the contiguous cached block containing dec_sec"),
    "universe": ("m3 matrix rows (candidate grain, v3 roster) with era in %s; "
                 "the m3 holdout guard (d8 < 20250701) is inherited at load"
                 % (list(UNIVERSE_ERAS),)),
    "folds": "walk-forward era ladder: train E2..Ek -> test E(k+1); whole DAYS",
    "targets": ["y_retg_rank_phase (the atlas champion)", "y_winner (D-021 flag)"],
    "architectures": list(ARCHS),
    "capacity_rungs": list(RUNGS),
    "capacity_rule": ("climb a rung ONLY while honest day-fold walk-forward "
                      "capture improves; the full ladder table is reported so "
                      "weak-model vs no-signal is decided by the curve"),
    "cnn_kernel": CNN_KERNEL,
    "normalisation": "mean/std fitted on TRAINING rows only, per channel",
    "early_stopping": "inner validation = the training block's last 20% of DAYS",
    "controls": ["shuffled-label (red-first, committed before the real run)",
                 "duplicate-day leak probe against assert_disjoint_days",
                 "non-causal era-order probe against assert_causal_era_order",
                 "tensor-causality probe on the seconds-to-decision channel"],
    "pretraining": ("masked-event self-supervised pretraining of the "
                    "transformer on the unlabelled stream, fine-tuned under the "
                    "same folds; reported as its own pretrained-vs-scratch row"),
    "schedule": ("top-%d per asset-day, D-077-UPDATE news veto ON, one-position "
                 "chronological phase-close replay — m3_walk.topn_takes / "
                 "replay_rows / per_trade_stats VERBATIM" % SCHEDULE_N),
    "inference": "panel_score CR1, clustered by DAY",
    "seed": SEED,
    "device": "cuda (RTX PRO 6000 Blackwell); bf16 autocast; TF32 matmul",
    "determinism": ("torch.use_deterministic_algorithms(warn_only) + "
                    "cudnn.deterministic + CUBLAS_WORKSPACE_CONFIG=:4096:8; "
                    "fused attention backward is the one op that may remain "
                    "nondeterministic and is named rather than hidden"),
}
