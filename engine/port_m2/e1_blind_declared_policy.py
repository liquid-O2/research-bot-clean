#!/usr/bin/python3
"""THE E1 PRE-BLIND DECLARATION, MADE EXECUTABLE (CC-M2-4.3 prospective
registration; frozen by the E1 STUDY day-8 reader on 2026-08-14).

This module IS the policy declared in `provenance/port_m2/E1_ROUND_SYNTHESIS.md`
§4.  It is what the E1 BLIND round tests.  It is FROZEN: no term may be added,
removed or retuned after the first blind day is drawn.

    TAKE(r)  iff  CLASS(r) and CORE(r) and not V2(r)

NO SIDE GATE.  NO VOLATILITY GATE.  NO CAPACITY GATE.  NO V3.  NO ABSTENTION.

WHY EACH TERM IS HERE (every number is on the study block, 9,026 rows / 8
day-complete sessions / 531 D-021 winners / 5.88% base):

  CLASS  `cls in {NEWS-WINDOW, OPEN-DYNAMICS}` — the two candidate classes whose
         POOLED mean certificate is positive: NEWS-WINDOW 284 rows / 44 winners
         / 15.49% / +$90.14, OPEN-DYNAMICS 209 / 25 / 11.96% / +$152.57, against
         REVERSAL-CONFIRMATION's 8,234 / 441 / 5.36% / -$25.32 (91% of all
         candidates).  Better than the rest on mean certificate in 7 of the 8
         sessions individually.  The set was chosen on the POOLED POOL, never on
         a replay (ERA_NOTES §33/§41).  MECHANISM: these are the classes where a
         move is being CREATED (a release, a phase open) rather than where a
         completed move is being FADED.  This reverses ERA_NOTES §6, which
         dismissed the class card on the 24-case warm-up.
  T1     P004 DEAD_BOOK_VETO — the round's only unbroken refusal, positive on
         all eight sessions.
  T2     P025's 12,000s runway floor — 408 of 462 study winners clear it; it is
         a concentrator, and it is retained as a REFUSAL (a refusal is not an
         entry) rather than as the feasibility claim CC-M2-19.3 broke.
  T3     freshness ceiling 3,600s.  CARRIED WITH A WARNING (defect D24): it was
         widened from 900s on day 2 on n=3 and has never been censused.
  T4/T5  P023's de-signed magnitude floor with the CC-M2-16.4 relative-OR-
         absolute repair.
  V2     the fuel-overhang veto — +$937.50 over CORE across the eight sessions,
         the only veto family with a positive record.  Its seat-spender record
         is hollow (four consecutive $0.00 replay deltas) and it is retained on
         the pooled number with that caveat stated.

WHAT IS DELIBERATELY ABSENT, each with its receipt:
  * every SIDE term — the reader's committed cell-side calls went 5 of 14 over
    three sessions against a mirror at 9 of 14, and twelve hand estimators
    mirror-law tested on 22 winner-bearing cells produced no survivor;
  * `rv1800 >= 250` — holds 92.8% of the round's winners and costs $7,562.50 as
    a gate (P034: a concentrator inverts on the seat-spending sub-population);
  * its INVERSION — the best arm on the training board (+$8,923.75) and
    pre-registered as NOT TRADED; it scored +$207.50 out of sample;
  * every CAPACITY term (`unspent_bind`, `ext_needed`, `cov_*`) — an anti-signal
    when the range expands, and a silent ASSET SELECTOR when fvol is REFUSED
    (defect D22);
  * V3/P018 — three sessions refusing winners at a positive mean for $0.00 of
    replay;
  * cell ABSTENTION (P035) — real as a feasibility fact, unproven as a gate
    (-$1,614 walk-forward over the eight sessions at its principled threshold).

STUDY-BLOCK SCORE (in-sample by construction; the blind days are the test):
  143 takes, 26 winners, precision 0.182 = 3.09x base; mean TAKE +$92.03 vs
  mean SKIP -$18.76; replay +$15,752.50 over 37 seats; CAPTURE 0.306; take MAE
  p50 $150 / p95 $731; positive on 7 of 8 sessions; margin over the best FIXED
  mechanical arm (EARLIEST + cond_value >= 516, +$9,865.00) = +$5,887.50 =
  +$736/session, positive on 6 of 8 day-paired.
NAMED CAVEAT: in E1 this is a METALS effect.  Per asset, HI-class vs the rest —
  SI 22.54% vs 7.42% (+$175.52 mean), HG 10.49% vs 5.03% (+$123.24), NKD 3.39%
  vs 3.82% (+$1.14).  An NKD-heavy blind block should be expected to underperform.

=======================================================================
DECLARED BEHAVIOUR ON REFUSED INPUTS (CC-M2-20.3 REFUSED-CLAUSE LAW)
=======================================================================
CC-M2-20.3 permits a clause to PASS on refused inputs only if "its pass
behavior is declared as an explicit selector".  The declaration was missing
(defect R21) and is made here.  NOTHING BELOW CHANGES A CALL — CC-M2-4.3
forbids retuning this module — the behaviour is stated and then COUNTED.

  CORE T1..T5 (`terms`)  REFUSE on a missing input: missing -> the term is
        False -> SKIP.  This is the conservative direction and needs no
        selector declaration: a refused input cannot buy an entry.

  V2 (`v2`)  PASSES on refused inputs, i.e. a refused fuel map means NO VETO
        and the row is TAKEN if CLASS and CORE hold.  DECLARED AS AN EXPLICIT
        SELECTOR: **V2 selects the sub-population whose S8 fuel map is
        READABLE.  On a row whose fuel map is refused, V2 makes no statement
        and the call is decided by CLASS and CORE alone.**  The refusals are
        no longer invisible: `v2_state()` is three-valued (True / False /
        "R"), `v2(r)` is exactly `v2_state(r) is True` (bit-identical to the
        frozen behaviour), and every row emits `v2_inputs_refused` so the
        measured population split is recoverable from the committed arms file.
        Refusal reaches V2 four ways, each counted under the same column:
        a missing `trapped_above`/`trapped_below`/`phase_total` (the early
        return), an unrecognised `side` token (R45 — never mapped to SHORT any
        more), and a refused through-book (`thru_n`/`thru_bid`/`thru_ask`)
        when the flow clause did not already fire.

  `grade()`  R24: a refused `sigma_to_exit` used to return "C", which is
        indistinguishable from a genuinely low grade and biases the CC-M2-4.4
        monotone-calibration curve by folding refusals into the bottom band.
        Refusal is now its own token ("R" = `m2_common.REFUSED_TOKEN`) and
        `conf_refused` counts it per row.  The grade gates nothing
        (CC-M2-10.5), so this changes no call; the calibration pass must drop
        conf == "R" rather than score it as a C.

  SCHEMA  R22: `F()` returns None on ANY exception, so a renamed or dropped
        index column made every term None -> every term False -> every row
        SKIP, silently, with a plausible-looking output file.  `assert_columns`
        now refuses that at load (D16: index headers are versioned APIs).  It
        is an assertion, not a retune.

  T2 / SHORT DAYS  R51: T2 reads `runway_phase`, the NOMINAL runway; D15
        (CC-M2-12.2) measured HG 2021-07-05 stopping at 71,354s while every
        sheet computes to 82,799s, and added `runway_observed`.  The policy is
        frozen, so the fix is on the REPORTING side: every row emits
        `short_day` and `runway_observed`, and the scoring pass reports
        short-day seats separately instead of quoting them inside the block.
"""
import argparse
import csv
import math
import os
import sys

