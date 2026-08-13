#!/usr/bin/python3
"""PORT M2 SHEET BUILDER — candidate id -> the 14-section compact-text sheet.

design/PORT_M2_SHEETS_SPEC.md §1 (the sheet), §2 (leak fixture + D-042
completeness certificate).  Gate P-M2a.

    build(cid, mode)  ->  Sheet(text, appendix, certificate, sidecar)

MODE SWITCH (spec §1 S14 / §3)
  BLIND  renders S1..S13 and NOTHING else.  S14 does not exist in the object.
  STUDY  renders S1..S13 *plus* a SEPARATE S14 appendix file.  The appendix is
         a different artefact with its own path, because the protocol releases
         it only after the call has been committed to git — a mode that
         appended outcomes to the same file could not implement that sequencing
         at all.

D-042 COMPLETENESS CERTIFICATE
  Every owned section must render, carry rows, and stay inside its token
  budget.  A sheet that fails any of those is CERTIFIED=0 and no reader round
  may run on it (§2: "a sheet missing any owned section fails certification").
  The certificate travels three ways: printed in S1 (the section checklist with
  per-section row counts, the D-042 shape), in the per-sheet sidecar JSON, and
  in the run-level STREAM_RECEIPT.tsv.

Run (pilot):
  lab/run.sh port-m2a -- /usr/bin/python3 engine/port_m2/pilot.py
"""
import hashlib
import json
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                    # noqa: E402
import assemble as A                      # noqa: E402
import sections as SEC                    # noqa: E402
import tape as TAPE                       # noqa: E402
import availability as AV                 # noqa: E402

PARAMS = {
    "spec_section": "§1 sheet + §2 certificate (P-M2a)",
    "sheets_version": MC.SHEETS_VERSION,
    "blind_sections": list(MC.BLIND_SECTIONS),
    "study_sections": list(MC.STUDY_SECTIONS),
    "section_budget_tokens": dict(MC.SECTION_BUDGET),
    "token_proxy": MC.TOKEN_PROXY_ID,
    "token_proxy_rule": "alpha run L -> max(1, ceil(L/5)); digit run L -> "
                        "ceil(L/3); every other non-space char -> 1; newline "
                        "-> 1 (no BPE tokenizer exists on this host)",
    "anchor": "entry_mid; every price also printed as a signed integer tick "
              "offset from it (§1 'integer ticks where possible')",
    "s6_raw_window_sec": TAPE.RIBBON_RAW_SEC,
    "s6_digest_window_sec": TAPE.RIBBON_DIGEST_SEC,
    "s6_episode_max_pre": SEC.S6_EPISODE_MAX_PRE,
    "s6_episode_max_in_raw_window": SEC.S6_EPISODE_MAX_IN,
    "s6_gap_sec": SEC.S6_GAP_SEC,
    "s6_shrink_step": SEC.S6_SHRINK_STEP,
    "s6_budget_rule": "the raw window is BUDGET-FILLED: as many of the newest "
                      "events as the S6 token budget allows are rendered "
                      "event-by-event, and the older remainder of the 90s "
                      "folds into the same gap-clustered episode digests as "
                      "the 10-minute pre-window (lossless membership, no "
                      "minimum-size filter anywhere)",
    "clocknorm_sessions": SEC.CLOCKNORM_SESSIONS,
    "clocknorm_bin_sec": SEC.BIN_SECONDS,
    "availability_join": "strict availability_ts < decision_ts (D-057 pinned "
                         "reading, CC-M2-1.2 blessed); lag table = "
                         + AV.LAG_TABLE,
    "sidecar_source_paths": "ABSOLUTE (CC-M2-1.4)",
    "known_traps": sorted(MC.KNOWN_TRAPS),
    "roster": "m1/generation_v3 union rosters (ORACLE_FREEZE.tsv)",
    "mid_sanity": "D-054 SANE seconds only (b7_sane owns the mask)",
}


def params_hash():
    return MC.params_hash(PARAMS)


class Sheet(object):
    __slots__ = ("cid", "mode", "text", "appendix", "certificate", "sidecar",
                 "sha256", "appendix_sha256", "appendix_sidecar")


def _sec_metrics(name, lines):
    text = "\n".join(lines) + "\n"
    m = MC.text_metrics(text)
    m["rows"] = len(lines)
    m["section"] = name
    m["budget"] = MC.SECTION_BUDGET[name]
    m["over_budget"] = 1 if m["tokens_proxy"] > m["budget"] else 0
    return text, m


