#!/usr/bin/env python3
"""D2 blind entry case drawer (design/D2_BLIND_CASES_PROTOCOL.md, frozen 2026-08-22).

Draws same-(asset, day, phase) winner/loser pairs from the E1R round-0 component
matrix for orchestrator-personal blind calls (D-020). The case file carries ONLY
causal features; outcomes and row identities go to a separate sealed key whose
sha256 is journaled before any case is read.

Selftest: python3 tools/draw_blind_entry_cases.py --selftest  (no real artifacts)
Real:     python3 tools/draw_blind_entry_cases.py --matrix-dir <component_matrix> \
              --out-dir <dir> [--pairs-per-asset 12] [--seed 20260822]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

WINNER_MIN_USD = 600.0
LOSER_MAX_USD = 0.0
VALUE_SCALE_USD = 600.0  # matrix target is asinh(usd/600) — tabular_recovery_contracts.py:28


class BlindDrawRefusal(RuntimeError):
    pass


def _load_matrix_columns(matrix_dir: Path) -> dict[str, np.ndarray]:
    manifest = json.loads((matrix_dir / "manifest.json").read_text())
    names = list(manifest["feature_names"])
    if "phase_index" not in names:
        raise BlindDrawRefusal(
            f"matrix at {matrix_dir} lacks 'phase_index' in feature_names "
            f"(got {len(names)} names)")
    rows = int(manifest["rows"])
    x = np.lib.format.open_memmap(matrix_dir / "x.npy", mode="r")
    if x.shape != (rows, len(names)):
        raise BlindDrawRefusal(
            f"x.npy shape {x.shape} != manifest ({rows}, {len(names)})")
    return {
        "feature_names": names,
        "x": x,
        "phase_col": names.index("phase_index"),
        "day": np.load(matrix_dir / "day.npy"),
        "asset": np.asarray(np.load(matrix_dir / "asset.npy"), str),
        "series_id": np.asarray(np.load(matrix_dir / "series_id.npy"), str),
        "y_usd": np.sinh(np.load(matrix_dir / "current_asinh.npy")) * VALUE_SCALE_USD,
    }


def _series_best(cols: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Best sampled second per series: row index and value."""
    _uniq, inv = np.unique(cols["series_id"], return_inverse=True)
    order = np.lexsort((cols["y_usd"], inv))
    boundaries = np.flatnonzero(np.diff(inv[order])) if len(order) > 1 else np.array([], int)
    last_of_group = np.concatenate([boundaries, [len(order) - 1]]) if len(order) else np.array([], int)
    best_rows = order[last_of_group]
    return {"best_row": best_rows, "best_usd": cols["y_usd"][best_rows]}


def draw_pairs(cols: dict[str, np.ndarray], *, pairs_per_asset: int,
               seed: int) -> list[dict[str, object]]:
    best = _series_best(cols)
    rows, usd = best["best_row"], best["best_usd"]
    phase = np.asarray(cols["x"][rows, cols["phase_col"]], np.float64)
    keys: dict[tuple[str, int, float], dict[str, list[int]]] = {}
    for row, value, ph in zip(rows, usd, phase):
        key = (str(cols["asset"][row]), int(cols["day"][row]), float(ph))
        bucket = keys.setdefault(key, {"win": [], "lose": []})
        if value >= WINNER_MIN_USD:
            bucket["win"].append(int(row))
        elif value <= LOSER_MAX_USD:
            bucket["lose"].append(int(row))
    rng = np.random.default_rng(seed)
    pairs: list[dict[str, object]] = []
    per_asset: dict[str, int] = {}
    eligible = [k for k, b in keys.items() if b["win"] and b["lose"]]
    rng.shuffle(eligible)
    seen_asset_day: set[tuple[str, int]] = set()
    for key in eligible:  # at most one pair per (asset, day): diversity across days
        asset, day, ph = key
        if per_asset.get(asset, 0) >= pairs_per_asset or (asset, day) in seen_asset_day:
            continue
        bucket = keys[key]
        pairs.append({
            "asset": asset, "day": day, "phase": ph,
            "win_row": int(rng.choice(bucket["win"])),
            "lose_row": int(rng.choice(bucket["lose"])),
        })
        per_asset[asset] = per_asset.get(asset, 0) + 1
        seen_asset_day.add((asset, day))
    short = {a: n for a, n in per_asset.items() if n < pairs_per_asset}
    assets = sorted(set(map(str, cols["asset"])))
    for asset in assets:
        if asset not in per_asset:
            short[asset] = 0
    if short:
        raise BlindDrawRefusal(
            f"cannot draw {pairs_per_asset} pairs/asset: eligible (asset,day,phase) "
            f"buckets give only {dict(sorted(per_asset.items()))} (need every asset at "
            f"{pairs_per_asset}); short: {dict(sorted(short.items()))}")
    return pairs


