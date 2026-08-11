// qr_candidates/prefix_reader.hpp — the bounded, physically non-prefetching
// event-signal prefix reader.
//
// SPEC (evidence/claims/native_state/TASK_CARD_V4_DRAFT.md section 2, verbatim):
//
//   "The prefix reader is physically non-prefetching. It reads the header one
//    byte at a time. With `R` admitted data-row newlines remaining, it calls
//    positional `pread` for exactly `min(1MiB,R-1)` bytes while R>1; this
//    cannot cross the boundary because reaching row750 requires consuming R
//    newline bytes. At R=1 it reads one byte at a time through the final
//    newline and closes before any row750 byte. No BufReader, mmap, readline,
//    or library prefetch is permitted. Decoded ordinal must be monotone
//    0..749. Every session must match the exact `signal_count` and
//    `signal_sequence_root` in `t14_bounds`; two independent extractions must
//    have identical schema, rows, leaves, per-session roots, and content root."
//
// WHY THE ARITHMETIC IS THE WALL. The file continues past ordinal 749 with
// sessions this project may never read. The reader does not *decide* to stop —
// it is arithmetically incapable of reaching row 750, because a block request
// of `min(1MiB, R-1)` bytes can contain at most R-1 newlines, and row 750
// begins only after the R-th. The last newline is therefore always consumed by
// a one-byte read, and the descriptor is closed before the next byte exists.
// That is why `min(1MiB, R)` would be a defect and `min(1MiB, R-1)` is not.
//
// EVERY BYTE COMES THROUGH `PositionalSource`. There is no `std::ifstream`, no
// `getline`, no `mmap`, and no buffered stream anywhere in this module: the
// only reader is `pread(2)` at an explicit offset. The indirection exists so a
// test can install a shim that REFUSES any offset at or beyond the wall, which
// turns "we do not read past the boundary" from a claim into a mechanically
// enforced property (see tests/test_prefix_reader.cpp).
#ifndef QR_CANDIDATES_PREFIX_READER_HPP
#define QR_CANDIDATES_PREFIX_READER_HPP

#include <cstddef>
#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

#include "qr_candidates/signal_root.hpp"
#include "qr_core/refusal.hpp"

namespace qr::candidates {

/// The last ordinal this prefix may ever decode. Ordinal 750 and beyond is the
/// sealed wall of the whole program (FINAL_PLAN section 6, "s750+").
inline constexpr std::uint32_t kMaxPrefixOrdinal = 749;
/// The first ordinal whose signals are RETAINED. Ordinals 0..124 are decoded —
/// the root chain requires every row — but nothing about them is kept.
inline constexpr std::uint32_t kFirstRetainedOrdinal = 125;
/// The block size named by the card. Requests are `min(kBlockBytes, R-1)`.
inline constexpr std::size_t kBlockBytes = 1U << 20U;
/// The t14-declared data-row count of ordinals 0..749 (card section 2:
/// "exactly the first 10,684,134 data rows are ordinals0..749").
inline constexpr std::uint64_t kAdmittedRows0To749 = 10'684'134;
/// The pinned byte size of event_signals.tsv (event_publication manifest row
/// `leaf_event_signals_byte_size`).
inline constexpr std::int64_t kEventSignalsBytes = 14'084'281'865;
/// The pinned byte size of t14_bounds.tsv (`leaf_t14_bounds_byte_size`).
inline constexpr std::int64_t kT14BoundsBytes = 1'078'135;

/// The two sides an event signal can carry. There is no third value and no
/// "unknown": a cell that is neither refuses.
enum class ExtremeSide : std::uint8_t { LOW = 0, HIGH = 1 };
[[nodiscard]] const char* extreme_side_name(ExtremeSide side) noexcept;

/// THE ONLY WAY BYTES ENTER THIS MODULE: one positional read at an explicit
/// offset. No stream, no cursor, no readahead hint, no buffer of its own.
class PositionalSource {
 public:
  PositionalSource() = default;
  PositionalSource(const PositionalSource&) = delete;
  PositionalSource& operator=(const PositionalSource&) = delete;
  virtual ~PositionalSource();