HI_CLASSES = ("NEWS-WINDOW", "OPEN-DYNAMICS")
# = m2_common.REFUSED_TOKEN.  Spelled locally so this frozen module keeps its
# stdlib-only import surface; the two must never diverge and the fix-lane test
# asserts they are equal.
REFUSED = "R"
SIDES = {"LONG": 1, "SHORT": -1}
RUNWAY_MIN = 12000.0
FRESH_MAX = 3600.0
F5_FRAC = 0.05
F5_VOL_FLOOR = 200.0
F5_VOL_REL = 0.08
GRADE_A, GRADE_B = 2500.0, 1200.0
TERMS = ("T1", "T2", "T3", "T4", "T5")


def F(r, k):
    """The typed read.  Returns None on absent / unparseable / NA ("." ) — and
    that None is a REFUSAL, never a zero.  R22: because this swallows KeyError,
    a schema change would silently SKIP a whole day, so `assert_columns` runs
    at load and refuses that instead."""
    try:
        return float(r[k])
    except Exception:
        return None


# R22: the columns this policy READS.  A renamed or dropped column here used to
# turn every term None -> False -> SKIP for a whole day with no error at all.
REQUIRED_COLUMNS = (
    # identity, read directly (these already raised loudly)
    "cid", "asset", "side", "cls", "sec", "clock", "phase_dec",
    # CORE T1..T5
    "f60_n", "f60_vol", "runway_phase", "extreme_age_trade_side",
    "f5m_sflow", "f5m_vol", "fph_vol",
    # V2
    "trapped_above", "trapped_below", "phase_total",
    "thru_n", "thru_bid", "thru_ask",
    # grade
    "rv1800",
)

