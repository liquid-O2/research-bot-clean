#!/usr/bin/python3
"""PORT M2 — the ERA PRIMER generator (spec §3 "ERA PRIMER page auto-generated
per era from committed censuses", D-071.4, gate P-M2b).

One page per era, the thing S2 of every sheet points at
(`primer=ERA_PRIMER_{ERA}.md`).  It is a READING of committed censuses and
nothing else: every number on the page is (a) copied from, or (b) an explicitly
named aggregate over, rows of a committed TSV, and every line carries its
SOURCE as `path:LINE` (a single row) or `path:L<first>-L<last> n=<rows>` (an
aggregate over a contiguous era slice).  No number is computed from raw data
here — if a figure is not in a census, it does not go on the primer.

CONTENT (spec §3 + D-071.4)
  1 header + block boundary (era_index BLOCKS.tsv)
  2 COST      m0/census_a_cost.tsv          cost_rt, spread, dominance
  3 OFFER     m0/census_b_offer.tsv         range, best leg, $1k legs/session
  4 VOL MIX   m1/fvol/fvol_forecasts.tsv    regime_tag mix, rv5/rv66
  5 PHASE MAP m0/census_c_phase_value.tsv   where the seated value sits
              + m0/census_a_cost.tsv        phase seconds / two-sided seconds
  6 CLASS     m2/class_census.tsv           per-class card (D-071.4)
  7 FAMILY    m1/generation_v3/census_family_value.tsv
  8 DATA      the era's own index counts (era_index INDEX_{ASSET}.tsv)

DETERMINISM: pure function of the committed TSVs; two runs are byte-identical
(the only clock reference is the era definition itself).

Run: /usr/bin/python3 engine/port_m2/era_primer.py E1 E2
"""
import os
import statistics as st
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import era_index as EI                    # noqa: E402
import class_census as CLS                # noqa: E402

SECTION = "§3 ERA PRIMER (P-M2b)"

COST = os.path.join(MC.M0_ROOT, "census_a_cost.tsv")
OFFER = os.path.join(MC.M0_ROOT, "census_b_offer.tsv")
PHASE_VALUE = os.path.join(MC.M0_ROOT, "census_c_phase_value.tsv")
FVOL = os.path.join(MC.M1_ROOT, "fvol", "fvol_forecasts.tsv")
FAM = os.path.join(MC.M1_ROOT, "generation_v3", "census_family_value.tsv")

PARAMS = {
    "spec_section": SECTION,
    "sources": [COST, OFFER, PHASE_VALUE, FVOL, FAM, CLS.OUT],
    "citation": "path:LINE for a single row, path:L<first>-L<last> n=<rows> "
                "for an aggregate over the era's contiguous slice",
    "aggregates": "median for per-session distributions (robust to the roll "
                  "and dying-book outliers the censuses flag), mean only where "
                  "the census column is already a rate",
}


# ------------------------------------------------------------------ reader --
def rows_with_lines(path):
    """[(lineno, dict)] — the line number is the primer's citation unit."""
    out = []
    cols = None
    with open(path) as fh:
        for n, line in enumerate(fh, 1):
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            out.append((n, dict(zip(cols, f))))
    return out


_CACHE = {}


def rows(path):
    if path not in _CACHE:
        _CACHE[path] = rows_with_lines(path)
    return _CACHE[path]


def cite(path, sel):
    """`name:L12-L44 n=33` for a selection, `name:L12` for one row."""
    name = path.replace("/workspace/", "")
    if not sel:
        return "%s:none" % name
    lo = min(n for n, _ in sel)
    hi = max(n for n, _ in sel)
    if lo == hi:
        return "%s:L%d" % (name, lo)
    return "%s:L%d-L%d n=%d" % (name, lo, hi, len(sel))


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _med(vals):
    vals = [v for v in vals if v == v]
    return st.median(vals) if vals else float("nan")


