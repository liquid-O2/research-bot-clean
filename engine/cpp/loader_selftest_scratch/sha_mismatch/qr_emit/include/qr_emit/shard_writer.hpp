// qr_emit/shard_writer.hpp — the DecisionTape shard container.
//
// SPEC: FINAL_PLAN.md APPENDIX C4, verbatim:
//   "C4 DecisionTape (per session/side): `features/`: direct_raw [N,3,60] f4;
//    groups_{mod} [G,69|65|89] f4; group_ts [G] i8; recent128 [N,2] i4;
//    phase_split [N] i4; bins_index [N,120,2] i4; grid_1s [S,4] f4; locclock
//    [N,32] f4; candset [N,64,24] f4 + len; keys [N,4] i8; masks. `truth/`:
//    menu_net_cent [N,7] i8; menu_mae_cent [N,7] i8; menu_exit_ts [N,7] i8;
//    stop_hit [N,7] u1; cert_net/mae [N] i8; barrier [N] u1; label_state [N]
//    u1; keys. manifest.tsv (path,dtype,shape,rows,sha256 + sources + census +
//    build id)."
//
// THIS WORK PACKAGE IS THE CONTAINER, NOT THE CONTENT. The leaf NAMES and
// SHAPES above are the tensors WP8 will produce; qr_emit neither invents them
// nor hard-codes them. What it owns is the directory layout, the .npy encoding,
// the manifest, and the publish discipline.
//
// TOPOLOGY (orchestrator ruling, 2026-08-10). ONE untagged emit process per
// (session, side) writes BOTH sections in a SINGLE publish: one manifest, one
// no-replace rename. The APPENDIX C4 process-separation law binds the
// FEATURE-CONSTRUCTION phase, not the emit step:
//
//   * feature constructors run FEATURE_BUILDER-tagged, where the qr_emit fd
//     census refuses any open of a truth/ path at the door and the run's census
//     receipt proves it never touched one (qr_emit/fd_census.hpp);
//   * those constructors hand their arrays to the emit step, which runs UNSET
//     and writes features/ and truth/ into one staged shard;
//   * a feature-construction process that tries to WRITE a truth leaf is
//     refused by the same door, so the separation cannot be laundered by
//     calling the emit API from a builder.
//
// Fixtures: FdCensusTest.TheBuilderPhaseIsTaggedAndTheEmitStepWritesBothSections
// (the whole topology, builder phase in its own process), and
// FdCensusTest.AFeatureBuilderIsRefusedAtTheDoorAndItsCensusFails +
// FdCensusTest.RefusingAnOpenNeverCreatesTheFile (the wall).
//
// SHARD NAMING (orchestrator ruling, 2026-08-10) is exactly the APPENDIX C4
// shape and nothing else:
//
//     <base>/s<ordinal zero-padded to 4 digits>/<L|S>/
//     e.g. /.../tapes/s0125/L/{features,truth,manifest.tsv}
//
// c4_shard_dir() composes it and validate_c4_shard_dir() is the wall: the
// destination is checked when the writer opens (so a malformed name costs
// nothing) and again immediately before the rename (so the publish itself is
// gated, not merely the setup).
//
// PUBLISH DISCIPLINE (the no-replace pattern, as used by the repo's existing
// publications): every byte is written into a sibling stage directory
// `.<name>.stage-<pid>`, each leaf is fsynced as it finishes, the manifest is
// written last, the directories are fsynced, and the stage directory is moved
// into place with renameat2(RENAME_NOREPLACE). Consequences that the fixtures
// pin: a process killed at any point before that rename leaves a stage
// directory and NO published shard, and a publish onto an existing path is a
// typed refusal rather than a replacement.
//
// DETERMINISM. Published bytes are a function of the leaf SET, not of the order
// the caller emitted them: manifest sections are in fixed order and rows are
// sorted (leaves by path, sources and censuses by id then path). Two runs, and
// two differently-ordered runs, are byte-identical — both are fixtures.
#ifndef QR_EMIT_SHARD_WRITER_HPP
#define QR_EMIT_SHARD_WRITER_HPP

#include <array>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <span>
#include <string>
#include <vector>

#include "qr_emit/npy_writer.hpp"