# R51 REPORTING columns.  Deliberately NOT in REQUIRED_COLUMNS: they are the
# D15 observed-close block, they gate nothing, and a pre-D15 index (E1D1..E1D4
# were built before D15 landed) must still be scoreable.  When they are absent
# the flag is REFUSED, which is what `short_day_flag` already returns — a
# refusal, never a "full session".
REPORTING_COLUMNS = ("short_day", "runway_observed")


class SchemaRefusal(RuntimeError):
    """The index does not carry the columns this policy reads.  Never caught
    to fall back on a default: a silent all-SKIP day is worse than a stop."""


def assert_columns(rows, stamps=None, path=""):
    """R22: REFUSE an index whose schema this frozen policy cannot read.

    `stamps` is `triage_index.read_index`'s second return value; when it is
    supplied the `columns_sha16` stamp must be present too (D13: an index with
    no stamp is pre-V2 and must not be attributed to the current extractor).
    """
    if not rows:
        raise SchemaRefusal("index %s carries no data rows" % (path or "?"))
    have = set(rows[0].keys())
    missing = [c for c in REQUIRED_COLUMNS if c not in have]
    if missing:
        raise SchemaRefusal(
            "D16 index schema refusal on %s: %d required column(s) absent: %s. "
            "The frozen policy reads them through F(), which returns None on a "
            "KeyError — every term would be False and the whole day would SKIP "
            "silently (R22)." % (path or "?", len(missing), ", ".join(missing)))
    if stamps is not None and not stamps.get("columns_sha16"):
        raise SchemaRefusal(
            "D13/D16 stamp refusal on %s: no `columns_sha16` header. An index "
            "without that stamp is pre-V2 and must not be read as if it were "
            "the current extractor's output." % (path or "?"))
    return True


def side_int(r):
    """+1 LONG / -1 SHORT / None REFUSED (R45).

    `1 if r["side"] == "LONG" else -1` mapped EVERY unrecognised token to
    SHORT, which inverts the fuel-overhang veto instead of refusing it.  A
    token this function does not know is a refusal, and the refusal is counted.
    """
    return SIDES.get(str(r.get("side")))


def klass(r):
    return r.get("cls") in HI_CLASSES


def terms(r):
    t = {}
    f60n, f60v = F(r, "f60_n"), F(r, "f60_vol")
    t["T1"] = bool(f60n is not None and f60n >= 5
                   and f60v is not None and f60v >= 10)
    rw = F(r, "runway_phase")
    t["T2"] = bool(rw is not None and rw >= RUNWAY_MIN)
    age = F(r, "extreme_age_trade_side")
    t["T3"] = bool(age is not None and 0 <= age <= FRESH_MAX)
    s5, v5 = F(r, "f5m_sflow"), F(r, "f5m_vol")
    t["T4"] = bool(s5 is not None and v5 and v5 > 0
                   and abs(s5) / v5 >= F5_FRAC)
    vph = F(r, "fph_vol")
    t["T5"] = bool(v5 is not None
                   and (v5 >= F5_VOL_FLOOR
                        or (vph is not None and vph > 0
                            and v5 >= F5_VOL_REL * vph)))
    return t


