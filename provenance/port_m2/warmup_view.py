#!/usr/bin/python3
"""P-M2c warm-up: sheet view server.

  full  CID   -> path of the BLIND sheet
  trunc CID   -> writes the ABLATION view (S1-S5 + the S13 block) to the
                 scratchpad and prints its path.  Split rule from the round
                 brief: split the BLIND sheet text at the S6 marker, keep
                 everything before it, then append the S13 block (from its
                 S13 marker up to the next section marker).
DEFECT NOTE: the brief specifies a '## S6' marker; the rendered sheets use a
bare line-initial 'S6 RAW EVENT RIBBON' heading (no '##').  The split rule is
implemented against the actual rendering and is otherwise identical.
Refuses any cid that is not in WARMUP_DRAW.tsv.  Never touches S14.
"""
import os
import re
import sys

ERA = "/workspace/artifacts/cache/port/m2/era/E1/STUDY"
DRAW = "/workspace/provenance/port_m2/WARMUP_DRAW.tsv"
SCRATCH = ("/tmp/claude-1001/-workspace/"
           "59a9b9f8-e018-4e60-914c-a85d8c30ef70/scratchpad")


def allowed():
    out = set()
    with open(DRAW) as fh:
        for ln in fh:
            if ln.startswith("#") or ln.startswith("cid\t"):
                continue
            out.add(ln.split("\t")[0])
    return out


def sheet_path(cid):
    asset, d8 = cid.split("-")[0], cid.split("-")[1]
    return os.path.join(ERA, asset, d8, "%s.BLIND.sheet.txt" % cid)


def main():
    mode, cid = sys.argv[1], sys.argv[2]
    if cid not in allowed():
        raise SystemExit("REFUSED: %s is not in the warm-up draw" % cid)
    p = sheet_path(cid)
    if mode == "full":
        print(p)
        return 0
    txt = open(p).read()
    m6 = re.search(r"^S6\b", txt, re.M)
    if not m6:
        raise SystemExit("no S6 marker in %s" % p)
    head = txt[:m6.start()]
    m13 = re.search(r"^S13\b", txt, re.M)
    if not m13:
        raise SystemExit("no S13 marker in %s" % p)
    rest = txt[m13.start():]
    nxt = re.search(r"^S1[4-9]\b|^S[2-9]\b", rest[1:], re.M)
    s13 = rest if not nxt else rest[:nxt.start() + 1]
    outp = os.path.join(SCRATCH, "%s.TRUNC.txt" % cid)
    with open(outp, "w") as fh:
        fh.write(head)
        fh.write("[ABLATION VIEW — S6..S12 WITHHELD]\n\n")
        fh.write(s13)
    print(outp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
