#!/usr/bin/python3
"""PORT M2 — TRIAGE INDEX (CC-M2-3 day-complete triage mechanics).

A day-complete STUDY day is ~1,000 candidates; the reader cannot deep-read
1,000 sheets.  This extractor turns every BLIND sheet of a (asset, date8) into
ONE mechanical line carrying the fields the E1 pattern ledger actually reads,
so triage is a scan over a table and deep reads are spent where the table says
something is there.

STRICTLY BLIND: this module reads `*.BLIND.sheet.txt` and REFUSES to open any
`*.S14.appendix.txt` (the refusal is an exception, not a filter).

VERSIONS (the stamp is written into every index it produces, so a table can
always be attributed to the extractor that built it — the D8 defect was found
only because someone re-derived a column by hand):
  TRIAGE-INDEX-V1  E1-STUDY-D1/D2 as built.
  TRIAGE-INDEX-V2  CC-M2-10.6 defects D9 + D10:
    * D9 REGIME COLUMNS.  S2's `day_type_so_far` and its `% of range_hat`, and
      S9's `surprise`, are the fields E1_POSTMORTEMS §3 shows are needed to
      make the capacity term regime-conditional.  They are parsed by EXPLICIT
      COLUMN NAME — every regime regex anchors on the printed label AND on the
      label of the neighbouring cell, so a sheet whose S2/S9 row gains or loses
      a column yields NOTHING rather than the wrong number (the D8 lesson: the
      V1 extractor took a POSITIONAL column and called it `slope5m` when it was
      the 1-minute slope).  The V1 names `day_type`/`pct_range_hat` are renamed
      to `day_type_so_far`/`range_vs_hat_pct` to match the sheet's own labels.
    * D10 `sflow_30m` (+ n/vol): the S8 window-nesting read (60s vs 5m vs 30m
      vs phase) made mechanical, so the horizon DISAGREEMENT that P022 names is
      visible in the table instead of only in a deep read.
  TRIAGE-INDEX-V3  CC-M2-12 items 1-2 + defects D13/D14/D15:
    * D13 (docstring/code/stamp agreement).  The V2 renames and the version
      header ARE in this file and this docstring no longer claims anything the
      code does not do; what the D13 note actually caught is that the indices
      the E1 D1-D3 rounds READ (E1D{1,2,3}_TRIAGE_INDEX.tsv) were built by the
      V1 extractor, carry the V1 column names and NO stamp, and sit in the same
      directory as the stamped V2 rebuilds (`*_V2R.tsv`).  Every index this
      build writes carries `extractor_version` + `columns_sha16`, and an index
      without that second header line is by definition pre-V2 and must not be
      attributed to this extractor.
    * D14 AS-OF PREFIX VIEW (`--as-of SEC`), the BLIND-GATING mechanic.  A
      day-complete index shows every row of the day, and a row's `mid` is the
      price at ITS decision second — so scanning the table at 03:00 shows the
      price path of 19:00.  CC-M2-12.1(a) makes the prefix view MANDATORY
      before any blind round: `--as-of SEC` emits ONLY rows with `sec <= SEC`
      and MASKS every field that is not knowable at SEC, and refuses to write
      a view that violates either law (`verify_as_of`, which the red-first
      test drives with a leaked later row).
      `--drive-step` / `--drive-out` are the chronological DAY DRIVER: the
      index revealed incrementally, one stamped prefix per cut, with a
      manifest — the mechanic every future round uses instead of one
      day-complete table.
    * D15 SHORT DAY (`short_day`, `observed_close`, `runway_observed`), read
      from the m0 session receipt (PORT_M0_CENSUS_SPEC §5 meta: `short_day`,
      `last_two_sided_sec`).  On 2021-07-05 the HG tape ends at 71,354s while
      every runway on every sheet is computed to the nominal 82,799s, so the
      index-level fix is `runway_observed = min(runway_phase, observed_close -
      sec)`.  These three columns are an END-OF-SESSION FACT (the repo has no
      early-close calendar; M0 §5 derives the flag from the observed span), so
      under `--as-of` they are MASKED until the observed close has passed —
      a reader at 03:00 cannot know when the tape will stop.  The S3 runway
      fix inside the rendered sheets is a separate V1.2 render-bundle item.
    * D16 THE INDEX HEADER IS A VERSIONED API, and frozen consumers get a
      PINNED READER.  The V2 stamp added a SECOND comment line and renamed two
      columns; `e1d1_policy.py`, `e1d2_policy.py` and `baseline_replay.py` all
      parse with `readlines()[1:]` and read the V1 names, so they broke (day 4
      ran them against a hand-built COMPAT file).  Frozen code must not be
      edited, so the FIX LIVES HERE, in two halves:
        - `read_index(path)` is the canonical reader for NEW consumers: it
          skips EVERY `#` line however many there are, returns the header
          stamps separately, and populates BOTH spellings of every renamed
          column, so no future header or rename can break a caller.
        - the COMPAT VIEW is written automatically beside every index (
          `<stem>_COMPAT.tsv`, suppress with `--no-compat`): exactly ONE
          comment line and both column spellings, i.e. the V1 API pinned
          forever.  A frozen consumer points at the compat file and never
          changes again.
      THE CONTRACT, stated so it can be checked: line 1 = the human title;
      lines 2..k = `#` machine stamps (version, columns_sha16, AS_OF); the
      first non-`#` line is the header row; column names are ADDITIVE and any
      rename keeps its old spelling in the compat view.
    * D17 S10 DEVELOPING VALUE AREA (`dev_poc`, `dev_vah`, `dev_val`,
      `d_POC`, `d_VAH`, `d_VAL`, `in_VA`).  S10 priced the magnitude on two
      separate days (day 3's give-back, day 4's seats) and there was no way to
      triage on it.  `d_POC` is parsed from the sheet; `d_VAH`/`d_VAL` are
      derived from the printed prices and `mult` in the sheet's OWN signed
      convention, (mid - level) x mult, positive when the level is BELOW the
      entry mid.
    * CC-M2-14.2a THE LEADING REGIME STATE joins the index (`rf_anchor`,
      `rf_anchor_ts`, `predicted_day_type_prob`, `range_hat_vs_trailing`,
      `menu_hat`), read from the accepted forecaster's
      artifacts/cache/port/m2/regime_forecast/forecast_{ASSET}.tsv keyed
      (asset, trade_date, anchor).  THE JOIN IS STRICTLY PRIOR: the anchor
      selected is the NEWEST one whose `anchor_ts` is strictly LESS than the
      row's `decision_ts` (the sheet's own S12 epoch second, also emitted as
      `dec_ts` so the join can be audited).  An anchor stamped AT the decision
      second is a same-second read and is refused — test t16 drives that
      mutant.  CAVEAT CARRIED FROM CC-M2-14.1: `menu_hat` is RANK-VALID
      everywhere but LEVEL-INVALID on SI — rank it, never read its level.
  TRIAGE-INDEX-V4  the D-001 fix pass (M2_CONSOLIDATED_REVIEW R03/R06/R07/R08/
    R09/R16/R27/R28/R45/R47/R48).  Every item below was queued for the V1.2
    render bundle that never landed, so it lands here, where the table the
    consumers actually read is built:
    * R03 PRINT PRECISION.  `_fmt` emitted `%.4g`, which renders every NKD
      price as `2.935e+04` — three consecutive rows with genuinely different
      decision mids print identically, and a consumer recomputing a distance
      from index prices is wrong by up to $25/mini.  Floats now print at
      `%.10g` (round-trip on every quantity this table carries: prices,
      ratios, dollars, derived roundings).  Mechanical; no re-render.
    * R06 THE REFUSED-CLAUSE LAW (CC-M2-20.3), swept.  Every derived flag was
      `int(bool(x is not None and cond))`, which emits 0 — the SAME TOKEN as a
      genuine negative — when the input is refused.  Measured consequence on
      the record: `unspent_bind` present on 304/304 HG and 0/327 SI rows, i.e.
      the capacity family was an ASSET SELECTOR in disguise and no consumer
      could tell.  Flags are now THREE-VALUED (1 / 0 / `R` = MC.REFUSED_TOKEN)
      and combine under KLEENE logic (`_kand`/`_kor`), so a decidable clause
      still decides and an undecidable one refuses.  `seat_score` — a RANKING,
      where a skipped penalty scores the row HIGHER — is REFUSED outright
      below a DECLARED minimum of present terms (SEAT_MIN_TERMS, and no
      penalty term may be refused at all), never partially summed.  The
      per-row `n_refused_inputs` and `seat_terms_present` counts are columns.
    * R07 `pct_unspent_phase` HELD DOLLARS.  Renamed `unspent_phase_usd`; the
      old spelling is a compat ALIAS (D16), so every frozen consumer keeps
      reading it.  The arithmetic was always coherent (P002 compares it to
      450.0 DOLLARS); the NAME was the defect, which is the D8 class.
    * R08 THE `~` ORDINAL MARKER IS NO LONGER DISCARDED.  Spec §1 S5: "a z
      whose scale came from the floor is suffixed '~' and is ORDINAL ONLY,
      never a threshold."  `_f()` stripped the suffix and `P004` then applied
      a hard threshold to exactly those values.  `_fmark()` returns
      (value, floored); the index carries `trades_min_z_floored` and
      `trades_min_n_ref`; P004's z term REFUSES on a floored z.  The V1.2
      PERCENTILE-Z form CC-M2-7.3 deferred also lands, as
      `trades_min_z_pctile`: the percentile rank of NOW within the SAME
      trailing same-half-hour reference sample the sheet's z is taken over
      (sections.clock_norm's sample, strictly prior sessions), mid-rank
      convention, REFUSED below the same 10-session floor.  An ordinal
      quantity, expressed ordinally.
    * R16 `field_asof_sec` IS A REAL PER-COLUMN TABLE.  It used to return the
      row's own `sec` for every column but three, making `verify_as_of`
      tautological for a row's own fields.  `ASOF_RULES` now partitions EVERY
      column into a named knowability rule, the partition is ASSERTED total at
      import (a new column with no declared rule is a refusal, not a silent
      "knowable now"), the forecast-anchor block resolves to its ANCHOR
      second, and an observed-close column with no observed close is MASKED
      rather than blessed.
    * R09 `--drive-per-row`: one prefix per DISTINCT DECISION SECOND, the
      `--next` semantics `e1d4_asof.py:120-132` already drives.  The blind
      round ran at `--drive-step 1800`, so a prefix carried up to 1,799
      seconds of LATER rows whose `mid` is the post-decision price path — the
      D14 SCAN-EXPOSED leak CC-M2-12.1 made blocking before any blind round.
    * R28 ROSTER COUNT GUARD (D30's root cause).  `main()` indexed whatever
      `.BLIND.sheet.txt` files happened to be on disk; blind day 7 sealed
      1,109 of 1,117 rows because of it, and the shell-level patch was skipped
      whenever the background render's pid file was missing.  The sheet count
      is now compared against `assemble.roster(asset)` for that date8 and
      REFUSES on any mismatch (`--allow-roster-mismatch` is the explicit,
      stamped opt-out).
    * R27 the compat view carries `AS_OF` when its source was a prefix, and
      R47 its header no longer claims "V1 column spellings" while emitting the
      current column list plus the aliases.
    * R48 `day_driver` REFUSES an empty cut range instead of raising
      IndexError off `cuts[-1]`.
    * R45 `side` is an EXACT token cross-checked against the cid; an unknown
      token REFUSES instead of silently mapping to SHORT.

Run:
  triage_index.py --era E1 --block STUDY \
                  --sessions HG:20210701,SI:20210701 \
                  --out artifacts/cache/port/m2/triage/E1D1_TRIAGE_INDEX.tsv
  triage_index.py ... --out IDX.tsv --as-of 43200          # prefix view
  triage_index.py ... --out IDX.tsv --drive-per-row \
                  --drive-out artifacts/cache/port/m2/triage/E1BLIND_D1_DRIVE
  (a stepped drive is still available — `--drive-step 60`; anything coarser
   than 60s is REFUSED unless `--allow-coarse-step` declares it, because each
   prefix then carries up to step-1 seconds of post-decision rows.)
"""
import argparse
import hashlib
import json
import os
import re
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402