  /// Reads exactly `size` bytes at `offset`. A short read is retried at the
  /// advanced offset; end-of-file before `size` bytes is a refusal, never a
  /// silently shorter answer.
  [[nodiscard]] virtual Expected<bool, Refusal> read_at(std::uint8_t* out, std::size_t size,
                                                        std::int64_t offset) = 0;
  /// The file's size in bytes, as the filesystem reports it.
  [[nodiscard]] virtual std::int64_t size_bytes() const noexcept = 0;
  /// Releases the descriptor. Called the instant the prefix ends, so the
  /// process holds no handle to the bytes beyond the wall.
  virtual void close() noexcept = 0;
  /// True once `close` has run.
  [[nodiscard]] virtual bool closed() const noexcept = 0;
};

/// The production source: an O_RDONLY descriptor read only through `pread`.
class FileSource final : public PositionalSource {
 public:
  [[nodiscard]] static Expected<std::unique_ptr<FileSource>, Refusal> open(const std::string& path);

  ~FileSource() override;
  [[nodiscard]] Expected<bool, Refusal> read_at(std::uint8_t* out, std::size_t size,
                                                std::int64_t offset) override;
  [[nodiscard]] std::int64_t size_bytes() const noexcept override { return size_; }
  void close() noexcept override;
  [[nodiscard]] bool closed() const noexcept override { return fd_ < 0; }

 private:
  FileSource(int fd, std::int64_t size, std::string path) noexcept
      : fd_(fd), size_(size), path_(std::move(path)) {}

  int fd_ = -1;
  std::int64_t size_ = 0;
  std::string path_;
};

/// The read ledger the receipt publishes, field-for-field the same shape the
/// frozen feasibility witness published (`receipt.json` -> `read_stats`), so
/// the two can be compared number by number.
struct ReadStats {
  std::uint64_t pread_calls = 0;
  std::uint64_t requested_bytes = 0;
  std::uint64_t header_calls = 0;
  std::uint64_t body_block_calls = 0;
  std::uint64_t final_byte_calls = 0;
  std::size_t max_request = 0;
  std::int64_t end_offset_exclusive = 0;
};

/// Kernel-level read accounting from /proc/self/io. `rchar` counts bytes this
/// process ASKED the kernel for; a buffered reader, a readline, or an mmap
/// fault would show up here as bytes the ledger above never requested.
struct IoAccounting {
  bool available = false;
  std::uint64_t rchar = 0;
  std::uint64_t syscr = 0;
  std::uint64_t read_bytes = 0;
};
[[nodiscard]] IoAccounting read_io_accounting() noexcept;

/// One t14_bounds row, restricted to the four cells this seal is entitled to.
struct T14Bound {
  std::uint32_t ordinal = 0;
  std::string day;
  std::uint64_t signal_count = 0;
  std::string signal_sequence_root;
};

/// Reads `t14_bounds.tsv` ONE BYTE AT A TIME through ordinal `stop` and stops.
/// Rows 750..1002 describe sessions outside every wall in this program, so the
/// reader never advances to them and the file's own sha is deliberately NOT
/// recomputed here (recomputing it would read exactly the bytes the wall
/// exists to keep out; the pinned digest is verified out of band).
[[nodiscard]] Expected<std::vector<T14Bound>, Refusal> load_t14_bounds(PositionalSource& source,
                                                                       std::uint32_t stop,
                                                                       ReadStats& stats);

/// One retained event signal — exactly the seven safe-leaf fields named by the
/// card ("The safe leaf retains ordinal,signal_id,physical_event_id,
/// policy_name,reversal_bps,extreme_side,causal_visible_ts_ns").
struct SignalAuth {
  std::uint32_t ordinal = 0;
  std::string signal_id;
  std::string physical_event_id;
  std::string policy_name;
  std::uint64_t reversal_bps = 0;
  ExtremeSide extreme_side = ExtremeSide::LOW;
  std::int64_t causal_visible_ts_ns = 0;
};

/// The retained signals of ONE session, sorted by `signal_id` and proven free
/// of duplicates. Sorted, not hashed: iteration order is an output here (the
/// safe leaf is written in this order) and unordered containers are banned on
/// output paths.
class SessionSignals {
 public:
  SessionSignals() = default;

