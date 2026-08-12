#!/usr/bin/env python3
"""ERA_RETEST — the first 2024-2025 validation of the v2 / v3 selectors.

The walk-forward ladder published in `WALKFORWARD_REPORT.md` (segments a..e)
and the v3 arms published in `MODEL_V3_REPORT.md` stop at session 447
(2023-10-13).  D-038 opened the whole research scope 125..917 (through
2025-08-29); this file extends the SAME ladder, with the SAME frozen estimator
and the SAME arms, over the four newly opened era blocks:

    segment f   train 125..447   test e4 = 448..497   (2023 Q4)
    segment g   train 125..497   test e5 = 498..623   (2024 H1)
    segment h   train 125..623   test e6 = 624..735   (2024 H2)
    segment i   train 125..735   test e7 = 736..917   (2025 to 2025-08-29)

`roster_blind_eN.json` is the LAST 20 SESSIONS of `roster_study_eN.json`, not a
disjoint roster (verified: identical candidate ids on the shared sessions), so
"study_e4 + blind_e4" IS 448..497 and every candidate is taken exactly once.
The blind sub-block is still scored separately, because the v3 report's own
caveat (3) asked for `E_/T_/I_ ONLY` to be retested on `blind_e4..e7`.

NOTHING is tuned here.  The estimator is v2's frozen config (`wf.FROZEN`), the
arms are model_v3's own column sets, the operating rate is the reader's own
11/40, and no threshold, column set or hyper-parameter is ever chosen by
looking at a test block.  Usable-column selection runs on each segment's own
TRAINING window (`dm.feature_columns`), which is the lawful side.

    era_retest.py [--stage features|eval|all] [--rebuild] [--jobs N]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

#: pinned before numpy/sklearn load, exactly as walkforward.py does, so the
#: histogram reductions sum in a fixed order and the report is reproducible
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np                                      # noqa: E402
import pandas as pd                                     # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import packlib as P                                     # noqa: E402
import distill_model as dm                              # noqa: E402
import model_v2 as mv                                   # noqa: E402
import walkforward as wf                                # noqa: E402
import model_v3 as mv3                                  # noqa: E402

ROOT = P.ROOT
SHEETS = ROOT / "sheets"
MATRIX = ROOT / "FEATURES_ERA.tsv"
REPORT = ROOT / "ERA_RETEST_REPORT.md"
#: the plain-language reading of the tables below.  It is written by hand AFTER
#: the numbers land (D-008) and spliced back in on every rerun, so re-running
#: this file reproduces the whole report rather than truncating it.
VERDICT = ROOT / "ERA_RETEST_VERDICT.md"
SEGDIR = ROOT / "era_segments"
SEED = dm.SEED
FROZEN = wf.FROZEN
OPERATING_RATE = mv.OPERATING_RATE

#: the six published blocks, unchanged, as the frozen history 125..447
HISTORY = ("study_e1", "study_e1b", "study_e2", "study_e3", "study_e3b", "blind_e3")
#: (block name, roster to read, blind sub-block roster) for the new eras
NEW_ERAS = (("e4", "study_e4", "blind_e4"),
            ("e5", "study_e5", "blind_e5"),
            ("e6", "study_e6", "blind_e6"),
            ("e7", "study_e7", "blind_e7"))
#: `e` is the REPRODUCTION CONTROL — the published rung, refitted inside this
#: harness on the extended matrix.  Its numbers must land on the published
#: 0.646 / $1,459 (v2) and 0.655 / $1,598 (v3 full); if they do not, the matrix
#: extension changed the old rows and every new number below is suspect.
SEGMENTS = (("e", "blind_e3"), ("f", "e4"), ("g", "e5"), ("h", "e6"), ("i", "e7"))
CONTROL_SEGMENT = "e"
ERA_LABEL = {"blind_e3": "2023-09-15..10-13 control",
             "e4": "2023 Q4  2023-10-16..12-26",
             "e5": "2024 H1  2023-12-27..2024-06-27",
             "e6": "2024 H2  2024-06-28..12-05",
             "e7": "2025     2024-12-06..2025-08-29"}
#: published anchors for the control rung (WALKFORWARD_REPORT / MODEL_V3_REPORT)
PUBLISHED = {"v2": (0.646, 1459.0), "v3 full": (0.655, 1598.0),
             "E/T/I only": (0.665, 1068.0), "v2 no-M": (0.651, 1511.0)}

SHUFFLE_SEGMENT = "i"
SHUFFLE_DRAWS = 5


# ==========================================================================
# rosters
# ==========================================================================

def roster(name: str) -> dict:
    return json.loads((SHEETS / f"roster_{name}.json").read_text())


def blind_sessions(name: str) -> set:
    return {int(k) for k in roster(name)["sessions"]}


def jobs_for_matrix() -> list:
    """(ordinal, block, candidates) for the six history blocks + four new eras."""
    jobs = []
    for name in HISTORY:
        record = roster(name)
        for key in sorted(record["sessions"], key=int):
            jobs.append((int(key), name, record["sessions"][key]))
    for block, study, _ in NEW_ERAS:
        record = roster(study)
        for key in sorted(record["sessions"], key=int):
            jobs.append((int(key), block, record["sessions"][key]))
    seen = set()
    for ordinal, _, _ in jobs:
        if ordinal in seen:
            raise SystemExit(f"duplicate session {ordinal} in the era ladder")
        seen.add(ordinal)
    return sorted(jobs, key=lambda job: job[0])


# ==========================================================================
# matrix assembly — walkforward's v1+v2+M_ row, then model_v3's E_/T_/I_ tiers
# ==========================================================================

def _row_job(job: tuple) -> list:
    ordinal, block, candidates = job
    base = wf.session_rows(job)
    extra = {row["id"]: row for row in mv3._job((ordinal, block, candidates))}
    for row in base:
        new = dict(extra.get(row["id"], {}))
        new.pop("session", None)
        new.pop("id", None)
        row.update(new)
    return base


def build_matrix(jobs_n: int) -> pd.DataFrame:
    jobs = jobs_for_matrix()
    #: causal hot/cool cut table, built ONCE in the parent so every forked
    #: worker inherits the identical table (and so a stale one is caught here)
    cuts = wf.ensure_hotcut()
    wf.fvol_sessions()
    wf._worker_norm()
    print(f"forecast-vol coverage: {len(cuts)} sessions "
          f"{min(cuts) if cuts else '-'}..{max(cuts) if cuts else '-'}", flush=True)
    print(f"building era matrix: {len(jobs)} sessions, {jobs_n} workers", flush=True)
    records = []
    if jobs_n <= 1:
        for done, job in enumerate(jobs, 1):
            records.extend(_row_job(job))
            if done % 20 == 0:
                print(f"  {done}/{len(jobs)} sessions, {len(records)} rows", flush=True)
    else:
        import multiprocessing as multi
        with multi.get_context("fork").Pool(jobs_n) as pool:
            for done, rows in enumerate(pool.imap_unordered(_row_job, jobs), 1):
                records.extend(rows)
                if done % 20 == 0 or done == len(jobs):
                    print(f"  {done}/{len(jobs)} sessions, {len(records)} rows", flush=True)
    frame = pd.DataFrame.from_records(records)
    frame = pd.concat([frame, mv3.derive_frame_features(frame)], axis=1)
    return frame.sort_values(["session", "second", "side"]).reset_index(drop=True)


# ==========================================================================
# arms — model_v3's own column sets, never re-derived here
# ==========================================================================

def arm_columns(frame: pd.DataFrame, train: pd.DataFrame) -> dict:
    """{arm: columns}; usability is decided on the TRAINING window only."""
    usable = dm.feature_columns(frame, train)
    columns = [c for c in usable if not c.startswith("J_")]
    v3 = columns
    v2 = [c for c in columns if not c.startswith(mv3.V3_PREFIXES)]
    return {
        "v2": v2,
        "v2 no-M": [c for c in v2 if not c.startswith("M_")],
        "v3 full": v3,
        "v3 no-M": [c for c in v3 if not c.startswith("M_")],
        "E/T/I only": [c for c in v3 if c.startswith(mv3.V3_PREFIXES)],
    }


ARMS = ("v2", "v2 no-M", "v3 full", "v3 no-M", "E/T/I only")


# ==========================================================================
# scoring
# ==========================================================================

_BASELINE: dict = {}


#: `dm.day_metrics` draws 200 random top-k baskets per day; on the 462-column
#: matrix every draw copies a full-width slice, which dominates the run.  The
#: baseline reads only these columns, and the draw sequence depends on SEED and
#: the iteration count alone, so slicing first changes cost and nothing else.
BASELINE_COLS = ("session", "second", "cert", "cert_mae", "menu60", "menu_close",
                 "winner")


def baselines(frame: pd.DataFrame, key: str) -> dict:
    """random-3 / oracle-3 / oracle-5 are properties of the BLOCK, not the score."""
    if key not in _BASELINE:
        slim = frame[list(BASELINE_COLS)].reset_index(drop=True)
        three = dm.day_metrics(slim, np.zeros(len(slim)), k=3)
        five = dm.day_metrics(slim, np.zeros(len(slim)), k=5)
        _BASELINE[key] = {"random3_day": three["random_per_day"],
                          "oracle3_day": three["oracle_per_day"],
                          "random5_day": five["random_per_day"],
                          "oracle5_day": five["oracle_per_day"],
                          "days": three["days"]}
    return _BASELINE[key]


def score_metrics(frame: pd.DataFrame, score: np.ndarray, key: str) -> dict:
    """AUC + top-k dollars + the 27.5% operating point for one (block, score)."""
    from sklearn.metrics import roc_auc_score
    base = baselines(frame, key)
    days = max(base["days"], 1)
    picks3, picks5, maes, close, sixty = [], [], [], [], []
    working = frame.assign(_score=score)
    for _, day in working.groupby("session", sort=True):
        top3 = day.nlargest(3, "_score")
        picks3.append(float(top3["cert"].sum()))
        picks5.append(float(day.nlargest(5, "_score")["cert"].sum()))
        maes.extend(top3["cert_mae"].tolist())
        #: the DEPLOYABLE shape (D-019): ONE position at a time, chronological.
        #: `close` enters the earliest of the day's three picks and holds it to
        #: the close; `60m` is the greedy 60-minute-occupancy replay.  Both are
        #: dm.day_metrics' own definitions, recomputed here per arm.
        ordered = top3.sort_values("second")
        close.append(float(ordered.iloc[0]["menu_close"]) if len(ordered) else 0.0)
        busy, total = -1, 0.0
        for _, row in ordered.iterrows():
            if row["second"] < busy:
                continue
            total += float(row["menu60"])
            busy = row["second"] + 3600
        sixty.append(total)
    point = mv.operating_point(frame, score, OPERATING_RATE)
    auc = (float(roc_auc_score(frame["winner"], score))
           if frame["winner"].nunique() > 1 else np.nan)
    top3 = float(np.mean(picks3))
    top5 = float(np.mean(picks5))
    return {
        "n": len(frame), "days": days,
        "winrate": float(frame["winner"].mean()),
        "auc": auc,
        "top3_day": top3, "top5_day": top5,
        "oracle3_day": base["oracle3_day"], "oracle5_day": base["oracle5_day"],
        "random3_day": base["random3_day"],
        "lift_random3": top3 / base["random3_day"] if base["random3_day"] else np.nan,
        "op_lift": point["lift"],
        "op_cert_taken": point["cert_taken"],
        "op_winrate_taken": point["winrate_taken"],
        "op_trades_day": point["n_taken"] / days,
        "mae_per_pick": float(np.mean(maes)) if maes else np.nan,
        "replay_close_day": float(np.mean(close)),
        "replay_60m_day": float(np.mean(sixty)),
    }


# ==========================================================================
# formatting
# ==========================================================================

def money(value) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"${value:,.0f}"


def number(value, digits: int = 3) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{value:.{digits}f}"


def pct(value) -> str:
    return "n/a" if value is None or not np.isfinite(value) else f"{100 * value:.1f}%"


def family_coverage(part: pd.DataFrame, prefix: str) -> float:
    """Mean finite-cell rate over every column of one feature family."""
    columns = [c for c in part.columns if c.startswith(prefix)]
    if not columns or not len(part):
        return 0.0
    return float(part[columns].notna().to_numpy().mean())


def write_tsv(path: pathlib.Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, sep="\t", index=False)


# ==========================================================================
# main
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="all", choices=("features", "eval", "all"))
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--jobs", type=int, default=24)
    args = parser.parse_args()

    if args.rebuild or not MATRIX.exists():
        frame = build_matrix(args.jobs)
        frame.to_csv(MATRIX, sep="\t", index=False)
        print(f"matrix {frame.shape} -> {MATRIX}", flush=True)
    else:
        frame = pd.read_csv(MATRIX, sep="\t", low_memory=False)
        print(f"matrix {frame.shape} <- {MATRIX}", flush=True)
    if args.stage == "features":
        return

    SEGDIR.mkdir(parents=True, exist_ok=True)
    blocks = list(HISTORY) + [name for name, _, _ in NEW_ERAS]
    blind_of = {block: blind_sessions(blind) for block, _, blind in NEW_ERAS}
    out = []

    # ---------------------------------------------------------------- census
    census = []
    for block in blocks:
        part = frame[frame["block"] == block]
        base = baselines(part.reset_index(drop=True), f"block/{block}")
        sessions = sorted(part["session"].unique())
        factors = wf.session_factors(sessions)
        census.append({
            "era": block, "first": sessions[0], "last": sessions[-1],
            "days": len(sessions), "candidates": len(part),
            "winrate": float(part["winner"].mean()),
            "mean_cert": float(part["cert"].mean()),
            "oracle3_day": base["oracle3_day"], "oracle5_day": base["oracle5_day"],
            "random3_day": base["random3_day"],
            "rty_f": float(np.nanmean([factors.get(s, np.nan) for s in sessions])),
            #: typed-absence bookkeeping: the FAMILY's mean cell coverage, not
            #: one representative column — a family that is partly absent in an
            #: era must be visible as such rather than averaged away
            **{f"{prefix}cov": family_coverage(part, prefix)
               for prefix in ("M_", "I_", "T_", "E_")},
        })
    write_tsv(SEGDIR / "era_census.tsv", census)

    # ---------------------------------------------------------------- ladder
    rty_factor = {row["era"]: row["rty_f"] for row in census}
    ladder, blind_rows, shuffle_rows = [], [], []
    for seg, test_block in SEGMENTS:
        test = frame[frame["block"] == test_block].reset_index(drop=True)
        train = frame[frame["session"] < int(test["session"].min())].reset_index(drop=True)
        assert train["session"].max() < test["session"].min(), "walk-forward purity"
        sets = arm_columns(frame, train)
        blind_set = blind_of.get(test_block, set())
        blind = test[test["session"].isin(blind_set)].reset_index(drop=True)
        print(f"segment {seg}: train {len(train)} rows "
              f"({train['session'].min()}..{train['session'].max()}) -> "
              f"test {test_block} {len(test)} rows "
              f"({test['session'].min()}..{test['session'].max()})", flush=True)
        seg_rows = []
        for arm in ARMS:
            columns = sets[arm]
            score = wf.fit_frozen(train, test, columns)
            metrics = score_metrics(test, score, f"block/{test_block}")
            row = {"segment": seg, "test_era": test_block,
                   "era_label": ERA_LABEL[test_block],
                   "train_first": int(train["session"].min()),
                   "train_last": int(train["session"].max()),
                   "train_rows": len(train), "arm": arm,
                   "features": len(columns), **metrics,
                   #: D-022 reporting overlay — one RTY mini at the block's own
                   #: mean per-session factor f(s) = median IWM mid / 200
                   "rty_f": rty_factor[test_block],
                   "top3_day_rty": metrics["top3_day"] * rty_factor[test_block],
                   "top5_day_rty": metrics["top5_day"] * rty_factor[test_block]}
            seg_rows.append(row)
            ladder.append(row)
            print(f"   {arm:12s} {len(columns):4d} cols  AUC {metrics['auc']:.3f}  "
                  f"top3 ${metrics['top3_day']:,.0f}  top5 ${metrics['top5_day']:,.0f}  "
                  f"lift@27.5% {metrics['op_lift']:.2f}x", flush=True)
            #: the blind sub-block — the v3 report's caveat (3) asked for exactly
            #: this: the same arms retested on `blind_e4..e7`
            mask = test["session"].isin(blind_set).to_numpy()
            if mask.any():
                sub = score_metrics(blind, score[mask], f"blind/{test_block}")
                blind_rows.append({"segment": seg, "test_era": test_block,
                                   "sub_block": f"blind_{test_block}", "arm": arm,
                                   "features": len(columns), **sub})
            if seg == SHUFFLE_SEGMENT:
                rng = np.random.default_rng(SEED)
                draws = []
                for draw in range(SHUFFLE_DRAWS):
                    labels = rng.permutation(train["winner"].to_numpy())
                    shuffled = wf.fit_frozen(train, test, columns, labels=labels,
                                             seed=SEED + draw)
                    draws.append(score_metrics(test, shuffled, f"block/{test_block}"))
                shuffle_rows.append({
                    "segment": seg, "test_era": test_block, "arm": arm,
                    "draws": SHUFFLE_DRAWS,
                    "auc_mean": float(np.mean([d["auc"] for d in draws])),
                    "auc_sd": float(np.std([d["auc"] for d in draws])),
                    "top3_mean": float(np.mean([d["top3_day"] for d in draws])),
                    "top3_sd": float(np.std([d["top3_day"] for d in draws])),
                    "auc_real": metrics["auc"], "top3_real": metrics["top3_day"]})
                print(f"   {arm:12s} SHUFFLE AUC "
                      f"{shuffle_rows[-1]['auc_mean']:.3f} +/- "
                      f"{shuffle_rows[-1]['auc_sd']:.3f}", flush=True)
        write_tsv(SEGDIR / f"segment_{seg}_{test_block}.tsv", seg_rows)
    write_tsv(SEGDIR / "ladder_summary.tsv", ladder)
    write_tsv(SEGDIR / "blind_subblocks.tsv", blind_rows)
    write_tsv(SEGDIR / "label_shuffle.tsv", shuffle_rows)

    # ---------------------------------------------------------------- report
    ladder_frame = pd.DataFrame(ladder)
    out.append("# ERA-RETEST REPORT — the first 2024-2025 validation "
               "of the v2 / v3 selectors\n")
    out.append(f"Frozen estimator for EVERY fit below (v2's config, never re-selected): "
               f"`{FROZEN}`.  Expanding-window ladder extended over the four newly "
               f"opened era blocks, {len(frame):,} candidates, "
               f"{frame['session'].nunique()} sessions "
               f"{frame['session'].min()}..{frame['session'].max()}.  "
               f"Sealed zone {P.SEALED_FROM}+ untouched.\n")

    if VERDICT.exists():
        out.append("\n" + VERDICT.read_text().rstrip())
    out.append("\n## Era census — the OFFER, extended into 2024-25\n")
    out.append("| era | sessions | days | candidates | winner rate | mean cert | "
               "oracle top-3/day | oracle top-5/day | random-3/day | RTY f | "
               "`M_` cov | `I_` cov | `T_` cov | `E_` cov |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in census:
        out.append(f"| `{row['era']}` | {row['first']}..{row['last']} | {row['days']} | "
                   f"{row['candidates']} | {pct(row['winrate'])} | "
                   f"{money(row['mean_cert'])} | {money(row['oracle3_day'])} | "
                   f"{money(row['oracle5_day'])} | {money(row['random3_day'])} | "
                   f"{number(row['rty_f'])} | {pct(row['M_cov'])} | "
                   f"{pct(row['I_cov'])} | {pct(row['T_cov'])} | "
                   f"{pct(row['E_cov'])} |")

    out.append("\n## Reproduction control — the published rung `e`, refitted here\n")
    out.append("Same rung, same frozen config, on the EXTENDED matrix.  Any drift "
               "against the published anchors would mean the extension changed the "
               "old rows.\n")
    out.append("| arm | AUC here | AUC published | top-3 $/day here | "
               "top-3 $/day published |")
    out.append("|---|---|---|---|---|")
    for row in ladder:
        if row["segment"] != CONTROL_SEGMENT:
            continue
        anchor = PUBLISHED.get(row["arm"])
        out.append(f"| {row['arm']} | {number(row['auc'])} | "
                   f"{number(anchor[0]) if anchor else 'n/a'} | "
                   f"{money(row['top3_day'])} | "
                   f"{money(anchor[1]) if anchor else 'n/a'} |")

    out.append("\n## The extended ladder — segments f..i, four new eras\n")
    out.append("| seg | test era | window | arm | features | AUC | top-3 $/day | "
               "top-3 RTY-mini | top-5 $/day | lift@27.5% | oracle top-3/day | "
               "trades/day | lift vs random-3 | cert/taken |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for row in ladder:
        if row["segment"] == CONTROL_SEGMENT:
            continue
        out.append(f"| **{row['segment']}** | `{row['test_era']}` "
                   f"({row['era_label']}) | {row['train_first']}..{row['train_last']} "
                   f"-> {row['test_era']} | {row['arm']} | {row['features']} | "
                   f"{number(row['auc'])} | **{money(row['top3_day'])}** | "
                   f"{money(row['top3_day_rty'])} | "
                   f"{money(row['top5_day'])} | {number(row['op_lift'], 2)}x | "
                   f"{money(row['oracle3_day'])} | {number(row['op_trades_day'], 1)} | "
                   f"{number(row['lift_random3'], 2)}x | "
                   f"{money(row['op_cert_taken'])} |")

    out.append("\n## The blind sub-blocks — `blind_e4..e7`, the last 20 days of each era\n")
    out.append("The v3 report's caveat (3) asked for the `E_/T_/I_ ONLY` result to be "
               "retested on exactly these rosters.  Same fits as above, scored on the "
               "sub-block only.\n")
    out.append("| seg | sub-block | arm | n | days | AUC | top-3 $/day | top-5 $/day | "
               "lift@27.5% | oracle top-3/day |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for row in blind_rows:
        out.append(f"| {row['segment']} | `{row['sub_block']}` | {row['arm']} | "
                   f"{row['n']} | {row['days']} | {number(row['auc'])} | "
                   f"**{money(row['top3_day'])}** | {money(row['top5_day'])} | "
                   f"{number(row['op_lift'], 2)}x | {money(row['oracle3_day'])} |")

    out.append("\n## D-043's $1,500/day floor — does ANY arm clear it?\n")
    out.append("`top-3` / `top-5` sum the exit-free certified value of k picks a "
               "day, averaged over EVERY day in the block.  The ONE-POSITION "
               "column is the deployable D-019 shape — the earliest of the day's "
               "three picks, entered and held to the close, one contract.  The "
               "floor is the user's stated minimum for a deployable era.\n")
    out.append("| test era | best arm @ top-3 | top-3 $/day | clears $1,500? | "
               "best arm @ top-5 | top-5 $/day | clears $1,500? | "
               "best one-position close $/day | oracle top-3/day |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for seg, test_block in SEGMENTS:
        if seg == CONTROL_SEGMENT:
            continue
        rows = [r for r in ladder if r["segment"] == seg]
        best3 = max(rows, key=lambda r: r["top3_day"])
        best5 = max(rows, key=lambda r: r["top5_day"])
        best1 = max(rows, key=lambda r: r["replay_close_day"])
        out.append(f"| `{test_block}` ({ERA_LABEL[test_block]}) | {best3['arm']} | "
                   f"**{money(best3['top3_day'])}** | "
                   f"{'YES' if best3['top3_day'] >= 1500 else 'no'} | "
                   f"{best5['arm']} | **{money(best5['top5_day'])}** | "
                   f"{'YES' if best5['top5_day'] >= 1500 else 'no'} | "
                   f"{money(best1['replay_close_day'])} ({best1['arm']}) | "
                   f"{money(best3['oracle3_day'])} |")

    out.append("\n## Does `E/T/I only` hold its out-of-era AUC lead?\n")
    out.append("| test era | `E/T/I only` AUC | best OTHER arm | its AUC | delta | "
               "`E/T/I only` top-3 $/day | best other top-3 $/day |")
    out.append("|---|---|---|---|---|---|---|")
    for seg, test_block in SEGMENTS:
        rows = {r["arm"]: r for r in ladder if r["segment"] == seg}
        eti = rows["E/T/I only"]
        others = [r for a, r in rows.items() if a != "E/T/I only"]
        best = max(others, key=lambda r: r["auc"])
        best_money = max(others, key=lambda r: r["top3_day"])
        label = ("`blind_e3` (control)" if seg == CONTROL_SEGMENT
                 else f"`{test_block}` ({ERA_LABEL[test_block]})")
        out.append(f"| {label} | {number(eti['auc'])} | {best['arm']} | "
                   f"{number(best['auc'])} | "
                   f"{eti['auc'] - best['auc']:+.3f} | "
                   f"{money(eti['top3_day'])} | {money(best_money['top3_day'])} "
                   f"({best_money['arm']}) |")

    out.append(f"\n## Control — label shuffle on segment {SHUFFLE_SEGMENT}\n")
    out.append(f"Training labels permuted ({SHUFFLE_DRAWS} draws), everything else "
               "identical.\n")
    out.append("| arm | shuffled AUC | shuffled top-3 $/day | real AUC | real top-3 $/day |")
    out.append("|---|---|---|---|---|")
    for row in shuffle_rows:
        out.append(f"| {row['arm']} | {number(row['auc_mean'])} +/- "
                   f"{number(row['auc_sd'])} | {money(row['top3_mean'])} +/- "
                   f"{money(row['top3_sd'])} | {number(row['auc_real'])} | "
                   f"{money(row['top3_real'])} |")

    out.append("\n## Controls and walls\n")
    out.append(f"- Sealed zone: `P.SEALED_FROM` = {P.SEALED_FROM}; the harness "
               f"refuses any read at or above it, and the highest session touched "
               f"here is {int(frame['session'].max())}.")
    out.append("- Walk-forward purity: every rung's test block is strictly LATER than "
               "every session in its training window (asserted in code).")
    out.append("- No config, column set, threshold or arm is chosen on a test block; "
               "usable columns come from each segment's own training window.")
    out.append("- Caches: `build_wf_cache.py` extended `sec2` / `sec3` / `sec4` / "
               "`qsec` / `w2cand` from 323 to 793 sessions (125..917) off the "
               "`sheets/roster_*.json` glob, and the causal `fvol` hot/cool cut "
               "table was regenerated to 917 with every pre-existing entry "
               "unchanged (it reads 20 strictly PRIOR sessions).")
    out.append("- `s829` (2025-04-24) is a day-complete roster session with ZERO "
               "confirmed extremes; it carries no candidate rows, so the ladder's "
               "day counts are candidate-bearing days.")
    out.append("- Typed absence: a family with no coverage in a segment's training "
               "window is dropped by `dm.feature_columns` rather than imputed; the "
               "census table above reports per-era coverage for `M_`, `I_` and `T_`.")

    REPORT.write_text("\n".join(out) + "\n")
    print(f"report -> {REPORT}", flush=True)
    print(ladder_frame[["segment", "arm", "auc", "top3_day", "top5_day",
                        "op_lift"]].to_string(index=False))


if __name__ == "__main__":
    main()
