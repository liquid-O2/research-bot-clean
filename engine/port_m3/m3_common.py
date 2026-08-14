#!/usr/bin/python3
"""PORT M3 — shared substrate for THE MODEL HARNESS (D-085: the model is the
SCALE-CERTIFIED object).

WHAT THIS MODULE OWNS
  * the M3 output root + pins (M3 pins its own brief-frozen constants AND every
    upstream spec whose receipts it reads, via m2_common.verify_spec);
  * THE FEATURE REGISTRY — every column of the matrix, with its group, its
    source field and its availability law.  Nothing enters the matrix that is
    not declared here (D-006: a constructor is "built" only with a spec);
  * THE TWO GUARDS the brief orders red-first:
      1. HOLDOUT GUARD  — a row with d8 >= 20250701 in the matrix is a refusal,
         never a filter (D-058 / m2_common.HOLDOUT_FROM_D8);
      2. FORWARD-FEATURE GUARD — a NAME half (the forbidden-source registry:
         outcome columns, the m2 KNOWN_TRAPS receipts, and the two fields
         pattern_lib itself declares non-causal) and a VALUE half (a feature
         column that reproduces an outcome column to within FORWARD_RHO of a
         perfect rank correlation is a refusal).  A future-feature mutant is
         caught by one or both.
  * the D-021 / D-048 bars, as named constants read by the scorer.

LAWS honoured here
  D-018  every byte of bulk output goes under artifacts/cache/port/m3/
  D-058  the pre-exam holdout is NEVER loaded (the guarded enumerator)
  D-021  per-trade expectancy / MAE / daily-drawdown acceptance
  D-048  >$2,000 per session per asset; $1,500 weak-era floor
  D-078  the NO-TEACHER flag: the feature set declares that it carries ZERO
         teacher-evidence features, so the coming teacher round's marginal
         value is measurable against this exact harness.
  determinism  no RNG outside the pinned seeds; every ordering is an explicit
         sort; two runs of the same stage are byte-identical.
"""
import os
import sys

import numpy as np

_M0 = "/workspace/engine/port_m0"
_M1 = "/workspace/engine/port_m1"
_M2 = "/workspace/engine/port_m2"
for _p in (_M0, _M1, _M2):
    if _p not in sys.path:
        sys.path.insert(0, _p)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common as C                        # noqa: E402
import census_common as X                 # noqa: E402
import m2_common as MC                    # noqa: E402

# ------------------------------------------------------------------- pins ---
# M3 carries no spec document of its own yet: the orchestrator's brief IS the
# design (D-002).  What CAN be pinned mechanically is pinned: the upstream spec
# shas (through MC.verify_spec) and the frozen constants below, all of which
# are stamped into every receipt.
HARNESS_VERSION = "PORT-M3-HARNESS-V1"
BRIEF = ("D-078/D-084/D-085 + PORT_M2_SHEETS_SPEC CC-M2-15..24 + "
         "LABEL_ATLAS_V2 §2.2/§2.5 (the atlas champion)")

M3_ROOT = "/workspace/artifacts/cache/port/m3"
MATRIX_DIR = os.path.join(M3_ROOT, "matrix")
WALK_DIR = os.path.join(M3_ROOT, "walk")

ASSET_ORDER = MC.ASSET_ORDER
PHASE_NAMES = X.PHASE_NAMES
ERAS = MC.ERAS
ERA_NAMES = tuple(e[0] for e in ERAS)
HOLDOUT_FROM_D8 = MC.HOLDOUT_FROM_D8

SEED = 20260813                          # the S4 pinned seed, reused verbatim

# ------------------------------------------------------------ the bars ------
BAR_PER_SESSION_USD = 2000.0             # D-048: >$2,000/session/asset
BAR_THIN_FLOOR_USD = 1500.0              # D-043/D-045 weak-era floor
BAR_TRADE_MIN_USD = 600.0                # D-021 absolute minimum expectancy
BAR_TRADE_TARGET_USD = 1000.0            # D-021 target expectancy
BAR_MAE_AT_MIN_USD = 300.0               # D-021 MAE acceptance at $600/trade
BAR_MAE_AT_HIGH_USD = 500.0              # ... up to $500 when expectancy >=$1,600
BAR_EXPECTANCY_FOR_HIGH_MAE_USD = 1600.0
BAR_DAILY_DD_USD = 1000.0                # D-030 daily drawdown target

