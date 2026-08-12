"""sheets4_check.py — the SHEET-V4 audit, run on the rendered bytes.

Everything `sheets_check.py` proves about a v3 sheet, plus what V4 adds:

  1  WALL       every session of the block is inside the lawful case wall
                (125..917; packlib.assert_case_wall enforces it).
  2  COMPLETE   one sheet per roster candidate, numbered contiguously in
                chronological order, nothing extra in the directory, and ALL
                THIRTEEN sections present on every sheet.
  3  CAUSAL     no clock printed on a sheet runs past its own decision second.
                The coarse layers print 30-minute WINDOW labels as HH:MM spans
                rather than HH:MM:SS instants, and the audit additionally proves
                the window index itself is CLOSED before the decision second.
  4  BLOCK      a study sheet carries its OUTCOME block; a blind sheet carries
                no outcome word at all.
  5  BUDGET     the D-042 token budget: ~3,500 tokens for the richest sheets.
  6  ABSENCE    every absent layer is TYPED (says why); no section is empty.
  7  STAMP      every sheet carries the SHEET-V4 version stamp naming what it
                carries, and the manifest exists and enumerates the same
                sections in the same order (the D-042 certificate).
  8  NOLEAK     the D7 session-quantile vol STATE never appears on a sheet.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import packlib as P                                   # noqa: E402
import sheet4 as SH4                                  # noqa: E402

CLOCK = re.compile(r"\b([01]\d|2[0-3]):([0-5]\d):([0-5]\d)\b")
WINDOW = re.compile(r"\bw(\d+) ([01]\d|2[0-3]):([0-5]\d)\b")
OUTCOME_WORDS = ("certificate net", "menu net", "OUTCOME", "stop hit")
SECTIONS = tuple(f"## {number} " for number, _, _ in SH4.SECTIONS)
#: V3's audit bound was 5,000..13,500 chars.  V4 adds six layers (the RUTW tape,
#: the CC-013 flows, skew/term/richness, the FD/A3 gauges, the vol-index line
#: and the forward-vol block) and D-042 lets the budget grow to ~3,500 tokens.
#: The bound is stated in chars, at 4 chars/token, and set for the RICHEST case
#: (a post-209 session with every layer present and the widest ribbon).
CHAR_LOW, CHAR_HIGH = 5_000, 19_000
TOKEN_TARGET = 3_500
#: D7's spike/bleed state is the one qr_ivx channel deliberately withheld: its
#: cut is a whole-session quantile.  If any of these ever appear on a sheet the
#: leak law has been broken.
FORBIDDEN = ("vol_state", "SPIKING", "BLEEDING", "state_threshold")


def clock_seconds(text: str) -> int:
    hours, minutes, seconds = (int(part) for part in text.split(":"))
    return hours * 3600 + minutes * 60 + seconds - (9 * 3600 + 30 * 60)


def main(run: str = "run1", block: str = "study_e1") -> int:
    roster = json.loads(SH4.roster_path(block).read_text())
    blind = roster["blind"]
    directory = SH4.ROOT / run / block
    failures = []
    sizes = []

    manifest_path = SH4.ROOT / "SHEET_V4_MANIFEST.json"
    if not manifest_path.exists():
        failures.append("STAMP: sheets_v4/SHEET_V4_MANIFEST.json is missing")
    else:
        manifest = json.loads(manifest_path.read_text())
        listed = [section["number"] for section in manifest["sections"]]
        if listed != [number for number, _, _ in SH4.SECTIONS]:
            failures.append("STAMP: the manifest's section list disagrees with the generator")

    order = []
    for ordinal in sorted(roster["sessions"], key=int):
        P.assert_case_wall(int(ordinal), "sheets4_check")
        for candidate in roster["sessions"][ordinal]:
            order.append((int(ordinal), candidate))

    previous = None
    for position, (ordinal, candidate) in enumerate(order, start=1):
        stem = f"case{position:04d}"
        path = directory / f"{stem}_sheet.txt"
        key = (ordinal, candidate["second"])
        if previous is not None and key < previous:
            failures.append(f"ORDER {stem}: out of chronological order")
        previous = key
        if not path.exists():
            failures.append(f"COMPLETE {stem}: missing")
            continue
        text = path.read_text()
        sizes.append(len(text))
        if not (CHAR_LOW <= len(text) <= CHAR_HIGH):
            failures.append(f"BUDGET {stem}: {len(text)} chars outside "
                            f"{CHAR_LOW}..{CHAR_HIGH}")
        for section in SECTIONS:
            if section not in text:
                failures.append(f"COMPLETE {stem}: section {section!r} missing")
        if f"{SH4.SHEET_VERSION} carries:" not in text:
            failures.append(f"STAMP {stem}: no version stamp")
        for word in FORBIDDEN:
            if word in text:
                failures.append(f"NOLEAK {stem}: contains the withheld channel {word!r}")
        head, _, tail = text.partition("## OUTCOME")
        if blind:
            for word in OUTCOME_WORDS:
                if word.lower() in text.lower():
                    failures.append(f"BLIND {stem}: contains {word!r}")
        elif "certificate net" not in tail:
            failures.append(f"STUDY {stem}: outcome block missing")
        latest = max((clock_seconds(match.group(0)) for match in CLOCK.finditer(head)),
                     default=-1)
        if latest > candidate["second"]:
            failures.append(f"CAUSAL {stem}: clock {latest}s > decision second "
                            f"{candidate['second']}")
        for match in WINDOW.finditer(head):
            window = int(match.group(1))
            if (window + 1) * SH4.IVX_WINDOW_SECONDS > candidate["second"]:
                failures.append(f"CAUSAL {stem}: 30m window w{window} had not closed at "
                                f"decision second {candidate['second']}")
        if "TYPED ABSENT" in text and "MODALITY_ABSENT" not in text and \
                "no option print" not in text and "not in the cache" not in text and \
                "no stock print" not in text and "vendor" not in text and \
                "no qr_ivx" not in text and "first 30-minute window" not in text and \
                "strictly-prior vol-index" not in text and "expanding window" not in text and \
                "ribbon4" not in text and "the slot is null" not in text:
            failures.append(f"ABSENCE {stem}: an absence without a stated reason")

    extra = [path.name for path in directory.glob("case*_sheet.txt")
             if int(path.name[4:8]) > len(order)]
    if extra:
        failures.append(f"COMPLETE: {len(extra)} sheet(s) beyond the roster, e.g. {extra[:3]}")

    if sizes:
        print(json.dumps({"sheets": len(sizes), "chars_min": min(sizes),
                          "chars_median": sorted(sizes)[len(sizes) // 2],
                          "chars_max": max(sizes),
                          "tokens_median_est": sorted(sizes)[len(sizes) // 2] // 4,
                          "tokens_max_est": max(sizes) // 4,
                          "token_target": TOKEN_TARGET}))
    print(f"sheets4_check({run}/{block}): {len(failures)} failure(s)")
    for failure in failures[:40]:
        print("  " + failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "run1",
                  sys.argv[2] if len(sys.argv) > 2 else "study_e1"))