ROOT = "/workspace/artifacts/cache/port/m2/era"
# PORT_M0_CENSUS_SPEC §5 session receipts — the ONLY thing read from outside
# the BLIND sheet tree, and only for its calendar meta (short_day, observed
# close).  Never the tape, never a certificate.
M0_SESSIONS = "/workspace/artifacts/cache/port/m0/sessions"
NA = "."
VERSION = "TRIAGE-INDEX-V4"
REFUSED = MC.REFUSED_TOKEN               # "R" — CC-M2-20.3, a VALUE not a gap

COLUMNS = (
    "cid asset date8 side sec clock phase_dec cls driver_family "
    "vol_regime rv5_rv66 day_type_so_far range_so_far range_vs_hat_pct "
    "cov_phase unspent_phase_usd cov_sess unspent_sess "
    "runway_phase runway_sess exit_is_sess short_day observed_close "
    "runway_observed fvol_source "
    "phase_H phase_H_sec phase_L phase_L_sec extreme_age_trade_side "
    "n_pivots n_in_band n_near100 near_fam near_d n_conf_max conf_d "
    "min_tc_near or_state "
    "trades_min trades_min_z trades_min_z_floored trades_min_n_ref "
    "trades_min_z_pctile slope15m slope5m slope1m accel spread_now "
    "l1_bid_sz l1_ask_sz spread_dec cost_rt rev_s_60 c2f_60 c2f_300 "
    "n_ev_60 n_ev_300 n_trades_300 dBsz_min dAsz_min refill_frac "
    "f60_n f60_vol f60_sflow f5m_n f5m_vol f5m_sflow "
    "f30m_n f30m_vol f30m_sflow fph_sflow fph_vol "
    "sched_last_age sched_next_in "
    "trapped_above trapped_below phase_total thru_n thru_bid thru_ask "
    "rv60 rv300 rv900 rv1800 rv_collapse jump_frac vol_of_vol "
    "q10 q50 ladder_pos surprise ev_ratio "
    "dev_poc dev_vah dev_val d_POC d_VAH d_VAL in_VA "
    "dec_ts rf_anchor rf_anchor_ts predicted_day_type_prob "
    "range_hat_vs_trailing menu_hat "
    "mid mult room_phase ext_needed unspent_bind "
    "P001 P002 P003 P004 P005 P013 P014 seat_score "
    "n_refused_inputs seat_terms_present"
).split()


def columns_sha16():
    """The VERSION STAMP's second half: the exact column list this build emits.

    A table's header can be read back and checked against the extractor that
    claims to have produced it — the D8 defect (a column that was not what its
    name said) survived a whole round because nothing pinned the schema.
    """
    h = hashlib.sha256(("%s\n%s" % (VERSION, "\t".join(COLUMNS))).encode())
    return h.hexdigest()[:16]


# ------------------------------------------------------- D15 session calendar
# Columns whose value is an END-OF-SESSION fact rather than a decision-second
# fact.  They are emitted in the day-complete index (CC-M2-12.2 orders them
# NOW) and MASKED by the as-of view until the observed close has passed.
OBSERVED_COLS = ("short_day", "observed_close", "runway_observed")

# D-057 SCHEDULE_EXEMPT: release DATES are published months ahead, so the
# forward offset to the next scheduled release is lawful at any as-of.
ASOF_EXEMPT = ("sched_next_in",)

# CC-M2-14.2a: the leading regime block is knowable at its ANCHOR second, which
# is STRICTLY EARLIER than the row's own decision second (regime_at enforces
# that).  Under `--as-of` these are the only columns whose knowability second is
# not the row's own, in the EARLIER direction.
FORECAST_COLS = ("rf_anchor", "rf_anchor_ts", "predicted_day_type_prob",
                 "range_hat_vs_trailing", "menu_hat")

# R16 — THE PER-COLUMN KNOWABILITY TABLE.  `field_asof_sec` used to answer
# "the row's own decision second" for every column but three, which made
# `verify_as_of`'s per-field loop a tautology for every row that had already
# survived the `sec <= as_of` filter.  Every column now carries a NAMED rule
# and the partition is asserted TOTAL at import, so a column added without a
# declared knowability rule is a refusal rather than a silent "knowable now".
ASOF_RULE_DECISION = "decision_second"    # computed at the row's own second
ASOF_RULE_CLOSE = "session_close"         # D15 end-of-session facts
ASOF_RULE_EXEMPT = "schedule_exempt"      # D-057 SCHEDULE_EXEMPT
ASOF_RULE_ANCHOR = "forecast_anchor"      # CC-M2-14.2a leading regime state

# A knowability second that no as-of can reach: used when a column's own
# knowability second cannot be established (e.g. an observed-close column on a
# session with no m0 receipt).  Masking is the refusing direction; the previous
# `return None` blessed the value at every as-of.
KNOW_NEVER = 1 << 62

_META = {}

# ------------------------------------------- CC-M2-14.2a leading regime state
# The accepted forward-offer / regime forecaster (CC-M2-14.1).  One row per
# (session, anchor); every prediction is strictly prior to its own anchor_ts,
# and the JOIN below is strictly prior to the DECISION second on top of that.
REGIME_DIR = "/workspace/artifacts/cache/port/m2/regime_forecast"
REGIME_FIELDS = (("predicted_day_type_prob", "p_expansion"),
                 ("range_hat_vs_trailing", "range_hat_vs_trailing"),
                 ("menu_hat", "menu_hat"))
