#!/usr/bin/env python3
"""sweep_caches.py — build the d020_v3 SUPPORT CACHES for a session range.

Until now the full-session caches (`_cache/w2sum`, `_cache/w2meta`,
`_cache/ribbon`, `_cache/w21norm`, `_cache/minutes`, `_cache/minutes_day`) were
produced by ad-hoc shell for 125..447.  FINAL_PLAN AMENDMENT 2026-08-12-c moved
the research wall to W = 917, so the same caches are needed for 448..917 and the
recipe has to be written down.  This is that recipe, and nothing else: every
stage shells the SAME lawful C++ dumper the v3 machinery already used, with the
same arguments the banked 125..447 files were built with (verified against
their own headers).

  stage w2sum    qr_wave2_dump summaries --from o --to o        -> _cache/w2sum/s{o}.tsv
  stage w2meta   qr_wave2_dump values --seconds 0               -> _cache/w2meta/s{o}.tsv
  stage ribbon   qr_tape_ribbon --streams prints,options 0..S   -> _cache/ribbon/s{o}.tsv
  stage w21norm  qr_w21_dump --stride 60 0..S   (o >= 209 only) -> _cache/w21norm/s{o}.tsv
  stage minutes  packlib.minute_aggregates                      -> _cache/minutes/s{o}.npy
  stage day      daylib.day_minutes                             -> _cache/minutes_day/s{o}.npy

SHEET-V4 STAGES (D-042 data-completeness; all three are the SAME lawful census
tools, read-only, two-run byte-identical):

  stage ribbon4  qr_tape_ribbon --streams options,rutw          -> _cache/ribbon4/s{o}.tsv
                 --greeks full  (the CC-013 columns + the B5 tape)
  stage ivx      qr_ivx_census  --prints/--rutw-prints/--tapes  -> _cache/ivx/s{o}.tsv
                 [--quotes when o >= 209]  (B1,B2,D1-D9)
  stage qskew    qr_ivx_qskew   --plane 0   (o >= 209 only)     -> _cache/ivx/qskew_s{o}.tsv

`ribbon4` is a SEPARATE cache from `ribbon` on purpose: the v3 sheet tree was
rendered from `ribbon`'s bytes and those files are never rewritten, so the v3
corpus stays reproducible while v4 reads the wider projection beside it.

Every stage SKIPS a session whose cache file already exists, so the banked
125..447 files are never rewritten and a re-run is a no-op.

usage: sweep_caches.py <stage> --from A --to B [--jobs N]
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import packlib as P  # noqa: E402

OPTION_QUOTES = "/workspace/data/tokens/option_quotes/IWM"
OPTION_PRINTS = "/workspace/data/tokens/options_prints/IWM"
RUTW_PRINTS = "/workspace/data/tokens/RUTW/options_prints"
#: qr_w21_dump refuses before this ordinal (Q12 MODALITY_ABSENT, no shard era).
FIRST_SURFACE_ORDINAL = 209
#: the strides/streams the banked 125..447 caches were built with (read off
#: their own `session stride` / row-kind census, not guessed).
W21_STRIDE = 60
RIBBON_STREAMS = "prints,options"


def target(stage: str, ordinal: int) -> pathlib.Path:
    return {
        "w2sum": P.CACHE / "w2sum" / f"s{ordinal}.tsv",
        "w2meta": P.CACHE / "w2meta" / f"s{ordinal}.tsv",
        "ribbon": P.CACHE / "ribbon" / f"s{ordinal}.tsv",
        "w21norm": P.CACHE / "w21norm" / f"s{ordinal}.tsv",
        "minutes": P.CACHE / "minutes" / f"s{ordinal}.npy",
        "day": P.CACHE / "minutes_day" / f"s{ordinal}.npy",
        "ribbon4": P.CACHE / "ribbon4" / f"s{ordinal}.tsv",
        "ivx": P.CACHE / "ivx" / f"s{ordinal}.tsv",
        "qskew": P.CACHE / "ivx" / f"qskew_s{ordinal}.tsv",
    }[stage]


def command(stage: str, ordinal: int, out: pathlib.Path) -> list:
    binary = str(P.BIN / {"w2sum": "qr_wave2_dump", "w2meta": "qr_wave2_dump",
                          "ribbon": "qr_tape_ribbon", "w21norm": "qr_w21_dump",
                          "ribbon4": "qr_tape_ribbon", "ivx": "qr_ivx_census",
                          "qskew": "qr_ivx_qskew"}[stage])
    if stage == "ribbon4":
        return [binary, "--ordinal", str(ordinal), "--from-second", "0",
                "--to-second", str(P.SESSION_SECONDS), "--streams", "options,rutw",
                "--greeks", "full", "--out", str(out)]
    if stage == "ivx":
        # Q12: the option-QUOTE corpus starts at 209, so the surface-coupled
        # channels (D1 richness, D7/D8/D9) are a TYPED ABSENCE before it — the
        # flag is omitted rather than pointed at a corpus that is not there.
        argv = [binary, "--prints", OPTION_PRINTS, "--rutw-prints", RUTW_PRINTS,
                "--tapes", str(P.TAPES), "--ordinals", str(ordinal), "--out", str(out)]
        if ordinal >= FIRST_SURFACE_ORDINAL:
            argv += ["--quotes", OPTION_QUOTES]
        return argv
    if stage == "qskew":
        return [binary, "--root", OPTION_QUOTES, "--tapes", str(P.TAPES),
                "--ordinals", str(ordinal), "--plane", "0", "--out", str(out)]
    if stage == "w2sum":
        return [binary, "summaries", "--from", str(ordinal), "--to", str(ordinal),
                "--out", str(out)]
    if stage == "w2meta":
        return [binary, "values", "--summaries", str(P.CACHE / "summaries.tsv"),
                "--ordinal", str(ordinal), "--seconds", "0", "--out", str(out)]
    if stage == "ribbon":
        return [binary, "--ordinal", str(ordinal), "--from-second", "0",
                "--to-second", str(P.SESSION_SECONDS), "--streams", RIBBON_STREAMS,
                "--out", str(out)]
    return [binary, "--root", OPTION_QUOTES, "--prints", OPTION_PRINTS,
            "--tapes", str(P.TAPES), "--ordinal", str(ordinal), "--from-second", "0",
            "--to-second", str(P.SESSION_SECONDS), "--stride", str(W21_STRIDE),
            "--out", str(out)]


def fallback_command(stage: str, ordinal: int, out: pathlib.Path) -> list | None:
    """The RUTW-UNCOVERED retry, and nothing else.

    The B5 corpus has vendor day gaps (measured: 2024-07-19 = ordinal 638 has no
    RUTW file at all), and both RUTW-reading tools refuse the whole session
    rather than return a silent nothing — which is the correct refusal.  The
    lawful response is to re-run WITHOUT the RUTW input so the IWM half of the
    session still exists, and to leave the RUTW half TYPED ABSENT: the retried
    output carries no `rutw_option` header/rows, and that MISSING HEADER is what
    the sheet generator reads as "this session is RUTW-uncovered" (as opposed to
    "covered, no prints in this window").  Nothing is substituted.
    """
    argv = command(stage, ordinal, out)
    if stage == "ribbon4":
        argv[argv.index("--streams") + 1] = "options"
        return argv
    if stage == "ivx":
        index = argv.index("--rutw-prints")
        return argv[:index] + argv[index + 2:]
    return None


def run_shell_stage(stage: str, ordinals: list, jobs: int) -> None:
    todo = [o for o in ordinals if not target(stage, o).exists()]
    if stage in ("w21norm", "qskew"):
        todo = [o for o in todo if o >= FIRST_SURFACE_ORDINAL]
    print(f"{stage}: {len(todo)} sessions to build", flush=True)
    target(stage, ordinals[0]).parent.mkdir(parents=True, exist_ok=True)
    running: list = []
    started = time.monotonic()
    done = 0
    for ordinal in todo:
        out = target(stage, ordinal)
        staged = out.with_suffix(out.suffix + ".partial")
        running.append((ordinal, staged, out, subprocess.Popen(
            command(stage, ordinal, staged),
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)))
        while len(running) >= jobs:
            done += reap(running, block=True, stage=stage)
    while running:
        done += reap(running, block=True, stage=stage)
    print(f"{stage}: built {done} in {time.monotonic() - started:.1f}s", flush=True)
    missing = [o for o in todo if not target(stage, o).exists()]
    if missing:
        print(f"{stage}: MISSING {len(missing)}: {missing[:20]}", flush=True)


def reap(running: list, block: bool, stage: str = "") -> int:
    """Waits for the oldest process, publishes its output atomically."""
    ordinal, staged, out, process = running[0]
    stderr = process.communicate()[1] if block else b""
    running.pop(0)
    if process.returncode != 0:
        message = stderr.decode(errors="replace").strip()
        retry = fallback_command(stage, ordinal, staged) if "rutw" in message else None
        if retry is not None:
            print(f"  RUTW-UNCOVERED s{ordinal}: retrying without the B5 tape "
                  f"({message[:160]})", flush=True)
            again = subprocess.run(retry, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE, check=False)
            if again.returncode == 0:
                staged.replace(out)
                return 1
            message = again.stderr.decode(errors="replace").strip()
        print(f"  REFUSED s{ordinal}: {message[:300]}", flush=True)
        staged.unlink(missing_ok=True)
        return 0
    staged.replace(out)
    return 1


def run_python_stage(stage: str, ordinals: list, jobs: int) -> None:
    """minutes / minutes_day are built by the library itself, in child processes
    so one bad session cannot take the sweep down."""
    todo = [o for o in ordinals if not target(stage, o).exists()]
    print(f"{stage}: {len(todo)} sessions to build", flush=True)
    started = time.monotonic()
    running = []
    for ordinal in todo:
        running.append(subprocess.Popen(
            [sys.executable, str(pathlib.Path(__file__).resolve()), stage,
             "--from", str(ordinal), "--to", str(ordinal), "--one"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))
        while len(running) >= jobs:
            running[0].communicate()
            running.pop(0)
    for process in running:
        process.communicate()
    built = [o for o in todo if target(stage, o).exists()]
    print(f"{stage}: built {len(built)}/{len(todo)} in {time.monotonic() - started:.1f}s",
          flush=True)
    missing = [o for o in todo if not target(stage, o).exists()]
    if missing:
        print(f"{stage}: MISSING {len(missing)}: {missing[:20]}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=("w2sum", "w2meta", "ribbon", "w21norm", "minutes", "day",
                                      "ribbon4", "ivx", "qskew"))
    ap.add_argument("--from", dest="start", type=int, required=True)
    ap.add_argument("--to", dest="stop", type=int, required=True)
    ap.add_argument("--jobs", type=int, default=12)
    ap.add_argument("--one", action="store_true", help="in-process single session (child mode)")
    args = ap.parse_args()

    ordinals = [P.assert_wall(o, "sweep") for o in range(args.start, args.stop + 1)]
    if args.one:
        import daylib as D  # noqa: E402
        if args.stage == "minutes":
            P.minute_aggregates(ordinals[0])
        else:
            D.day_minutes(ordinals[0])
        return 0
    if args.stage in ("minutes", "day"):
        run_python_stage(args.stage, ordinals, args.jobs)
    else:
        run_shell_stage(args.stage, ordinals, args.jobs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
