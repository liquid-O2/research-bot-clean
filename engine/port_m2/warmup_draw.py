#!/usr/bin/python3
"""THE CC-M2-8.1 WARM-UP EXCLUSION, ON THE DRAW SIDE (R34).

CC-M2-8.1 removed the six P-M2c warm-up sessions from every future draw:

    SI  2021-07-01 / 2021-08-31
    HG  2021-07-01 / 2021-09-29
    NKD 2021-07-01 / 2021-08-18

WHAT WAS ACTUALLY ENFORCED, BEFORE THIS MODULE.  Nothing on the draw side.
`e1d1_seal.py:33-38` was the only place in `engine/` that named the sessions at
all, and it named them only to LABEL its own rows (`taint = DIRECT | WINDOW |
CLEAN`).  Days 2-8 and the blind lane each SAY "warm-up sessions excluded
(CC-M2-8.1)" in a docstring and none of them checks it.  The whole enforcement
was `used_cases.check_blind`, which is a LEDGER-side rule: it refuses a blind
draw touching a session that a STUDY entry has already tainted.  That works
only because all six warm-up sessions happen to be on the ledger as STUDY (391
/ 5 / 338 / 5 / 310 / 5 rows, verified) — i.e. the law was satisfied by an
accident of history rather than by a guard.  A warm-up session that had been
read WITHOUT being recorded would have been drawable BLIND, which is precisely
the day-5 gap class CC-M2-17.4 exists to kill.

THE GUARD.  `assert_draw_lawful` is called by every seal path with the exact
cid list it is about to write, BEFORE it writes anything:

  * mode=BLIND  + any warm-up session  -> ALWAYS a refusal.  There is no
    declaration that makes a warm-up session blind-drawable; its outcomes are
    in `provenance/port_m2/WARMUP_POSTMORTEMS.md`, which is mandated inherited
    memory, so the reader carries explicit outcome knowledge into it.
  * mode=STUDY  + any warm-up session  -> a refusal UNLESS the seal declares it
    (`declared=True`).  E1 STUDY DAY 1 is the one lawful case: its
    deterministic draw IS 2021-07-01 for all three assets, and the day is
    sealed with a per-row DIRECT/WINDOW/CLEAN taint column that says so.  Any
    other study day that reaches a warm-up session has drawn wrong and stops.

The refusal is an EXCEPTION, never a filter: a draw that silently dropped its
warm-up members would hide the protocol violation that produced it (the same
rule `used_cases.check_blind` states for the one-way door).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

MODE_STUDY = "STUDY"
MODE_BLIND = "BLIND"

# (asset, date8) — CC-M2-8.1, verbatim.
WARMUP_SESSIONS = frozenset({
    ("SI", 20210701), ("SI", 20210831),
    ("HG", 20210701), ("HG", 20210929),
    ("NKD", 20210701), ("NKD", 20210818),
})

PARAMS = {
    "rule": "CC-M2-8.1: the six P-M2c warm-up sessions are excluded from every "
            "future draw; enforcement is on the DRAW side, at every seal, "
            "before any write",
    "blind": "never drawable, no declaration accepted",
    "study": "drawable only with declared=True (E1 STUDY DAY 1, which seals a "
             "per-row DIRECT/WINDOW/CLEAN taint column)",
    "sessions": ",".join("%s:%d" % k for k in sorted(WARMUP_SESSIONS)),
}


class WarmupRefusal(RuntimeError):
    """Raised when a draw touches a CC-M2-8.1 warm-up session unlawfully.
    NEVER caught to filter."""


def sessions_of(cids):
    """{(asset, date8)} touched by these cids, parsed from the cid itself so
    the guard needs no roster and cannot be fooled by a stale index."""
    out = set()
    for cid in cids:
        parts = str(cid).split("-")
        if len(parts) < 2:
            raise WarmupRefusal("unparseable cid %r — the warm-up guard "
                                "refuses rather than skipping it" % cid)
        try:
            out.add((parts[0], int(parts[1])))
        except ValueError:
            raise WarmupRefusal("unparseable cid %r — the warm-up guard "
                                "refuses rather than skipping it" % cid)
    return out


def warmup_hits(cids):
    return sorted(sessions_of(cids) & WARMUP_SESSIONS)


def assert_draw_lawful(cids, mode, declared=False, who=""):
    """REFUSE an unlawful draw.  Returns the hit list (possibly empty) when the
    draw is lawful; raises `WarmupRefusal` otherwise."""
    if mode not in (MODE_STUDY, MODE_BLIND):
        raise ValueError("mode %r" % mode)
    hits = warmup_hits(cids)
    if not hits:
        return hits
    if mode == MODE_BLIND:
        raise WarmupRefusal(
            "CC-M2-8.1 WARM-UP REFUSAL [%s]: this BLIND draw touches %d "
            "warm-up session(s) %s. The warm-up post-mortems are mandated "
            "inherited memory, so the reader carries explicit outcome "
            "knowledge into those sessions and they are never blind-drawable."
            % (who or "?", len(hits),
               ", ".join("%s/%d" % h for h in hits)))
    if not declared:
        raise WarmupRefusal(
            "CC-M2-8.1 WARM-UP REFUSAL [%s]: this STUDY draw touches %d "
            "warm-up session(s) %s and does not declare them. Every study day "
            "after day 1 draws 'the next chronological STUDY session strictly "
            "after X, WARM-UPS EXCLUDED' — reaching one means the draw is "
            "wrong. Only a seal that commits a per-row warm-up taint column "
            "may pass declared=True."
            % (who or "?", len(hits), ", ".join("%s/%d" % h for h in hits)))
    return hits
