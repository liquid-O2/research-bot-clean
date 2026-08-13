#!/usr/bin/python3
"""PORT M0 census driver — ONE detached run.sh job carrying spec §6-§10.

Stage 0  poll  artifacts/workflow_memory/runs/port-m0-substrate.rc every 60s,
               forever (no timeout).  rc == 0 -> run the censuses.  rc != 0 ->
               exit 3 immediately; the orchestrator handles a failed substrate.
Stage 1  c_a   §6  cost           (must precede c_c: it supplies the
                                   per-(asset,year,phase) median spread that
                                   floors the ZigZag rungs)
Stage 2  c_b   §7  offer
Stage 3  c_c   §8  roster (sub-pass 1) -> wall (2) -> certificates + DP (3)
Stage 4  c_d   §9  recall
Stage 5  s5    §10 M0_REPORT.md
Stage 6  byte-identity check B (§10/§11.2): every census re-run on
               2024-06 x one asset into two scratch trees; output sha256 must
               match.  Result -> m0/byte_identity_B.tsv.

Everything is written under artifacts/cache/port/m0/ (D-018).  Internal pools
never exceed WORKERS processes.  No RNG anywhere.
"""
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import census_common as X
import c_a_cost as CA
import c_b_offer as CB
import c_c_roster as CC
import c_d_recall as CD
import s5_report as S5

RUNS_DIR = "/workspace/artifacts/workflow_memory/runs"
SUBSTRATE_RUN = "port-m0-substrate"
POLL_SECONDS = 60
WORKERS = 10

BYTEID_ASSET = "SI"
BYTEID_MONTHS = {"2024-06"}
BYTEID_ROOT = "_byteid_B"


def wait_for_substrate():
    """Poll the substrate rc forever; return its integer rc."""
    rc_path = os.path.join(RUNS_DIR, SUBSTRATE_RUN + ".rc")
    pid_path = os.path.join(RUNS_DIR, SUBSTRATE_RUN + ".pid")
    n = 0
    while True:
        if os.path.exists(rc_path):
            with open(rc_path) as fh:
                txt = fh.read().strip()
            try:
                rc = int(txt)
            except ValueError:
                C.hb("poll: %s.rc holds %r — treating as failure" %
                     (SUBSTRATE_RUN, txt))
                return 1
            C.hb("poll: %s.rc = %d after %d polls (%d min)"
                 % (SUBSTRATE_RUN, rc, n, n * POLL_SECONDS // 60))
            return rc
        alive = "?"
        try:
            with open(pid_path) as fh:
                pid = int(fh.read().strip())
            os.kill(pid, 0)
            alive = "pid %d alive" % pid
        except (OSError, ValueError, FileNotFoundError):
            alive = "pid not readable/alive"
        n += 1
        C.hb("poll %d: waiting for %s.rc (%s); next check in %ds"
             % (n, SUBSTRATE_RUN, alive, POLL_SECONDS))
        time.sleep(POLL_SECONDS)


def stage(n, msg):
    C.hb("=== STAGE %s: %s" % (n, msg))


# --------------------------------------------------- byte-identity check B --
def byte_identity_b():
    root = os.path.join(C.OUT_ROOT, BYTEID_ROOT)
    shutil.rmtree(root, ignore_errors=True)
    walls = None
    wp = os.path.join(C.OUT_ROOT, "walls.json")
    if os.path.exists(wp):
        import json
        with open(wp) as fh:
            walls = json.load(fh)["walls"]
    shots = {}
    for tag in ("run1", "run2"):
        d = os.path.join(root, tag)
        os.makedirs(d, exist_ok=True)
        C.hb("byte-id B %s: %s x %s" % (tag, BYTEID_ASSET,
                                        ",".join(sorted(BYTEID_MONTHS))))
        CA.run(assets=[BYTEID_ASSET], out_root=d, months=BYTEID_MONTHS,
               workers=WORKERS)
        CB.run(assets=[BYTEID_ASSET], out_root=d, months=BYTEID_MONTHS,
               workers=WORKERS)
        CC.run(assets=[BYTEID_ASSET], out_root=d, months=BYTEID_MONTHS,
               workers=WORKERS, walls=walls)
        CD.run(assets=[BYTEID_ASSET], out_root=d, months=BYTEID_MONTHS,
               workers=WORKERS)
        shots[tag] = dict(X.sha_dir(d))
    names = sorted(set(shots["run1"]) | set(shots["run2"]))
    rows = []
    for n in names:
        a = shots["run1"].get(n, "")
        b = shots["run2"].get(n, "")
        rows.append([BYTEID_ASSET, sorted(BYTEID_MONTHS)[0], n, a, b,
                     "MATCH" if (a and a == b) else "MISMATCH"])
    n_bad = sum(1 for r in rows if r[5] != "MATCH")
    X.write_tsv(X.out_path(C.OUT_ROOT, "byte_identity_B.tsv"),
                "§10/§11.2 byte-identity B",
                C.params_hash({"asset": BYTEID_ASSET,
                               "months": sorted(BYTEID_MONTHS),
                               "walls": "pinned from the full run"}),
                ["asset", "month", "output", "sha256_run1", "sha256_run2",
                 "verdict"], rows,
                extra=["c_a/c_b/c_c/c_d re-run twice on the same restricted "
                       "scope; the wall is pinned from the full run so this "
                       "measures census determinism, not the wall fit"])
    C.hb("byte-id B: %d outputs, %d mismatches" % (len(rows), n_bad))
    shutil.rmtree(root, ignore_errors=True)
    return n_bad


# --------------------------------------------------------------------- main --
def main():
    X.verify_spec()
    t_all = time.time()
    C.hb("census driver start; polling %s/%s.rc every %ds (no timeout)"
         % (RUNS_DIR, SUBSTRATE_RUN, POLL_SECONDS))
    rc = wait_for_substrate()
    if rc != 0:
        C.hb("census driver ABORT: substrate rc=%d — exiting rc=3" % rc)
        return 3

    assets = list(C.ASSET_ORDER)

    stage(1, "c_a cost census (§6)")
    t = time.time()
    CA.run(assets=assets, workers=WORKERS)
    C.hb("stage 1 done in %.0fs" % (time.time() - t))

    stage(2, "c_b offer census (§7)")
    t = time.time()
    CB.run(assets=assets, workers=WORKERS)
    C.hb("stage 2 done in %.0fs" % (time.time() - t))

    stage(3, "c_c roster + wall + DP (§8, three sub-passes)")
    t = time.time()
    CC.run(assets=assets, workers=WORKERS)
    C.hb("stage 3 done in %.0fs" % (time.time() - t))

    stage(4, "c_d recall census (§9)")
    t = time.time()
    CD.run(assets=assets, workers=WORKERS)
    C.hb("stage 4 done in %.0fs" % (time.time() - t))

    stage(5, "s5 report (§10)")
    S5.run()

    stage(6, "byte-identity check B (§10)")
    t = time.time()
    n_bad = byte_identity_b()
    C.hb("stage 6 done in %.0fs (%d mismatches)" % (time.time() - t, n_bad))

    stage(7, "s5 report refresh (picks up byte-identity B)")
    S5.run()

    C.hb("census driver COMPLETE in %.0fs" % (time.time() - t_all))
    return 0


if __name__ == "__main__":
    sys.exit(main())
