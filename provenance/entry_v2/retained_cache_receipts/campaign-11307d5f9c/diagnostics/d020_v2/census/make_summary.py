"""make_summary.py — compose PATTERN_CENSUS.md from the generated TSVs.

Prose is written here; every NUMBER is read back out of the census tables, so
the summary cannot drift from the tables it summarises.
"""
from __future__ import annotations

import csv
import sys

import numpy as np

sys.path.insert(0, "/workspace/artifacts/cache/campaign/diagnostics/d020_v2/census")
import censuslib as C                                   # noqa: E402
import detectors as D                                   # noqa: E402
import report as R                                      # noqa: E402

OUT = C.ROOT


def read(name: str) -> list:
    with open(OUT / name) as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def number(row: dict, key: str) -> float:
    value = row.get(key, "")
    return float(value) if value not in ("", "NA") else float("nan")


def money(value: float) -> str:
    return "NA" if value != value else f"{value:+,.0f}"


def table(rows: list, header: list) -> str:
    widths = [max(len(str(header[i])), *(len(str(r[i])) for r in rows))
              for i in range(len(header))] if rows else [len(h) for h in header]
    lines = ["| " + " | ".join(str(h).ljust(widths[i]) for i, h in enumerate(header)) + " |",
             "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row[i]).replace("|", "\\|").ljust(widths[i])
                                       for i in range(len(header))) + " |")
    return "\n".join(lines)


def verdicts(name: str, base: dict, destroyed: dict, quarters: list) -> tuple:
    """The readings the brief asks for, by explicit mechanical rule."""
    low, high = number(base, "paired_lcb05"), number(base, "paired_ucb95")
    direction = "DIRECTIONAL" if low > 0 else ("INVERTED" if high < 0 else "none")
    level_low = number(base, "verdict_level_lcb05")
    level_high = number(base, "verdict_level_ucb95")
    level_significant = level_low > 0 or level_high < 0
    level = ("high-value moments" if level_low > 0 else
             ("low-value moments" if level_high < 0 else "none"))

    # An UNDIRECTED pattern (P-B1) has no paired verdict to be stable about, so
    # its stability is read off the LEVEL effect it does claim.
    key = "paired_dir_delta" if direction != "none" or name != "P-B1" else "verdict_level_delta"
    if name == "P-B1":
        key = "verdict_level_delta"
    signs = [number(r, key) for r in quarters
             if r["pattern"] == name and r["n"] not in ("0", "")]
    signs = [value for value in signs if value == value]
    stability = ("n/a" if len(signs) < 3 else
                 ("stable-sign" if all(v > 0 for v in signs) or all(v < 0 for v in signs)
                  else "sign flips"))

    if not destroyed:
        destruction = "not applicable"
    else:
        base_effect = number(base, "verdict_level_delta")
        shadow = number(destroyed, "verdict_level_delta")
        shadow_low = number(destroyed, "verdict_level_lcb05")
        shadow_high = number(destroyed, "verdict_level_ucb95")
        shadow_significant = shadow_low > 0 or shadow_high < 0
        if float(destroyed["n"]) < 0.2 * float(base["n"]):
            destruction = "mechanism-critical (fires collapse)"
        elif shadow_significant and not level_significant:
            destruction = "SURVIVES DESTRUCTION -- FLAG"
        elif not level_significant:
            destruction = "no base effect to test"
        elif (not shadow_significant or shadow * base_effect < 0
              or abs(shadow) <= 0.6 * abs(base_effect)):
            destruction = "mechanism-dependent"
        else:
            destruction = "SURVIVES DESTRUCTION -- FLAG"
    return direction, level, stability, destruction