def _s1_header(case, order, metrics, mode, phash, refusals, refused_derived):
    """S1 renders LAST (it reports on the others) and is placed FIRST."""
    L = ["S1 HEADER"]
    L.append(MC.row("  cid", MC.fstr(case.cid, 26),
                    " sheets_version=" + MC.SHEETS_VERSION,
                    " mode=" + mode))
    L.append(MC.row("  asset/session", MC.fstr(case.asset, 4),
                    case.trade_date.isoformat(),
                    " era=" + case.era,
                    " phase_dec=" + MC.fstr(SEC.X.PHASE_NAMES[case.phase_dec], 6),
                    " phase_conf=" + MC.fstr(SEC.X.PHASE_NAMES[case.phase_conf], 6),
                    " iid=" + str(case.s.iid)))
    L.append(MC.row("  decision", "sec=" + MC.fsec(case.dec_sec),
                    " (" + str(case.dec_sec) + ")",
                    " utc=" + MC.futc(case.decision_ts),
                    " conf_sec=" + MC.fsec(case.conf_sec),
                    " lag=" + str(case.dec_sec - case.conf_sec) + "s"))
    L.append(MC.row("  side", MC.fstr("LONG" if case.side > 0 else "SHORT", 6),
                    " families=" + ",".join(MC.fam_names(case.fam_mask)),
                    " rungs=" + ",".join(MC.rung_names(case.rung_mask)) + "xATR",
                    " level_families=" + (",".join(MC.level_fam_names(case.level_mask)) or "none"),
                    " flags=" + (",".join(MC.bits_to_names(case.flags, MC.FLAG_NAMES)) or "none")))
    # D-071: the candidate DECLARES its class — "Opus needs to know exactly
    # what it is".  The class is observable at generation (the emitting family
    # IS the mechanism); the driver family and every other tag are named too.
    cls, driver, others = MC.class_of(case.fam_mask)
    L.append(MC.row("  CANDIDATE CLASS", MC.fstr(cls, 22),
                    " driver_family=" + MC.fstr(str(driver), 13),
                    " other_tags=" + (",".join(others) or "none"),
                    " cross_class=" + (",".join(MC.classes_of(case.fam_mask)[1:])
                                       or "none"),
                    " (D-071; CC-M1-11.4 priority)"))
    L.append(MC.row("  anchor", MC.fnum(case.anchor, 1, 4).strip(),
                    " tick_px=" + MC.fnum(case.tick_px, 1, 6).strip(),
                    " tick_$=" + MC.fnum(case.tick_usd, 1, 2).strip(),
                    " mult=" + str(case.mult),
                    " ATR14_prev=$" + MC.fnum(case.atr, 1, 2).strip()))
    sh = MC.spec_shas()
    L.append(MC.row("  spec_shas", "m2=" + sh["m2_spec_sha16"],
                    " m1b=" + sh["m1b_spec_sha16"],
                    " m1=" + sh["m1_spec_sha16"],
                    " m0=" + sh["m0_spec_sha16"]))
    L.append(MC.row("  params_hash", phash))
    L.append("  D-042 COMPLETENESS CERTIFICATE (owned sections; rows = rendered lines)")
    L.append("    section  title                              status  rows")
    n_fail = 0
    for name in order:
        m = metrics[name]
        status = "OK"
        if m["rows"] <= 1:
            status = "EMPTY"
        elif m["over_budget"]:
            status = "OVER"
        if status != "OK":
            n_fail += 1
        L.append(MC.row("   ", MC.fstr(name, 8),
                        MC.fstr(MC.SECTION_TITLES[name], 34),
                        MC.fstr(status, 7), MC.fint(m["rows"], 5)))
    L.append(MC.row("   ", MC.fstr("S1", 8),
                    MC.fstr(MC.SECTION_TITLES["S1"], 34),
                    MC.fstr("OK", 7), MC.fstr("self", 5)))
    L.append(MC.row("  certified", "1" if (n_fail == 0 and not refusals) else "0",
                    " n_sections=" + str(len(order) + 1),
                    " n_failed=" + str(n_fail),
                    " n_leak_refusals=" + str(len(refusals)),
                    " n_refused_derived=" + str(len(refused_derived)),
                    " guard_checks=" + str(case.guard.checks)))
    if refused_derived:
        # V1.1: named, not just counted — the reader must know WHICH field is
        # absent and why, on the face of the sheet.
        L.append("  REFUSED DERIVED FIELDS (inputs refused; printed as '"
                 + MC.NA + "')")
        for e in refused_derived:
            L.append(MC.row("   ", MC.fstr(e["key"], 26), e["reason"]))
    return L, n_fail


