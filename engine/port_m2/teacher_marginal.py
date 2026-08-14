#!/usr/bin/python3
"""PORT M2 — THE D-078 CLEAN DIFF: what the teacher round's features are worth.

ONE harness, ONE matrix, ONE policy, TWO runs.  `m3_walk.py --run` with and
without `--drop-groups teacher_evidence`, over the identical 202-column matrix
whose last 18 columns are the teacher-evidence group.  Because the group is
APPENDED, the dropped run's feature block is byte-identical to the pre-teacher
matrix, and its era curve is checked against the COMMITTED pre-teacher curve as
the instrument's own control: if the control run does not reproduce the
committed numbers, the diff is not measuring the teacher features.

Writes provenance/port_m2/TEACHER_MARGINAL.tsv.
"""
import os
import sys

TF = "/workspace/artifacts/cache/port/m3/walk_tf"
MATRIX_NPZ = "/workspace/artifacts/cache/port/m3/matrix/matrix.npz"
NOTF = "/workspace/artifacts/cache/port/m3/walk_notf"
COMMITTED = "/workspace/provenance/port_m3/ERA_CURVE.tsv"
PROV = "/workspace/provenance/port_m2"


def read(path):
    rows, hdr = {}, None
    with open(path) as fh:
        for ln in fh:
            if ln.startswith("#") or not ln.strip():
                continue
            f = ln.rstrip("\n").split("\t")
            if hdr is None:
                hdr = f
                continue
            rows[f[0]] = dict(zip(hdr, f))
    return rows


def num(v):
    try:
        return float(v)
    except Exception:                      # noqa: BLE001
        return None


GATES = (
    ("SEAT_LIVE", "tf_seat_live", 0.5, "PROVEN r1 2.62x / DECAYED r2"),
    ("SEAT_DEAD_TIME", "tf_seat_dead_time", 0.5, "PROVEN r1 0.04x / WEAKENED"),
    ("PHASE_SPENT", "tf_phase_spent", 0.5, "PROVEN r1 0.54x / HOLDS_WEAK"),
    ("COV_SWEET_20_60", "tf_cov_sweet_20_60", 0.5, "PROVEN r1 2.00x / BROKEN"),
    ("capacity_room", "tf_capacity_room", 0.5, "PROVEN r1 1.70x"),
    ("capacity_big", "tf_capacity_big", 0.5, "PROVEN r1 2.23x / BROKEN r2"),
    ("LEVEL_VIRGIN", "tf_level_virgin", 0.5, "SUPPORTED r1 1.67x / UNSTABLE"),
    ("LEVEL_NEAR", "tf_level_near", 0.5, "leg, 0.97x alone in r1"),
    ("PHASE_OPEN_RESET", "tf_phase_open_reset", 0.5, "UNSTABLE r1 1.65x"),
    ("NAMED_TRIAD", "tf_named_triad", 0.5, "SUPPORTED r1 1.77x pooled"),
    ("NAMED_TRIAD_soft", "tf_named_triad_soft", 0.5, "PROVEN r1 1.64x"),
)