_FCAST = {}


def forecast_rows(asset):
    """[(anchor_ts, anchor, {field: value})] for one asset, ascending."""
    if asset in _FCAST:
        return _FCAST[asset]
    import csv
    p = os.path.join(REGIME_DIR, "forecast_%s.tsv" % asset)
    out = {}
    if os.path.exists(p):
        with open(p) as fh:
            rd = csv.DictReader((ln for ln in fh if not ln.startswith("#")),
                                delimiter="\t")
            for r in rd:
                key = r["trade_date"].replace("-", "")
                out.setdefault(key, []).append(
                    (int(r["anchor_ts"]), r["anchor"],
                     {c: _f(r.get(src)) for c, src in REGIME_FIELDS}))
        for k in out:
            out[k].sort(key=lambda x: x[0])
    _FCAST[asset] = out
    return out


def regime_at(asset, date8, dec_ts):
    """The NEWEST forecast anchor STRICTLY BEFORE `dec_ts`.

    Strictly: an anchor stamped AT the decision second is a same-second read
    and must not be joined (CC-M2-1.2's availability law, restated for this
    join by CC-M2-14.2a).
    """
    rows = forecast_rows(asset).get(str(date8), [])
    best = None
    for ats, anchor, vals in rows:
        if ats < dec_ts:
            best = (ats, anchor, vals)
        else:
            break
    return best


# ------------------------------------------ R08 / CC-M2-7.3 the PERCENTILE-Z
# CC-M2-7.3 accepted the `~` marker for V1.1 and deferred the PERCENTILE-RANK
# form to V1.2 with the render bundle that never landed.  It lands here.  The
# reference sample is EXACTLY the one the sheet's own z is taken over —
# sections.clock_norm's trailing-CLOCKNORM_SESSIONS same-half-hour cell, over
# STRICTLY PRIOR sessions (bisect_left on the session's own d8), so the column
# is causal by construction and needs no as-of exception.  Mid-rank convention,
# so ties do not manufacture an extreme.  Below the same 10-session floor
# clock_norm uses, the percentile is REFUSED and the refusal is counted.
CLOCK_PCTILE_FIELD = "trades_per_min"
CLOCK_MIN_REF = 10
PCTILE_REFUSALS = {}
_CLOCK_REF = {}


def clock_reference(asset, date8, bin_idx):
    """The trailing same-half-hour sample for (asset, session, bin), or []."""
    key = (str(asset), int(date8), int(bin_idx))
    if key in _CLOCK_REF:
        return _CLOCK_REF[key]
    import bisect
    import assemble as A                  # noqa: E402 — lazy: tape-side deps
    import sections as SEC                # noqa: E402
    vals = []
    try:
        ds = sorted(A.session_index(asset))
        i = bisect.bisect_left(ds, int(date8))
        for p in ds[max(0, i - SEC.CLOCKNORM_SESSIONS):i]:
            st = SEC._session_bin_stats(asset, p)
            if st and int(bin_idx) in st:
                vals.append(float(st[int(bin_idx)][CLOCK_PCTILE_FIELD]))
    except (OSError, RuntimeError, KeyError, ValueError) as e:
        PCTILE_REFUSALS[type(e).__name__] = (
            PCTILE_REFUSALS.get(type(e).__name__, 0) + 1)
        vals = []
    _CLOCK_REF[key] = vals
    return vals


