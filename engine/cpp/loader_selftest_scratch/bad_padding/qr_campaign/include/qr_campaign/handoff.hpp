// qr_campaign/handoff.hpp — the FEATURE_BUILDER → emit handoff.
//
// SPEC: FINAL_PLAN.md APPENDIX C4, "Separation BY PROCESS (review F4)", as
// qr_emit's ShardWriter states the topology verbatim: "feature constructors run
// FEATURE_BUILDER-tagged, where the qr_emit fd census refuses any open of a
// truth/ path at the door and the run's census receipt proves it never touched
// one; those constructors hand their arrays to the emit step, which runs UNSET
// and writes features/ and truth/ into one staged shard". The topology fixture
// (FdCensusTest.TheBuilderPhaseIsTaggedAndTheEmitStepWritesBothSections) hands
// the arrays over through a FILE; a 625-session campaign moves ~750MB of group
// table per session, so this driver hands them over through an ANONYMOUS
// MEMORY FILE instead — same topology, same census, no filesystem round trip.
//
// WHY A memfd AND NOT A PIPE OR SHARED HEAP. The builder must be a SEPARATE
// PROCESS for its fd census to mean anything, so a heap is out; a pipe would
// serialise 750MB through a 64KB kernel buffer and force the two phases to
// interleave, which would deny the label pass its overlap with the feature
// pass. `memfd_create` gives one anonymous tmpfs inode created BEFORE the fork:
// the builder writes it, the emit step maps it read-only, and it dies with the
// last descriptor. It carries no path, so it can never be an unaudited channel
// to a truth leaf: the census's /proc/self/fd sweep sees it as a descriptor the
// builder inherited (snapshotted as pre-existing by `FdCensus::begin`), and no
// path with a `truth` component ever exists for it.
//
// THE BLOB IS SELF-DESCRIBING AND DETERMINISTIC. A fixed 64KiB header carries a
// magic, the leaf count and one 96-byte descriptor per leaf (name, scope,
// dtype, shape, offset, byte count); payloads follow, each 64-byte aligned so
// the emit step can read an i8/i4/f4 leaf straight out of the mapping. The
// builder appends leaves in a frozen order and writes the header LAST, so a
// builder that dies mid-way hands back a blob with a zero leaf count rather
// than a plausible-looking half.
#ifndef QR_CAMPAIGN_HANDOFF_HPP
#define QR_CAMPAIGN_HANDOFF_HPP

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_emit/npy_writer.hpp"

namespace qr::campaign {

using qr::emit::NpyDtype;
using qr::emit::ok_status;
using qr::emit::Status;

/// Which shard(s) of the session a leaf belongs to.
enum class LeafScope : std::uint8_t {
  /// Written ONCE, into the LONG shard: the side-neutral group tables, their
  /// timestamps and the orientation tables (qr_carriers/native_emit.hpp's
  /// side-neutral storage ruling).
  SESSION_LONG_SHARD = 0,
  /// Side-independent but small enough to be restated in both shards.
  BOTH_SHARDS = 1,
  LONG_SHARD = 2,
  SHORT_SHARD = 3,
  /// NOT a shard leaf: a byte block the constructor phase hands to the emit
  /// step and the emit step publishes elsewhere (the builder's own census
  /// text). It travels here rather than through a file so that the ONLY paths
  /// the tagged phase ever opens are the three payload parquets — which is what
  /// makes its fd census identical in two runs published under two roots.
  HANDOFF_ONLY = 4,
};

struct HandoffLeaf {
  std::string name;  ///< leaf name without the `.npy` suffix
  LeafScope scope = LeafScope::LONG_SHARD;
  NpyDtype dtype = NpyDtype::F4;
  std::vector<std::int64_t> shape;
  std::uint64_t offset = 0;
  std::uint64_t bytes = 0;
};

inline constexpr std::string_view kHandoffMagic = "QRCAMPAIGN_HANDOFF_V1\n";
/// The reserved header region: magic + counts + up to 680 descriptors.
inline constexpr std::uint64_t kHandoffHeaderBytes = 64U * 1024U;
inline constexpr std::size_t kHandoffNameBytes = 48;
inline constexpr std::size_t kHandoffDescriptorBytes = 96;
inline constexpr std::size_t kHandoffMaxLeaves =
    (kHandoffHeaderBytes - 64U) / kHandoffDescriptorBytes;

/// Creates the anonymous memory file the two phases share. The caller forks
/// AFTER this returns, so the descriptor is inherited.
[[nodiscard]] Expected<int, Refusal> create_handoff_fd();

/// The builder's side of the handoff.
class HandoffWriter {
 public:
  explicit HandoffWriter(int fd) noexcept : fd_(fd) {}

  [[nodiscard]] Status append(std::string_view name, LeafScope scope, NpyDtype dtype,
                              std::span<const std::int64_t> shape, const void* data,
                              std::uint64_t bytes);

  template <class T>
  [[nodiscard]] Status append_values(std::string_view name, LeafScope scope, NpyDtype dtype,
                                     std::span<const std::int64_t> shape,
                                     std::span<const T> values) {
    return append(name, scope, dtype, shape, values.data(),
                  static_cast<std::uint64_t>(values.size()) * sizeof(T));
  }

  /// Writes the header. Nothing before this call is readable as a blob.
  [[nodiscard]] Status finish();

  [[nodiscard]] std::size_t leaves() const noexcept { return leaves_.size(); }

 private:
  int fd_ = -1;
  std::uint64_t cursor_ = kHandoffHeaderBytes;
  std::vector<HandoffLeaf> leaves_;
};

/// The emit step's side of the handoff: a read-only mapping plus the parsed
/// descriptor table.
class HandoffReader {
 public:
  HandoffReader(const HandoffReader&) = delete;
  HandoffReader& operator=(const HandoffReader&) = delete;
  HandoffReader(HandoffReader&& other) noexcept;
  HandoffReader& operator=(HandoffReader&& other) noexcept;
  ~HandoffReader();

  [[nodiscard]] static Expected<HandoffReader, Refusal> map(int fd);

  [[nodiscard]] const std::vector<HandoffLeaf>& leaves() const noexcept { return leaves_; }
  /// The raw payload of one leaf. The pointer is 64-byte aligned.
  [[nodiscard]] const void* payload(const HandoffLeaf& leaf) const noexcept;
  /// Element count implied by the leaf's own shape and dtype; refuses when the
  /// byte count does not match it exactly.
  [[nodiscard]] Expected<std::uint64_t, Refusal> elements(const HandoffLeaf& leaf) const;

 private:
  HandoffReader() = default;

  const std::uint8_t* base_ = nullptr;
  std::size_t size_ = 0;
  std::vector<HandoffLeaf> leaves_;
};

}  // namespace qr::campaign

#endif  // QR_CAMPAIGN_HANDOFF_HPP