namespace qr::emit {

/// σ = +1 LONG / −1 SHORT (APPENDIX A notation).
enum class Side : std::uint8_t { LONG, SHORT };

/// "LONG" / "SHORT" — the manifest's `side` value.
[[nodiscard]] const char* side_name(Side side) noexcept;

/// 'L' / 'S' — the shard directory's side component.
[[nodiscard]] char side_letter(Side side) noexcept;

/// The frozen shard path: `<base>/s0125/L`. Refuses an ordinal that does not
/// fit the four-digit field rather than truncating or widening it.
[[nodiscard]] Expected<std::filesystem::path, Refusal> c4_shard_dir(
    const std::filesystem::path& base, std::int64_t session_ordinal, Side side);

/// The wall: `dir` must end in exactly `s<0000..9999>/<L|S>` and those two
/// components must be the ordinal and side the shard actually carries.
[[nodiscard]] Status validate_c4_shard_dir(const std::filesystem::path& dir,
                                           std::int64_t session_ordinal, Side side);

/// The two C4 sections. They are the two subdirectory names, and the process
/// separation is stated in terms of them.
enum class Section : std::uint8_t { FEATURES, TRUTH };

[[nodiscard]] const char* section_dir(Section section) noexcept;

/// THE ONE LEAF APPENDIX C4 PUTS IN BOTH SECTIONS, and therefore the one pair
/// the publish-time digest-collision refusal must not fire on.
///
/// C4, verbatim: "`features/`: ... candset [N,64,24] f4 + len; keys [N,4] i8;
/// masks. `truth/`: menu_net_cent [N,7] i8; ... label_state [N] u1; keys." The
/// prediction key is the JOIN between the two halves and is the same array on
/// both sides by construction, so `features/keys.npy` and `truth/keys.npy` have
/// the same sha256 in every lawful shard.
///
/// DECLARED TENSION, for the record: card section 7(p) says publishing "refuses
/// when any features/ leaf sha256 equals any truth/ leaf sha256" with no
/// exception, and C4 mandates a pair that always collides. The two frozen
/// statements are not jointly satisfiable for any real shard; this is the
/// narrowest reading under which both stand — the refusal fires on every
/// collision except a SAME-NAMED pair whose name is on this one-element list.
inline constexpr std::array<std::string_view, 1> kC4SharedLeafNames = {"keys.npy"};

/// True when `leaf_name` (with its `.npy` suffix) is a leaf C4 declares in both
/// sections.
[[nodiscard]] constexpr bool is_c4_shared_leaf(std::string_view leaf_name) noexcept {
  for (const std::string_view shared : kC4SharedLeafNames) {
    if (leaf_name == shared) {
      return true;
    }
  }
  return false;
}

inline constexpr std::string_view kManifestName = "manifest.tsv";
inline constexpr std::string_view kManifestSchema = "qr_emit_manifest_v1";

/// A pinned input the tape was built from (manifest `sources`).
struct SourceRow {
  std::string id;
  std::string sha256;
  std::string path;
};

/// A census artifact this tape points at (manifest `census pointers`).
struct CensusRow {
  std::string id;
  std::string sha256;
  std::string path;
};

/// Everything the manifest header carries plus where the shard is published.
struct ShardSpec {
  /// Must not exist, is created by the rename, and must be exactly the C4 shape
  /// `<base>/s<0125>/<L|S>` for this spec's ordinal and side — compose it with
  /// c4_shard_dir() rather than by hand.
  std::filesystem::path publish_dir;
  std::int64_t session_ordinal = 0;   ///< registry ordinal (125..749 in scope)
  Side side = Side::LONG;
  std::string build_id;               ///< manifest `build id`
  std::vector<SourceRow> sources;
  std::vector<CensusRow> census;
};

struct ShardReceipt {
  std::filesystem::path publish_dir;
  std::int64_t leaf_count = 0;
  std::int64_t total_leaf_bytes = 0;
  std::string manifest_sha256;
  std::vector<NpyLeafReceipt> leaves;  ///< sorted by rel_path, as published
};

class ShardWriter {
 public:
  ShardWriter(const ShardWriter&) = delete;
  ShardWriter& operator=(const ShardWriter&) = delete;
  ~ShardWriter();

  /// Creates the stage directory and both section directories. Refuses when the
  /// publish path already exists, when a manifest field carries a tab/newline,
  /// or when the process role forbids the sections it would have to create.
  [[nodiscard]] static Expected<std::unique_ptr<ShardWriter>, Refusal> begin(ShardSpec spec);

  /// Opens one leaf for streaming. Only one leaf is open at a time; the
  /// previous one must have been finished. Refuses a duplicate leaf name.
  [[nodiscard]] Expected<NpyWriter*, Refusal> open_leaf(Section section, std::string_view name,
                                                        NpyDtype dtype,
                                                        std::span<const std::int64_t> shape);

  /// Finishes the open leaf, fsyncs it, and records its manifest row.
  [[nodiscard]] Status finish_leaf();

  /// open_leaf + append + finish_leaf for a leaf that is already in memory.
  template <class T>
  [[nodiscard]] Status write_leaf(Section section, std::string_view name, NpyDtype dtype,
                                  std::span<const std::int64_t> shape, std::span<const T> values) {
    auto opened = open_leaf(section, name, dtype, shape);
    if (!opened) {
      return Status::refuse(opened.error());
    }
    Status appended = opened.value()->append(values);
    if (!appended) {
      return appended;
    }
    return finish_leaf();
  }

  /// Writes manifest.tsv, fsyncs everything, and moves the stage directory into
  /// place with RENAME_NOREPLACE. After this the writer owns nothing.
  [[nodiscard]] Expected<ShardReceipt, Refusal> publish();

  [[nodiscard]] const std::filesystem::path& stage_dir() const noexcept { return stage_dir_; }
  [[nodiscard]] bool published() const noexcept { return published_; }
  [[nodiscard]] std::int64_t leaf_count() const noexcept;

  /// The exact manifest bytes for the leaves recorded so far. Deterministic and
  /// independent of emission order; exposed so a test can compare two orders
  /// without publishing twice.
  [[nodiscard]] Expected<std::string, Refusal> manifest_bytes() const;

 private:
  explicit ShardWriter(ShardSpec spec, std::filesystem::path stage_dir);

  ShardSpec spec_;
  std::filesystem::path stage_dir_;
  std::unique_ptr<NpyWriter> open_writer_;
  std::vector<NpyLeafReceipt> leaves_;
  bool published_ = false;
};

}  // namespace qr::emit

#endif  // QR_EMIT_SHARD_WRITER_HPP