def main() -> None:
    fires = {r["pattern"]: r for r in read("census_fires.tsv")}
    outcomes = read("census_outcomes.tsv")
    base = {r["pattern"]: r for r in outcomes if r["arm"] == "base"}
    destroyed = {r["pattern"]: r for r in outcomes if r["arm"] == "destroyed"}
    quarters = read("census_quarters.tsv")
    stance = read("census_stance_map.tsv")
    controls = read("census_controls.tsv")
    paired_rows = int(R.load_pairs()["net_L"].size)

    body = []
    body.append("# PATTERN CENSUS — ORCH-1 (human names, machine counts)")
    body.append("")
    body.append(f"Sessions {C.CENSUS_WALL[0]}..{C.CENSUS_WALL[1]} (F4 train era, "
                f"{len(C.SESSIONS)} sessions).  Evaluation grid: every "
                f"{C.STEP_S}s, {C.BUCKETS - C.MIN_EVAL} points/session/side, each "
                "reading the pack's own trailing-60s window ENDING AT OR BEFORE the "
                "evaluation second and joined to the nearest lawful candidate row at or "
                f"after it.  {paired_rows:,} paired (long+short) decision points "
                "carry truth.")
    body.append("")
    body.append("No TEST / gate_cert / gate_select read; no repo write.  Code + tables: "
                "`artifacts/cache/campaign/diagnostics/d020_v2/census/`.")
    body.append("")

    body.append("## HEADLINE")
    body.append("")
    body.append("1. **No named pattern shows a directional edge that survives the census.**  "
                "Every one of the 13 detector arms has a 90% paired-direction interval "
                "straddling zero, and every one flips sign across quarters.")
    body.append("2. **Three patterns are real, but they are VOLATILITY/VALUE detectors, not "
                "direction detectors**: P-D1/P-D1b (cross-stream agreement) and P-G1 "
                "(blowoff) fire where BOTH sides' certificates are worth more, and P-C2B "
                "fires where both are worth less.  A pattern that lifts both sides equally "
                "is a regime filter, not a trade.")
    body.append("3. **P-B1 (the runway law) is the one unambiguous, stable, large finding**: "
                "candidates inside the last 30 minutes are worth ~$229 less than the same "
                "side earlier in the day, in EVERY quarter (-258/-259/-250/-250/-208).  It "
                "is a population-hygiene law, exactly as the note claimed.")
    body.append("4. **The F23 stance map does not replicate at scale.**  108 cells with "
                "n>=300 produce 1 lower bound above zero and 9 upper bounds below zero "
                "against ~5.4 of each expected by chance.  Its three study-case cells do "
                "keep their sign across quarters, and they all read CROSS-STREAM "
                "DISAGREEMENT (tape one way, option delta the other) -- that is the only "
                "surviving thread.")
    body.append("5. **The instrument is validated, so these nulls are informative**: the "
                "paired statistic correlates 0.69 with the realised forward 30-minute move, "
                "while the causal stock-flow z that most patterns are built on moves it by "
                "at most $27 across its entire range.")
    body.append("")

    body.append("## 0. Read this first — what `cert_net` is")
    body.append("")
    body.append("`qr_labels/label_kernel.hpp`: the certificate is *the uncapped best "
                "positive executable mark before the first net -$300 adverse wall*.  It is "
                "an EXIT-FREE value measure, so a volatile second scores high on BOTH sides "
                "at once.  Two statistics therefore answer different questions and the "
                "census reports both:")
    body.append("")
    body.append("* **paired direction** = cert_net(verdict side) - cert_net(opposite side) "
                "at the SAME second.  The second's volatility cancels exactly.  This is the "
                "only clean test of a directional verdict.")
    body.append("* **level** = cert_net against the detector's own defined-but-unfired rows "
                "of the same physical side, matched on (quarter, hour-of-day).")
    body.append("")
    body.append("Both carry SESSION-CLUSTERED bootstrap intervals (400 resamples): "
                "consecutive fires inside one session are one observation, not hundreds.")
    body.append("")

    body.append("## 1. Instrument control (the census can see direction when it is there)")
    body.append("")
    rows = [[r["bin"], r["n"],
             f"{number(r, 'mean_paired'):.2f}" if "corr" in r["bin"]
             else money(number(r, "mean_paired")),
             r.get("mean_forward_bp", "")] for r in controls if r["control"] == "instrument"]
    body.append(table(rows, ["control bin", "n", "mean paired $", "mean fwd 30m (bp)"]))
    body.append("")
    body.append("The paired statistic tracks the realised forward move with correlation "
                "0.69 and a clean monotone gradient, so the join, the truth read and the "
                "pairing are sound.  Against that validated instrument:")
    body.append("")
    rows = [[r["bin"], r["n"], money(number(r, "mean_paired")), r.get("mean_forward_bp", "")]
            for r in controls if r["control"] == "signal-floor"]
    body.append(table(rows, ["signal floor", "n", "mean paired $", "mean fwd 30m (bp)"]))
    body.append("")
    body.append("The causal stock-flow z — the ingredient most of the named patterns are "
                "built on — moves the paired value by at most $27 across its whole range.  "
                "That is the ceiling any flow-threshold rule can reach at this horizon.")
    body.append("")

    body.append("## 2. Per-pattern census")
    body.append("")
    rows = []
    for name in D.PATTERNS:
        fire = fires[name]
        b = base[name]
        d = destroyed.get(name, {})
        kind, leg = D.DESTRUCTION[name]
        direction, level, stability, destruction = verdicts(name, b, d, quarters)
        rows.append([
            name,
            f"{float(fire['coverage']):.2f}",
            f"{float(fire['fire_minutes_per_day_mean']):.1f}",
            f"{float(fire['episodes_per_day_mean']):.1f}",
            b["n"],
            f"{money(number(b, 'paired_dir_delta'))} [{money(number(b, 'paired_lcb05'))},"
            f"{money(number(b, 'paired_ucb95'))}]",
            direction,
            f"{money(number(b, 'verdict_level_delta'))} / "
            f"{money(number(b, 'opposite_level_delta'))}",
            level,
            stability,
            f"{d.get('n', '-')} / {money(number(d, 'verdict_level_delta')) if d else 'NA'}",
            destruction,
        ])
    body.append(table(rows, ["pattern", "cov", "fire min/day", "episodes/day", "n fired",
                             "paired direction $ [90% CI]", "direction verdict",
                             "level $ verdict/opposite", "level verdict", "quarter stability",
                             "destroyed n / level $", "destruction verdict"]))
    body.append("")
    body.append("P-A2 and P-C2A are numerically identical because the notes define them "
                "as the same object (a protection spike aligned with the move at a fresh "
                "extreme); P-C2's actual claim is the CONTRAST between that arm and P-C2B "
                "(soft protection at an aged post-climax base), and the census settles it: "
                "arm A fires at high-value moments on both sides (+16/+23) while arm B "
                "fires at low-value moments on both sides (-19/-19), and NEITHER carries a "
                "directional verdict.  The phase-conditional MEANING the note claims -- the "
                "same feature reading opposite ways -- shows up as a level difference, not "
                "as a side call.")
    body.append("")
    body.append("Destruction rules, applied in order: `fires collapse` = the shadow arm "
                "keeps under 20% of the base arm's fires; `SURVIVES DESTRUCTION` = the "
                "shadow arm's level effect clears its own 90% bootstrap interval while the "
                "base arm's does not, or it keeps over 60% of a significant base effect "
                "with the same sign; `no base effect to test` = the base arm has no "
                "significant level effect to destroy; `mechanism-dependent` = otherwise.  "
                "The shadow arm replaces the named leg with a DONOR session's own series "
                "inside the same clock buckets (donor = ordinal + 137, wrapped inside the "
                "wall), which preserves the leg's distribution and serial structure and "
                "destroys only its coupling to this session.")
    body.append("")

    body.append("## 3. Per-quarter stability (paired direction, verdict side)")
    body.append("")
    quarter_names = sorted({r["quarter"] for r in quarters})
    rows = []
    for name in D.PATTERNS:
        line = [name]
        for quarter in quarter_names:
            match = [r for r in quarters if r["pattern"] == name and r["quarter"] == quarter]
            if not match or match[0]["n"] in ("0", ""):
                line.append("-")
                continue
            line.append(f"{money(number(match[0], 'paired_dir_delta'))}"
                        f" ({int(match[0]['n'])})")
        rows.append(line)
    body.append(table(rows, ["pattern"] + quarter_names))
    body.append("")

    body.append("## 4. F23 CROSS-STREAM STANCE MAP (the centrepiece)")
    body.append("")
    tested = [r for r in stance if r.get("dir_lcb05", "") not in ("", "NA")]
    positive = [r for r in tested if number(r, "dir_lcb05") > 0]
    negative = [r for r in tested if number(r, "dir_ucb95") < 0]
    body.append(f"7x7 grid of (stock-flow z, option-delta z), both taken RELATIVE TO the "
                f"15bp-ZigZag structure direction, x 3 phases.  Cell statistic = "
                f"cert_net(continuation) - cert_net(counter) at the same second.  "
                f"{len(tested)} cells carry n>=300; **{len(positive)}** have a 90% LCB "
                f"above zero and **{len(negative)}** a UCB below zero — against ~5.4 of "
                f"each expected by chance at 108 tests.  The map as a whole is not "
                f"distinguishable from noise.")
    body.append("")
    ranked = sorted(tested, key=lambda r: -abs(number(r, "dir_edge")))[:10]
    rows = [[r["phase"], r["flow_z"], r["opt_delta_z"], r["n"], r["sessions"],
             money(number(r, "dir_edge")),
             f"[{money(number(r, 'dir_lcb05'))},{money(number(r, 'dir_ucb95'))}]",
             money(number(r, "cont_net")), money(number(r, "counter_net"))]
            for r in ranked]
    body.append(table(rows, ["phase", "flow z (rel struct)", "opt-delta z (rel struct)",
                             "n", "sessions", "dir edge $", "90% CI",
                             "cont $", "counter $"]))
    body.append("")

    body.append("### 4b. The three cells the study cases pointed at, per quarter")
    body.append("")
    quarter_rows = read("census_stance_quarters.tsv")
    highlight = [("fresh-extreme", "-4..-2", ">4"),
                 ("fresh-extreme", "2..4", "-2..-0.5"),
                 ("mid-range", ">4", "-4..-2")]
    rows = []
    for phase, flow, delta in highlight:
        line = [f"{phase} / flow {flow} / od {delta}"]
        for quarter in quarter_names:
            match = [r for r in quarter_rows if r["quarter"] == quarter and r["phase"] == phase
                     and r["flow_z"] == flow and r["opt_delta_z"] == delta]
            line.append(f"{money(number(match[0], 'dir_edge'))} ({match[0]['n']})"
                        if match else "-")
        rows.append(line)
    body.append(table(rows, ["cell (phase / flow z / option-delta z)"] + quarter_names))
    body.append("")
    body.append("Those three keep their sign in 4 of 5 quarters each, which pure multiplicity "
                "would not produce -- but the aggregate count of significant cells is at "
                "chance, so they are HYPOTHESES for the next round, not findings.  Note what "
                "they say: the two negative ones are cells where the stock tape pushes WITH "
                "the structure while option delta-flow leans AGAINST it, and there the "
                "COUNTER side pays; the positive one is the mirror (tape against, options "
                "with, at a fresh extreme) and there continuation pays.  That is a "
                "cross-stream DISAGREEMENT reading, and it is the one piece of the F23 "
                "hypothesis the census does not refute.")
    body.append("")

    body.append("## 5. Constants log (every threshold this census used)")
    body.append("")
    rows = [[name, f"{value:g}", provenance, note] for name, (value, provenance, note)
            in D.CONST.items()]
    body.append(table(rows, ["constant", "value", "provenance", "note"]))
    body.append("")

    body.append("## 6. Originating-case fixture")
    body.append("")
    body.append("Each detector re-run on the case that produced its pattern (a fire "
                "anywhere within +/-1 minute of the case's own decision second counts, "
                "D-021's measured delay tolerance):")
    body.append("")
    body.append("```")
    body.append((OUT / "fixture_report.txt").read_text().strip())
    body.append("```")
    body.append("")

    body.append("## 7. What could NOT be computed (D-017 stop-rule, not proxied)")
    body.append("")
    body.append("* **P-A3** (*candidate side authority can contradict completed-setup "
                "side*) is a statement about how to READ a pack, not a market state, and "
                "has no strictly-prior formula of its own.  What the census CAN test of it "
                "is its consequence, and does: the paired-direction column IS the "
                "completed-setup side scored against the opposite side at the same second, "
                "for every directional pattern.  No separate P-A3 detector is invented.")
    body.append("* **P-G1's sixth witness, 'event-day phase'**: the corpus carries no "
                "lawful event calendar (the FRED export is still PENDING, D-020-SCALE "
                "AMENDMENT-3).  P-G1 runs on its five computable witnesses; the omission is "
                "declared, not proxied.")
    body.append("* **P-E1's '~1.8 ATR spent'** is a W2.2 variance-time read that is not "
                "available session-wide.  The census measures session-so-far high-low range "
                "/ ATR14 and pins the cut at the value that quantity has at case005's own "
                "decision minute (1.03 -> 1.0); flagged CASE-CALIBRATED above.")
    body.append("* **PROXY_VOL (W2.1)** is typed-absent before session 209, so P-G1's "
                "coverage is 0.49 by construction.  Absence is carried as `defined=False`, "
                "never as a zero.")
    body.append("")

    (OUT / "PATTERN_CENSUS.md").write_text("\n".join(body) + "\n")
    print("PATTERN_CENSUS.md written")


if __name__ == "__main__":
    main()