# D-077-UPDATE: the prop-firm restricted window is +/-10 minutes around a
# scheduled high-impact release, and AVOIDANCE is the preferred posture.
NEWS_WINDOW_MIN = 10.0

# ------------------------------------------------- D-084 the break points ---
# D-084(b) names four historical regime breaks and orders a MEASURED adaptation
# latency at each.  The named breaks are mapped, pre-registered, onto the era
# boundary that opens each one — which is exactly the walk-forward instrument
# the ladder already builds: the era's model was fitted ONLY on pre-break data,
# so "sessions until the era's achievable capture is recovered" is a number the
# harness can read straight off its own per-session curve.
BREAKS = (("2021_metal_fade", "E1"),
          ("2022_rate_shock", "E2"),
          ("2023_chop_onset", "E4"),
          ("2024_trend_onset", "E6"))
LATENCY_WINDOW_SESSIONS = 20             # trailing window of the rolling curve

# ---------------------------------------------------------- the guards ------
class HarnessRefusal(RuntimeError):
    """A guard fired.  Never a silent filter, never a default."""


# THE FORBIDDEN-SOURCE REGISTRY (the NAME half of the forward-feature guard).
# Three provenances, all named:
#   (a) OUTCOME     — the label side of the corpus; reading one as a feature is
#                     the trivial leak.
#   (b) TRAP        — m2_common.KNOWN_TRAPS, the registry of receipt fields
#                     whose committed value is not knowable at decision time.
#   (c) DECLARED    — fields pattern_lib itself documents as non-causal
#                     (runway_binding_sec / observed_close_sec are built from an
#                     end-of-session fact; short_day is the same fact's flag).
FORBIDDEN_SOURCES = {
    # (a) outcomes
    "cert_close_usd": "OUTCOME", "cert_peak_usd": "OUTCOME",
    "mae_before_argmax": "OUTCOME", "walled": "OUTCOME", "winner": "OUTCOME",
    "mfe_unwalled": "OUTCOME", "mfe_argmax_sec": "OUTCOME",
    "exit_close_sec": "OUTCOME", "exit_peak_sec": "OUTCOME",
    "f_h30": "OUTCOME", "f_h60": "OUTCOME", "f_h120": "OUTCOME",
    "f_phase_close": "OUTCOME", "f_sess_close": "OUTCOME",
    "skel_f_t": "OUTCOME", "skel_f_v": "OUTCOME",
    "skel_a_t": "OUTCOME", "skel_a_v": "OUTCOME",
    # (c) declared non-causal
    "runway_binding_sec": "DECLARED", "observed_close_sec": "DECLARED",
    "short_day": "DECLARED",
    "range_phase_usd": "DECLARED",       # whole-phase range (frame diagnostic)
    "range_sess_usd": "DECLARED",        # == range_so_far only at the row; the
                                         # frame carries it as the session-clock
                                         # twin and it is not read here
}
for _k, _v in MC.KNOWN_TRAPS.items():
    FORBIDDEN_SOURCES.setdefault(_k.split(".")[-1], "TRAP")
FORBIDDEN_SOURCES.setdefault("last_test_outcome", "TRAP")
FORBIDDEN_SOURCES.setdefault("touch_count", "TRAP")
FORBIDDEN_SOURCES.setdefault("ratio_range_over_sigmahat", "TRAP")
FORBIDDEN_SOURCES.setdefault("dominant_share", "TRAP")

# The VALUE half.  A feature that reproduces an outcome to within this much of
# a perfect rank correlation is refused: a mutant that smuggles a forward
# quantity in under an innocent NAME is caught here.
FORWARD_RHO = 0.98
FORWARD_PROBE_ROWS = 120000              # deterministic fixed-stride subsample

# The reference set for the VALUE probe: the quantities that are genuinely
# UNKNOWABLE at the decision second.  `cost_rt` and the exit seconds live in the
# outcome block for the replay's sake but are NOT forward quantities (the cost
# is the session's own published round trip; the exit second of an unwalled
# close IS the phase boundary, which the runway already names lawfully), so
# probing against them would manufacture false positives rather than catch
# leaks.
FORWARD_PROBE_REF = ("cert_close_usd", "cert_peak_usd", "mae_before_argmax",
                     "mfe_unwalled", "f_sess_close", "winner", "walled")