def v2_state(r):
    """THREE-VALUED V2 (R21/R45).  True = veto fires, False = veto does not
    fire on readable inputs, REFUSED = V2's inputs are not readable and V2
    makes no statement about this row.

    The FIRE set is bit-identical to the frozen boolean rule — every branch
    that returned True still returns True and every branch that returned False
    on READABLE inputs still returns False.  What changes is only that the
    branches which returned False because an input was ABSENT now say so.
    """
    side = side_int(r)                                   # R45: no silent SHORT
    if side is None:
        return REFUSED
    ta, tb, pt = F(r, "trapped_above"), F(r, "trapped_below"), F(r, "phase_total")
    if ta is None or tb is None or not pt:
        return REFUSED                                   # declared: -> no veto
    frac = (ta / pt) if side > 0 else (tb / pt)
    if frac < 0.90:
        return False                                     # a genuine pass
    s5, v5 = F(r, "f5m_sflow"), F(r, "f5m_vol")
    flow = bool(s5 is not None and v5 and abs(s5) / v5 >= 0.10
                and ((s5 < 0) == (side > 0)))
    if flow:
        return True
    tn, tbid, task = F(r, "thru_n"), F(r, "thru_bid"), F(r, "thru_ask")
    if tn is None or tbid is None or task is None:
        # the flow clause did not fire and the book clause cannot be read:
        # V2's answer on this row is REFUSED, not "no overhang".
        return REFUSED
    book = bool(tn >= 10
                and ((tbid >= 2 * task) if side > 0 else (task >= 2 * tbid)))
    if book:
        return True
    return False if (s5 is not None and v5) else REFUSED


def v2(r):
    """The frozen boolean: the veto FIRES.  CC-M2-4.3 — unchanged behaviour."""
    return v2_state(r) is True


def v2_inputs_refused(r):
    """1 when V2 made no statement about this row because its inputs were
    refused (the declared pass-on-refused selector, R21).  This is the counted
    column that makes the population split recoverable."""
    return int(v2_state(r) == REFUSED)


def sigma_to_exit(r):
    rv, rw = F(r, "rv1800"), F(r, "runway_phase")
    if rv is None or rw is None:
        return None
    return rv * math.sqrt(max(rw, 1.0) / 1800.0)


def grade(r):
    """Carried for calibration accounting ONLY — it gates nothing, its top band
    has been empty of winners for five consecutive sessions, and CC-M2-10.5
    disqualified it as a judge-aux target.

    R24: a refused `sigma_to_exit` returns the REFUSED token, not "C".  A
    refusal folded into the bottom band is indistinguishable from a genuinely
    low grade and biases the CC-M2-4.4 monotone-calibration curve; the
    calibration pass DROPS conf == "R" rather than scoring it.
    """
    s = sigma_to_exit(r)
    if s is None:
        return REFUSED
    return "A" if s >= GRADE_A else ("B" if s >= GRADE_B else "C")


def short_day_flag(r):
    """R51 REPORTING SIDE.  T2 thresholds `runway_phase`, the NOMINAL runway,
    and D15 measured that runway wrong by hours on an early-close session (HG
    2021-07-05: the tape stops at 71,354s, every sheet computes 82,799s).  The
    policy is FROZEN and is not touched; the row carries the flag instead so
    the scoring pass can report short-day seats separately.

    "1" short session / "0" full session / "R" refused (the D15 observed-close
    block is masked under `--as-of`, so a prefix view cannot know it — that is
    a refusal, never a 0).
    """
    v = r.get("short_day")
    if v in (None, "", "."):
        return REFUSED
    try:
        return "1" if int(float(v)) else "0"
    except Exception:
        return REFUSED