def build(cid, mode=MC.MODE_BLIND, with_appendix=False):
    """Render one candidate.  Raises LeakRefusal / SealRefusal rather than
    emitting a sheet that a guard rejected.

    `with_appendix` renders the S14 appendix BESIDE a BLIND sheet (P-M2b era
    builds: the reader gets the blind sheet, the protocol releases the appendix
    only after the call is committed).  The blind sheet's bytes are unchanged by
    it — S1 reports on the blind sections only — and the appendix's own sidecar
    values are kept in a SEPARATE list so no outcome number can reach the blind
    sidecar.
    """
    if mode not in MC.MODES:
        raise ValueError("mode %r" % mode)
    MC.verify_spec()
    case = A.Case(cid, mode=mode)
    phash = params_hash()

    sidecar_vals = []
    appendix_vals = []
    refused = []
    sink = [sidecar_vals]

    def put(key, value, source, source_key):
        if isinstance(value, (np.integer,)):
            value = int(value)
        elif isinstance(value, (np.floating,)):
            value = float(value)
        if isinstance(value, float) and not np.isfinite(value):
            value = None
        sink[0].append({"key": key, "value": value,
                        "source": _rel(source),
                        "source_key": source_key})

    def _refuse(key, reason):
        """REFUSED-CONSISTENCY ACCOUNTING (V1.1, spec §2).

        A derived field whose inputs are refused carries no value, prints the
        typed-missing glyph, and is COUNTED here.  A refusal is LAWFUL — it does
        not fail the certificate the way a missing section or a D-057 leak
        refusal does — but it must be visible, because "how many of this sheet's
        derived fields could not be computed" is a question the reader protocol
        has to be able to answer per sheet and per corpus.
        """
        refused.append({"key": key, "reason": reason})
        put(key, None, "derived(refused)", reason)

    put.refuse = _refuse

    order = [s for s in MC.BLIND_SECTIONS if s != "S1"]
    body = {}
    metrics = {}
    for name in order:
        lines = SEC.RENDERERS[name](case, put)
        text, m = _sec_metrics(name, lines)
        body[name] = text
        metrics[name] = m

    s1_lines, n_fail = _s1_header(case, order, metrics, mode, phash,
                                  case.guard.refusals, refused)
    s1_text, s1_m = _sec_metrics("S1", s1_lines)
    metrics["S1"] = s1_m
    if s1_m["over_budget"]:
        n_fail += 1

    parts = [s1_text] + [body[n] for n in order]
    text = "\n".join(parts)
    total = MC.text_metrics(text)
    certified = 1 if (n_fail == 0 and not case.guard.refusals
                      and total["tokens_proxy"] <= MC.SHEET_BUDGET_BLIND) else 0

    sh = Sheet()
    sh.cid = cid
    sh.mode = mode
    sh.text = text
    sh.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    sh.appendix = None
    sh.appendix_sha256 = None
    app_m = None
    if mode == MC.MODE_STUDY or with_appendix:
        sink[0] = appendix_vals
        try:
            lines = SEC.RENDERERS["S14"](case, put)
        finally:
            sink[0] = sidecar_vals
        atext, app_m = _sec_metrics("S14", lines)
        metrics["S14"] = app_m
        sh.appendix = atext
        sh.appendix_sha256 = hashlib.sha256(atext.encode("utf-8")).hexdigest()
        if mode == MC.MODE_STUDY:
            # P-M2a behaviour: a STUDY sidecar is the study artefact and carries
            # the appendix values inline.  A BLIND sidecar never does.
            sidecar_vals.extend(appendix_vals)

    sh.certificate = {
        "cid": cid,
        "mode": mode,
        "certified": certified,
        "n_failed_sections": n_fail,
        "n_leak_refusals": len(case.guard.refusals),
        "leak_refusals": [list(map(str, r)) for r in case.guard.refusals],
        # V1.1: lawful refusals of DERIVED fields (inputs refused).  Counted,
        # named, and NOT a certification failure — see _refuse.
        "n_refused_derived": len(refused),
        "refused_derived": list(refused),
        "guard_checks": case.guard.checks,
        "sections": {k: metrics[k] for k in sorted(metrics)},
        "sheet": total,
        "sheet_budget": MC.SHEET_BUDGET_BLIND,
        "sheet_sha256": sh.sha256,
        "appendix_sha256": sh.appendix_sha256,
        "appendix": app_m,
        "sheets_version": MC.SHEETS_VERSION,
        "token_proxy": MC.TOKEN_PROXY_ID,
        "params_hash": phash,
        "spec_shas": MC.spec_shas(),
        "decision_ts": case.decision_ts,
        "era": case.era,
        "asset": case.asset,
        "trade_date": case.trade_date.isoformat(),
    }
    sh.sidecar = {
        "cid": cid,
        "mode": mode,
        "certificate": sh.certificate,
        "anchor_price": case.anchor,
        "tick_px": case.tick_px,
        "mult": case.mult,
        "roster_row": int(case.i),
        "receipts": {
            "roster": _rel(case.roster_path),
            "session": _rel(case.session_path),
            "levels": _rel(case.levels_path),
            "profile": _rel(case.profile_path),
            "prior_profile": _rel(case.prior_profile_path),
            "fvol": _rel(case.fvol_path),
            "events": _rel(os.path.join(TAPE.EVENTS_DIR, case.asset,
                                        "%08d.npz" % case.d8)),
            "bars": _rel(os.path.join(MC.M0_ROOT, "bars_%s.tsv" % case.asset)),
            "walls": _rel(os.path.join(MC.M0_ROOT, "walls.json")),
            "cost": _rel(os.path.join(MC.M0_ROOT, "census_a_cost.tsv")),
            "family_census": _rel(A.FAM_VALUE),
            "oracle_legs": _rel(A.ORACLE_LEGS),
            "lag_table": _rel(AV.LAG_TABLE),
        },
        "known_traps": MC.KNOWN_TRAPS,
        "values": sidecar_vals,
    }
    sh.appendix_sidecar = (
        None if (mode == MC.MODE_STUDY or not appendix_vals) else
        {"cid": cid, "mode": "S14_APPENDIX",
         "appendix_sha256": sh.appendix_sha256,
         "certificate_appendix": app_m, "values": appendix_vals})
    return sh