def emit(cols: dict[str, np.ndarray], pairs: list[dict[str, object]], *,
         out_dir: Path, seed: int) -> tuple[Path, Path, str]:
    rng = np.random.default_rng(seed + 1)
    names = cols["feature_names"]
    cases, key_rows = [], []
    for index, pair in enumerate(pairs):
        case_id = f"case_{index:03d}"
        winner_side = "left" if rng.integers(2) == 0 else "right"
        left_row = pair["win_row"] if winner_side == "left" else pair["lose_row"]
        right_row = pair["lose_row"] if winner_side == "left" else pair["win_row"]
        def features(row: int) -> dict[str, float]:
            values = np.asarray(cols["x"][row], np.float64)
            return {n: (None if math.isnan(v) else round(float(v), 6))
                    for n, v in zip(names, values)}
        cases.append({"case_id": case_id, "asset": pair["asset"],
                      "left": features(left_row), "right": features(right_row)})
        key_rows.append({"case_id": case_id, "winner_side": winner_side,
                         "day": pair["day"], "phase": pair["phase"],
                         "win_row": pair["win_row"], "lose_row": pair["lose_row"],
                         "win_usd": round(float(cols["y_usd"][pair["win_row"]]), 2),
                         "lose_best_usd": round(float(cols["y_usd"][pair["lose_row"]]), 2)})
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_path = out_dir / f"cases_seed{seed}.json"
    key_path = out_dir / f"sealed_key_seed{seed}.json"
    cases_path.write_text(json.dumps(
        {"schema": "QRE2BLINDCASES1", "seed": seed, "n_cases": len(cases),
         "protocol": "design/D2_BLIND_CASES_PROTOCOL.md", "cases": cases}, indent=1))
    key_bytes = json.dumps(
        {"schema": "QRE2BLINDKEY1", "seed": seed, "key": key_rows},
        indent=1).encode()
    key_path.write_bytes(key_bytes)
    return cases_path, key_path, hashlib.sha256(key_bytes).hexdigest()


