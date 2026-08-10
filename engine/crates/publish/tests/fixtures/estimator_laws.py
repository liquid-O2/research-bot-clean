#!/usr/bin/env python3
"""estimator_laws.py -- frozen estimator LAWS for the Phase 5-7 harness.

Implements the BUILD-NOW item from
/tmp/.../scratchpad/phase567_harness_brief_final.md section (e):
    "LCB/support/degradation/correction-envelope/admissibility estimator laws -- freeze
     the exact laws | plan + freeze spec | NOW (design); C17 execution stays
     BLOCKED-PENDING-ESTIMATOR until checkpoint 5 pins the numbers"

This module freezes the *form* of each law now and provides a reference implementation of
the parts that are fully determined pre-Phase-4 (so they can be selftested at the 0.80
knife-edge, per section (f)). The parts that require Phase-3/4 artifacts or a pinned numeric
scheme FAIL CLOSED with an explicit binding-point message -- never fabricated.

BINDING POINTS (documented, not fabricated):
  - YEAR_STRATIFIED_SESSION_BLOCK_LCB is the FROZEN v4 gate statistic (requirement (b)) and has
    ZERO free parameters: block length (5 sessions), replicate count (10000), and seed (the low
    64 bits of the published accepted-session registry root) are all fixed registered constants,
    so there is no post-rerun tuning surface. It is `year_stratified_session_block_lcb`; freeze
    v4 pins it by THIS FILE's sha256. It fails closed unless the REGISTERED scheme is passed and
    refuses to certify a bound under `python -O`. The closed-form Wilson reference is the
    executable knife-edge cross-check (`block_lcb_wilson_crosscheck`).
  - The older SESSION_BLOCK_LCB (`session_block_lcb`, `EstimatorParams`) pooled every block
    across years and never stratified; the v3 verification found that gap (TA-03 NOT-CLOSED). It
    is retained for backward compatibility but is NO LONGER the gate; v4 names the year-stratified
    function above. Its old checkpoint-5 knobs are therefore moot for the gate.
  - ADMISSIBILITY_RECOMPUTE binds to the real R2 admissibility registry (column-typed
    allowlist + provenance certificates + machine-checked lineage) at Phase-3 checkpoint 3.
    Here it is validated against a SYNTHETIC lineage DAG fixture only.

The laws frozen here:
  POOLED_RECALL, FAIL_CLOSED_TRUTH_IDENTITY (confirmed_truths == hits + 5 typed misses),
  SESSION_BLOCK_LCB (Wilson reference + blocked bootstrap interface), DISTINCT_EPISODE_SUPPORT
  (attack #7), RECENCY_DECAY (attack #4), CORRECTION_ENVELOPE (attack #8),
  ADMISSIBILITY_RECOMPUTE (attack #10 / C8).

Stdlib only.
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass, field
from statistics import NormalDist
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

# The five typed miss categories the brief pins for the fail-closed identity
# (C15: "confirmed_truths == hits + 5 typed misses"). Frozen here as an ordered set.
TYPED_MISS_CATEGORIES: Tuple[str, ...] = (
    "no_candidate",       # truth had no candidate at all
    "untimely",           # candidate(s) present but none within the timely window
    "wrong_side",         # candidate on the wrong side/anchor
    "unsettled_tail",     # horizon never matured before the frozen deadline (stays a miss)
    "typed_other",        # any other registered typed miss
)

# One-sided 95% normal quantile, recomputed deterministically from stdlib (no magic constant).
ONE_SIDED_95_Z = NormalDist().inv_cdf(0.95)


class EstimatorLawError(ValueError):
    pass


class EstimatorBindingError(EstimatorLawError):
    """Raised when a law whose numbers are pinned at a later checkpoint is invoked without
    those pinned inputs -- the honest fail-closed for a not-yet-bound estimator."""


# ---------------------------------------------------------------------------
# POOLED_RECALL + FAIL_CLOSED_TRUTH_IDENTITY
# ---------------------------------------------------------------------------

def pooled_recall(hits: int, confirmed_truths: int) -> float:
    """recall = hits / confirmed_truths (R<=2 pooled). confirmed_truths must be > 0."""
    if confirmed_truths <= 0:
        raise EstimatorLawError(f"confirmed_truths must be positive, got {confirmed_truths}")
    if not (0 <= hits <= confirmed_truths):
        raise EstimatorLawError(f"hits {hits} out of range [0, {confirmed_truths}]")
    return hits / confirmed_truths


def check_confirmed_truth_identity(
    confirmed_truths: int, hits: int, typed_misses: Mapping[str, int]
) -> None:
    """Fail-closed: confirmed_truths == hits + sum of exactly the 5 typed miss categories.
    Missing/extra categories, or an arithmetic mismatch, is a hard reject (C15)."""
    keys = set(typed_misses.keys())
    if keys != set(TYPED_MISS_CATEGORIES):
        raise EstimatorLawError(
            f"typed_misses must carry exactly the 5 categories {list(TYPED_MISS_CATEGORIES)}; "
            f"got {sorted(keys)}"
        )
    total_miss = sum(typed_misses[k] for k in TYPED_MISS_CATEGORIES)
    if any(typed_misses[k] < 0 for k in TYPED_MISS_CATEGORIES) or hits < 0:
        raise EstimatorLawError("hits and typed miss counts must be non-negative")
    if confirmed_truths != hits + total_miss:
        raise EstimatorLawError(
            f"fail-closed identity violated: confirmed_truths={confirmed_truths} != "
            f"hits={hits} + typed_misses={total_miss}"
        )


# ---------------------------------------------------------------------------
# SESSION_BLOCK_LCB: frozen Wilson reference + BLOCKED bootstrap interface
# ---------------------------------------------------------------------------

def wilson_one_sided_lcb(hits: int, n: int, z: float = ONE_SIDED_95_Z) -> float:
    """Frozen closed-form one-sided lower confidence bound (Wilson score). This is the
    reference the checkpoint-5 block bootstrap must AGREE WITH at the 0.80 knife-edge
    (section (f)). Pure function of (hits, n, z); fully determined pre-Phase-4."""
    if n <= 0:
        raise EstimatorLawError(f"n must be positive, got {n}")
    if not (0 <= hits <= n):
        raise EstimatorLawError(f"hits {hits} out of range [0, {n}]")
    p = hits / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2 * n)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / n + (z * z) / (4 * n * n))
    return center - margin


@dataclass(frozen=True)
class EstimatorParams:
    """The numeric knobs the brief pins at CHECKPOINT 5 (Phase-4 pre-run law). Constructing
    this with the UNPINNED sentinel models 'not yet frozen'."""
    block_scheme: str        # e.g. "session-block-year-stratified"
    replicates: int
    seed: int

    def is_unpinned(self) -> bool:
        return self.block_scheme == "" or self.replicates <= 0


UNPINNED_PARAMS = EstimatorParams(block_scheme="", replicates=0, seed=0)


def session_block_lcb(
    per_block_hits: Sequence[int],
    per_block_truths: Sequence[int],
    params: EstimatorParams,
    confidence: float = 0.95,
) -> float:
    """Session-block year-stratified one-sided LCB by stratified block bootstrap.

    The LAW form is frozen (resample blocks with replacement -> recompute pooled recall per
    replicate -> take the (1-confidence) percentile for a one-sided lower bound). The concrete
    block scheme / replicate count / seed are PINNED AT CHECKPOINT 5; calling with
    UNPINNED_PARAMS FAILS CLOSED. Deterministic given pinned params (seed-driven)."""
    if params.is_unpinned():
        raise EstimatorBindingError(
            "BLOCKED-PENDING-ESTIMATOR: session-block LCB block scheme/replicates/seed are "
            "pinned at checkpoint 5 (Phase-4 pre-run law); refusing to compute with unpinned "
            "params -- see section (c) C17 and section (e)."
        )
    if len(per_block_hits) != len(per_block_truths) or len(per_block_hits) == 0:
        raise EstimatorLawError("per-block hits/truths must be equal-length and non-empty")
    nblocks = len(per_block_hits)
    rng = random.Random(params.seed)
    recalls: List[float] = []
    for _ in range(params.replicates):
        h = 0
        t = 0
        for _ in range(nblocks):
            j = rng.randrange(nblocks)
            h += per_block_hits[j]
            t += per_block_truths[j]
        recalls.append(h / t if t > 0 else 0.0)
    recalls.sort()
    # one-sided lower bound = the (1 - confidence) empirical percentile
    idx = int((1.0 - confidence) * (len(recalls) - 1))
    return recalls[idx]


# ---------------------------------------------------------------------------
# YEAR_STRATIFIED_SESSION_BLOCK_LCB -- the FROZEN v4 gate statistic (requirement (b))
# ---------------------------------------------------------------------------
#
# This is the actual official-session, year-stratified block-bootstrap one-sided 95%
# lower confidence bound that truth-authority freeze v4 Section 5.2 pins by this file's
# sha256. The older `session_block_lcb` above is retained unchanged for backward
# compatibility, but it pooled every block across all years and never stratified; v4 no
# longer names it the gate. `year_stratified_session_block_lcb` below does the real
# thing and has ZERO free parameters: block length, replicate count, and seed are all
# fixed registered constants (the seed derived from a published root), so there is no
# post-rerun tuning surface. The v3 verification (t16_freeze_v3_verification.md sec. 2)
# marked TA-03 NOT-CLOSED precisely because the pinned function did not stratify, did
# not authenticate its scheme, and did not validate block counts; every one of those is
# closed here.

# The published root the deterministic seed law binds to: the accepted compact-session
# registry root (freeze Section 0.4) -- the population authority the block bootstrap
# resamples over. The seed is a PURE FUNCTION of this frozen published root; nobody may
# choose it. This mirrors the chart plan's systematic-midpoint philosophy: a fixed
# arithmetic derivation from a frozen published quantity, hand-recomputable (it is the
# last 16 hex digits of the root), not a human-selectable PRNG seed.
ACCEPTED_COMPACT_SESSIONS_ROOT = (
    "233dc10ab4c0973a8caa92792757a322bbff102296f0e7ffb71c6d78810bcaed"
)

# Registered block length: 5 consecutive official sessions (~ one trading week), the
# fixed within-year autocorrelation block. Registered constant, not a tunable.
SESSION_BLOCK_LEN = 5

# Registered replicate count. Fixed constant, not a tunable.
SESSION_BLOCK_REPLICATES = 10_000

# Registered agreement tolerance for the executable Wilson cross-check (Section 5.2):
# on the near-homogeneous 0.80 knife-edge reference the block bootstrap must agree with
# the closed-form Wilson LCB to within one recall point.
WILSON_AGREEMENT_TOL = 0.01


def _derive_session_block_seed(root_hex: str) -> int:
    """Deterministic seed law with ZERO free parameters: the low 64 bits of the published
    session-registry root, read as a hex integer (equivalently, the value of its last 16
    hex digits). Steer-proof -- there is no offset, label, or seed anyone may choose."""
    if len(root_hex) != 64 or any(c not in "0123456789abcdef" for c in root_hex):
        raise EstimatorLawError(
            f"seed root must be a 64-char lowercase sha256 hex string, got {root_hex!r}"
        )
    return int(root_hex, 16) & ((1 << 64) - 1)


SESSION_BLOCK_SEED = _derive_session_block_seed(ACCEPTED_COMPACT_SESSIONS_ROOT)


def _guard_optimize(where: str, level: Optional[int] = None) -> None:
    """python -O guard. Under `python -O`/`-OO` (`sys.flags.optimize > 0`) `assert`
    statements are stripped, so the invariant checks that protect a gate result are
    silently disabled. A frozen gate statistic must never be certified in that mode:
    refuse. `level` is injectable so the refusal path is itself self-tested."""
    lvl = sys.flags.optimize if level is None else level
    if lvl != 0:
        raise EstimatorBindingError(
            f"REFUSING under python -O (optimize level {lvl}): {where} certifies a frozen "
            f"gate result and requires assertion-checked invariants; rerun without -O."
        )


@dataclass(frozen=True)
class SessionRecall:
    """One official session's recall contribution to the year-stratified bootstrap.

    `year` is the stratum label (2022/2023/2024/2025); `ordinal` orders the session
    within the full frozen calendar (only its order inside a year is used). `hits` and
    `truths` are non-negative integers with `hits <= truths`."""
    year: int
    ordinal: int
    hits: int
    truths: int


@dataclass(frozen=True)
class SessionBlockScheme:
    """The REGISTERED year-stratified session-block bootstrap configuration. Every field
    is a fixed registered constant or a pure function of a published root -- ZERO free
    parameters. `seed` is DERIVED from `seed_root`; an arbitrary seed cannot be injected.
    Only `REGISTERED_SESSION_BLOCK_SCHEME` is accepted at the gate."""
    block_len: int
    replicates: int
    seed_root: str

    @property
    def seed(self) -> int:
        return _derive_session_block_seed(self.seed_root)

    def is_registered(self) -> bool:
        return (
            self.block_len == SESSION_BLOCK_LEN
            and self.replicates == SESSION_BLOCK_REPLICATES
            and self.seed_root == ACCEPTED_COMPACT_SESSIONS_ROOT
        )


REGISTERED_SESSION_BLOCK_SCHEME = SessionBlockScheme(
    block_len=SESSION_BLOCK_LEN,
    replicates=SESSION_BLOCK_REPLICATES,
    seed_root=ACCEPTED_COMPACT_SESSIONS_ROOT,
)

# Sentinel modelling 'not yet pinned' -- parallels UNPINNED_PARAMS for the old interface.
UNPINNED_SESSION_BLOCK_SCHEME = SessionBlockScheme(block_len=0, replicates=0, seed_root="")


def year_stratified_session_block_lcb(
    sessions: Sequence[SessionRecall],
    scheme: SessionBlockScheme = REGISTERED_SESSION_BLOCK_SCHEME,
    confidence: float = 0.95,
) -> float:
    """One-sided (1 - confidence) lower confidence bound on pooled recall by a
    DETERMINISTIC year-stratified session-block bootstrap. This is the frozen v4 gate
    statistic for floor requirement (b).

    Frozen law form (matches freeze v4 Section 5.2 verbatim):
      * strata = the distinct `year` values; each stratum's sessions are ordered by
        `ordinal`.
      * within a stratum, consecutive sessions are partitioned into non-overlapping
        blocks of `scheme.block_len` (the final block is short iff the stratum size is
        not a multiple of block_len).
      * one replicate: for each stratum in ascending-year order, draw whole blocks WITH
        REPLACEMENT, concatenating their sessions, until at least the stratum's own
        session count is reached, then truncate to EXACTLY that count -- so every
        replicate preserves the exact per-year cardinality (e.g. 251/250/252/250).
      * pooled recall of a replicate = sum(hits) / sum(truths) over its resampled
        sessions; a replicate whose resampled truths are 0 contributes recall 0.0
        (conservative zero-truth handling).
      * repeat `scheme.replicates` times; the LCB is the value at index
        floor((1 - confidence) * (replicates - 1)) of the ascending-sorted replicate
        recalls -- the (1 - confidence) empirical percentile, one-sided lower bound.

    Determinism: a single random.Random(scheme.seed) drives every draw in a fixed
    (year-ascending, then within-replicate block-draw) order; the seed has zero free
    parameters. FAILS CLOSED (EstimatorBindingError) unless `scheme` is the REGISTERED
    scheme, and refuses under `python -O`."""
    _guard_optimize("year_stratified_session_block_lcb")
    if not scheme.is_registered():
        raise EstimatorBindingError(
            "BLOCKED-PENDING-ESTIMATOR: year-stratified session-block LCB accepts only "
            "REGISTERED_SESSION_BLOCK_SCHEME (block_len=5, replicates=10000, seed derived "
            "from the accepted compact-session registry root "
            f"{ACCEPTED_COMPACT_SESSIONS_ROOT}); refusing an unpinned/ad-hoc scheme "
            f"(got block_len={scheme.block_len}, replicates={scheme.replicates}, "
            f"seed_root={scheme.seed_root!r})."
        )
    if not (0.0 < confidence < 1.0):
        raise EstimatorLawError(f"confidence must be in (0, 1), got {confidence}")
    if len(sessions) == 0:
        raise EstimatorLawError("sessions must be non-empty")

    strata: Dict[int, List[SessionRecall]] = {}
    for s in sessions:
        if type(s.hits) is not int or type(s.truths) is not int:
            raise EstimatorLawError(
                f"hits/truths must be plain ints (session ordinal {s.ordinal})"
            )
        if s.hits < 0 or s.truths < 0:
            raise EstimatorLawError(
                f"negative counts: hits={s.hits} truths={s.truths} (ordinal {s.ordinal})"
            )
        if s.hits > s.truths:
            raise EstimatorLawError(
                f"hits {s.hits} exceed truths {s.truths} (session ordinal {s.ordinal})"
            )
        strata.setdefault(s.year, []).append(s)

    for year, recs in strata.items():
        recs.sort(key=lambda r: r.ordinal)
        ordinals = [r.ordinal for r in recs]
        if len(set(ordinals)) != len(ordinals):
            raise EstimatorLawError(f"duplicate session ordinal within year {year}")

    total_truths = sum(s.truths for s in sessions)
    if total_truths <= 0:
        raise EstimatorLawError("pooled truths must be positive")

    ordered_years = sorted(strata.keys())
    stratum_blocks: List[Tuple[List[List[SessionRecall]], int]] = []
    L = scheme.block_len
    for year in ordered_years:
        recs = strata[year]
        n = len(recs)
        blocks = [recs[i : i + L] for i in range(0, n, L)]
        stratum_blocks.append((blocks, n))

    rng = random.Random(scheme.seed)
    recalls: List[float] = []
    for _ in range(scheme.replicates):
        h = 0
        t = 0
        for blocks, n in stratum_blocks:
            nb = len(blocks)
            got = 0
            while got < n:
                blk = blocks[rng.randrange(nb)]
                take = blk if got + len(blk) <= n else blk[: n - got]
                for rec in take:
                    h += rec.hits
                    t += rec.truths
                got += len(take)
        recalls.append(h / t if t > 0 else 0.0)
    recalls.sort()
    idx = int((1.0 - confidence) * (len(recalls) - 1))
    return recalls[idx]


def block_lcb_wilson_crosscheck(
    sessions: Sequence[SessionRecall],
    scheme: SessionBlockScheme = REGISTERED_SESSION_BLOCK_SCHEME,
    confidence: float = 0.95,
) -> Tuple[bool, float, float]:
    """Executable Wilson cross-check (freeze v4 Section 5.2). Returns
    `(agree, block_lcb, wilson_lcb)` where `agree` is True iff BOTH bounds are genuine
    one-sided lower bounds (<= the pooled point recall) AND they agree within the
    registered tolerance WILSON_AGREEMENT_TOL. Applies to the near-homogeneous 0.80
    knife-edge reference; a clustered real stream may legitimately diverge more, which is
    exactly why the block bootstrap -- not Wilson -- is the gate."""
    pooled_h = sum(s.hits for s in sessions)
    pooled_n = sum(s.truths for s in sessions)
    if pooled_n <= 0:
        raise EstimatorLawError("pooled truths must be positive")
    point = pooled_h / pooled_n
    block = year_stratified_session_block_lcb(sessions, scheme, confidence)
    wilson = wilson_one_sided_lcb(pooled_h, pooled_n)
    agree = (
        block <= point + 1e-12
        and wilson <= point + 1e-12
        and abs(block - wilson) <= WILSON_AGREEMENT_TOL
    )
    return agree, block, wilson


# ---------------------------------------------------------------------------
# DISTINCT_EPISODE_SUPPORT (attack #7 adequacy-dedup law)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CandidateRecord:
    truth_id: str
    session_id: str
    candidate_id: str
    timely: bool
    emit_order: int  # lower = earlier; ties broken by candidate_id for determinism


def distinct_episode_support(records: Sequence[CandidateRecord]) -> Tuple[int, Dict[str, str]]:
    """Support counted by distinct truth episodes: credit exactly ONE earliest-timely unique
    hit per truth, regardless of candidate multiplicity (1/2/1000 duplicates -> still one).
    Returns (support_count, {truth_id: credited candidate_id})."""
    best: Dict[str, CandidateRecord] = {}
    for r in records:
        if not r.timely:
            continue
        cur = best.get(r.truth_id)
        if cur is None or (r.emit_order, r.candidate_id) < (cur.emit_order, cur.candidate_id):
            best[r.truth_id] = r
    credited = {tid: rec.candidate_id for tid, rec in best.items()}
    return len(credited), credited


# ---------------------------------------------------------------------------
# RECENCY_DECAY (attack #4 recency/TTL law)
# ---------------------------------------------------------------------------

def recency_decay_weight(age: float, half_life: float) -> float:
    """Exponential recency decay: weight = 0.5 ** (age / half_life). age/half_life > 0."""
    if half_life <= 0:
        raise EstimatorLawError(f"half_life must be positive, got {half_life}")
    if age < 0:
        raise EstimatorLawError(f"age must be non-negative, got {age}")
    return 0.5 ** (age / half_life)


def is_expired(age: float, ttl: float) -> bool:
    """Hard TTL: strictly past the TTL, the expert is expired (loses the route)."""
    if ttl <= 0:
        raise EstimatorLawError(f"ttl must be positive, got {ttl}")
    return age > ttl


# ---------------------------------------------------------------------------
# CORRECTION_ENVELOPE (attack #8 late-correction law)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CommittedOrigin:
    origin_id: str
    origin_ts: int  # monotone logical time

@dataclass(frozen=True)
class CorrectionEnvelope:
    correction_id: str
    corrects_origin_id: str      # which committed origin this corrects
    received_ts: int             # correction-received time (its OWN prospective timestamp)
    creates_new_origin_ids: Sequence[str] = field(default_factory=tuple)  # must be empty


def validate_correction_envelope(
    original: CommittedOrigin, correction: CorrectionEnvelope
) -> List[str]:
    """Return the list of violations of the append-only, prospective-only correction law
    (attack #8). Empty list == a valid prospective correction."""
    violations: List[str] = []
    if correction.corrects_origin_id != original.origin_id:
        violations.append(
            f"correction targets {correction.corrects_origin_id!r} but original origin is "
            f"{original.origin_id!r}"
        )
    if correction.received_ts <= original.origin_ts:
        violations.append(
            f"correction received_ts={correction.received_ts} is not strictly after the "
            f"committed origin_ts={original.origin_ts} -- it would masquerade as the original "
            f"observation, not a prospective correction"
        )
    if correction.correction_id == original.origin_id:
        violations.append("correction reuses the committed origin_id as its own id")
    if len(correction.creates_new_origin_ids) != 0:
        violations.append(
            f"correction must create NO new session/truth/event/OOF origin, but declares "
            f"{list(correction.creates_new_origin_ids)}"
        )
    return violations


# ---------------------------------------------------------------------------
# ADMISSIBILITY_RECOMPUTE (attack #10 / C8: recompute from typed transitive lineage)
# ---------------------------------------------------------------------------

AUTHORIZED_ROOT_ROLES: Set[str] = {"source", "event", "truth"}


@dataclass(frozen=True)
class LineageNode:
    field: str
    role: str                 # "source"/"event"/"truth" (root) or "derived"
    economic: bool = False    # True if THIS node is an economic quantity (MFE/MAE/PnL/...)
    parents: Sequence[str] = field(default_factory=tuple)  # parent field names (derived only)
    formula_id: str = ""      # authorized formula id (derived only)


def recompute_admissibility(
    dag: Mapping[str, LineageNode], input_field: str
) -> Tuple[bool, str]:
    """Walk the lineage DAG from a fitting/routing input through formula IDs to roots and
    RECOMPUTE admissibility (never trust a declared tag/name). Rejects: unknown/missing
    provenance; a root whose role is not an authorized source/event/truth role; ANY node in
    the transitive derivation that is economically derived (incl. renamed-but-still-economic).
    Returns (admissible, reason). This is the SYNTHETIC-DAG reference; it binds to the real R2
    registry at Phase-3 checkpoint 3."""
    if input_field not in dag:
        return False, f"unknown/missing provenance for input field {input_field!r}"
    seen: Set[str] = set()
    stack = [input_field]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        node = dag.get(name)
        if node is None:
            return False, f"missing provenance node for {name!r} (free-form/unknown lineage)"
        if node.economic:
            return False, (
                f"economically-derived node {name!r} on the lineage of {input_field!r} -- "
                f"rejected regardless of declared tag/role={node.role!r}"
            )
        if node.role == "derived":
            if not node.parents:
                return False, f"derived node {name!r} has no parents (free-form lineage)"
            if node.formula_id == "":
                return False, f"derived node {name!r} has no authorized formula_id"
            stack.extend(node.parents)
        elif node.role in AUTHORIZED_ROOT_ROLES:
            if node.parents:
                return False, f"root node {name!r} (role={node.role}) must have no parents"
        else:
            return False, f"node {name!r} has unauthorized role {node.role!r}"
    return True, "admissible: lineage terminates in authorized roots with no economic node"


# ---------------------------------------------------------------------------
# Frozen law catalogue (for `show` + binding-point audit)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LawSpec:
    id: str
    name: str
    binding_point: str  # "" = fully frozen now; else where its numbers/artifacts bind


LAWS: List[LawSpec] = [
    LawSpec("POOLED_RECALL", "hits / confirmed_truths (R<=2)", ""),
    LawSpec("FAIL_CLOSED_TRUTH_IDENTITY", "confirmed_truths == hits + 5 typed misses", ""),
    LawSpec("SESSION_BLOCK_LCB", "Wilson reference + (legacy) pooled block bootstrap",
            "superseded as the gate by YEAR_STRATIFIED_SESSION_BLOCK_LCB; retained for compatibility"),
    LawSpec("YEAR_STRATIFIED_SESSION_BLOCK_LCB",
            "year-stratified session-block bootstrap one-sided 95% LCB (v4 gate statistic)",
            ""),
    LawSpec("DISTINCT_EPISODE_SUPPORT", "one earliest-timely credit per truth", ""),
    LawSpec("RECENCY_DECAY", "0.5 ** (age/half_life) + hard TTL", ""),
    LawSpec("CORRECTION_ENVELOPE", "append-only prospective-only correction", ""),
    LawSpec("ADMISSIBILITY_RECOMPUTE", "recompute from typed transitive lineage",
            "binds to the real R2 registry at Phase-3 checkpoint 3 (synthetic DAG now)"),
]


def _run_selftest() -> int:
    # A frozen gate module must never certify SELFTEST OK with assertions stripped.
    if sys.flags.optimize != 0:
        print(f"SELFTEST REFUSED under python -O (optimize level {sys.flags.optimize}): "
              f"rerun without -O so the fail-closed guards are active.")
        return 1
    failures: List[str] = []

    def check(label: str, cond: bool) -> None:
        if not cond:
            failures.append(label)

    def approx(a: float, b: float, tol: float = 1e-12) -> bool:
        return abs(a - b) <= tol

    # --- pooled recall + fail-closed identity ---
    check("pooled recall 80/100 == 0.8", pooled_recall(80, 100) == 0.8)
    raised = False
    try:
        pooled_recall(5, 0)
    except EstimatorLawError:
        raised = True
    check("pooled recall with 0 confirmed_truths is rejected", raised)

    ok_misses = {"no_candidate": 10, "untimely": 5, "wrong_side": 3,
                 "unsettled_tail": 2, "typed_other": 0}
    try:
        check_confirmed_truth_identity(100, 80, ok_misses)
        identity_ok = True
    except EstimatorLawError:
        identity_ok = False
    check("valid fail-closed identity (80 + 20) passes", identity_ok)

    raised = False
    try:
        check_confirmed_truth_identity(100, 80, {"no_candidate": 10, "untimely": 5, "wrong_side": 3})
    except EstimatorLawError:
        raised = True
    check("identity with only 3 miss categories is rejected (must be exactly 5)", raised)

    raised = False
    try:  # arithmetic mismatch: 80 + 19 != 100
        bad = dict(ok_misses); bad["typed_other"] = -1  # also negative -> two ways to fail
        check_confirmed_truth_identity(100, 80, bad)
    except EstimatorLawError:
        raised = True
    check("identity arithmetic mismatch / negative count is rejected", raised)

    # --- Wilson one-sided LCB: independent recomputation at the 0.80 knife-edge ---
    lcb = wilson_one_sided_lcb(80, 100)
    z = ONE_SIDED_95_Z
    p = 0.8
    denom = 1.0 + z * z / 100
    center = (p + z * z / 200) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / 100 + z * z / (4 * 100 * 100))
    ref = center - margin
    check("Wilson LCB matches an independent inline recomputation (bit-for-bit)", lcb == ref)
    check("Wilson LCB at point-recall 0.80 is strictly below 0.80 (it is a LOWER bound)", lcb < 0.80)
    check("more hits at fixed n raises the LCB (monotone)",
          wilson_one_sided_lcb(85, 100) > wilson_one_sided_lcb(80, 100))
    # knife-edge: at large n the LCB approaches the point estimate from below
    check("large-n LCB is closer to 0.80 than small-n LCB (knife-edge tightens)",
          (0.80 - wilson_one_sided_lcb(7131, 8914)) < (0.80 - wilson_one_sided_lcb(80, 100)))

    # --- session-block LCB: BLOCKED without pinned params; deterministic with them ---
    raised = False
    try:
        session_block_lcb([8, 9], [10, 10], UNPINNED_PARAMS)
    except EstimatorBindingError:
        raised = True
    check("session-block LCB fails closed with unpinned params (C17 binding point)", raised)

    pinned = EstimatorParams(block_scheme="session-block-year-stratified", replicates=200, seed=1234)
    v1 = session_block_lcb([8, 9, 7, 8], [10, 10, 10, 10], pinned)
    v2 = session_block_lcb([8, 9, 7, 8], [10, 10, 10, 10], pinned)
    check("session-block LCB is deterministic for a fixed seed", v1 == v2)
    check("session-block LCB lies in [0,1]", 0.0 <= v1 <= 1.0)

    # --- YEAR-STRATIFIED session-block LCB (v4 gate statistic) ---
    # Deterministic seed law: zero free parameters, hand-recomputable from the published root.
    check("seed is the low 64 bits of the accepted-session registry root (hand-checkable)",
          SESSION_BLOCK_SEED == int(ACCEPTED_COMPACT_SESSIONS_ROOT[-16:], 16)
          == 13194541372617247469)
    check("registered scheme reports is_registered()",
          REGISTERED_SESSION_BLOCK_SCHEME.is_registered()
          and REGISTERED_SESSION_BLOCK_SCHEME.seed == SESSION_BLOCK_SEED)

    # python -O guard: the injectable refusal path is self-tested (and we confirm this run
    # is NOT under -O, so the assertion-checked invariants are actually live).
    check("this selftest run is not under python -O", sys.flags.optimize == 0)
    _guard_optimize("probe", level=0)  # must NOT raise
    for lvl in (1, 2):
        raised = False
        try:
            _guard_optimize("probe", level=lvl)
        except EstimatorBindingError:
            raised = True
        check(f"year-stratified LCB refuses under python -O (optimize level {lvl})", raised)

    # typed refusal for unpinned / ad-hoc schemes (closes the TA-03 post-hoc-knob loophole)
    def _refuses(scheme_obj) -> bool:
        try:
            year_stratified_session_block_lcb(
                [SessionRecall(2022, 0, 8, 10), SessionRecall(2022, 1, 9, 10)], scheme_obj)
        except EstimatorBindingError:
            return True
        return False
    check("year-stratified LCB fails closed with the UNPINNED scheme",
          _refuses(UNPINNED_SESSION_BLOCK_SCHEME))
    check("year-stratified LCB refuses an ad-hoc block_len",
          _refuses(SessionBlockScheme(7, SESSION_BLOCK_REPLICATES, ACCEPTED_COMPACT_SESSIONS_ROOT)))
    check("year-stratified LCB refuses an ad-hoc replicate count",
          _refuses(SessionBlockScheme(SESSION_BLOCK_LEN, 500, ACCEPTED_COMPACT_SESSIONS_ROOT)))
    check("year-stratified LCB refuses a foreign (non-published) seed root",
          _refuses(SessionBlockScheme(SESSION_BLOCK_LEN, SESSION_BLOCK_REPLICATES, "00" * 32)))

    # count / hits<=truths validation on the real interface
    raised = False
    try:
        year_stratified_session_block_lcb([SessionRecall(2022, 0, 11, 10)])
    except EstimatorLawError:
        raised = True
    check("year-stratified LCB rejects hits > truths", raised)
    raised = False
    try:
        year_stratified_session_block_lcb([SessionRecall(2022, 0, -1, 10)])
    except EstimatorLawError:
        raised = True
    check("year-stratified LCB rejects negative counts", raised)
    raised = False
    try:
        year_stratified_session_block_lcb(
            [SessionRecall(2022, 0, 1, 1), SessionRecall(2022, 0, 1, 1)])
    except EstimatorLawError:
        raised = True
    check("year-stratified LCB rejects duplicate session ordinals within a year", raised)

    # exact deterministic knife-edge vector -----------------------------------------
    # Build the 1,003-session authority shape (251/250/252/250) at pooled hits/truths
    # 7132/8914 -- 7132 is the FIRST PASSING integer point count (5*7132 >= 4*8914,
    # point recall 0.80009). The block LCB must land STRICTLY BELOW 0.80: the point gate
    # passes but the stability guard (b) correctly refuses this knife-edge stream.
    def _knife_edge_population() -> List[SessionRecall]:
        sizes = ((2022, 251), (2023, 250), (2024, 252), (2025, 250))
        n = 1003
        total_h, total_t = 7132, 8914
        base_h, extra_h = divmod(total_h, n)   # 7, 111
        base_t, extra_t = divmod(total_t, n)   # 8, 890
        pop: List[SessionRecall] = []
        idx = 0
        ordinal = 0
        for year, sz in sizes:
            for _ in range(sz):
                h = base_h + (1 if idx < extra_h else 0)
                t = base_t + (1 if idx < extra_t else 0)
                pop.append(SessionRecall(year, ordinal, h, t))
                ordinal += 1
                idx += 1
        return pop

    ke = _knife_edge_population()
    check("knife-edge population totals are exactly 7132 / 8914",
          sum(s.hits for s in ke) == 7132 and sum(s.truths for s in ke) == 8914)
    check("knife-edge point recall PASSES the integer point gate (5*hits >= 4*8914)",
          5 * 7132 >= 4 * 8914)
    ke_lcb = year_stratified_session_block_lcb(ke)
    check("year-stratified LCB is exactly the pinned knife-edge value (bit-for-bit)",
          ke_lcb == 0.7959869969734334)
    check("knife-edge LCB is STRICTLY BELOW 0.80 -- guard (b) refuses a knife-edge point pass",
          ke_lcb < 0.80)
    check("year-stratified LCB is deterministic (identical on re-run)",
          year_stratified_session_block_lcb(ke) == ke_lcb)

    # executable Wilson cross-check at the knife edge (Section 5.2 predicate)
    agree, block, wil = block_lcb_wilson_crosscheck(ke)
    check("block LCB agrees with the closed-form Wilson LCB at the knife edge (<= tol)", agree)
    check("both block and Wilson LCB are genuine lower bounds below 0.80",
          block < 0.80 and wil < 0.80)

    # a comfortably-passing stream: pooled 7500/8914 (point recall 0.8414) clears both halves
    def _pass_population() -> List[SessionRecall]:
        ke2 = _knife_edge_population()
        # promote 368 misses to hits deterministically -> pooled 7500/8914
        out: List[SessionRecall] = []
        promoted = 0
        for s in ke2:
            if promoted < 368 and s.hits < s.truths:
                out.append(SessionRecall(s.year, s.ordinal, s.hits + 1, s.truths))
                promoted += 1
            else:
                out.append(s)
        return out
    pp = _pass_population()
    check("passing population totals are 7500 / 8914",
          sum(s.hits for s in pp) == 7500 and sum(s.truths for s in pp) == 8914)
    check("passing-stream LCB clears the 0.80 floor (guard (b) passes)",
          year_stratified_session_block_lcb(pp) >= 0.80)

    # --- distinct-episode support: multiplicity invariance (attack #7) ---
    dupes = [CandidateRecord("T1", "S1", f"c{i}", True, emit_order=i) for i in range(1000)]
    one = [CandidateRecord("T2", "S1", "c0", True, emit_order=0)]
    support, credited = distinct_episode_support(dupes + one)
    check("1000 duplicates around T1 + 1 for T2 -> support == 2 (distinct truths)", support == 2)
    check("earliest-timely candidate credited for T1", credited["T1"] == "c0")
    # untimely-only truth earns no support
    untimely = [CandidateRecord("T3", "S1", "cX", False, emit_order=0)]
    support2, _ = distinct_episode_support(untimely)
    check("a truth with only untimely candidates earns zero support", support2 == 0)

    # --- recency decay + TTL (attack #4) ---
    check("decay weight halves after one half-life", approx(recency_decay_weight(5, 5), 0.5))
    check("decay weight quarters after two half-lives", approx(recency_decay_weight(10, 5), 0.25))
    check("age within TTL is not expired", not is_expired(4, 5))
    check("age past TTL is expired", is_expired(6, 5))

    # --- correction envelope (attack #8) ---
    origin = CommittedOrigin(origin_id="O1", origin_ts=100)
    good = CorrectionEnvelope(correction_id="K1", corrects_origin_id="O1", received_ts=200)
    check("a strictly-later correction with no new origin is valid",
          validate_correction_envelope(origin, good) == [])
    early = CorrectionEnvelope(correction_id="K2", corrects_origin_id="O1", received_ts=100)
    check("a correction dated at/before origin_ts is rejected (masquerade)",
          validate_correction_envelope(origin, early) != [])
    masq = CorrectionEnvelope(correction_id="K3", corrects_origin_id="O1", received_ts=200,
                              creates_new_origin_ids=("O2",))
    check("a correction that creates a new origin is rejected",
          any("NO new" in v for v in validate_correction_envelope(origin, masq)))

    # --- admissibility recompute (attack #10 / C8) ---
    clean = {
        "src_px": LineageNode("src_px", "source"),
        "evt_tape": LineageNode("evt_tape", "event"),
        "regime_feat": LineageNode("regime_feat", "derived", parents=("src_px", "evt_tape"),
                                   formula_id="F1"),
    }
    adm, _ = recompute_admissibility(clean, "regime_feat")
    check("a clean lineage to authorized roots is admissible", adm)

    econ_direct = {"mfe": LineageNode("mfe", "derived", economic=True, parents=("src_px",),
                                      formula_id="F2"),
                   "src_px": LineageNode("src_px", "source")}
    adm2, reason2 = recompute_admissibility(econ_direct, "mfe")
    check("a directly economic field is rejected", not adm2 and "economic" in reason2)

    # the renamed attack: innocuous tag, but its lineage still passes through an economic node
    renamed = {
        "benign_tag": LineageNode("benign_tag", "derived", parents=("hidden_pnl",),
                                  formula_id="F3"),
        "hidden_pnl": LineageNode("hidden_pnl", "derived", economic=True, parents=("src_px",),
                                  formula_id="F4"),
        "src_px": LineageNode("src_px", "source"),
    }
    adm3, _ = recompute_admissibility(renamed, "benign_tag")
    check("a renamed-but-still-economically-derived field is rejected (walks lineage, not tag)",
          not adm3)

    missing = {"x": LineageNode("x", "derived", parents=("gone",), formula_id="F5")}
    adm4, _ = recompute_admissibility(missing, "x")
    check("a lineage with a missing parent is rejected", not adm4)

    unauth = {"y": LineageNode("y", "mystery_role")}
    adm5, reason5 = recompute_admissibility(unauth, "y")
    check("an unauthorized root role is rejected", not adm5 and "unauthorized" in reason5)

    adm6, _ = recompute_admissibility(clean, "not_present")
    check("an unknown input field is rejected", not adm6)

    # --- law catalogue binding points documented ---
    by_id = {l.id: l for l in LAWS}
    check("legacy SESSION_BLOCK_LCB is marked superseded as the gate",
          "superseded" in by_id["SESSION_BLOCK_LCB"].binding_point)
    check("YEAR_STRATIFIED_SESSION_BLOCK_LCB is fully frozen now (no binding point)",
          by_id["YEAR_STRATIFIED_SESSION_BLOCK_LCB"].binding_point == "")
    check("ADMISSIBILITY_RECOMPUTE documents the Phase-3 checkpoint-3 binding point",
          "checkpoint 3" in by_id["ADMISSIBILITY_RECOMPUTE"].binding_point)
    check("fully-frozen laws carry no binding point",
          by_id["POOLED_RECALL"].binding_point == "" and by_id["RECENCY_DECAY"].binding_point == "")

    if failures:
        print("SELFTEST FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("SELFTEST OK")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest", help="run internal self-tests at the 0.80 knife-edge + hostile cases")
    sub.add_parser("show", help="print the frozen law catalogue + binding points")
    args = p.parse_args(argv)
    if args.cmd == "selftest":
        return _run_selftest()
    if args.cmd == "show":
        for l in LAWS:
            bp = l.binding_point if l.binding_point else "(fully frozen now)"
            print(f"{l.id}\t{l.name}\t{bp}")
        return 0
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except EstimatorLawError as e:
        print(f"estimator law error: {e}", file=sys.stderr)
        sys.exit(1)