def _rel(p):
    """CC-M2-1.4 (BINDING): sidecar source paths are ABSOLUTE.

    P-M2a emitted workspace-relative paths and the orchestrator's verification
    hit a relative-root ambiguity (which root does 'artifacts/...' mean when the
    sidecar is read from anywhere but /workspace?).  Every source path a sidecar
    names is now an absolute filesystem path.  The name is kept so the call
    sites read the same; the behaviour is inverted.

    A value's source is either a FILE (now always absolute) or an explicitly
    typed non-file tag `derived...` — a quantity this builder computes from
    receipts already named elsewhere in the sidecar.  Tags are left alone; a
    tag is never silently turned into a path.
    """
    if not p:
        return None
    p = str(p)
    if p.startswith("derived"):
        return p
    return AV.abs_source(p)


# ------------------------------------------------------------------ output --
def emit(sh, out_dir, sidecars=True):
    """Write sheet / appendix / sidecar under out_dir (D-018: under M2_ROOT).

    `sidecars=False` writes the reader-facing artefacts only (sheet + S14
    appendix).  Era-scale renders use it: the sidecar is the hand-verification
    aid, ~2x the sheet's bytes, and is regenerated on demand for any candidate
    by re-running the builder (the sheet is a pure function of the receipts).
    """
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, "%s.%s.sheet.txt" % (sh.cid, sh.mode))
    MC.write_text(p, sh.text)
    if sidecars:
        MC.write_json(os.path.join(out_dir, "%s.%s.sidecar.json"
                                   % (sh.cid, sh.mode)), sh.sidecar)
    if sh.appendix is not None:
        MC.write_text(os.path.join(out_dir, "%s.S14.appendix.txt" % sh.cid),
                      sh.appendix)
        if sidecars and sh.appendix_sidecar is not None:
            MC.write_json(os.path.join(out_dir, "%s.S14.sidecar.json" % sh.cid),
                          sh.appendix_sidecar)
    return p


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: sheets.py <candidate_id> [BLIND|STUDY]\n")
        return 2
    mode = sys.argv[2] if len(sys.argv) > 2 else MC.MODE_BLIND
    sh = build(sys.argv[1], mode)
    sys.stdout.write(sh.text)
    if sh.appendix:
        sys.stdout.write("\n" + sh.appendix)
    sys.stderr.write(json.dumps({"certified": sh.certificate["certified"],
                                 "tokens": sh.certificate["sheet"],
                                 "sha256": sh.sha256}, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