def check_holdout(d8):
    """THE HOLDOUT GUARD.  A refusal, never a filter (D-058)."""
    a = np.asarray(d8, dtype=np.int64)
    bad = a[a >= HOLDOUT_FROM_D8]
    if bad.size:
        raise HarnessRefusal(
            "D-058 HOLDOUT GUARD: %d matrix row(s) carry a pre-exam holdout "
            "session (d8 >= %d, first %d). The holdout is NEVER loaded."
            % (int(bad.size), HOLDOUT_FROM_D8, int(bad.min())))
    return int(a.size)


def check_forbidden_names(features):
    """THE FORWARD-FEATURE GUARD, name half."""
    bad = []
    for f in features:
        for src in f.sources:
            why = FORBIDDEN_SOURCES.get(src)
            if why is not None:
                bad.append((f.name, src, why))
    if bad:
        raise HarnessRefusal(
            "FORWARD-FEATURE GUARD (name): %d feature(s) read a forbidden "
            "source: %s" % (len(bad), bad[:8]))
    return len(features)


def _rank(v):
    """Average-rank transform with NaNs sent to the mean rank (stable)."""
    a = np.asarray(v, dtype=np.float64)
    out = np.full(a.size, np.nan)
    ok = np.isfinite(a)
    n = int(ok.sum())
    if n < 2:
        return out
    x = a[ok]
    order = np.argsort(x, kind="stable")
    r = np.empty(n, dtype=np.float64)
    sx = x[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sx[j + 1] == sx[i]:
            j += 1
        r[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    out[ok] = r
    return out


def _rho(a, b):
    """Spearman over the rows where BOTH are finite."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    m = np.isfinite(a) & np.isfinite(b)
    if int(m.sum()) < 30:
        return float("nan")
    ra = _rank(a[m])
    rb = _rank(b[m])
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    den = np.sqrt((ra * ra).sum() * (rb * rb).sum())
    if den <= 0:
        return float("nan")
    return float((ra * rb).sum() / den)


def check_forward_values(names, Xm, outcomes, rho_bar=FORWARD_RHO,
                         probe_rows=FORWARD_PROBE_ROWS):
    """THE FORWARD-FEATURE GUARD, value half.

    `outcomes` = {name: vector} of the corpus's forward quantities; only the
    FORWARD_PROBE_REF members are probed.  A feature whose |Spearman| against
    ANY of them exceeds `rho_bar` is refused.  The probe runs on a
    deterministic evenly-spaced subsample so the guard costs the same on 1.5M
    rows as on 100k and is reproducible byte-for-byte.
    """
    n = int(Xm.shape[0])
    if n == 0:
        return []
    step = max(1, n // int(probe_rows))
    sl = slice(0, n, step)
    ref = {k: v for k, v in outcomes.items() if k in FORWARD_PROBE_REF}
    hits = []
    for j, nm in enumerate(names):
        col = Xm[sl, j]
        if not np.isfinite(col).any():
            continue
        for on, ov in sorted(ref.items()):
            r = _rho(col, np.asarray(ov)[sl])
            if np.isfinite(r) and abs(r) > rho_bar:
                hits.append((nm, on, float(r)))
    if hits:
        raise HarnessRefusal(
            "FORWARD-FEATURE GUARD (value): %d feature/outcome pair(s) exceed "
            "|rho| > %.3f — a forward quantity is in the matrix under an "
            "innocent name: %s" % (len(hits), rho_bar, hits[:8]))
    return hits


# ------------------------------------------------------------- receipts -----
def out_path(*parts):
    p = os.path.join(M3_ROOT, *parts)
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    return p


def env_receipt(params):
    e = C.env_receipt(params)
    e.update(MC.spec_shas())
    e["harness_version"] = HARNESS_VERSION
    e["brief"] = BRIEF
    return e


def write_tsv(path, section, phash, columns, rows, extra=()):
    tmp = path + ".tmp"
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    lines = ["# PORT M3 %s (harness=%s; m2_spec_sha16=%s)"
             % (section, HARNESS_VERSION, MC.SPEC_SHA16),
             "# params_hash=%s" % phash]
    for e in extra:
        lines.append("# %s" % e)
    lines.append("\t".join(columns))
    with open(tmp, "w", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
        for r in rows:
            fh.write("\t".join(MC._cell(v) for v in r) + "\n")
    os.replace(tmp, path)
    return path


write_json = MC.write_json
write_text = MC.write_text
params_hash = MC.params_hash
hb = MC.hb