def evidence(r, t, cls_ok, vetoed):
    if not cls_ok:
        return ("primary: S13/S1 candidate class = %s — the declared policy "
                "trades only NEWS-WINDOW and OPEN-DYNAMICS, the two classes "
                "whose pooled mean certificate over 9,026 E1 study rows is "
                "POSITIVE (15.49%% and 11.96%% win rates against a 5.36%% "
                "REVERSAL-CONFIRMATION bulk that is 91%% of all candidates); "
                "a move being CREATED, not a completed move being FADED"
                % r.get("cls"))
    if not t["T1"]:
        return ("primary: S8 60s n=%s vol=%s — no transacting counterparty in "
                "the last minute (T1, P004, positive on all eight study "
                "sessions)" % (r.get("f60_n"), r.get("f60_vol")))
    if not t["T2"]:
        return ("primary: S3 runway to the binding %s phase close = %ss "
                "against the 12,000s floor (T2, P025 — 408 of 462 study "
                "winners clear it)"
                % (r.get("phase_dec"), r.get("runway_phase")))
    if not t["T3"]:
        return ("primary: S3 %s-phase extreme on the trade's side is %ss old, "
                "past the 3,600s window (T3 — carried with defect D24: this "
                "ceiling was widened from 900s on n=3 and never censused)"
                % (r.get("phase_dec"), r.get("extreme_age_trade_side")))
    if not t["T4"]:
        return ("primary: S8 5m sflow=%s on %s contracts is under the 5%% "
                "floor — no aggressive stream at magnitude (T4, de-signed "
                "P023)" % (r.get("f5m_sflow"), r.get("f5m_vol")))
    if not t["T5"]:
        return ("primary: S8 5m vol=%s against phase vol=%s — under 200 "
                "contracts AND under 8%% of the phase's volume (T5, CC-M2-16.4 "
                "repair)" % (r.get("f5m_vol"), r.get("fph_vol")))
    if vetoed:
        return ("primary: V2 VETO — S8's FUEL MAP puts >= 90%% of the phase's "
                "transacted volume against this trade with the adverse stream "
                "still running (+$937.50 over CORE across the eight study "
                "sessions; its seat-spender record is hollow and that caveat "
                "is declared)")
    return ("primary: candidate class %s [the declared filter: 3.09x the base "
            "winner rate, the only classes with a positive pooled mean "
            "certificate]; S8 60s n=%s vol=%s is a live book [T1, P004]; %ss "
            "of runway to the binding %s close [T2, P025]; the trade-side "
            "extreme is %ss old [T3]; S8 5m sflow=%s on %s clears the "
            "magnitude floor against a phase volume of %s [T4/T5]; no V2 veto "
            "— and NO SIDE, VOLATILITY OR CAPACITY TERM IS READ, by declaration"
            % (r.get("cls"), r.get("f60_n"), r.get("f60_vol"),
               r.get("runway_phase"), r.get("phase_dec"),
               r.get("extreme_age_trade_side"), r.get("f5m_sflow"),
               r.get("f5m_vol"), r.get("fph_vol")))


def against(r):
    bits = []
    for k, why in (("rv1800", "P034: this field holds 92.8%% of the round's "
                              "winners and costs $7,562.50 as a gate — it is a "
                              "FEATURE for a model that chooses among admitted "
                              "rows, never a gate in a policy that takes the "
                              "earliest"),
                   ("unspent_bind", "the capacity arithmetic is an anti-signal "
                                    "when the range expands, and a silent "
                                    "ASSET SELECTOR when fvol is REFUSED "
                                    "(defect D22)"),
                   ("d_POC", "S10's side geometry is 2 right / 6 wrong over 22 "
                             "winner-bearing cells (P037, dead)"),
                   ("slope15m", "the momentum family is dead across four "
                                "grains and four disguises (P036)")):
        v = r.get(k)
        if v not in (None, "", "."):
            bits.append("%s=%s — READ AND NOT TRADED: %s" % (k, v, why))
    return "; ".join(bits) if bits else "no field of the sheet opposes."