def _n(v, dec=2):
    """MINOR (review 3.1): every numeric cell on this page was formatted with a
    bare `%.2f` / `%.0f`, so a census slice with no rows (or a typed-missing
    column) wrote the literal string `nan` into a COMMITTED markdown table — a
    reader-facing artefact whose whole contract is "every figure carries its
    source".  A missing figure is now the program's single typed-missing glyph
    (`m2_common.NA`), which is what the sheets themselves print."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return MC.NA
    if v != v or v in (float("inf"), float("-inf")):
        return MC.NA
    return "%.*f" % (int(dec), v)


def in_era(sel, era, date_key="trade_date"):
    lo, hi = EI.era_bounds(era)
    out = []
    for n, d in sel:
        ds = d.get(date_key, "")
        if len(ds) != 10:
            continue
        d8 = int(ds[0:4]) * 10000 + int(ds[5:7]) * 100 + int(ds[8:10])
        if lo <= d8 <= hi:
            out.append((n, d))
    return out


# ------------------------------------------------------------------ writer --
def primer(era, assets=MC.ASSET_ORDER):
    lo, hi = EI.era_bounds(era)
    bdate, _union = EI.boundary_date(era, assets)
    L = ["# ERA PRIMER — %s (%d..%d)" % (era, lo, hi), "",
         "Auto-generated from COMMITTED CENSUSES by engine/port_m2/era_primer.py "
         "(spec §3).", "Every figure carries its source as `file:line`. "
         "sheets_version=%s  spec_sha16=%s" % (MC.SHEETS_VERSION, MC.SPEC_SHA16),
         "STUDY/BLIND boundary date (day-complete, D-058/D-036): **%s** — "
         "sessions <= boundary are STUDY." % bdate, ""]

    # ---- 1 volume -----------------------------------------------------------
    L += ["## 1. THE ERA'S MATERIAL", "",
          "| asset | sessions | candidates | STUDY sess | STUDY cand | "
          "BLIND sess | BLIND cand | source |",
          "|---|---|---|---|---|---|---|---|"]
    for asset in assets:
        idx = EI.load_index(era, asset)
        el = [r for r in idx if r["eligible"] == "1"]
        stu = [r for r in el if r["block"] == EI.BLOCK_STUDY]
        bli = [r for r in el if r["block"] == EI.BLOCK_BLIND]
        src = "artifacts/cache/port/m2/era/%s/INDEX_%s.tsv" % (era, asset)
        L.append("| %s | %d | %d | %d | %d | %d | %d | %s n=%d |"
                 % (asset, len({r["date8"] for r in el}), len(el),
                    len({r["date8"] for r in stu}), len(stu),
                    len({r["date8"] for r in bli}), len(bli), src, len(idx)))
    L.append("")

    # ---- 2 cost -------------------------------------------------------------
    L += ["## 2. COST (m0 census A)", "",
          "Session round-trip cost is the entry bar's denominator: a $1,000 "
          "trade is a $1,000 trade AFTER this.", "",
          "| asset | cost_rt median $ | spread_med $ | spread_p90 $ | "
          "dominance median | source |", "|---|---|---|---|---|---|"]
    for asset in assets:
        sel = [(n, d) for n, d in in_era(rows(COST), era)
               if d["asset"] == asset and d["phase"] == "ALL"]
        if not sel:
            sel = [(n, d) for n, d in in_era(rows(COST), era)
                   if d["asset"] == asset]
        L.append("| %s | %s | %s | %s | %s | %s |"
                 % (asset, _n(_med([_f(d["cost_rt"]) for _, d in sel]), 2),
                    _n(_med([_f(d["spread_med_usd"]) for _, d in sel]), 2),
                    _n(_med([_f(d["spread_p90_usd"]) for _, d in sel]), 2),
                    _n(_med([_f(d["dominant_share"]) for _, d in sel]), 4),
                    cite(COST, sel)))
    L.append("")

    # ---- 3 offer ------------------------------------------------------------
    L += ["## 3. OFFER (m0 census B, SESSION/FULL convention)", "",
          "| asset | range median $ | best_leg median $ | legs_1k mean/session "
          "| sessions | source |", "|---|---|---|---|---|---|"]
    for asset in assets:
        sel = [(n, d) for n, d in in_era(rows(OFFER), era)
               if d["asset"] == asset and d.get("convention") == "SESSION"
               and d.get("window") == "FULL"]
        legs = [_f(d["legs_1k"]) for _, d in sel]
        L.append("| %s | %s | %s | %s | %d | %s |"
                 % (asset, _n(_med([_f(d["range_usd"]) for _, d in sel]), 0),
                    _n(_med([_f(d["best_leg_usd"]) for _, d in sel]), 0),
                    _n((sum(legs) / len(legs)) if legs else float("nan"), 2),
                    len(sel), cite(OFFER, sel)))
    L.append("")

    # ---- 4 vol regime -------------------------------------------------------
    L += ["## 4. VOL-REGIME MIX (m1 fvol, SESSION segment)", "",
          "The regime tag every sheet's S2 shows, counted over the era.", "",
          "| asset | regime mix (n sessions) | rv5/rv66 median | "
          "sigma_hat median $ | source |", "|---|---|---|---|---|"]
    for asset in assets:
        sel = [(n, d) for n, d in in_era(rows(FVOL), era)
               if d["asset"] == asset and d.get("segment") == "SESSION"]
        mix = {}
        for _, d in sel:
            mix[d.get("regime_tag", ".")] = mix.get(d.get("regime_tag", "."),
                                                    0) + 1
        L.append("| %s | %s | %s | %s | %s |"
                 % (asset,
                    " ".join("%s=%d" % kv for kv in sorted(mix.items()))
                    or MC.NA,
                    _n(_med([_f(d.get("rv5_over_rv66")) for _, d in sel]), 3),
                    _n(_med([_f(d.get("sigma_hat_usd")) for _, d in sel]), 1),
                    cite(FVOL, sel)))
    L.append("")

    # ---- 5 phase map --------------------------------------------------------
    L += ["## 5. PHASE MAP", "",
          "Where the seated value sits (census C, by calendar year — the "
          "census's own era vocabulary) and what each phase costs (census A).",
          "", "| asset | phase | seated value share | cost_rt median $ | "
          "two-sided seconds median | sources |", "|---|---|---|---|---|---|"]
    years = sorted({str(y) for y in (lo // 10000, hi // 10000)})
    for asset in assets:
        for ph in MC.PHASE_NAMES:
            pv = [(n, d) for n, d in rows(PHASE_VALUE)
                  if d["asset"] == asset and d["phase"] == ph
                  and d["era"] in years]
            ca = [(n, d) for n, d in in_era(rows(COST), era)
                  if d["asset"] == asset and d["phase"] == ph]
            if not pv and not ca:
                continue
            L.append("| %s | %s | %s | %s | %s | %s ; %s |"
                     % (asset, ph,
                        " ".join("%s=%s" % (d["era"], _n(d["share"], 3))
                                 for _, d in pv) or MC.NA,
                        _n(_med([_f(d["cost_rt"]) for _, d in ca]), 2),
                        _n(_med([_f(d["two_sided_seconds"]) for _, d in ca]), 0),
                        cite(PHASE_VALUE, pv), cite(COST, ca)))
    L.append("")

    # ---- 6 class cards (D-071.4) -------------------------------------------
    L += ["## 6. CANDIDATE-CLASS CARDS (D-071.4)", "",
          "The class every sheet declares in S1, with its census card FOR THIS "
          "ERA.  `fires/sess` is the class's fire rate; `cond_value$` is the "
          "CC-M1-7.3 conditional value (mean walled phase-close certificate "
          "over positive candidates); `win_frac` is the D-021 winner share "
          "(>= $1,000 with MAE <= $300, never walled).", "",
          "| asset | class | n_cand | fires/sess | cond_value $ | pos_frac | "
          "win_frac | cond_peak $ | source |",
          "|---|---|---|---|---|---|---|---|---|"]
    cc = rows(CLS.OUT)
    for asset in assets:
        for cls in list(MC.CLASS_ORDER) + ["ALL_CLASSES"]:
            sel = [(n, d) for n, d in cc
                   if d["asset"] == asset and d["class"] == cls
                   and d["era"] == era]
            if not sel:
                continue
            n, d = sel[0]
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                     % (asset, cls, d["n_candidates"],
                        _n(d["fires_per_session"], 2),
                        _n(d["conditional_value_usd"], 2),
                        _n(d["positive_frac"], 4),
                        _n(d["winner_frac"], 4),
                        _n(d["conditional_value_peak_usd"], 2),
                        cite(CLS.OUT, sel)))
    L.append("")

    # ---- 7 family cards -----------------------------------------------------
    L += ["## 7. FAMILY CARDS (m1 generation_v3 census, calendar-year rows)",
          "", "| asset | family | era | n_cand | cond_value $ | pos_frac | "
          "cond_peak $ | source |", "|---|---|---|---|---|---|---|---|"]
    fam = rows(FAM)
    for asset in assets:
        for f in MC.FAMILIES:
            sel = [(n, d) for n, d in fam
                   if d["asset"] == asset and d["family"] == f
                   and d["era"] in years]
            for n, d in sel:
                L.append("| %s | %s | %s | %s | %s | %s | %s | %s |"
                         % (asset, f, d["era"], d["n_candidates"],
                            _n(d["conditional_value_usd"], 2),
                            _n(d["positive_frac"], 4),
                            _n(d["conditional_value_peak_usd"], 2),
                            cite(FAM, [(n, d)])))
    L.append("")
    L += ["## 8. HOW TO READ THIS PAGE", "",
          "* It is a PRIOR, not a rule (D-068.2 duty to contradict): the tape "
          "is the data and overturning a primer item is the most valuable "
          "output of a study block.",
          "* Class cards are POPULATION quality, never trade targets — the "
          "$1,000+/trade bar (D-021) applies to SELECTED trades (D-062).",
          "* Era-learned patterns are ERA-TAGGED HYPOTHESES (D-059.1); each "
          "new era opens with the library re-test before new discovery.", ""]
    return "\n".join(L) + "\n"


def build(eras, assets=MC.ASSET_ORDER):
    MC.verify_spec(force=True)
    out = []
    for era in eras:
        text = primer(era, assets)
        p = os.path.join(EI.era_dir(era), "ERA_PRIMER_%s.md" % era)
        MC.write_text(p, text)
        MC.hb("era_primer %s: %d lines -> %s" % (era, text.count("\n"), p))
        out.append(p)
    MC.write_json(MC.out_path("era", "era_primer.receipt.json"),
                  {"env": MC.env_receipt(PARAMS), "pages": out})
    return out


def main():
    eras = [a for a in sys.argv[1:] if not a.startswith("-")] or ["E1", "E2"]
    build(eras)
    return 0


if __name__ == "__main__":
    sys.exit(main())
