"""Self-test for decision_tape_loader and check_truth_separation.

Plain asserts, no pytest, no new pip dependencies (numpy only). It reads a REAL
shard written by the C++ qr_emit_make_shard tool, which is what makes it the
round trip: C++ writes the bytes, numpy mmaps them, and the values are compared
against the formulas recomputed here, independently of the writer.

usage: test_decision_tape_loader.py --shard DIR [--scratch DIR]
exit:  0 all checks pass; 1 a check failed (every check prints PASS/FAIL)
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sys
import traceback

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_truth_separation  # noqa: E402
from decision_tape_loader import (  # noqa: E402
    DecisionTape,
    DecisionTapeError,
    assert_no_truth_arrays,
    read_npy_header,
)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str):
    def decorate(function):
        def run(*args, **kwargs):
            try:
                function(*args, **kwargs)
            except Exception:  # noqa: BLE001 — a self-test reports, never raises
                RESULTS.append((name, False, traceback.format_exc()))
            else:
                RESULTS.append((name, True, ""))

        return run

    return decorate


def expect_refusal(name: str, thunk) -> None:
    try:
        thunk()
    except DecisionTapeError:
        return
    except Exception as error:  # noqa: BLE001
        raise AssertionError(
            f"{name}: refused with {type(error).__name__}, expected DecisionTapeError"
        ) from error
    raise AssertionError(f"{name}: was ACCEPTED; it must be refused")


# --- the formulas, recomputed independently of qr_emit_make_shard.cpp ------


def expected_direct_raw(rows: int) -> np.ndarray:
    out = np.zeros((rows, 3, 60), dtype=np.float32)
    for row in range(rows):
        for channel in range(3):
            for column in range(60):
                out[row, channel, column] = np.float32(
                    ((row * 180 + channel * 60 + column) % 4096) / 8.0
                )
    return out


def expected_group_ts(groups: int) -> np.ndarray:
    return np.array(
        [1600000000000000000 + index * 1000000 for index in range(groups)], dtype=np.int64
    )


def expected_recent128(rows: int) -> np.ndarray:
    return np.array(
        [[row * 2 + column - 7 for column in range(2)] for row in range(rows)], dtype=np.int32
    )


def expected_grid_1s(seconds: int) -> np.ndarray:
    return np.array(
        [[np.float32((second * 4 + column) / 4.0) for column in range(4)]
         for second in range(seconds)],
        dtype=np.float32,
    )


def expected_keys(rows: int) -> np.ndarray:
    return np.array(
        [[row * 4 + column + 1000 for column in range(4)] for row in range(rows)], dtype=np.int64
    )


def expected_menu_net_cent(rows: int) -> np.ndarray:
    return np.array(
        [[(row * 7 + horizon) * 13 - 30000 for horizon in range(7)] for row in range(rows)],
        dtype=np.int64,
    )


def expected_stop_hit(rows: int) -> np.ndarray:
    return np.array(
        [[(row + horizon) % 2 for horizon in range(7)] for row in range(rows)], dtype=np.uint8
    )


def expected_barrier(rows: int) -> np.ndarray:
    return np.array([row % 3 for row in range(rows)], dtype=np.uint8)


# --- checks ----------------------------------------------------------------


@check("manifest is read and every C4 field is present")
def check_manifest(shard: pathlib.Path) -> None:
    tape = DecisionTape(shard)
    assert tape.build_id, "build id is empty"
    assert tape.side in ("LONG", "SHORT"), tape.side
    assert tape.session_ordinal == 125, tape.session_ordinal
    assert tape.leaf_names("features") == [
        "direct_raw",
        "grid_1s",
        "group_ts",
        "keys",
        "recent128",
    ], tape.leaf_names("features")
    assert tape.leaf_names("truth") == [
        "barrier",
        "keys",
        "menu_net_cent",
        "stop_hit",
    ], tape.leaf_names("truth")
    assert tape.sources and len(tape.sources[0]) == 3, tape.sources
    assert tape.census and len(tape.census[0]) == 3, tape.census
    direct = tape.leaf("features", "direct_raw")
    assert direct.dtype == "<f4" and len(direct.shape) == 3, direct
    assert direct.rows == direct.shape[0]


@check("C++-written leaves load through numpy and equal the expected literals")
def check_round_trip(shard: pathlib.Path) -> None:
    tape = DecisionTape(shard)
    features = tape.features()
    rows = tape.leaf("features", "direct_raw").rows
    groups = tape.leaf("features", "group_ts").rows
    seconds = tape.leaf("features", "grid_1s").rows
    assert np.array_equal(features["direct_raw"], expected_direct_raw(rows))
    assert features["direct_raw"].dtype == np.dtype("<f4")
    assert np.array_equal(features["group_ts"], expected_group_ts(groups))
    assert np.array_equal(features["recent128"], expected_recent128(rows))
    assert np.array_equal(features["grid_1s"], expected_grid_1s(seconds))
    assert np.array_equal(features["keys"], expected_keys(rows))

    truth = tape.truth(["menu_net_cent", "stop_hit", "barrier", "keys"])
    assert np.array_equal(truth["menu_net_cent"], expected_menu_net_cent(rows))
    assert np.array_equal(truth["stop_hit"], expected_stop_hit(rows))
    assert np.array_equal(truth["barrier"], expected_barrier(rows))
    assert np.array_equal(truth["keys"], expected_keys(rows))
    # mmap, not a copy: the loader must not read 27GB into RAM.
    assert isinstance(features["direct_raw"], np.memmap)
    assert features["direct_raw"].mode == "r", "features are mapped read-only"


@check("features() never maps a truth leaf")
def check_features_never_touch_truth(shard: pathlib.Path) -> None:
    tape = DecisionTape(shard)
    tape.features()
    tape.assert_features_never_touched_truth()
    assert all("truth" not in pathlib.PurePath(path).parts for path in tape.opened_paths)
    expect_refusal("features(['menu_net_cent'])", lambda: tape.features(["menu_net_cent"]))
    expect_refusal("features(['barrier'])", lambda: tape.features(["barrier"]))


@check("truth() demands an explicit allowlist and honours it exactly")
def check_truth_allowlist(shard: pathlib.Path) -> None:
    tape = DecisionTape(shard)
    allowed = tape.truth(["menu_net_cent"])
    assert list(allowed) == ["menu_net_cent"]
    expect_refusal("empty allowlist", lambda: tape.truth([]))
    expect_refusal("repeated allowlist", lambda: tape.truth(["barrier", "barrier"]))
    expect_refusal("unknown leaf", lambda: tape.truth(["not_a_leaf"]))
    expect_refusal(
        "request outside the allowlist",
        lambda: tape.truth(["menu_net_cent"], names=["stop_hit"]),
    )
    expect_refusal("feature leaf via truth()", lambda: tape.truth(["direct_raw"]))


@check("verify() recomputes every sha256 and accepts the published shard")
def check_verify_accepts(shard: pathlib.Path) -> None:
    tape = DecisionTape(shard, verify_sha=True)
    tape.verify()
    manifest = (shard / "manifest.tsv").read_text(encoding="utf-8")
    assert tape.manifest_sha256 == hashlib.sha256(manifest.encode("utf-8")).hexdigest()


@check("a single flipped payload byte is refused by sha verification")
def check_sha_mismatch(shard: pathlib.Path, scratch: pathlib.Path) -> None:
    copy = scratch / "sha_mismatch"
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(shard, copy)
    target = copy / "features" / "direct_raw.npy"
    payload = bytearray(target.read_bytes())
    payload[200] ^= 0x01  # one bit, inside the payload, shape and size untouched
    target.write_bytes(bytes(payload))
    # The structural checks still pass — only the digest can see this.
    tape = DecisionTape(copy)
    expect_refusal("flipped payload byte", tape.verify)
    expect_refusal("flipped payload byte at open", lambda: DecisionTape(copy, verify_sha=True))


@check("every off-by-one header padding is refused by the loader (numpy is not a gate)")
def check_header_padding_off_by_one(shard: pathlib.Path, scratch: pathlib.Path) -> None:
    """MEASURED, numpy 2.1.2: numpy's READER does not enforce the 64-byte rule
    its own writer follows, so an off-by-one padding is not caught by np.load.
    Two of the three off-by-one shapes below are ACCEPTED by numpy, and one of
    those returns silently shifted garbage. That is the whole reason this loader
    parses the prologue itself instead of trusting np.load."""
    copy = scratch / "bad_padding"
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(shard, copy)
    target = copy / "features" / "group_ts.npy"
    original = bytes((copy / "features" / "group_ts.npy").read_bytes())
    header_len = int.from_bytes(original[8:10], "little")
    assert (10 + header_len) % 64 == 0, "the published shard is already misaligned"
    truth = expected_group_ts(DecisionTape(shard).leaf("features", "group_ts").rows)

    # (a) one pad space removed and HEADER_LEN shrunk to match: the payload is
    #     intact but starts at offset 127. numpy accepts it; the ruling does not.
    dropped_pad = (
        original[:8]
        + (header_len - 1).to_bytes(2, "little")
        + original[10 : 10 + header_len - 2]
        + b"\n"
        + original[10 + header_len :]
    )
    # (b) HEADER_LEN shrunk with every byte left in place: numpy accepts this
    #     and returns the payload SHIFTED BY ONE BYTE — silently wrong numbers.
    short_declaration = original[:8] + (header_len - 1).to_bytes(2, "little") + original[10:]
    # (c) HEADER_LEN grown: numpy refuses this one.
    long_declaration = original[:8] + (header_len + 1).to_bytes(2, "little") + original[10:]

    target.write_bytes(short_declaration)
    shifted = np.load(target, mmap_mode="r", allow_pickle=False)
    assert not np.array_equal(shifted, truth), (
        "the shifted-header case is supposed to demonstrate silent corruption"
    )

    for name, mutation in (
        ("dropped pad byte", dropped_pad),
        ("short HEADER_LEN", short_declaration),
        ("long HEADER_LEN", long_declaration),
    ):
        target.write_bytes(mutation)
        expect_refusal(f"{name}: read_npy_header", lambda: read_npy_header(target))
        expect_refusal(f"{name}: DecisionTape", lambda: DecisionTape(copy))


@check("a manifest that disagrees with the file on disk is refused")
def check_manifest_mismatch(shard: pathlib.Path, scratch: pathlib.Path) -> None:
    def mutate(name: str, transform) -> pathlib.Path:
        copy = scratch / name
        shutil.rmtree(copy, ignore_errors=True)
        shutil.copytree(shard, copy)
        manifest = (copy / "manifest.tsv").read_text(encoding="utf-8")
        (copy / "manifest.tsv").write_text(transform(manifest), encoding="utf-8")
        return copy

    wrong_shape = mutate(
        "wrong_shape",
        lambda text: text.replace("\t<i4\t", "\t<i4\t").replace(
            "leaf\tfeatures/recent128.npy\t<i4\t", "leaf\tfeatures/recent128.npy\t<i4\tX"
        ),
    )
    expect_refusal("non-integer shape", lambda: DecisionTape(wrong_shape))

    wrong_dtype = mutate(
        "wrong_dtype",
        lambda text: text.replace("leaf\tfeatures/recent128.npy\t<i4", "leaf\tfeatures/recent128.npy\t<i8"),
    )
    expect_refusal("dtype disagreement", lambda: DecisionTape(wrong_dtype))

    dropped_row = mutate(
        "dropped_row",
        lambda text: "\n".join(
            line for line in text.split("\n") if not line.startswith("leaf\ttruth/barrier.npy")
        ),
    )
    expect_refusal("leaf on disk that the manifest omits", lambda: DecisionTape(dropped_row))

    bad_count = mutate(
        "bad_count", lambda text: text.replace("meta\tleaf_count\t9", "meta\tleaf_count\t8")
    )
    expect_refusal("leaf_count disagreement", lambda: DecisionTape(bad_count))

    bad_schema = mutate(
        "bad_schema", lambda text: text.replace("qr_emit_manifest_v1", "qr_emit_manifest_v2", 1)
    )
    expect_refusal("unknown manifest schema", lambda: DecisionTape(bad_schema))

    missing = scratch / "missing_leaf"
    shutil.rmtree(missing, ignore_errors=True)
    shutil.copytree(shard, missing)
    (missing / "truth" / "barrier.npy").unlink()
    expect_refusal("manifest names a leaf that is gone", lambda: DecisionTape(missing))

    truncated = scratch / "truncated_leaf"
    shutil.rmtree(truncated, ignore_errors=True)
    shutil.copytree(shard, truncated)
    target = truncated / "features" / "direct_raw.npy"
    payload = target.read_bytes()
    target.write_bytes(payload[:-4])
    expect_refusal("payload shorter than the declared shape", lambda: DecisionTape(truncated))

    extra = scratch / "extra_leaf"
    shutil.rmtree(extra, ignore_errors=True)
    shutil.copytree(shard, extra)
    shutil.copy(extra / "features" / "group_ts.npy", extra / "features" / "smuggled.npy")
    expect_refusal("unmanifested .npy on disk", lambda: DecisionTape(extra))


@check("a truth array that reached a feature bundle is caught at runtime")
def check_runtime_truth_guard(shard: pathlib.Path) -> None:
    tape = DecisionTape(shard)
    features = tape.features()
    assert_no_truth_arrays(features)  # clean
    truth = tape.truth(["menu_net_cent"])
    smuggled = dict(features)
    # These two lines are REAL violations of the static rule and are declared as
    # such: the runtime guard can only be tested by building the object it must
    # refuse. The marker is line-scoped and counted in the checker's summary.
    smuggled["menu_net_cent"] = truth["menu_net_cent"]  # truth-separation: guard-fixture
    expect_refusal("truth memmap in a feature bundle", lambda: assert_no_truth_arrays(smuggled))
    # A VIEW of a truth leaf is still a truth array.
    viewed = dict(features)
    viewed["sliced"] = truth["menu_net_cent"][:2]  # truth-separation: guard-fixture
    expect_refusal("truth view in a feature bundle", lambda: assert_no_truth_arrays(viewed))


@check("the static check accepts clean trainer code and catches a concatenation")
def check_static_separation(scratch: pathlib.Path) -> None:
    clean = scratch / "clean_trainer.py"
    clean.write_text(
        "import numpy as np\n"
        "def build(tape):\n"
        "    features = tape.features()\n"
        "    y = tape.truth(['menu_net_cent'])['menu_net_cent']\n"
        "    x = np.concatenate([features['direct_raw'], features['grid_1s']], axis=0)\n"
        "    return x, y\n",
        encoding="utf-8",
    )
    assert check_truth_separation.check_source(clean, clean.read_text(encoding="utf-8")) == []

    dirty = scratch / "dirty_trainer.py"
    dirty.write_text(
        "import numpy as np\n"
        "def build(tape):\n"
        "    features = tape.features()\n"
        "    truth = tape.truth(['menu_net_cent'])\n"
        "    y = truth['menu_net_cent']\n"
        "    return np.concatenate([features['direct_raw'], y], axis=1)\n",
        encoding="utf-8",
    )
    violations = check_truth_separation.check_source(dirty, dirty.read_text(encoding="utf-8"))
    assert len(violations) == 1, violations
    assert "concatenated" in violations[0]

    indirect = scratch / "indirect_trainer.py"
    indirect.write_text(
        "import torch\n"
        "def build(tape):\n"
        "    labels = tape.truth(['stop_hit'])\n"
        "    for name, array in labels.items():\n"
        "        stacked = torch.cat([array, array])\n"
        "    return stacked\n",
        encoding="utf-8",
    )
    assert check_truth_separation.check_source(indirect, indirect.read_text(encoding="utf-8"))


@check("the static check catches setitem, put, insert and out= as well as concatenation")
def check_static_sinks(scratch: pathlib.Path) -> None:
    # Review F4/F5: concatenation was never the only way a truth array reaches a
    # feature tensor. Each of these four writes truth into a tensor without
    # calling a concatenator once.
    cases = {
        "setitem": (
            "def build(tape):\n"
            "    features = tape.features()\n"
            "    y = tape.truth(['menu_net_cent'])['menu_net_cent']\n"
            "    features['direct_raw'][:, 0] = y\n",
            "setitem",
        ),
        "augmented_setitem": (
            "def build(tape):\n"
            "    features = tape.features()\n"
            "    y = tape.truth(['menu_net_cent'])['menu_net_cent']\n"
            "    features['direct_raw'][:, 0] += y\n",
            "setitem",
        ),
        "put": (
            "import numpy as np\n"
            "def build(tape):\n"
            "    features = tape.features()\n"
            "    y = tape.truth(['menu_net_cent'])['menu_net_cent']\n"
            "    np.put(features['direct_raw'], 0, y)\n",
            "put()",
        ),
        "insert": (
            "import numpy as np\n"
            "def build(tape):\n"
            "    features = tape.features()\n"
            "    y = tape.truth(['menu_net_cent'])['menu_net_cent']\n"
            "    return np.insert(features['direct_raw'], 0, y, axis=1)\n",
            "insert()",
        ),
        "out": (
            "import numpy as np\n"
            "def build(tape):\n"
            "    features = tape.features()\n"
            "    y = tape.truth(['menu_net_cent'])['menu_net_cent']\n"
            "    np.add(y, 0, out=features['direct_raw'])\n",
            "out=",
        ),
    }
    for name, (source, needle) in cases.items():
        path = scratch / f"sink_{name}.py"
        path.write_text(source, encoding="utf-8")
        violations = check_truth_separation.check_source(path, path.read_text(encoding="utf-8"))
        assert violations, f"{name}: the widened sink set missed it"
        assert any(needle in v for v in violations), (name, violations)

    # The control: the same shapes with NO truth in them are clean.
    clean = scratch / "sink_clean.py"
    clean.write_text(
        "import numpy as np\n"
        "def build(tape):\n"
        "    features = tape.features()\n"
        "    features['direct_raw'][:, 0] = features['grid_1s'][:, 0]\n"
        "    np.add(features['grid_1s'], 0, out=features['direct_raw'])\n",
        encoding="utf-8",
    )
    assert check_truth_separation.check_source(clean, clean.read_text(encoding="utf-8")) == []


# The name deliberately avoids spelling the marker: `check_red_ledger_python.sh`
# reads these names with an anchored regex, so a trailing suppression comment on
# this line would make the check invisible to the red-ledger gate.
@check("the census scope marker outside qr_emit's internals is a violation")
def check_census_scope_rule(scratch: pathlib.Path) -> None:
    # The marker silences fd-census recording for whatever is opened inside it,
    # so anywhere but qr_emit's own internals it is a hole in the wall.
    outside = scratch / "qr_labels" / "src" / "leaky.cpp"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text(
        "void f() {\n"
        "  const qr::emit::CensusInternalScope scope;\n"  # truth-separation: guard-fixture
        "  std::ifstream truth(\"s0125/L/truth/menu_net_cent.npy\");\n"
        "}\n",
        encoding="utf-8",
    )
    violations = check_truth_separation.check_census_scope(
        outside, outside.read_text(encoding="utf-8"))
    assert len(violations) == 1, violations
    assert "CensusInternalScope" in violations[0]  # truth-separation: guard-fixture
    assert ":2:" in violations[0], violations

    # qr_emit's own internals are the two directories that may name it.
    for owner in ("qr_emit/src/fd_census.cpp", "qr_emit/include/qr_emit/fd_census.hpp"):
        path = scratch / owner
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("CensusInternalScope scope;\n", encoding="utf-8")  # truth-separation: guard-fixture
        assert check_truth_separation.check_census_scope(
            path, path.read_text(encoding="utf-8")) == []


@check("a declared guard-fixture line is suppressed, counted, and suppresses nothing else")
def check_suppression_is_narrow(scratch: pathlib.Path) -> None:
    path = scratch / "suppressed.py"
    path.write_text(
        "import numpy as np\n"
        "def build(tape):\n"
        "    features = tape.features()\n"
        "    y = tape.truth(['menu_net_cent'])['menu_net_cent']\n"
        "    features['a'][0] = y  # truth-separation: guard-fixture\n"
        "    features['b'][0] = y\n",
        encoding="utf-8",
    )
    text = path.read_text(encoding="utf-8")
    found = check_truth_separation.check_source(path, text)
    assert len(found) == 2, found
    kept, dropped = check_truth_separation.apply_suppressions(text, found)
    assert dropped == 1, (kept, dropped)
    assert len(kept) == 1, kept
    assert ":6:" in kept[0], kept


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard", type=pathlib.Path, required=True)
    parser.add_argument("--scratch", type=pathlib.Path, default=None)
    args = parser.parse_args()
    scratch = args.scratch or (args.shard.parent / "loader_selftest_scratch")
    scratch.mkdir(parents=True, exist_ok=True)

    check_manifest(args.shard)
    check_round_trip(args.shard)
    check_features_never_touch_truth(args.shard)
    check_truth_allowlist(args.shard)
    check_verify_accepts(args.shard)
    check_sha_mismatch(args.shard, scratch)
    check_header_padding_off_by_one(args.shard, scratch)
    check_manifest_mismatch(args.shard, scratch)
    check_runtime_truth_guard(args.shard)
    check_static_separation(scratch)
    check_static_sinks(scratch)
    check_census_scope_rule(scratch)
    check_suppression_is_narrow(scratch)

    failures = 0
    for name, passed, detail in RESULTS:
        if passed:
            print(f"PASS: {name}")
        else:
            failures += 1
            print(f"FAIL: {name}\n{detail}")
    print(f"{len(RESULTS) - failures}/{len(RESULTS)} loader self-test checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