def _synthetic_store(root: Path, *, drop_losers: bool = False) -> Path:
    """Tiny fake matrix: 3 assets x 4 days x 2 phases, 4 series each of 3 rows."""
    rng = np.random.default_rng(7)
    names = ["asset_SI", "asset_HG", "asset_NKD", "side", "phase_index", "f_a", "f_b"]
    rows_asset, rows_day, rows_series, rows_phase, rows_y = [], [], [], [], []
    for asset in ("SI", "HG", "NKD"):
        for day in (20210601, 20210602, 20210603, 20210604):
            for phase in (0.0, 1.0):
                for series in range(4):
                    sid = f"{asset}_{day}_{phase:.0f}_{series}"
                    is_winner = series == 0
                    best = 900.0 if is_winner else (-120.0 if not drop_losers else 700.0)
                    for offset in range(3):
                        rows_asset.append(asset); rows_day.append(day)
                        rows_series.append(sid); rows_phase.append(phase)
                        rows_y.append(best if offset == 1 else best - 55.0)
    n = len(rows_y)
    x = np.zeros((n, len(names)), np.float32)
    x[:, 4] = rows_phase
    x[:, 5] = rng.normal(size=n); x[:, 6] = rng.normal(size=n)
    matrix_dir = root / ("bad_store" if drop_losers else "good_store")
    matrix_dir.mkdir(parents=True)
    np.save(matrix_dir / "x.npy", x)
    np.save(matrix_dir / "day.npy", np.asarray(rows_day, np.int64))
    np.save(matrix_dir / "asset.npy", np.asarray(rows_asset))
    np.save(matrix_dir / "series_id.npy", np.asarray(rows_series))
    np.save(matrix_dir / "current_asinh.npy",
            np.arcsinh(np.asarray(rows_y, np.float64) / VALUE_SCALE_USD))
    (matrix_dir / "manifest.json").write_text(json.dumps(
        {"feature_names": names, "rows": n}))
    return matrix_dir


def selftest() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        cols = _load_matrix_columns(_synthetic_store(root))
        pairs = draw_pairs(cols, pairs_per_asset=3, seed=11)
        assert len(pairs) == 9, f"expected 9 pairs, got {len(pairs)}"
        for pair in pairs:
            win_r, lose_r = pair["win_row"], pair["lose_row"]
            assert cols["asset"][win_r] == cols["asset"][lose_r] == pair["asset"]
            assert cols["day"][win_r] == cols["day"][lose_r] == pair["day"]
            assert float(cols["x"][win_r, cols["phase_col"]]) == float(
                cols["x"][lose_r, cols["phase_col"]]) == pair["phase"]
            assert cols["series_id"][win_r] != cols["series_id"][lose_r]
            assert cols["y_usd"][win_r] >= WINNER_MIN_USD - 1e-6
            assert cols["y_usd"][lose_r] <= LOSER_MAX_USD + 1e-6
        days_used = {(p["asset"], p["day"]) for p in pairs}
        assert len(days_used) == 9, "one pair per (asset, day) violated"
        cases_path, key_path, key_sha = emit(
            cols, pairs, out_dir=root / "out", seed=11)
        cases = json.loads(cases_path.read_text())
        key = {row["case_id"]: row for row in
               json.loads(key_path.read_text())["key"]}
        sides = {key[c["case_id"]]["winner_side"] for c in cases["cases"]}
        assert sides == {"left", "right"}, f"left/right never randomized: {sides}"
        forbidden = ("usd", "y", "row", "day", "winner")
        for case in cases["cases"]:
            leak = [k for k in case if any(f in k.lower() for f in forbidden)]
            assert not leak, f"case leaks outcome-shaped keys: {leak}"
        assert len(key_sha) == 64
        # red fixture: a store with no losers anywhere must REFUSE, not emit cases
        try:
            draw_pairs(_load_matrix_columns(_synthetic_store(root, drop_losers=True)),
                       pairs_per_asset=3, seed=11)
        except BlindDrawRefusal as refusal:
            assert "cannot draw" in str(refusal)
        else:
            raise AssertionError("red fixture accepted: loser-free store drew pairs")
    print("selftest OK: 9 pairs constrained, sides randomized, no outcome leak, "
          "red fixture refused")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--matrix-dir", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--pairs-per-asset", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260822)
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.matrix_dir or not args.out_dir:
        parser.error("--matrix-dir and --out-dir required (or --selftest)")
    cols = _load_matrix_columns(args.matrix_dir)
    pairs = draw_pairs(cols, pairs_per_asset=args.pairs_per_asset, seed=args.seed)
    cases_path, key_path, key_sha = emit(cols, pairs, out_dir=args.out_dir,
                                         seed=args.seed)
    print(f"cases: {cases_path}")
    print(f"sealed key: {key_path}")
    print(f"SEALED KEY SHA256 (journal this BEFORE reading cases): {key_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
