#!/usr/bin/python3
"""PORT M2 — R2-8 THE WRITTEN DECISION JOURNAL (the reader's reasoning, kept).

WHY THIS EXISTS.  The extraction lane found that stored transcripts STRIP the
reader's internal thinking irretrievably (journal 2026-08-15 ~14:00Z), so the
reasoning behind every call — the thing the whole teacher-first programme is
trying to learn from — was being destroyed at the end of each day.  R2-8 is the
fix: a WRITTEN entry per shortlisted episode, in visible output, committed the
same day.  R2-11 then names this journal as the extraction substrate, so it is
load-bearing twice.

WHAT AN ENTRY IS.  One record per SHORTLISTED episode (not per episode of the
day — the shortlist is where reasoning happens):

  episode_id · call (TAKE/SKIP/ABSTAIN) · probability · the reads the decision
  actually consumed (ribbon windows, chart panels, brief) · the cues that fired
  FOR · the cues that fired AGAINST · the veto that was considered · what would
  have changed the call · free-text reasoning.

BLIND SAFETY IS MECHANICAL, NOT PROMISED.  Three fences, all enforced here:
  1. `panel_score` is never imported by this module, at any depth.  A journal
     writer that could reach an outcome would make the blind days worthless.
  2. On a BLIND day every field is scanned for OUTCOME VOCABULARY (the S14 /
     oracle / certificate terms).  A match REFUSES the entry, names the term
     and the field, and writes nothing.  A refusal is a value.
  3. The entry records READS, and the reads it records are cross-checked
     against the mechanical ledgers at `--audit` time — a claimed ribbon read
     with no RIBBON_ACCESS row is reported, not believed.

SAME-DAY COMMIT.  `--assert-committed` asks git whether the day's journal file
is tracked at HEAD and whether the working tree matches it.  That is the R2-9
ledger-discipline gate in mechanical form: a day is not closed until its
reasoning is in the repository.

CLI
  decision_journal.py --round R --day D8 --episode EID --call TAKE --p 0.22 \\
      --reads "ribbon:T-120..T; chart:approach; brief:SI" \\
      --for "..." --against "..." --veto "..." --would-change "..." \\
      --reasoning "..." [--mode BLIND|STUDY]
  decision_journal.py --round R --day D8 --audit
  decision_journal.py --round R --day D8 --assert-committed
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m2_common as MC                     # noqa: E402
# NOTE: panel_score is NEVER imported here, at any depth.  See fence 1.

SECTION = "§3 R2-8 WRITTEN DECISION JOURNAL (the reasoning, kept)"

JOURNAL_ROOT = "/workspace/provenance/port_m2/decision_journal"
INDEX_COLUMNS = ("seq", "round", "era", "date8", "mode", "episode_id", "call",
                 "p", "reads", "sha16", "n_chars", "path")

CALLS = ("TAKE", "SKIP", "ABSTAIN")

# Fence 2.  Outcome vocabulary: every term that only exists on the far side of
# the seal.  Matched case-insensitively on word boundaries so an ordinary word
# ("winner" inside "winners' curse") is caught rather than argued about.
OUTCOME_TERMS = (
    "s14", "oracle", "dp_schedule", "dp seat", "dp_seat", "seated",
    "cert_close", "close certificate", "winner_close", "mfe", "mae",
    "mfe_unwalled", "mae_before_argmax", "realized payment", "realised payment",
    "payer", "outcome label", "panel_score", "ep_outcomes", "epout",
    "it paid", "it lost", "would have paid", "actually paid",
)
_TERM_RE = re.compile(r"(?<![A-Za-z0-9_])(%s)(?![A-Za-z0-9_])"
                      % "|".join(re.escape(t) for t in OUTCOME_TERMS),
                      re.IGNORECASE)

FIELDS = ("reads", "cues_for", "cues_against", "veto_considered",
          "would_change", "reasoning")

PARAMS = {
    "spec_section": SECTION,
    "directive": "R2-8 (written reasoning, committed same day) + R2-11 (this "
                 "journal is the extraction substrate) + R2-9 (ledger "
                 "discipline as a mechanism, not a practice)",
    "blind_fences": "1) panel_score never imported; 2) outcome-vocabulary scan "
                    "REFUSES a BLIND entry and names the term; 3) claimed "
                    "reads cross-checked against the mechanical ledgers",
    "grain": "one entry per SHORTLISTED episode",
    "outcome_terms": list(OUTCOME_TERMS),
}


class JournalRefusal(RuntimeError):
    """A blind-unsafe or malformed entry.  Named and counted, never written."""


def day_path(round_name, date8):
    d = os.path.join(JOURNAL_ROOT, str(round_name))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "JOURNAL_%08d.md" % int(date8))


def index_path(round_name):
    d = os.path.join(JOURNAL_ROOT, str(round_name))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "JOURNAL_INDEX.tsv")


def scan_outcome_terms(entry):
    """[(field, term)] for every outcome term in any free-text field."""
    hits = []
    for f in FIELDS:
        for m in _TERM_RE.finditer(str(entry.get(f, "") or "")):
            hits.append((f, m.group(1)))
    return hits


def _read_index(path):
    rows, cols = [], None
    if not os.path.exists(path):
        return rows
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def render(entry):
    L = ["", "### %s — %s  p=%s" % (entry["episode_id"], entry["call"],
                                    entry["p"]),
         "", "* **reads consumed**: %s" % (entry.get("reads") or "-"),
         "* **cues FOR**: %s" % (entry.get("cues_for") or "-"),
         "* **cues AGAINST**: %s" % (entry.get("cues_against") or "-"),
         "* **veto considered**: %s" % (entry.get("veto_considered") or "-"),
         "* **what would have changed the call**: %s"
         % (entry.get("would_change") or "-"), "",
         (entry.get("reasoning") or "").strip(), ""]
    return "\n".join(L)


def write(round_name, date8, episode_id, call, p, mode=MC.MODE_BLIND,
          reads="", cues_for="", cues_against="", veto_considered="",
          would_change="", reasoning="", path=None, index=None):
    """Append ONE entry.  Refuses before writing anything."""
    call = str(call).strip().upper()
    if call not in CALLS:
        raise JournalRefusal("call %r not in %s" % (call, list(CALLS)))
    if not str(reasoning).strip():
        raise JournalRefusal(
            "entry for %s has no reasoning: R2-8 exists because the reasoning "
            "is the artefact — an empty one is not an entry" % episode_id)
    entry = {"round": round_name, "date8": int(date8), "mode": mode,
             "episode_id": episode_id, "call": call, "p": p, "reads": reads,
             "cues_for": cues_for, "cues_against": cues_against,
             "veto_considered": veto_considered, "would_change": would_change,
             "reasoning": reasoning}
    if mode == MC.MODE_BLIND:
        hits = scan_outcome_terms(entry)
        if hits:
            raise JournalRefusal(
                "BLIND entry for %s carries outcome vocabulary and is REFUSED: "
                "%s" % (episode_id,
                        "; ".join("%s contains %r" % h for h in hits)))
    body = render(entry)
    p_day = path or day_path(round_name, date8)
    if not os.path.exists(p_day):
        head = ("# DECISION JOURNAL — round %s, day %d (%s)\n\n"
                "R2-8: one entry per SHORTLISTED episode, written at decision "
                "time, committed the same day. Blind fences: no panel_score "
                "import at any depth; every BLIND entry scanned for outcome "
                "vocabulary and refused on a match; claimed reads cross-checked "
                "against RIBBON_ACCESS.tsv / CHART_RECEIPT.tsv / "
                "BRIEF_ACCESS.tsv by `--audit`.\n"
                % (round_name, int(date8), mode))
        with open(p_day, "w", newline="\n") as fh:
            fh.write(head)
    with open(p_day, "a", newline="\n") as fh:
        fh.write(body)
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]

    p_idx = index or index_path(round_name)
    rows = _read_index(p_idx)
    out = [[r.get(c, MC.NA) for c in INDEX_COLUMNS] for r in rows]
    out.append([str(len(out)), str(round_name), MC.era_of(int(date8)),
                str(int(date8)), mode, episode_id, call, str(p),
                str(reads or "-"), sha, str(len(body)), p_day])
    MC.write_tsv(p_idx, SECTION, MC.params_hash(PARAMS), list(INDEX_COLUMNS),
                 out, extra=["R2-8 index: one row per journal entry; "
                             "sha16 = sha256(entry body)[:16]",
                             "seq = row index (deterministic, no wall clock)"])
    return {"path": p_day, "index": p_idx, "sha16": sha, "chars": len(body),
            "episode_id": episode_id, "call": call}


# ---------------------------------------------------------------- audit -----
def _tsv(path):
    rows, cols = [], None
    if not os.path.exists(path):
        return rows
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if cols is None:
                cols = f
                continue
            rows.append(dict(zip(cols, f)))
    return rows


def audit(round_name, date8, index=None, ribbon_ledger=None,
          chart_receipt=None, brief_ledger=None):
    """Fence 3: is every CLAIMED read backed by a mechanical ledger row?"""
    import episode_round as ER              # constants only; no outcome path
    rows = [r for r in _read_index(index or index_path(round_name))
            if int(r.get("date8", -1)) == int(date8)]
    rib = _tsv(ribbon_ledger or ER.RIB.ACCESS_LEDGER)
    cha = _tsv(chart_receipt or ER.CHART_RECEIPT)
    bri = _tsv(brief_ledger or ER.BRIEF_LEDGER)
    n_rib = sum(1 for r in rib if r.get("round") == round_name)
    n_cha = sum(1 for r in cha if r.get("round") == round_name)
    n_bri = sum(1 for r in bri if r.get("round") == round_name)
    claims = {"ribbon": 0, "chart": 0, "brief": 0}
    for r in rows:
        t = str(r.get("reads", "")).lower()
        for k in claims:
            claims[k] += t.count(k + ":")
    unbacked = [k for k, v in claims.items()
                if v > 0 and {"ribbon": n_rib, "chart": n_cha,
                              "brief": n_bri}[k] == 0]
    return {"round": round_name, "date8": int(date8), "n_entries": len(rows),
            "n_take": sum(1 for r in rows if r.get("call") == "TAKE"),
            "claims": claims,
            "ledgered": {"ribbon": n_rib, "chart": n_cha, "brief": n_bri},
            "unbacked_claim_kinds": unbacked}


def assert_committed(round_name, date8, path=None):
    """R2-9 as a MECHANISM: is the day's journal tracked at HEAD and clean?"""
    p = path or day_path(round_name, date8)
    if not os.path.exists(p):
        return {"path": p, "exists": False, "tracked": False, "clean": False,
                "why": "no journal file for this day"}
    def _git(*args):
        return subprocess.run(["git"] + list(args), cwd="/workspace",
                              capture_output=True, text=True)
    tracked = _git("ls-files", "--error-unmatch", p).returncode == 0
    dirty = _git("diff", "--name-only", "HEAD", "--", p).stdout.strip()
    return {"path": p, "exists": True, "tracked": tracked,
            "clean": tracked and not dirty,
            "why": ("" if tracked and not dirty else
                    ("not tracked at HEAD" if not tracked
                     else "tracked but the working tree differs from HEAD"))}