def call_day(rows, path=""):
    assert_columns(rows, path=path)              # R22: schema, not a fallback
    out = []
    for r in sorted(rows, key=lambda x: (int(float(x["sec"])), x["cid"])):
        t = terms(r)
        cls_ok = klass(r)
        core_ok = all(t[k] for k in TERMS)
        # "-" = NOT EVALUATED: CLASS/CORE already refused the row, so V2 was
        # never asked (that is the frozen order, and it is not a V2 refusal).
        vst = v2_state(r) if (cls_ok and core_ok) else "-"
        vetoed = vst is True
        fire = cls_ok and core_ok and not vetoed
        sig = sigma_to_exit(r)
        g = grade(r)
        out.append({
            "cid": r["cid"], "call": "TAKE" if fire else "SKIP",
            "conf": g, "n_terms": sum(1 for k in TERMS if t[k]),
            "cls_gate": int(cls_ok), "vetoes": "V2" if vetoed else "",
            "primary": evidence(r, t, cls_ok, vetoed), "against": against(r),
            # R24/R06: a refused sigma is the REFUSED token, not 0.0 — a zero
            # here sorted refusals to the bottom of every scan that used it.
            "sigma_to_exit": REFUSED if sig is None else round(sig, 1),
            "conf_refused": int(g == REFUSED),
            # R21: the declared pass-on-refused selector, made countable.
            "v2_state": ("-" if vst == "-" else
                         (REFUSED if vst == REFUSED
                          else ("1" if vst is True else "0"))),
            "v2_inputs_refused": int(vst == REFUSED),
            # R51: the reporting-side short-day flag (T2 reads the nominal
            # runway; this is what lets the scorer separate those seats).
            "short_day": short_day_flag(r),
            "runway_observed": (r.get("runway_observed")
                                if r.get("runway_observed") not in
                                (None, "", ".") else REFUSED),
            "asset": r["asset"], "phase_dec": r["phase_dec"],
            "clock": r["clock"], "sec": int(float(r["sec"])),
            "side": r["side"], "cls": r["cls"],
            **{k: int(t[k]) for k in TERMS}})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()
    # R22/R26: the CANONICAL reader.  It skips every `#` line (there have been
    # 1, then 2, and an as-of view has 3), returns the header stamps, and
    # fills both spellings of every renamed column.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import triage_index as TI                                     # noqa: E402
    rows, stamps = TI.read_index(a.index)
    assert_columns(rows, stamps=stamps, path=a.index)
    out = call_day(rows, path=a.index)
    cols = (["cid", "call", "conf", "conf_refused", "n_terms"] + list(TERMS)
            + ["cls_gate", "vetoes", "v2_state", "v2_inputs_refused",
               "sigma_to_exit", "short_day", "runway_observed", "asset",
               "phase_dec", "clock", "sec", "side", "cls", "primary",
               "against"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, delimiter="\t",
                           extrasaction="ignore")
        w.writeheader()
        for o in out:
            w.writerow(o)
    n = sum(1 for o in out if o["call"] == "TAKE")
    nvr = sum(o["v2_inputs_refused"] for o in out)
    ncr = sum(o["conf_refused"] for o in out)
    nsd = sum(1 for o in out if o["short_day"] == "1")
    print("e1_blind_declared_policy: %d rows, %d TAKE, %d SKIP -> %s"
          % (len(out), n, len(out) - n, a.out))
    print("  index columns_sha16=%s extractor=%s"
          % (stamps.get("columns_sha16", "-"),
             stamps.get("extractor_version", "-")))
    print("  REFUSAL ACCOUNTING (CC-M2-20.3): V2 inputs refused on %d of the "
          "%d rows V2 was asked about (declared pass-on-refused selector); "
          "conf REFUSED on %d rows (kept out of the CC-M2-4.4 calibration "
          "curve); %d rows sit on a SHORT SESSION (R51: T2 read the nominal "
          "runway)" % (nvr, sum(1 for o in out if o["v2_state"] != "-"),
                       ncr, nsd))
    if not a.quiet:
        for o in out:
            if o["call"] == "TAKE":
                print("   TAKE %-28s %s %-5s %-22s %s"
                      % (o["cid"], o["clock"], o["side"], o["cls"], o["conf"]))


if __name__ == "__main__":
    sys.exit(main())
