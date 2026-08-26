"""Build, load and register the qrdisc native extension.

BUILD LOCATION LAW
    Build trees live ONLY under /workspace/artifacts/cache/cpp.  The loader
    invokes g++ directly.  Nothing is written to the container overlay, and
    nothing is ever downloaded: the extension is the raw CPython C API against
    the interpreter's own headers plus numpy's, both already on this box.

STALE-BINARY REFUSAL
    The compiled module carries the sha256 of the exact C++ sources it was built
    from, baked in at compile time as QRDISC_SOURCE_MANIFEST_SHA256.  The loader
    recomputes that manifest from disk and REFUSES a module whose baked value
    disagrees.  Without it, an edited kernel plus a cached .so silently produces
    a differential PASS for code nobody is running any more — the exact failure
    mode D-017's byte comparison exists to make impossible.

REGISTRATION
    `qrdisc_register_builder` inserts the builder into DISC_NATIVE_BUILDERS
    (disc_native_builders.py:373).  It is a function here rather than a literal
    entry there because disc_native_builders.py is stage-1 proven code and the
    rehearsal forbids editing existing engine files; tools/
    diff_discretionary_native_qrdisc.py calls it before argument parsing.
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import sysconfig
from pathlib import Path
from types import ModuleType

import numpy as np
from threadpoolctl import threadpool_limits

from engine.entry_v2.disc_native_builders import (
    DISC_NATIVE_BUILDERS, DiscSessionCapture, RegisteredDiscBuilder,
    StoredShardView)
from engine.entry_v2.disc_native_differential import BuiltFeatures
from engine.entry_v2.discretionary_features import (
    CausalDiscretionaryPlane, DiscretionaryFeatureRefusal,
    PriorSessionContext)
from engine.entry_v2.qrdisc_state_marshal import (
    qrdisc_marshal_plane, qrdisc_warm_plane_caches)
from engine.entry_v2.tabular_campaign import NATIVE_THREADS_PER_CORPUS_WORKER

QRDISC_MODULE_NAME = "qr_disc_native"
QRDISC_BUILDER_NAME = "qrdisc-native-skeleton"
QRDISC_WAVE1_BUILDER_NAME = "qrdisc-native-wave1"
QRDISC_TAIL_BUILDER_NAME = "qrdisc-native-tail"
# Stage 4 wave 1 (rising-entanglement order): the candidate-only vol family,
# the second-clock regime family, then the first family that reads marshalled
# session state.  A name here is switched to native by mapping it to None in
# the delegation table; every other family stays the oracle's, which is always
# lawful.
QRDISC_WAVE1_FAMILIES = ("_forward_vol_map", "_regime_map", "_target_map")
QRDISC_WAVE2A_BUILDER_NAME = "qrdisc-native-wave2a"
# Stage 4 wave 2, lane A: wave 1 plus the heaviest event family.  Lane A's other
# target, `_trade_slice_map`, is NOT a feature_map family — it is the shared body
# of the two clock families lane B owns (discretionary_features.py:1677, :1694) —
# so it lands as a kernel gated at its own seam and joins a builder only when
# those clocks go native.
QRDISC_WAVE2A_FAMILIES = QRDISC_WAVE1_FAMILIES + ("_event_micro_map",)
QRDISC_WAVE2B_BUILDER_NAME = "qrdisc-native-wave2b"
# Stage 4 wave 2, lane B: wave 1 plus the two event-driven clock families, the
# volume clock and the prior-reaction family.  The two trade clocks call lane
# A's `_trade_slice_map` kernel, so this builder is the seam that first exercises
# it through a whole row.
QRDISC_WAVE2B_FAMILIES = QRDISC_WAVE1_FAMILIES + (
    "_prior_reaction_map", "_event_clock_map", "_trade_clock_map",
    "_volume_clock_map")
# Stage 4, wave 2, lane C: the families are wave 1's, unchanged — what is new is
# that the port ASSEMBLES the row (qrdisc_assembly.cpp) instead of splicing over
# the whole-map delegate.  Holding the family set fixed is the point: the only
# difference from qrdisc-native-wave1 is the assembly, so the differential
# arbitrates the assembly and the speed delta measures it.
QRDISC_TAIL_FAMILIES = QRDISC_WAVE1_FAMILIES
QRDISC_WAVE2_BUILDER_NAME = "qrdisc-native-wave2"
# Stage 4, wave 2, the SHIPPED end state: every ported family native AND the
# port assembling the row.  Lanes A, B and C each proved one axis on its own;
# this builder is the combination the production path would actually run, and
# until R6 F10 it had no differential receipt of its own.
QRDISC_WAVE2_FAMILIES = QRDISC_WAVE2B_FAMILIES + ("_event_micro_map",)
QRDISC_CPP_ROOT = Path("/workspace/engine/cpp/qr_entry_v2")
QRDISC_BUILD_ROOT = Path("/workspace/artifacts/cache/cpp/qrdisc")
# Order is part of the manifest: a reordering would change the sha and force a
# rebuild, which is harmless, while a MISSING file would not — so the list is
# explicit and every file the module compiles or includes is on it.
QRDISC_CPP_SOURCES = (
    "include/qr_entry_v2/qrdisc_types.hpp",
    "include/qr_entry_v2/qrdisc_np_kernels.hpp",
    "include/qr_entry_v2/qrdisc_plane_state.hpp",
    "include/qr_entry_v2/qrdisc_maps.hpp",
    "include/qr_entry_v2/qrdisc_kernels_events.hpp",
    "src/qrdisc_np_kernels.cpp",
    "src/qrdisc_plane_state.cpp",
    "src/qrdisc_kernels_events.cpp",
    "src/qrdisc_maps_vol.cpp",
    "src/qrdisc_maps_regime.cpp",
    "src/qrdisc_maps_micro.cpp",
    "src/qrdisc_maps_slice.cpp",
    "src/qrdisc_maps_clock.cpp",
    "src/qrdisc_maps_prior.cpp",
    "include/qr_entry_v2/qrdisc_assembly.hpp",
    "src/qrdisc_assembly_merge.cpp",
    "src/qrdisc_assembly.cpp",
    "src/qrdisc_assembly_tail.cpp",
    "src/qrdisc_pymodule.cpp",
)
# House FP law: -ffp-contract=off, no fast-math,
# warnings are errors.  Python/numpy headers come in with -isystem so their own
# pedantic diagnostics cannot fail our build.
# Ticket 41, and the measurement matters more than the reasoning. -O3 with
# -fno-math-errno is lossless here because -ffp-contract=off stays and nothing
# enables -ffast-math or -fassociative-math, so GCC may not reorder a
# floating-point reduction and the float64 bytes are the oracle's; that is
# PROVEN by the standing differential, not argued (receipt
# disc_native_differential_o3_allstore300.json, 5/5 store sessions PASS).
#
# It also buys almost nothing: 3.8385 ms/row against -O2's 3.8616, which is 0.6%
# and inside the run-to-run spread the oracle itself shows (7.0668 vs 7.1473).
# Recorded so nobody re-runs this experiment: the remaining cost is NOT compute
# in the ported families, it is the row's calls back into Python for the
# families wave 2 did not port. More speed means porting more families, not more
# flags. -march=native was tried in the same pass, passed the differential, and
# was REMOVED anyway: zero measured gain does not justify a binary that dies
# with SIGILL if the pod's CPU changes under it.
QRDISC_COMPILE_FLAGS = (
    "-std=c++20", "-O3", "-fno-math-errno", "-g", "-fPIC", "-shared",
    "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-ffp-contract=off",
)


class QrdiscNativeRefusal(RuntimeError):
    """The native module could not be built, or is not the sources on disk."""


def qrdisc_source_manifest() -> tuple[str, str]:
    """(sha256, text) over the listed C++ sources AND the compile flags.

    The sha addresses the build directory, so anything that changes the emitted
    binary must be in it. Sources alone are not enough: raising -O2 to -O3 leaves
    the cached `.so` at the same address, the next run loads the OLD binary, and
    any speed or byte-identity number taken from it is measuring code that is no
    longer the code on disk. Ticket 41; fixture
    test_qrdisc_state_marshal.test_manifest_sha_covers_the_compile_flags.
    """

    lines = [f"FLAGS {' '.join(QRDISC_COMPILE_FLAGS)}"]
    for relative in QRDISC_CPP_SOURCES:
        path = QRDISC_CPP_ROOT / relative
        if not path.is_file():
            raise QrdiscNativeRefusal(
                f"qrdisc source is missing: {path}; the manifest covers "
                f"{len(QRDISC_CPP_SOURCES)} files and all must exist")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{relative} {digest}")
    text = "\n".join(lines) + "\n"
    return hashlib.sha256(text.encode()).hexdigest(), text


def qrdisc_build_extension(*, force: bool = False) -> tuple[Path, str]:
    """Compile the extension into a sha-addressed directory; return its path."""

    manifest_sha, manifest_text = qrdisc_source_manifest()
    build_dir = QRDISC_BUILD_ROOT / manifest_sha[:16]
    library = build_dir / f"{QRDISC_MODULE_NAME}.so"
    if library.is_file() and not force:
        return library, manifest_sha
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "source_manifest.txt").write_text(manifest_text)
    partial = library.with_name(f"{QRDISC_MODULE_NAME}.so.partial")
    command = [
        "g++", *QRDISC_COMPILE_FLAGS,
        f"-DQRDISC_SOURCE_MANIFEST_SHA256=\"{manifest_sha}\"",
        f"-I{QRDISC_CPP_ROOT / 'include'}",
        f"-isystem{sysconfig.get_paths()['include']}",
        f"-isystem{np.get_include()}",
        # Derived from the manifest, never a second hand-kept list: a source in
        # one and not the other is exactly the drift the sha is meant to catch.
        *[str(QRDISC_CPP_ROOT / relative) for relative in QRDISC_CPP_SOURCES
          if relative.endswith(".cpp")],
        # Compiled under a partial name and renamed on success: a build killed
        # half-way must not leave a truncated .so that the next call accepts
        # because the path exists.
        "-o", str(partial),
    ]
    (build_dir / "compile_command.txt").write_text(" ".join(command) + "\n")
    finished = subprocess.run(command, capture_output=True, text=True)
    (build_dir / "compile.log").write_text(finished.stderr)
    if finished.returncode != 0:
        partial.unlink(missing_ok=True)
        raise QrdiscNativeRefusal(
            f"qrdisc extension failed to compile (exit {finished.returncode}); "
            f"log={build_dir / 'compile.log'}\n{finished.stderr[-4000:]}")
    partial.replace(library)
    return library, manifest_sha


def load_qrdisc_native(*, force_rebuild: bool = False) -> ModuleType:
    """Import the extension, then prove it is the sources on disk."""

    library, manifest_sha = qrdisc_build_extension(force=force_rebuild)
    cached = sys.modules.get(QRDISC_MODULE_NAME)
    if cached is not None:
        baked_in_process = cached.source_manifest_sha256()
        if baked_in_process == manifest_sha:
            return cached
        # A second `.so` cannot be exec'd beside the live one: planes already
        # built carry pointers into the first module's heap type and its numpy
        # table, and the two binaries' QrdiscPlaneType would not compare equal.
        # An edit-then-reload inside one process is a REFUSAL, not a swap.
        raise QrdiscNativeRefusal(
            "qrdisc sources changed inside a live process: the loaded module "
            f"was built from manifest {baked_in_process} but the sources on "
            f"disk now hash to {manifest_sha}; restart the process rather than "
            "loading a second extension beside the planes already built")
    spec = importlib.util.spec_from_file_location(QRDISC_MODULE_NAME, library)
    if spec is None or spec.loader is None:
        raise QrdiscNativeRefusal(f"cannot load extension spec from {library}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    baked = module.source_manifest_sha256()
    if baked != manifest_sha:
        raise QrdiscNativeRefusal(
            "qrdisc native module is STALE: the binary was built from manifest "
            f"{baked} but the sources on disk hash to {manifest_sha}; "
            f"library={library}")
    sys.modules[QRDISC_MODULE_NAME] = module
    return module


def qrdisc_assembly_delegates(plane) -> dict[str, object]:
    """The per-method delegation table native row assembly needs.

    Native assembly (engine/cpp/qr_entry_v2/src/qrdisc_assembly.cpp) calls every
    family individually, so a family the port has not ported must be reachable
    by NAME rather than through the whole-map delegate.  The values are the
    oracle's own bound methods, so delegated arithmetic is still literally its
    bytes.  `_state_series` is here because the tail reads it
    (discretionary_features.py:2526), not because feature_map's fan-out does.

    The prior-session entry follows the oracle's own branch at :2417: a session
    with no prior day gets `PriorSessionContext.empty_feature_map`, which takes
    no arguments, and one with a prior day gets that context's bound feature_map.
    """

    delegates: dict[str, object] = {
        name: getattr(plane, name) for name in (
            "_profile_map", "_initial_balance_map", "_forward_vol_map",
            "_regime_map", "_target_map", "_level_values",
            "_prior_reaction_map", "_event_clock_map", "_trade_clock_map",
            "_volume_clock_map", "_tape_slope_map", "_test_maturity_map",
            "_best_quote_response_map", "_event_micro_map",
            "_price_shape_values", "_state_series")}
    if plane.prior_session is None:
        delegates["_prior_session_empty_feature_map"] = (
            PriorSessionContext.empty_feature_map)
    else:
        delegates["_prior_session_feature_map"] = plane.prior_session.feature_map
    return delegates


def qrdisc_build_native_plane(
    construction, queries, native_families: tuple[str, ...] = (),
    *, assemble_natively: bool = False,
) -> tuple[object, ModuleType, object]:
    """One session: build the oracle plane, WARM it, marshal it, hand it over.

    Returns (native_plane, module, python_plane).  Memory safety does not depend
    on the caller: `build_plane` INCREFs every buffer array it adopts, and each
    `plane_buffer` view keeps the native plane alive as its base.  The Python
    plane is returned because the delegate table is bound to it and stages 4+
    will need it for per-family comparison.

    The warming step is not optional: the phase-scoped profile/TPO series and
    the per-candidate state series are built lazily at row time, so an unwarmed
    plane marshals a cache holding only the constructor's start=0 entry and the
    native side has nothing to read for any other start.
    """

    module = load_qrdisc_native()
    plane = CausalDiscretionaryPlane(**construction)
    qrdisc_warm_plane_caches(plane, queries)
    scalars, buffers = qrdisc_marshal_plane(plane)
    delegates: dict[str, object] = {"feature_map": plane.feature_map}
    # With per-method delegates present the native path assembles the row and
    # the whole-map delegate above becomes the debugging fallback only.
    if assemble_natively:
        delegates.update(qrdisc_assembly_delegates(plane))
    # None marks a family the port owns.  It OVERRIDES the per-method entry, so
    # the two dicts compose: everything reachable by name, the ported ones native.
    delegates.update({family: None for family in native_families})
    native = module.build_plane(
        scalars=scalars, buffers=buffers, delegates=delegates,
        refusal_type=DiscretionaryFeatureRefusal)
    return native, module, plane


def qrdisc_rows_through_native(
    capture: DiscSessionCapture, native_families: tuple[str, ...],
    *, assemble_natively: bool = False,
) -> BuiltFeatures:
    """Answer one session's recorded queries through the native boundary.

    `native_families` selects which map families the port computes itself; the
    rest stay with the whole-map delegate, so the two registered builders are
    the same code path with a different delegation table.

    Pinned to the corpus workers' BLAS topology (tabular_campaign.py:359) for
    the same reason build_disc_features is: float64 provenance varies with
    reduction topology, and the delegated arithmetic still runs in numpy.
    """

    names: tuple[str, ...] | None = None
    matrix: np.ndarray | None = None
    queries = capture.queries
    snapshots = np.empty(len(queries), np.int64)
    sides = np.empty(len(queries), np.int64)
    with threadpool_limits(limits=NATIVE_THREADS_PER_CORPUS_WORKER):
        native, module, _oracle_plane = qrdisc_build_native_plane(
            capture.construction, queries, native_families,
            assemble_natively=assemble_natively)
        # The switch must be ASSERTED, never assumed: a table missing one family
        # falls back to the whole-map delegate, which still emits correct bytes,
        # and a speed number quoted off that run would be measuring the old path.
        if assemble_natively and not module.assembly_available(native):
            raise QrdiscNativeRefusal(
                "native row assembly was requested but the delegation table "
                "cannot answer every family individually; the row would fall "
                "back to the whole-map delegate and the run would measure the "
                "wrong path")
        calls_before = module.family_call_count(native)
        for index, query in enumerate(queries):
            values, emitted = module.feature_map_row(native, **query)
            if names is None:
                names = emitted
                matrix = np.empty((len(queries), len(names)), np.float32)
            elif emitted != names:
                raise QrdiscNativeRefusal(
                    "native builder emitted a different name order at row "
                    f"{index}: first divergence "
                    f"{next(a for a, b in zip(emitted, names) if a != b)!r}")
            matrix[index] = values
            snapshots[index] = int(query["snapshot_ts_ns"])
            sides[index] = int(query["side"])
        # The splice path's engagement guard, the counterpart of the assembly
        # branch's `assembly_available` assertion above.  A native family that
        # is silently never entered — a delegation-table typo, a name the
        # dispatcher does not know — still emits the oracle's own correct bytes,
        # so the differential PASSES and the run measures the old path.
        if not assemble_natively:
            observed = module.family_call_count(native) - calls_before
            expected = len(queries) * len(native_families)
            if observed != expected:
                raise QrdiscNativeRefusal(
                    "the native families were not all entered: the port ran "
                    f"{observed} family calls over {len(queries)} rows, "
                    f"expected {expected} "
                    f"({len(native_families)} native families per row)")
    return BuiltFeatures(names, matrix, snapshots, sides)


def qrdisc_skeleton_build(
    capture: DiscSessionCapture, stored: StoredShardView,
) -> BuiltFeatures:
    """Every family delegated: the boundary alone, no native arithmetic."""

    del stored
    return qrdisc_rows_through_native(capture, ())


def qrdisc_wave1_build(
    capture: DiscSessionCapture, stored: StoredShardView,
) -> BuiltFeatures:
    """Wave 1: the three families of QRDISC_WAVE1_FAMILIES computed natively."""

    del stored
    return qrdisc_rows_through_native(capture, QRDISC_WAVE1_FAMILIES)


def qrdisc_wave2a_build(
    capture: DiscSessionCapture, stored: StoredShardView,
) -> BuiltFeatures:
    """Wave 2 lane A: wave 1 plus `_event_micro_map` computed natively."""

    del stored
    return qrdisc_rows_through_native(capture, QRDISC_WAVE2A_FAMILIES)


def qrdisc_wave2b_build(
    capture: DiscSessionCapture, stored: StoredShardView,
) -> BuiltFeatures:
    """Wave 2 lane B: wave 1 plus the clock families and `_prior_reaction_map`."""

    del stored
    return qrdisc_rows_through_native(capture, QRDISC_WAVE2B_FAMILIES)


def qrdisc_tail_build(
    capture: DiscSessionCapture, stored: StoredShardView,
) -> BuiltFeatures:
    """Stage 4 wave 2: the port ASSEMBLES the row.

    Every family reachable by name — the ported ones native, the rest the
    oracle's own bound methods — merged in feature_map's insertion order, then
    the tail (discretionary_features.py:2502-2694) natively.  The whole-map
    delegate is not on this path, so this is the first builder whose native
    families cost nothing extra.
    """

    del stored
    return qrdisc_rows_through_native(
        capture, QRDISC_TAIL_FAMILIES, assemble_natively=True)


def qrdisc_wave2_build(
    capture: DiscSessionCapture, stored: StoredShardView,
) -> BuiltFeatures:
    """Stage 4 wave 2 END STATE: all eight native families AND native assembly.

    Lane A proved `_event_micro_map`, lane B the clocks and the prior reaction,
    lane C the assembly — each against a builder that held the other axis fixed.
    This is the combination, and the only builder whose delegation table matches
    what a production run would use.
    """

    del stored
    return qrdisc_rows_through_native(
        capture, QRDISC_WAVE2_FAMILIES, assemble_natively=True)


def qrdisc_register_builder(registry=DISC_NATIVE_BUILDERS) -> str:
    """Insert the skeleton and wave builders into the stage-1 registry."""

    registry.setdefault(QRDISC_BUILDER_NAME, RegisteredDiscBuilder(
        QRDISC_BUILDER_NAME, qrdisc_skeleton_build, True, False,
        "the qrdisc CPython extension with every map family still delegated to "
        "the oracle; it exercises the marshalled state and the row boundary, "
        "so a mismatch means plumbing, not arithmetic"))
    registry.setdefault(QRDISC_WAVE1_BUILDER_NAME, RegisteredDiscBuilder(
        QRDISC_WAVE1_BUILDER_NAME, qrdisc_wave1_build, True, False,
        "the qrdisc extension with " + ", ".join(QRDISC_WAVE1_FAMILIES) +
        " computed in C++ and spliced over the delegate's values; a mismatch "
        "here is native ARITHMETIC, because the skeleton builder already "
        "proved the boundary"))
    registry.setdefault(QRDISC_WAVE2A_BUILDER_NAME, RegisteredDiscBuilder(
        QRDISC_WAVE2A_BUILDER_NAME, qrdisc_wave2a_build, True, False,
        "the qrdisc extension with " + ", ".join(QRDISC_WAVE2A_FAMILIES) +
        " computed in C++ and spliced over the delegate's values"))
    registry.setdefault(QRDISC_WAVE2B_BUILDER_NAME, RegisteredDiscBuilder(
        QRDISC_WAVE2B_BUILDER_NAME, qrdisc_wave2b_build, True, False,
        "the qrdisc extension with " + ", ".join(QRDISC_WAVE2B_FAMILIES) +
        " computed in C++ and spliced over the delegate's values"))
    registry.setdefault(QRDISC_TAIL_BUILDER_NAME, RegisteredDiscBuilder(
        QRDISC_TAIL_BUILDER_NAME, qrdisc_tail_build, True, False,
        "the qrdisc extension ASSEMBLING the row: " +
        ", ".join(QRDISC_TAIL_FAMILIES) + " native, every other family "
        "delegated individually, and the tail (feature_map:2502-2694) in C++; "
        "the whole-map delegate is off the path"))
    registry.setdefault(QRDISC_WAVE2_BUILDER_NAME, RegisteredDiscBuilder(
        QRDISC_WAVE2_BUILDER_NAME, qrdisc_wave2_build, True, False,
        "the qrdisc extension ASSEMBLING the row with every ported family "
        "native: " + ", ".join(QRDISC_WAVE2_FAMILIES) + "; this is the wave-2 "
        "end state, the combination lanes A, B and C each proved one axis of"))
    return QRDISC_BUILDER_NAME


__all__ = [
    "QRDISC_BUILDER_NAME", "QRDISC_BUILD_ROOT", "QRDISC_CPP_ROOT",
    "QRDISC_CPP_SOURCES", "QRDISC_MODULE_NAME", "QRDISC_WAVE1_BUILDER_NAME",
    "QRDISC_TAIL_BUILDER_NAME", "QRDISC_TAIL_FAMILIES",
    "qrdisc_assembly_delegates", "qrdisc_tail_build",
    "QRDISC_WAVE1_FAMILIES", "QRDISC_WAVE2A_BUILDER_NAME",
    "QRDISC_WAVE2A_FAMILIES", "qrdisc_wave2a_build",
    "QRDISC_WAVE2B_BUILDER_NAME", "QRDISC_WAVE2B_FAMILIES",
    "qrdisc_wave2b_build",
    "QRDISC_WAVE2_BUILDER_NAME", "QRDISC_WAVE2_FAMILIES", "qrdisc_wave2_build",
    "QrdiscNativeRefusal", "load_qrdisc_native",
    "qrdisc_build_extension", "qrdisc_build_native_plane",
    "qrdisc_register_builder", "qrdisc_rows_through_native",
    "qrdisc_skeleton_build", "qrdisc_source_manifest", "qrdisc_wave1_build",
]