def cue_ladder():
    """Every shipped teacher GATE, re-measured on the whole D-088 era ladder.

    TEACHER_FEATURES_V1 §7 is explicit that its numbers are six days of one
    era and that the harness must re-measure per era before any of them is
    allowed to carry weight.  This is that re-measurement, on 1.4M candidates
    across eight eras — the same target (D-021 winner), the same arithmetic,
    day-clustered intervals.
    """
    import numpy as np
    sys.path.insert(0, "/workspace/engine/port_m2")
    sys.path.insert(0, "/workspace/engine/port_m3")
    import panel_score as PS
    import m3_common as M3

    z = np.load(MATRIX_NPZ, allow_pickle=False)
    names = [str(x) for x in z["feature_names"]]
    era = z["era_idx"]
    d8 = z["d8"]
    y = z["y_winner"]
    X = z["X"]
    out = []
    for e in range(len(M3.ERA_NAMES)):
        m = np.nonzero((era == e) & np.isfinite(y))[0]
        if m.size == 0:
            continue
        base = float(y[m].mean())
        for label, col, cut, prior in GATES:
            v = X[m, names.index(col)]
            sel = m[np.isfinite(v) & (v >= cut)]
            if sel.size == 0:
                out.append([M3.ERA_NAMES[e], label, prior, 0, base, None,
                            None, None, None, None])
                continue
            yy = y[sel]
            cl = [str(int(x)) for x in d8[sel].tolist()]
            st = PS.cluster_mean(yy, cl)
            rate = float(yy.mean())
            dv = PS.cluster_mean(yy - base, cl)
            out.append([M3.ERA_NAMES[e], label, prior, int(sel.size),
                        round(base, 5), round(rate, 5),
                        round(rate / base, 4) if base > 0 else None,
                        round(st["ci_lo"], 5) if st else None,
                        round(st["ci_hi"], 5) if st else None,
                        (round(dv["p"], 6) if dv and dv.get("p") is not None
                         else None)])
    z.close()
    p = os.path.join(PROV, "TEACHER_CUE_ERA_LADDER.tsv")
    with open(p + ".tmp", "w", newline="\n") as fh:
        fh.write("# PORT M2 — every SHIPPED teacher gate re-measured on the "
                 "full D-088 era ladder (1.4M candidates, 8 eras)\n")
        fh.write("# target = D-021 winner (cert_close >= $1,000 AND MAE <= "
                 "$300 AND not walled); base = the ERA's own winner rate\n")
        fh.write("# ci_lo/ci_hi are CR1 intervals on the GATE's rate, "
                 "clustered by calendar day; p is on (rate - era base)\n")
        fh.write("\t".join(["era", "gate", "round1_2_verdict", "n", "era_base",
                            "gate_rate", "lift", "ci_lo", "ci_hi",
                            "p_vs_base"]) + "\n")
        for r in out:
            fh.write("\t".join("." if x is None else str(x) for x in r) + "\n")
    os.replace(p + ".tmp", p)
    sys.stderr.write("wrote %s (%d rows)\n" % (p, len(out)))


def main():
    if "--cue-ladder" in sys.argv:
        cue_ladder()
        if "--diff" not in sys.argv:
            return 0
    a = read(os.path.join(TF, "ERA_CURVE.tsv"))
    b = read(os.path.join(NOTF, "ERA_CURVE.tsv"))
    c = read(COMMITTED)
    cols = ("usd_per_session", "ci_lo", "ci_hi", "expectancy_usd",
            "capture_day_ceiling", "capture_oracle", "composed_usd_per_session",
            "composed_expectancy_usd", "policy")
    out = []
    n_repro = n_cmp = 0
    for era in sorted(set(a) | set(b)):
        ra, rb, rc = a.get(era, {}), b.get(era, {}), c.get(era, {})
        if rc:
            n_cmp += 1
            same = all(rb.get(k) == rc.get(k) for k in
                       ("usd_per_session", "expectancy_usd", "policy"))
            n_repro += int(same)
        row = [era, ra.get("status", "."), ra.get("n_eval_sessions", ".")]
        for k in cols:
            va, vb = num(ra.get(k)), num(rb.get(k))
            row += [ra.get(k, "."), rb.get(k, "."),
                    (round(va - vb, 4) if (va is not None and vb is not None)
                     else ".")]
        row.append("YES" if (rc and all(rb.get(k) == rc.get(k) for k in
                                        ("usd_per_session", "expectancy_usd",
                                         "policy"))) else
                   ("NO" if rc else "."))
        out.append(row)

    head = ["era", "status", "n_eval_sessions"]
    for k in cols:
        head += ["tf_" + k, "notf_" + k, "delta_" + k]
    head.append("control_reproduces_committed")
    os.makedirs(PROV, exist_ok=True)
    p = os.path.join(PROV, "TEACHER_MARGINAL.tsv")
    with open(p + ".tmp", "w", newline="\n") as fh:
        fh.write("# PORT M2 D-078 TEACHER-FEATURE MARGINAL (clean diff)\n")
        fh.write("# tf_* = m3_walk on the 202-column matrix; notf_* = the same "
                 "harness, same matrix, --drop-groups teacher_evidence (184 "
                 "columns, byte-identical to the pre-teacher block)\n")
        fh.write("# control_reproduces_committed: does the DROPPED run "
                 "reproduce provenance/port_m3/ERA_CURVE.tsv exactly?  If not, "
                 "the diff is not measuring the teacher features.\n")
        fh.write("\t".join(head) + "\n")
        for r in out:
            fh.write("\t".join(str(x) for x in r) + "\n")
    os.replace(p + ".tmp", p)
    sys.stderr.write("wrote %s (%d eras; control reproduces %d/%d)\n"
                     % (p, len(out), n_repro, n_cmp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