def clock_pctile(asset, date8, dec_ts, x):
    """Percentile rank (0..100) of `x` in the trailing same-half-hour cell."""
    if x is None or dec_ts is None:
        PCTILE_REFUSALS["no_value"] = PCTILE_REFUSALS.get("no_value", 0) + 1
        return None
    import sections as SEC                # noqa: E402
    vals = clock_reference(asset, date8,
                           (int(dec_ts) % 86400) // SEC.BIN_SECONDS)
    if len(vals) < CLOCK_MIN_REF:
        PCTILE_REFUSALS["thin_reference"] = (
            PCTILE_REFUSALS.get("thin_reference", 0) + 1)
        return None
    lo = sum(1 for v in vals if v < x)
    eq = sum(1 for v in vals if v == x)
    return round(100.0 * (lo + 0.5 * eq) / len(vals), 3)


def session_meta(asset, date8):
    """(short_day, observed_close_sec) from the m0 session receipt; (None,
    None) when the receipt is absent."""
    key = (asset, str(date8))
    if key in _META:
        return _META[key]
    p = os.path.join(M0_SESSIONS, str(asset), "%s.npz" % date8)
    out = (None, None)
    if os.path.exists(p):
        z = np.load(p, allow_pickle=False)
        try:
            m = json.loads(str(z["meta_json"]))
            out = (int(bool(m.get("short_day", False))),
                   int(m.get("last_two_sided_sec", -1)))
        finally:
            z.close()
    _META[key] = out
    return out


def _fmark(x):
    """(value, floored) — the `~` ORDINAL MARKER, kept.

    Spec §1 S5, verbatim: "a z whose scale came from the floor is suffixed '~'
    and is ORDINAL ONLY, never a threshold."  R08: `_f` discarded the suffix
    one layer below the rule, so the index could not express which z values
    were floor-scaled and `P004` — the E1 round's only unbroken refusal, frozen
    into the blind policy as T1 — applied a hard threshold to exactly those.
    """
    s = str(x)
    floored = s.rstrip().endswith("~")
    try:
        return (float(s.replace("$", "").replace(",", "").rstrip("~")),
                1 if floored else 0)
    except Exception:
        return (None, None)


def _f(x):
    return _fmark(x)[0]


def _hms(s):
    try:
        h, m, sec = s.split(":")
        return int(h) * 3600 + int(m) * 60 + int(sec)
    except Exception:
        return None


def _fmt(v):
    """R03 (D18).  `%.4g` destroyed NKD price resolution: every NKD mid, phase
    extreme and developing-value price rendered as `2.935e+04`, so three
    consecutive rows with genuinely different decision mids printed identically
    (NKD's 10-point grid = 2 ticks = $50/mini) and any consumer recomputing a
    distance from index prices was wrong by up to $25/mini.  `%.10g` round-trips
    every quantity this table carries and is byte-identical run to run.
    """
    if v is None:
        return NA
    if isinstance(v, float):
        return ("%.10g" % v)
    return str(v)


def _search(pat, text, grp=1, cast=str):
    m = re.search(pat, text)
    if not m:
        return None
    try:
        return cast(m.group(grp))
    except Exception:
        return None


def parse_sheet(path):
    if path.endswith(".S14.appendix.txt"):
        raise RuntimeError("BLIND REFUSAL: triage_index may never open S14 (%s)"
                           % path)
    with open(path) as fh:
        text = fh.read()
    r = {c: None for c in COLUMNS}

    # ---- S1 -------------------------------------------------------------
    r["cid"] = _search(r"cid\s+(\S+)", text)
    m = re.search(r"asset/session (\S+)\s+(\d{4}-\d{2}-\d{2}).*?phase_dec=(\S+)",
                  text)
    if m:
        r["asset"], r["date8"] = m.group(1), m.group(2).replace("-", "")
        r["phase_dec"] = m.group(3)
    m = re.search(r"decision sec=(\d\d:\d\d:\d\d)\s+\((\d+)\)", text)
    if m:
        r["clock"], r["sec"] = m.group(1), int(m.group(2))
    r["side"] = _search(r"\n  side (\S+)", text)
    m = re.search(r"CANDIDATE CLASS (\S+)\s+driver_family=(\S+)", text)
    if m:
        r["cls"], r["driver_family"] = m.group(1), m.group(2)

    # ---- S2 -------------------------------------------------------------
    m = re.search(r"vol_regime (\S+)\s+rv5/rv66=(\S+)", text)
    if m:
        r["vol_regime"], r["rv5_rv66"] = m.group(1), _f(m.group(2))
    # D9 REGIME COLUMNS, parsed by EXPLICIT COLUMN NAME: the pattern names
    # `day_type_so_far`, `range_so_far=$` AND the trailing `% of range_hat`
    # label, so it cannot slide onto a neighbouring cell the way the D8
    # positional slope read did.  A REFUSED day_type prints the typed-missing
    # glyph on the sheet, which _f() turns into None — never 0.
    m = re.search(r"day_type_so_far\s+(\S+)\s+range_so_far=\$(\S+)\s+"
                  r"=\s*(\S+)% of range_hat", text)
    if m:
        r["day_type_so_far"] = m.group(1)
        r["range_so_far"] = _f(m.group(2))
        r["range_vs_hat_pct"] = _f(m.group(3))

    # ---- S3 -------------------------------------------------------------
    m = re.search(r"\n  phase (\S+)\s+open=\S+\s+H=(\S+)@(\d\d:\d\d:\d\d)\s+"
                  r"L=(\S+)@(\d\d:\d\d:\d\d)", text)
    if m:
        r["phase_H"], r["phase_H_sec"] = _f(m.group(2)), _hms(m.group(3))
        r["phase_L"], r["phase_L_sec"] = _f(m.group(4)), _hms(m.group(5))
    m = re.search(r"runway to_phase_close=(\d+)s.*?to_sess_close=(\d+)s", text)
    if m:
        r["runway_phase"], r["runway_sess"] = int(m.group(1)), int(m.group(2))
    m = re.search(r"COVERAGE SESSION.*?COVERAGE=(\S+)%\s+unspent=\$(\S+)", text)
    if m:
        r["cov_sess"], r["unspent_sess"] = _f(m.group(1)), _f(m.group(2))
    # the PHASE coverage row is the one whose label is not SESSION
    for mm in re.finditer(r"COVERAGE (\S+)\s+range_so_far=\$\S+\s+"
                          r"exp_move_q50=\S+\s+COVERAGE=(\S+)%\s+"
                          r"unspent=\$(\S+)", text):
        if mm.group(1) != "SESSION":
            # R07: group 3 is the `unspent=$` cell — DOLLARS, which is what the
            # sibling SESSION parse calls `unspent_sess`.  The V1 spelling
            # `pct_unspent_phase` said percent and was read as percent for 20
            # reader-days; it survives as a compat ALIAS, never as the name.
            r["cov_phase"] = _f(mm.group(2))
            r["unspent_phase_usd"] = _f(mm.group(3))
    r["fvol_source"] = _search(r"fvol_source (\S+)", text)
    r["n_pivots"] = _search(r"n_pivots_total\s+(\d+)", text, cast=int)
    r["mult"] = _search(r"mult=(\d+)", text, cast=_f)
    r["mid"] = _search(r"entry mid=(\S+)", text, cast=_f)

    # exit: phase_close == session_close  =>  the hold runs to the session end
    m = re.search(r"exit_default phase_close@(\d\d:\d\d:\d\d)\s+\((\d+)s\)\s+"
                  r"session_close@(\d\d:\d\d:\d\d)", text)
    if m:
        r["exit_is_sess"] = 1 if m.group(1) == m.group(3) else 0

    # ---- S4 -------------------------------------------------------------
    r["n_in_band"] = _search(r"n_in_band=(\d+)", text, cast=int)
    lvls = []
    for line in re.findall(r"\n    [Kr] (\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)"
                           r"\s+(\S+)\s+(\S+)\s+(\S+)", text):
        fam, lid, px, dd, V, tc, tm, out = line
        lvls.append((fam, lid, _f(px), _f(dd), tc, tm))
    near = [l for l in lvls if l[3] is not None and abs(l[3]) <= 100.0]
    r["n_near100"] = len(near)
    if lvls:
        best = min((l for l in lvls if l[3] is not None),
                   key=lambda l: abs(l[3]), default=None)
        if best:
            r["near_fam"], r["near_d"] = best[0], best[3]
        bypx = {}
        for l in lvls:
            if l[2] is None:
                continue
            bypx.setdefault(round(l[2], 6), set()).add(l[0])
        if bypx:
            px, fams = max(bypx.items(), key=lambda kv: len(kv[1]))
            r["n_conf_max"] = len(fams)
            dd = [l[3] for l in lvls if l[2] is not None
                  and round(l[2], 6) == px and l[3] is not None]
            r["conf_d"] = dd[0] if dd else None
        tcs = [int(l[4]) for l in near if l[4].isdigit()]
        r["min_tc_near"] = min(tcs) if tcs else None
    if "OR STATE         none built" in text:
        r["or_state"] = "none"
    else:
        st = re.findall(r"\n     \S+\s+\S+\s+(TODAY|NOT_OPEN)", text)
        r["or_state"] = ("TODAY:%d/NOT_OPEN:%d" % (st.count("TODAY"),
                                                   st.count("NOT_OPEN"))
                         if st else "none")

    # ---- S5 -------------------------------------------------------------
    m = re.search(r"\n  trades/min\s+(.*)", text)
    if m:
        t = m.group(1).split()
        if len(t) >= 7:
            r["trades_min"] = _f(t[4])
            r["trades_min_z"], r["trades_min_z_floored"] = _fmark(t[5])
            r["trades_min_n_ref"] = _search(r"^(\d+)$", t[6], cast=int)
    m = re.search(r"\n  spread_\$\s+(.*)", text)
    if m:
        t = m.group(1).split()
        if len(t) >= 6:
            r["spread_now"] = _f(t[4])
    # CC-M2-9.3: S5 prints THREE slopes on one line and sections.py emits them
    # in the order sl_15, sl_5, sl_1 (see sections.py "slope / accel on the
    # mid").  The V1 extractor took the LAST column and called it `slope5m`,
    # which was in fact the ONE-MINUTE slope.  All three are now named.
    m = re.search(r"\n  mid_slope_\$/min\s+(.*?)accel\(1m-5m\)=\s*(\S+)", text)
    if m:
        t = m.group(1).split()
        if len(t) >= 3:
            r["slope15m"], r["slope5m"], r["slope1m"] = (_f(t[0]), _f(t[1]),
                                                        _f(t[2]))
        r["accel"] = _f(m.group(2))

    # ---- S7 -------------------------------------------------------------
    m = re.search(r"L1_now bid=\S+ x(\d+)\s+ask=\S+ x(\d+)", text)
    if m:
        r["l1_bid_sz"], r["l1_ask_sz"] = int(m.group(1)), int(m.group(2))
    for w, tag in ((60, "60"), (300, "300")):
        mm = re.search(r"\n\s+%d\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
                       r"(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)" % w, text)
        if mm:
            r["n_ev_%s" % tag] = int(mm.group(1))
            if w == 300:
                r["n_trades_300"] = int(mm.group(5))
                r["c2f_300"] = _f(mm.group(8))
            else:
                r["rev_s_60"] = _f(mm.group(6))
                r["c2f_60"] = _f(mm.group(8))
                r["dBsz_min"], r["dAsz_min"] = _f(mm.group(9)), _f(mm.group(10))
    r["refill_frac"] = _search(r"refill_after_trade.*?frac=(\S+)", text, cast=_f)

    # ---- S8 -------------------------------------------------------------
    for lbl, pre in (("60s", "f60"), ("5m", "f5m"), ("30m", "f30m")):
        mm = re.search(r"\n\s+%s\s+(\d+)\s+(\d+)\s+(-?\d+)\s+" % re.escape(lbl),
                       text)
        if mm:
            r[pre + "_n"], r[pre + "_vol"] = int(mm.group(1)), int(mm.group(2))
            r[pre + "_sflow"] = int(mm.group(3))
    mm = re.search(r"\n\s+phase\s+(\d+)\s+(\d+)\s+(-?\d+)\s+", text)
    if mm:
        r["fph_vol"], r["fph_sflow"] = int(mm.group(2)), int(mm.group(3))
    m = re.search(r"trapped above_mid=(\d+)\s+below_mid=(\d+)\s+at_mid=(\d+)"
                  r"\s+phase_total=(\d+)", text)
    if m:
        r["trapped_above"], r["trapped_below"] = int(m.group(1)), int(m.group(2))
        r["phase_total"] = int(m.group(4))
    m = re.search(r"through_book_600s n=(\d+)\s+thru_bid=(\d+)\s+thru_ask=(\d+)",
                  text)
    if m:
        r["thru_n"], r["thru_bid"], r["thru_ask"] = (int(m.group(1)),
                                                     int(m.group(2)),
                                                     int(m.group(3)))

    # ---- S9 -------------------------------------------------------------
    m = re.search(r"rv_nowcast_\$.*?\n\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)", text)
    if m:
        r["rv60"], r["rv300"] = _f(m.group(1)), _f(m.group(2))
        r["rv900"], r["rv1800"] = _f(m.group(3)), _f(m.group(4))
    if r["rv60"] and r["rv1800"]:
        r["rv_collapse"] = round(r["rv1800"] / r["rv60"], 2) if r["rv60"] else None
    r["jump_frac"] = _search(r"jump_frac=\s*(\S+)", text, cast=_f)
    r["vol_of_vol"] = _search(r"vol_of_vol\s+(\S+)", text, cast=_f)
    # D9: `surprise` is read from the S9 fvol row by EXPLICIT COLUMN NAME —
    # anchored on its own label AND on the label of the cell to its left, so a
    # bare `surprise=` printed anywhere else on the sheet can never supply it.
    r["surprise"] = _search(r"realized_range_so_far=\$\S+\s+surprise=(\S+)",
                            text, cast=_f)
    m = re.search(r"move_ladder_\$ q10=(\S+)\s+q25=\S+\s+q50=(\S+)", text)
    if m:
        r["q10"], r["q50"] = _f(m.group(1)), _f(m.group(2))
    r["ladder_pos"] = _search(r"ladder_position (\S+)", text)
    r["ev_ratio"] = _search(r"event_intensity .*?ratio=(\S+)", text, cast=_f)

    # ---- S10 (D17) -------------------------------------------------------
    # The DEVELOPING value area, parsed by explicit label (the D9 lesson): the
    # section also prints phase_final and prior_session rows carrying the same
    # POC/VAH/VAL labels, so the anchor is the `developing as_of=` prefix.
    m = re.search(r"developing as_of=\d\d:\d\d:\d\d\s+POC=(\S+)\s+VAH=(\S+)\s+"
                  r"VAL=(\S+)\s+d_POC=\$(\S+)\s+in_VA=(\d)", text)
    if m:
        r["dev_poc"], r["dev_vah"] = _f(m.group(1)), _f(m.group(2))
        r["dev_val"], r["d_POC"] = _f(m.group(3)), _f(m.group(4))
        r["in_VA"] = int(m.group(5))

    # ---- S12 (D10) -------------------------------------------------------
    # The scheduled-release clock.  ERA_NOTES §22: a phase-length flow window
    # that CONTAINS a scheduled release is a fossil, so the age of the last
    # release is the field that says whether the phase window can be trusted.
    r["dec_ts"] = _search(r"decision_ts = \S+ \((\d+)\)", text, cast=int)
    r["sched_last_age"] = _search(r"last_scheduled\s+.*?\s(\d+)s ago", text,
                                  cast=_f)
    m = re.search(r"next_scheduled\s+.*?\sin (\d+)d (\d+):(\d+):(\d+)", text)
    if m:
        r["sched_next_in"] = (int(m.group(1)) * 86400 + int(m.group(2)) * 3600
                              + int(m.group(3)) * 60 + int(m.group(4)))

    # ---- S13 ------------------------------------------------------------
    m = re.search(r"entry mid=\S+\s+side=\S+\s+spread_at_decision=\$(\S+)\s+"
                  r"cost_rt=\$(\S+)", text)
    if m:
        r["spread_dec"], r["cost_rt"] = _f(m.group(1)), _f(m.group(2))

    _derive(r)
    return r


SPREAD_MED = {"SI": 25.0, "HG": 25.0, "NKD": 50.0}

# ------------------------------------------------ R06 the REFUSED-CLAUSE LAW
# CC-M2-20.3 ruled it and ordered the sweep "with the next tooling pass"; this
# is that pass.  A derived flag has THREE states — fired (1), did not fire (0),
# could not be computed (`R`) — and clauses combine under KLEENE logic so a
# clause that is decidable on the inputs present still decides.  `_kor` is
# true if any disjunct is true even when another is refused; `_kand` is false
# if any conjunct is false even when another is refused.  Anything else that
# touches a refused input is refused, never quietly zero.
SIDE_TOKENS = {"LONG": 1, "SHORT": -1}

# The inputs every derived flag and the seat score read.  `n_refused_inputs`
# counts, per row, how many of these the sheet could not supply — the column
# CC-M2-20 D22 needed to tell "the capacity family did not fire" apart from
# "the capacity family could not be evaluated on this asset at all".
DERIVED_INPUTS = ("side", "exit_is_sess", "cov_phase", "unspent_phase_usd",
                  "cov_sess", "unspent_sess", "f60_n", "f60_vol",
                  "n_trades_300", "c2f_300", "trades_min_z", "spread_dec",
                  "rv_collapse", "ladder_pos", "runway_phase",
                  "extreme_age_trade_side", "slope5m", "accel", "ext_needed")

# seat_score is a RANKING, and the V1 form added each term only when its input
# was present — so a row with refused fvol skipped three of the five penalties
# and scored systematically HIGHER than an otherwise identical row with values.
# On the record (CC-M2-20.3 D23) SI's fvol is refused on 5 of 8 E1 study
# sessions, so the scan-ordering instrument was an asset selector.  The score
# is therefore REFUSED, never partially summed, unless BOTH hold:
#   * every PENALTY term is computable (a missing penalty can only inflate), and
#   * at least SEAT_MIN_TERMS of the SEAT_N_TERMS terms are present.
SEAT_POS_TERMS = ("exit_is_sess", "cov_phase", "ladder_pos", "runway_phase",
                  "extreme_age_trade_side", "slope5m", "accel")
SEAT_PEN_TERMS = ("P004", "P005", "P013", "P002", "P003", "ext_needed")
SEAT_N_TERMS = len(SEAT_POS_TERMS) + len(SEAT_PEN_TERMS)          # 13
SEAT_MIN_TERMS = 11                       # = all 6 penalties + 5 of 7 positives


def _t(inputs_ok, condition):
    """One leaf term of a flag: 1 / 0 / R (m2_common.flag3)."""
    return MC.flag3(inputs_ok, condition)


def _kor(*ts):
    if any(t == 1 for t in ts):
        return 1
    if any(MC.is_refused(t) for t in ts):
        return REFUSED
    return 0


def _kand(*ts):
    if any(t == 0 for t in ts):
        return 0
    if any(MC.is_refused(t) for t in ts):
        return REFUSED
    return 1


def _side_of(r):
    """+1 / -1 from the sheet's own token, CROSS-CHECKED against the cid.

    R45: the V1 form was `1 if side.upper().startswith("L") else -1`, which
    maps every unknown or missing token to SHORT — inverting every side-signed
    term rather than refusing.  The cid's own side character is the identity,
    so a disagreement is a defect and refuses.
    """
    tok = SIDE_TOKENS.get(str(r.get("side") or "").strip().upper())
    cid = str(r.get("cid") or "")
    cid_side = MC.CHAR_SIDE.get(cid[-1]) if len(cid) > 2 and cid[-2] == "-" \
        else None
    if tok is None or (cid_side is not None and cid_side != tok):
        return None
    return tok


def _derive(r):
    """The E1 pattern ledger, made mechanical.  Flags are TRIAGE PRIORS, not
    calls: the reader decides, these only route attention."""
    side = _side_of(r)

    # D15: the session's OBSERVED close, and the runway that actually binds.
    # A nominal runway on a holiday session is wrong by hours (2021-07-05: the
    # HG tape stops at 71,354s while every sheet computes to 82,799s).
    if r["asset"] and r["date8"]:
        sd, oc = session_meta(r["asset"], r["date8"])
        r["short_day"], r["observed_close"] = sd, (oc if (oc or -1) >= 0
                                                   else None)
    if r["runway_phase"] is not None:
        if r["observed_close"] is not None and r["sec"] is not None:
            r["runway_observed"] = min(r["runway_phase"],
                                       max(0, r["observed_close"] - r["sec"]))
        else:
            r["runway_observed"] = r["runway_phase"]

    # CC-M2-14.2a: the leading regime state, joined STRICTLY BEFORE the
    # decision second (the sheet's own S12 epoch).  No dec_ts -> no join.
    if r["asset"] and r["date8"] and r["dec_ts"] is not None:
        hit = regime_at(r["asset"], r["date8"], int(r["dec_ts"]))
        if hit is not None:
            r["rf_anchor_ts"], r["rf_anchor"] = hit[0], hit[1]
            for c, _src in REGIME_FIELDS:
                r[c] = hit[2].get(c)

    # D17: the VAH/VAL distances the sheet does not print, in the SAME UNITS
    # AND SIGN CONVENTION as the printed d_POC, which is (mid - level) x mult
    # — POSITIVE when the level sits BELOW the entry mid.
    if r["mid"] is not None and r["mult"]:
        for px, key in ((r["dev_vah"], "d_VAH"), (r["dev_val"], "d_VAL")):
            if px is not None:
                r[key] = round((r["mid"] - px) * r["mult"], 1)

    # R08 / CC-M2-7.3: the ORDINAL form of the S5 clock-norm comparison, over
    # the same trailing same-half-hour reference the sheet's z is taken over.
    if r["asset"] and r["date8"]:
        r["trades_min_z_pctile"] = clock_pctile(r["asset"], r["date8"],
                                                r["dec_ts"], r["trades_min"])

    # phase-extreme age on the side the trade needs (SHORT -> H, LONG -> L)
    if side is not None:
        ext = r["phase_H_sec"] if side < 0 else r["phase_L_sec"]
        if ext is not None and r["sec"] is not None:
            r["extreme_age_trade_side"] = r["sec"] - ext

    # A1 STRICT FORM (warmup #21): how much of the $1,000 bar lives INSIDE the
    # phase range already, and how much range EXTENSION the bar therefore needs.
    if side is not None and r["mid"] is not None and r["mult"]:
        ext = r["phase_H"] if side > 0 else r["phase_L"]
        if ext is not None:
            room = (ext - r["mid"]) * r["mult"] * side
            r["room_phase"] = round(room, 1)
            r["ext_needed"] = round(max(0.0, 1000.0 - room), 1)
    # binding unspent: the session row also binds when the hold runs to the
    # session end (P003), so the conservative reading is the smaller of the two
    cand = [x for x in (r["unspent_phase_usd"],
                        r["unspent_sess"] if r["exit_is_sess"] == 1 else None)
            if x is not None]
    r["unspent_bind"] = min(cand) if cand else None
    # P014 CAPACITY_TO_BAR: the binding row's remaining expected move cannot
    # reach the $1,000 bar however good the entry is (sharper than P002's 75%)
    r["P014"] = _t(r["unspent_bind"] is not None,
                   r["unspent_bind"] is not None and r["unspent_bind"] < 1000.0)

    # P002 A1_EXIT_SECOND_VETO — phase-close exit into a spent phase
    r["P002"] = _kand(
        _t(r["exit_is_sess"] is not None, r["exit_is_sess"] == 0),
        _kor(_t(r["cov_phase"] is not None,
                r["cov_phase"] is not None and r["cov_phase"] >= 75.0),
             _t(r["unspent_phase_usd"] is not None,
                r["unspent_phase_usd"] is not None
                and r["unspent_phase_usd"] <= 450.0)))
    # P003 A1_SESSION_BINDING — session-close exit: the SESSION row binds
    r["P003"] = _kand(
        _t(r["exit_is_sess"] is not None, r["exit_is_sess"] == 1),
        _kor(_t(r["cov_sess"] is not None,
                r["cov_sess"] is not None and r["cov_sess"] >= 95.0),
             _t(r["unspent_sess"] is not None,
                r["unspent_sess"] is not None
                and r["unspent_sess"] <= 450.0)))
    # P004 DEAD_BOOK_VETO.  R08: the z term REFUSES on a FLOOR-SCALED z rather
    # than thresholding it — spec §1 S5 says a `~` z is ORDINAL ONLY, and P004
    # is the E1 round's only unbroken refusal, frozen into the blind policy.
    r["P004"] = _kor(
        _t(r["f60_n"] is not None, r["f60_n"] is not None and r["f60_n"] <= 1),
        _t(r["f60_vol"] is not None,
           r["f60_vol"] is not None and r["f60_vol"] <= 1),
        _kand(_t(r["n_trades_300"] is not None,
                 r["n_trades_300"] is not None and r["n_trades_300"] <= 15),
              _t(r["c2f_300"] is not None,
                 r["c2f_300"] is not None and r["c2f_300"] >= 20.0)),
        _t(r["trades_min_z"] is not None and not r["trades_min_z_floored"],
           r["trades_min_z"] is not None and r["trades_min_z"] <= -1.3))
    # P005 ENTRY_SPREAD_TAX
    med = SPREAD_MED.get(r["asset"] or "", 25.0)
    r["P005"] = _t(r["spread_dec"] is not None,
                   r["spread_dec"] is not None and r["spread_dec"] >= 1.5 * med)
    # P013 WALL_BINDS — collapsed rv ratio marks a leg that is ENDING
    r["P013"] = _t(r["rv_collapse"] is not None,
                   r["rv_collapse"] is not None and r["rv_collapse"] >= 8.0)
    # P001 PHASE_ROLLOVER_UNDERMOVED (the era's only bar-clearing seat)
    r["P001"] = _kand(
        _t(r["exit_is_sess"] is not None, r["exit_is_sess"] == 1),
        _t(r["cov_phase"] is not None,
           r["cov_phase"] is not None and r["cov_phase"] <= 70.0),
        _t(r["ladder_pos"] is not None,
           (r["ladder_pos"] or "") in ("below_q10", "at_or_above_q10")),
        _t(r["runway_phase"] is not None,
           r["runway_phase"] is not None and r["runway_phase"] >= 26000),
        _t(r["extreme_age_trade_side"] is not None,
           r["extreme_age_trade_side"] is not None
           and 0 <= r["extreme_age_trade_side"] <= 200),
        _t(side is not None and r["slope5m"] is not None,
           side is not None and r["slope5m"] is not None
           and r["slope5m"] * side > 0),
        _t(side is not None and r["accel"] is not None,
           side is not None and r["accel"] is not None
           and r["accel"] * side > 0))

    # ---- the refused-input census, per row (R06) -------------------------
    n_ref = sum(1 for c in DERIVED_INPUTS
                if (side is None if c == "side" else r.get(c) is None))
    # a FLOOR-SCALED z is an ordinal, i.e. refused as a threshold input
    if r["trades_min_z"] is not None and r["trades_min_z_floored"]:
        n_ref += 1
    r["n_refused_inputs"] = n_ref

    # ---- seat_score: REFUSED, never partially summed (R06) ---------------
    s = 0.0
    present = 0
    if r["exit_is_sess"] is not None:
        present += 1
        if r["exit_is_sess"] == 1:
            s += 1.0
    if r["cov_phase"] is not None:
        present += 1
        s += max(0.0, (80.0 - r["cov_phase"]) / 40.0)
    if r["ladder_pos"] is not None:
        present += 1
        if r["ladder_pos"] in ("below_q10", "at_or_above_q10"):
            s += 1.0
    if r["runway_phase"] is not None:
        present += 1
        s += min(1.0, r["runway_phase"] / 30000.0)
    if r["extreme_age_trade_side"] is not None:
        present += 1
        if 0 <= r["extreme_age_trade_side"] <= 300:
            s += 1.0 - r["extreme_age_trade_side"] / 300.0
    if side is not None and r["slope5m"] is not None:
        present += 1
        if r["slope5m"] * side > 0:
            s += 0.75
    if side is not None and r["accel"] is not None:
        present += 1
        if r["accel"] * side > 0:
            s += 0.75
    pen_refused = 0
    for col, w in (("P004", 1.5), ("P005", 1.0), ("P013", 0.5),
                   ("P002", 1.0), ("P003", 1.0)):
        if MC.is_refused(r[col]):
            pen_refused += 1
            continue
        present += 1
        s -= w * int(r[col])
    # P014 is REPORTED, never weighted: it fires on 96% of HG/NKD candidates,
    # and a flag that fires on 96% of the population cannot discriminate.
    # The range-EXTENSION arithmetic (ext_needed) is the discriminating form
    # (it is 0 on only ~12% of the day) and carries the weight instead.
    if r["ext_needed"] is None:
        pen_refused += 1
    else:
        present += 1
        s -= min(1.5, r["ext_needed"] / 1000.0)
    r["seat_terms_present"] = present
    r["seat_score"] = (REFUSED if (pen_refused or present < SEAT_MIN_TERMS)
                       else round(s, 3))


# ------------------------------------------------------ D14 as-of prefix view
def _asint(v):
    """int(v) for a native OR a read_index string cell; None on the typed
    missing glyph and on anything that is not an integer."""
    if v is None or v == "" or v == NA:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _asof_rules():
    """col -> knowability rule.  A TOTAL partition of COLUMNS, asserted.

    R16.  The V3 form answered "the row's own decision second" for every column
    but three, so `verify_as_of`'s per-field loop compared each field's
    knowability second against the row's own decision second — a condition
    guaranteed true for every row that survived the `sec <= as_of` filter, i.e.
    a tautology presented as the D14 leak guard.  The fix is the shape the
    OBSERVED_COLS exception already had, EXTENDED to a real table: every column
    names its rule, and the assertion below means a column added without one is
    a refusal rather than a silent inheritance of "knowable now".
    """
    out = {}
    for c in COLUMNS:
        out[c] = ASOF_RULE_DECISION
    for c in OBSERVED_COLS:
        out[c] = ASOF_RULE_CLOSE
    for c in ASOF_EXEMPT:
        out[c] = ASOF_RULE_EXEMPT
    for c in FORECAST_COLS:
        out[c] = ASOF_RULE_ANCHOR
    missing = [c for c in COLUMNS if c not in out]
    extra = [c for c in out if c not in COLUMNS]
    if missing or extra:
        raise RuntimeError("AS-OF RULE TABLE is not total: missing=%s extra=%s"
                           % (missing, extra))
    return out


ASOF_RULES = _asof_rules()


def field_asof_sec(row, col):
    """The session second at which `col` of `row` becomes KNOWABLE.

    None = lawful at ANY as-of (the D-057 SCHEDULE_EXEMPT case only).
    KNOW_NEVER = the knowability second cannot be established, so the value is
    masked at every as-of — the refusing direction, where the V3 form returned
    None (i.e. blessed the value) for an observed-close column on a session
    with no m0 receipt.
    """
    rule = ASOF_RULES.get(col)
    if rule is None:
        raise RuntimeError("AS-OF REFUSAL: column %r declares no knowability "
                           "rule (add it to ASOF_RULES)" % col)
    if rule == ASOF_RULE_EXEMPT:
        return None
    if rule == ASOF_RULE_CLOSE:
        oc = _asint(row.get("observed_close"))
        return KNOW_NEVER if oc is None else oc
    sec = _asint(row.get("sec"))
    if sec is None:
        return KNOW_NEVER
    if rule == ASOF_RULE_ANCHOR:
        # CC-M2-14.2a: the leading regime state is knowable at its ANCHOR, and
        # the anchor is strictly prior to the decision (regime_at enforces it).
        # The anchor's own session second is dec_sec - (dec_ts - anchor_ts).
        ats, dts = _asint(row.get("rf_anchor_ts")), _asint(row.get("dec_ts"))
        if ats is None or dts is None:
            return sec
        return sec - (dts - ats)
    return sec


def as_of_row(row, as_of):
    """A copy of `row` with every field not knowable at `as_of` set to None."""
    out = dict(row)
    for c in COLUMNS:
        if out.get(c) is None:
            continue
        k = field_asof_sec(row, c)
        if k is not None and k > as_of:
            out[c] = None
    return out


def verify_as_of(rows, as_of):
    """REFUSE to emit a leaky prefix view.  Raises on the first violation.

    Two laws, and the first one is the D14 leak verbatim: a row whose decision
    second is after the as-of second must not be in the table at all, because
    its `mid` IS the price path after the second being called.
    """
    for r in rows:
        sec = r.get("sec")
        if sec is None:
            raise RuntimeError("AS-OF REFUSAL: row %s carries no decision "
                               "second" % r.get("cid"))
        if int(sec) > as_of:
            raise RuntimeError("AS-OF REFUSAL: row %s at sec=%d is LATER than "
                               "as_of=%d (D14 scan exposure: its mid is the "
                               "price path after the decision)"
                               % (r.get("cid"), int(sec), as_of))
        for c in COLUMNS:
            if r.get(c) is None:
                continue
            k = field_asof_sec(r, c)
            if k is not None and k > as_of:
                raise RuntimeError("AS-OF REFUSAL: row %s field %s is knowable "
                                   "only at %d > as_of=%d"
                                   % (r.get("cid"), c, k, as_of))
    return True


def prefix_view(rows, as_of):
    """The rows of `rows` visible at `as_of`, masked and verified."""
    out = [as_of_row(r, as_of) for r in rows
           if r.get("sec") is not None and int(r["sec"]) <= as_of]
    verify_as_of(out, as_of)
    return out


DRIVE_STEP_MAX = 60
"""R09.  A prefix emits every row with `sec <= cut`, so a cut of STEP seconds
carries up to STEP-1 seconds of LATER rows whose `mid` is the post-decision
price path — the D14 SCAN-EXPOSED leak CC-M2-12.1 made blocking before any
blind round.  The study rounds ran at 300s (275/277 cuts); the BLIND round the
teacher gate scores ran at 1800s (47 cuts), six times coarser on the one
instrument that had to be tighter.  A stepped drive is capped here, and
`per_row=True` is the exact form: one prefix per DISTINCT DECISION SECOND."""


def day_driver(rows, step_sec=None, first=None, last=None, per_row=False,
               allow_coarse_step=True):
    """The chronological reveal: [(as_of, prefix_rows)].

    The driver is the mechanic CC-M2-12.1(a) makes mandatory — candidates are
    processed in decision order and the index is revealed incrementally, so
    the table can never show a row the clock has not reached.  The final cut is
    always the last decision second (the day-complete view, which is only
    lawful once the day is over).

    `per_row=True` cuts at every distinct decision second (R09, the `--next`
    semantics `e1d4_asof.py:120-132` drives); otherwise the cut is every
    `step_sec`.

    THE COARSE-STEP CAP IS ENFORCED AT THE CLI, not here: `main()` passes
    `allow_coarse_step=False` unless `--allow-coarse-step` is given, so no
    ROUND can be driven at a leaky step, while a library caller that wants a
    deliberately coarse reveal (a monotonicity check over a handful of cuts,
    say) still gets one.  The refusals below that are UNCONDITIONAL are the
    R48 class: an empty cut range is a defect at any step.
    """
    secs = sorted(int(r["sec"]) for r in rows if r.get("sec") is not None)
    if not secs:
        # R48: an empty day is a refusal, not an empty list a caller can
        # mistake for "the driver ran and revealed nothing".
        raise RuntimeError("DRIVER REFUSAL: no row carries a decision second, "
                           "so there is no chronological reveal to build")
    lo = int(first if first is not None else secs[0])
    hi = int(last if last is not None else secs[-1])
    if lo > hi:
        raise RuntimeError("DRIVER REFUSAL: empty cut range first=%d > last=%d"
                           % (lo, hi))
    if per_row:
        cuts = sorted({s for s in secs if lo <= s <= hi})
        if not cuts:
            raise RuntimeError("DRIVER REFUSAL: no decision second inside "
                               "[%d, %d]" % (lo, hi))
    else:
        if step_sec is None or int(step_sec) <= 0:
            raise RuntimeError("DRIVER REFUSAL: step_sec=%r is not a positive "
                               "number of seconds" % (step_sec,))
        if int(step_sec) > DRIVE_STEP_MAX and not allow_coarse_step:
            raise RuntimeError(
                "DRIVER REFUSAL (R09/D14): --drive-step %d > %ds exposes up to "
                "%d seconds of post-decision rows in every prefix; use "
                "--drive-per-row, or a step <= %d, or declare "
                "--allow-coarse-step"
                % (int(step_sec), DRIVE_STEP_MAX, int(step_sec) - 1,
                   DRIVE_STEP_MAX))
        cuts = list(range(lo, hi + 1, int(step_sec)))
        if not cuts:
            raise RuntimeError("DRIVER REFUSAL: empty cut range [%d, %d] "
                               "step=%d" % (lo, hi, int(step_sec)))
    if cuts[-1] != hi:
        cuts.append(hi)
    return [(c, prefix_view(rows, c)) for c in cuts]


# --------------------------------------------------- D16 the versioned API --
# Every rename this extractor has ever made, CURRENT -> LEGACY.  The compat
# view carries both spellings and `read_index` populates both, so a consumer
# pinned to either name keeps working.
ALIASES = (("day_type_so_far", "day_type"),
           ("range_vs_hat_pct", "pct_range_hat"),
           # R07: the column holds DOLLARS and always did; the V1/V2/V3 name
           # said percent.  The name is corrected and the old spelling is
           # pinned here for e1d1_policy / e1d1_seal, which read it by name.
           ("unspent_phase_usd", "pct_unspent_phase"))


def read_index(path):
    """(rows, stamps) — the CANONICAL reader.  Use this, never readlines()[1:].

    Skips every `#` line (there have been 1, then 2, and an as-of view has 3),
    returns the machine stamps it found, and fills in both spellings of every
    renamed column.
    """
    import csv
    stamps, body = {}, []
    with open(path) as fh:
        for ln in fh:
            if ln.startswith("#"):
                m = re.search(r"extractor_version (\S+)", ln)
                if m:
                    stamps["extractor_version"] = m.group(1)
                m = re.search(r"columns_sha16 (\S+)", ln)
                if m:
                    stamps["columns_sha16"] = m.group(1)
                m = re.search(r"AS_OF (\d+)", ln)
                if m:
                    stamps["as_of"] = int(m.group(1))
                continue
            body.append(ln)
    rows = list(csv.DictReader(body, delimiter="\t"))
    for r in rows:
        for cur, legacy in ALIASES:
            if cur in r and legacy not in r:
                r[legacy] = r[cur]
            elif legacy in r and cur not in r:
                r[cur] = r[legacy]
    return rows, stamps


def compat_path(path):
    stem, ext = os.path.splitext(path)
    return stem + "_COMPAT" + (ext or ".tsv")


def write_compat(path, rows, as_of=None):
    """The PINNED V1 API: ONE comment line, both column spellings.

    `e1d1_policy.py` / `e1d2_policy.py` / `baseline_replay.py` are FROZEN
    scoreboard code and parse with `readlines()[1:]`; this file is the view
    they can read for ever, whatever the versioned index grows into.

    R47: the header used to claim "V1 column spellings retained" while the
    emitted list is the CURRENT column set plus every legacy alias — the file's
    own description of its contract was not what it emitted, which is how the
    D8/D13 class recurs.  It now says what it does.
    R27: a compat view built from an `--as-of` prefix carries the AS_OF stamp
    in its one comment line, so neither a consumer nor a later audit can
    mistake a masked prefix for a day-complete table.
    """
    cols = list(COLUMNS) + [legacy for _cur, legacy in ALIASES
                            if legacy not in COLUMNS]
    # R22 (cross-lane): `e1_blind_declared_policy.assert_columns` refuses any
    # index with no `columns_sha16` stamp, and the ONE comment line carried
    # none — so every COMPAT view failed the frozen policy's schema gate at day
    # one.  The stamp rides on the same single line, which keeps the D16
    # one-comment-line contract intact.
    lines = ["# TRIAGE INDEX COMPAT VIEW (D16 pinned reader: ONE comment line; "
             "the CURRENT %s column list plus every legacy alias, so a "
             "consumer pinned to either spelling keeps working; data identical "
             "to the versioned index)  columns_sha16=%s%s"
             % (VERSION, columns_sha16(),
                ("  AS_OF %d  (D14 prefix view: rows with sec > as_of are "
                 "ABSENT; fields knowable only later are masked to '%s')"
                 % (as_of, NA)) if as_of is not None else "")]
    lines.append("\t".join(cols))
    src = {legacy: cur for cur, legacy in ALIASES}
    for r in rows:
        lines.append("\t".join(_fmt(r[src[c]] if c in src else r[c])
                               for c in cols))
    text = "\n".join(lines) + "\n"
    with open(path, "w") as fh:
        fh.write(text)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


# ------------------------------------------------------------------ output --
def write_index(path, rows, as_of=None):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    if as_of is not None:
        verify_as_of(rows, as_of)
    body = ["# TRIAGE INDEX (CC-M2-3) — BLIND sheets only, S14 never opened",
            "# extractor_version %s  columns_sha16 %s  n_columns %d"
            % (VERSION, columns_sha16(), len(COLUMNS))]
    if as_of is not None:
        body.append("# AS_OF %d  (D14 prefix view: rows with sec > as_of are "
                    "ABSENT; fields knowable only later are masked to '%s')"
                    % (as_of, NA))
    body.append("\t".join(COLUMNS))
    for r in rows:
        body.append("\t".join(_fmt(r[c]) for c in COLUMNS))
    text = "\n".join(body) + "\n"
    with open(path, "w") as fh:
        fh.write(text)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def roster_count(asset, date8):
    """How many candidates generation-v3's union roster carries for that
    (asset, date8) — i.e. how many sheets a COMPLETE render must have left."""
    import assemble as A                  # noqa: E402 — lazy: roster-side dep
    r = A.roster(asset)
    return int(np.sum(r["date8"] == int(date8)))


def assert_day_complete(asset, date8, n_sheets, allow_mismatch=False):
    """R28 (D30's root cause).  REFUSE to index a partially rendered day.

    `main()` indexed whatever `.BLIND.sheet.txt` files happened to be in the
    directory.  Blind day 7 sealed 1,109 of 1,117 rows because of exactly that,
    and the patch lived in `lab/e1blind_day.sh` — conditional on a `.pid` file
    whose creator was wrapped in `|| true`, so a failed render launch skipped
    the guard entirely.  The roster is the count of record, so the guard
    belongs here, where the table is built.
    """
    exp = roster_count(asset, date8)
    if n_sheets == exp:
        return exp
    msg = ("ROSTER REFUSAL (R28/D30): %s %s has %d rendered sheets but the "
           "generation-v3 union roster carries %d candidates (%+d). The index "
           "would silently be built on a partial render."
           % (asset, date8, n_sheets, exp, n_sheets - exp))
    if not allow_mismatch:
        raise RuntimeError(msg)
    sys.stderr.write("DECLARED ROSTER MISMATCH: %s\n" % msg)
    return exp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--era", default="E1")
    ap.add_argument("--block", default="STUDY")
    ap.add_argument("--sessions", required=True,
                    help="ASSET:DATE8[,ASSET:DATE8...]")
    ap.add_argument("--out", required=True)
    ap.add_argument("--as-of", type=int, default=None,
                    help="emit the D14 PREFIX VIEW at this decision second")
    ap.add_argument("--drive-step", type=int, default=None,
                    help="chronological day driver: one prefix per STEP sec "
                         "(R09: > %ds is refused unless --allow-coarse-step)"
                         % DRIVE_STEP_MAX)
    ap.add_argument("--drive-per-row", action="store_true",
                    help="chronological day driver: one prefix per DISTINCT "
                         "DECISION SECOND (R09, the exact as-of stepper)")
    ap.add_argument("--allow-coarse-step", action="store_true",
                    help="declare a --drive-step coarser than %ds (each prefix "
                         "then carries up to step-1 seconds of LATER rows)"
                         % DRIVE_STEP_MAX)
    ap.add_argument("--drive-out", default=None,
                    help="directory for the driver's prefixes + manifest")
    ap.add_argument("--no-compat", action="store_true",
                    help="do NOT write the D16 pinned-reader compat view")
    ap.add_argument("--allow-roster-mismatch", action="store_true",
                    help="declare (never hide) a sheet count that disagrees "
                         "with the roster for that session — R28/D30")
    a = ap.parse_args()

    rows = []
    for tok in a.sessions.split(","):
        asset, date8 = tok.split(":")
        d = os.path.join(ROOT, a.era, a.block, asset, date8)
        files = sorted(f for f in os.listdir(d) if f.endswith(".BLIND.sheet.txt"))
        exp = assert_day_complete(asset, date8, len(files),
                                  allow_mismatch=a.allow_roster_mismatch)
        for f in files:
            rows.append(parse_sheet(os.path.join(d, f)))
        sys.stderr.write("%s %s: %d sheets (roster %d)\n"
                         % (asset, date8, len(files), exp))
    rows.sort(key=lambda r: (r["sec"] or 0, r["asset"] or "", r["cid"] or ""))
    if PCTILE_REFUSALS:
        sys.stderr.write("clock-percentile refusals: %s\n"
                         % sorted(PCTILE_REFUSALS.items()))

    if a.as_of is not None:
        rows_out = prefix_view(rows, a.as_of)
        sha = write_index(a.out, rows_out, as_of=a.as_of)
        sys.stderr.write("wrote %s (%d/%d rows, as_of=%d, sha16 %s)\n"
                         % (a.out, len(rows_out), len(rows), a.as_of, sha))
    else:
        rows_out = rows
        sha = write_index(a.out, rows)
        sys.stderr.write("wrote %s (%d rows, sha16 %s)\n"
                         % (a.out, len(rows), sha))
    if not a.no_compat:
        cp = compat_path(a.out)
        csha = write_compat(cp, rows_out, as_of=a.as_of)
        sys.stderr.write("wrote %s (D16 pinned view, sha16 %s)\n" % (cp, csha))

    if a.drive_step or a.drive_per_row:
        if not a.drive_out:
            raise SystemExit("--drive-step/--drive-per-row requires --drive-out")
        os.makedirs(a.drive_out, exist_ok=True)
        man = [["as_of_sec", "clock", "n_rows", "n_new_rows", "sha16", "path"]]
        prev = 0
        for cut, sub in day_driver(rows, a.drive_step,
                                   per_row=bool(a.drive_per_row),
                                   allow_coarse_step=a.allow_coarse_step):
            p = os.path.join(a.drive_out, "ASOF_%06d.tsv" % cut)
            s = write_index(p, sub, as_of=cut)
            man.append([cut, "%02d:%02d:%02d" % (cut // 3600, cut // 60 % 60,
                                                 cut % 60),
                        len(sub), len(sub) - prev, s, os.path.basename(p)])
            prev = len(sub)
        mp = os.path.join(a.drive_out, "DRIVE_MANIFEST.tsv")
        with open(mp, "w") as fh:
            fh.write("# TRIAGE DAY DRIVER (CC-M2-12.1a) — %s  columns_sha16 "
                     "%s  cut_rule=%s\n"
                     % (VERSION, columns_sha16(),
                        "per_row" if a.drive_per_row
                        else "step_%ds" % int(a.drive_step)))
            fh.write("# every ASOF_*.tsv is a verified prefix view; the reader "
                     "opens them IN ORDER and never the day-complete table\n")
            for row in man:
                fh.write("\t".join(str(x) for x in row) + "\n")
        sys.stderr.write("driver: %d cuts -> %s\n" % (len(man) - 1, a.drive_out))


if __name__ == "__main__":
    main()
