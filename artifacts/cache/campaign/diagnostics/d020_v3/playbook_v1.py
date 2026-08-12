#!/usr/bin/env python3
"""PLAYBOOK V1 — the orchestrator's era synthesis (ERA_NOTES S1-S3 + noise gates)
as a frozen deterministic decision function.  Committed BEFORE any blind-block
evaluation; the decision function reads ONLY causal minute aggregates strictly
before each candidate's decision second.  Outcome fields are touched only by
the scorer, after calls are made in-memory.

Signatures (from the committed study notes):
  S1 two-stream agreement at the confirmed extreme
  S2 divergence resolution (institutions vs price/crowd)
  S3 trend-day continuation at a confirmed retest
Noise gates: runway < 20 min; compression day; dead-tape micro-confirmation.
Replay: chronological one-position per session at the 60m menu horizon.
"""
import json, sys, pathlib
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib

K = {name: i for i, name in enumerate(packlib.TRAJECTORY_KEYS)}
H60 = 4  # menu index of the 60m horizon in {2,5,15,30,60,120,close}

def sgn(x): return 1 if x > 0 else (-1 if x < 0 else 0)

def decide(cand, table, med, sig, meta):
    """TAKE/SKIP + signature tag. Causal: rows strictly before the decision minute."""
    m = min(cand["second"] // 60, 389)
    side = 1 if cand["side"] == "L" else -1
    atr = float(meta.get("atr14_bps") or 150.0)
    open_u6 = float(meta.get("open_u6") or 0.0)

    lo = max(0, m - 5)
    win = table[lo:m]                       # last <=5 completed minutes
    hour = table[max(0, m - 60):m]
    if len(win) < 2:
        return "SKIP", "warmup"

    def val(rows, key, agg):
        col = rows[:, K[key]]
        col = col[~np.isnan(col)]
        return agg(col) if len(col) else np.nan

    flow5 = val(win, "signed_flow", np.nansum)
    flow_sig = sig[m, K["signed_flow"]] if not np.isnan(sig[m, K["signed_flow"]]) else np.nan
    flow5_z = flow5 / (flow_sig * np.sqrt(len(win))) if flow_sig and not np.isnan(flow_sig) else 0.0
    od5 = val(win, "option_delta_dir", np.nansum)
    cum_flow_h = val(hour, "signed_flow", np.nansum)
    zer_now = val(win[-2:], "zerodte_share", np.nanmean)
    zer_before = val(hour[:30], "zerodte_share", np.nanmean)

    # day context from causal aggregates: proxy of price via absorption is unreliable;
    # use meta open + pivot_mid (the confirmed pivot price, strictly prior)
    pivot = float(cand["pivot_mid"])
    move_from_open_bps = (pivot - open_u6 / 1e6) / (open_u6 / 1e6) * 1e4 if open_u6 else 0.0
    trend_sign = sgn(move_from_open_bps)
    trend_size = abs(move_from_open_bps) / atr

    # ---- noise gates ----
    runway_s = 390 * 60 - cand["second"]
    if runway_s < 1200:
        return "SKIP", "gate-runway"
    # compression / dead tape: hour flow tiny AND trend tiny
    if trend_size < 0.30 and (np.isnan(cum_flow_h) or abs(cum_flow_h) < 60_000):
        return "SKIP", "gate-dead"

    # ---- signatures ----
    s1 = (sgn(flow5) == side and abs(flow5_z) >= 0.8 and sgn(od5) == side)
    crowd = (not np.isnan(zer_now) and not np.isnan(zer_before)
             and (zer_now - zer_before) > 0.10)          # 0DTE piling in late
    s1b = (sgn(flow5) == side and abs(flow5_z) >= 1.5 and crowd)
    s2 = (not np.isnan(cum_flow_h) and abs(cum_flow_h) >= 100_000
          and sgn(cum_flow_h) == side and trend_sign == -side and trend_size >= 0.30)
    s3 = (trend_size >= 0.60 and side == trend_sign
          and sgn(flow5) != -side)                        # continuation not against live flow
    if s1 or s1b:
        return "TAKE", "S1"
    if s2:
        return "TAKE", "S2"
    if s3:
        return "TAKE", "S3"
    return "SKIP", "no-signature"

def run_block(block):
    rosters = json.load(open(pathlib.Path(__file__).parent / "daysheets" /
                             "rosters_DO_NOT_READ_UNTIL_CALLS_COMMITTED.json"))
    sessions = [int(s) for s, rec in rosters["sessions"].items() if rec["block"] == block]
    norm = packlib.ClockNorm(sorted(set(range(125, 448)) - set()))  # priors pool: lawful range
    day_rows, all_calls = [], []
    for s in sorted(sessions):
        rec = rosters["sessions"][str(s)]
        table = packlib.minute_aggregates(s)
        med, sig, _ = norm.stats(s)
        meta = packlib.session_meta(s)
        calls = []
        for cand in sorted(rec["candidates"], key=lambda c: c["second"]):
            call, tag = decide(cand, table, med, sig, meta)
            calls.append((cand, call, tag))
            all_calls.append((s, cand["id"], cand["second"], cand["side"], call, tag))
        # one-position chronological replay of TAKEs at 60m
        busy_until, day_net, took = -1, 0.0, 0
        for cand, call, tag in calls:
            if call != "TAKE" or cand["second"] < busy_until:
                continue
            day_net += cand["menu_net"][H60]
            took += 1
            busy_until = cand["second"] + 3600
        # baselines
        alln = sum(c["menu_net"][H60] for c, _, _ in calls)
        day_rows.append((s, rec["day"], len(calls), took, day_net, alln))
    return day_rows, all_calls

if __name__ == "__main__":
    block = sys.argv[1]
    rows, calls = run_block(block)
    nets = np.array([r[4] for r in rows])
    print(f"== {block}: {len(rows)} days ==")
    print(f"{'sess':>5} {'day':>11} {'cands':>5} {'took':>4} {'playbook$':>10} {'all-take$':>10}")
    for r in rows:
        print(f"{r[0]:>5} {r[1]:>11} {r[2]:>5} {r[3]:>4} {r[4]:>10.0f} {r[5]:>10.0f}")
    print(f"MEAN/day: playbook ${nets.mean():,.0f} | median ${np.median(nets):,.0f} | "
          f"positive days {int((nets>0).sum())}/{len(nets)} | worst ${nets.min():,.0f} | "
          f"trades/day {np.mean([r[3] for r in rows]):.1f} | all-take mean ${np.mean([r[5] for r in rows]):,.0f}")
    out = pathlib.Path(__file__).parent / f"playbook_calls_{block}.tsv"
    with open(out, "w") as f:
        f.write("session\tid\tsecond\tside\tcall\ttag\n")
        for row in calls:
            f.write("\t".join(map(str, row)) + "\n")
    print("calls ->", out)