  [[nodiscard]] std::uint32_t ordinal() const noexcept { return ordinal_; }
  [[nodiscard]] const std::vector<SignalAuth>& rows() const noexcept { return rows_; }
  [[nodiscard]] std::size_t size() const noexcept { return rows_.size(); }

  /// Binary search by signal id. Null when the id is not in this session —
  /// which is exactly the "member does not resolve in-session" state.
  [[nodiscard]] const SignalAuth* find(std::string_view signal_id) const noexcept;

  // --- construction, used by the reader and by fixtures --------------------
  void begin(std::uint32_t ordinal) noexcept;
  void append(SignalAuth row);
  /// Sorts by signal id and refuses a duplicate id inside the session.
  [[nodiscard]] Expected<bool, Refusal> seal();
  void clear() noexcept;

 private:
  std::uint32_t ordinal_ = 0;
  std::vector<SignalAuth> rows_;
};

/// What the reader hands back when a retained session's root has been verified.
/// Returning `false` (not a refusal) is not permitted: a sink either accepts or
/// refuses, so a silent drop cannot happen.
using SessionSink = std::function<Expected<bool, Refusal>(SessionSignals&)>;

struct PrefixSealOptions {
  /// Last ordinal to decode, inclusive. 749 is the full seal.
  std::uint32_t stop_ordinal = kMaxPrefixOrdinal;
  /// Lowest ordinal whose signals are retained and handed to the sink.
  std::uint32_t retain_from = kFirstRetainedOrdinal;
  /// Highest ordinal whose signals are retained. Set both bounds to the same
  /// value to retain exactly one session (the RSS-cheap seal).
  std::uint32_t retain_to = kMaxPrefixOrdinal;
  /// Enforce the pinned event_signals.tsv byte size before reading. Fixtures
  /// turn this off; production never does.
  bool require_pinned_event_bytes = true;
  /// Enforce that the summed t14 counts equal kAdmittedRows0To749 when the
  /// stop ordinal is 749.
  bool require_full_row_census = true;
};

/// The receipt of one seal.
struct PrefixSeal {
  std::uint32_t stop_ordinal = 0;
  std::uint64_t expected_data_rows = 0;
  std::uint64_t decoded_data_rows = 0;
  std::uint32_t roots_verified = 0;
  ReadStats event_stats;
  ReadStats t14_stats;
  IoAccounting io_before;
  IoAccounting io_after;
  /// sha256 of exactly the prefix bytes this reader consumed, header included.
  /// The whole-file digest is pinned externally and must NOT be recomputed by
  /// a process that is forbidden to touch the bytes past the wall; this digest
  /// covers precisely the region that was lawfully read.
  std::string consumed_prefix_sha256;
  /// Per-session roots, in ordinal order, as verified against t14.
  std::vector<std::string> session_roots;
};

/// Seals the ordinal-0..`stop` prefix of `event_signals.tsv`.
///
/// `bounds` must be the t14 rows 0..stop in ordinal order. The reader verifies
/// each session's row count and sequence root against them, hands every
/// retained session to `sink`, and closes `event` before returning.
[[nodiscard]] Expected<PrefixSeal, Refusal> seal_prefix(PositionalSource& event,
                                                        const std::vector<T14Bound>& bounds,
                                                        const PrefixSealOptions& options,
                                                        const SessionSink& sink);

/// Serializes a sealed session as the frozen safe leaf: a seven-column header
/// line, then one line per signal in ascending `signal_id` order. Byte-for-byte
/// the layout the feasibility witness wrote, so its published leaf sha256
/// 549a9225000de0ba27b982434b379da5433eb712807d21756d52c6193c192eed is an
/// independent check on this port.
[[nodiscard]] std::string render_safe_leaf(const SessionSignals& session);

}  // namespace qr::candidates

#endif  // QR_CANDIDATES_PREFIX_READER_HPP