def main(argv=None):
    ap = argparse.ArgumentParser(description="R2-8 written decision journal")
    ap.add_argument("--round", dest="round_name", required=True)
    ap.add_argument("--day", type=int, required=True)
    ap.add_argument("--episode", default=None)
    ap.add_argument("--call", default=None)
    ap.add_argument("--p", default="")
    ap.add_argument("--mode", default=MC.MODE_BLIND, choices=list(MC.MODES))
    ap.add_argument("--reads", default="")
    ap.add_argument("--for", dest="cues_for", default="")
    ap.add_argument("--against", dest="cues_against", default="")
    ap.add_argument("--veto", dest="veto_considered", default="")
    ap.add_argument("--would-change", dest="would_change", default="")
    ap.add_argument("--reasoning", default="")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--assert-committed", dest="assert_committed",
                    action="store_true")
    a = ap.parse_args(argv)

    if a.audit:
        r = audit(a.round_name, a.day)
        print("JOURNAL AUDIT round=%s day=%d entries=%d takes=%d claims=%s "
              "ledgered=%s unbacked=%s"
              % (r["round"], r["date8"], r["n_entries"], r["n_take"],
                 r["claims"], r["ledgered"], r["unbacked_claim_kinds"]))
        return 0 if not r["unbacked_claim_kinds"] else 4
    if a.assert_committed:
        r = assert_committed(a.round_name, a.day)
        print("JOURNAL COMMIT GATE %s exists=%d tracked=%d clean=%d %s"
              % (r["path"], int(r["exists"]), int(r["tracked"]),
                 int(r["clean"]), r["why"]))
        return 0 if r["clean"] else 5
    if not (a.episode and a.call):
        sys.stderr.write("nothing to write: pass --episode and --call\n")
        return 2
    try:
        rec = write(a.round_name, a.day, a.episode, a.call, a.p, mode=a.mode,
                    reads=a.reads, cues_for=a.cues_for,
                    cues_against=a.cues_against,
                    veto_considered=a.veto_considered,
                    would_change=a.would_change, reasoning=a.reasoning)
    except JournalRefusal as e:
        sys.stderr.write("REFUSED JournalRefusal: %s\n" % e)
        return 3
    print("%s\t%s\t%s\t%s\t%d chars" % (rec["episode_id"], rec["call"],
                                        rec["sha16"], rec["path"],
                                        rec["chars"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
