// qr_campaign/driver.hpp — THE CAMPAIGN CORPUS-BUILD DRIVER (payload-free half).
//
// WHAT THIS MODULE IS. FINAL_PLAN.md §9 R2 ("corpus build (extraction + labels
// + tensors; per-session shards)") needs ONE tool that produces the complete
// APPENDIX C4 DecisionTape for all 793 scoped sessions by COMPOSING the modules
// M1 already built and reviewed: qr_candidates (roster + seal), qr_labels
// (watches + kernel), qr_carriers (streams + DIRECT + native carriers + grid +
// location + candidate set) and qr_emit (ShardWriter + fd census). It contains
// NO SCIENCE: every value it publishes is produced by a constructor that was
// specified, fixtured and reviewed inside its own work package. What lives here
// is orchestration — the spec gate, the ordinal wall, ordinal-ordered dispatch,
// the publish/resume discipline, and the deterministic receipts.
//
// THE HALF THAT LIVES IN THIS HEADER is the half that touches no payload, so
// every law below is directly fixturable: the frozen-card gate, the 125..917
// wall, the run layout, the task plan (resume), the shard emitter (stage →
// no-replace publish) and the ordinal-ordered ledger. session_build.hpp holds
// the half that opens the corpus.
//
// FOUR LAWS THIS FILE ENFORCES, EACH WITH ITS OWN FIXTURE:
//
//   1. SPEC GATE (card §7 A8: "No implementation or launch precedes a GREEN
//      review on these exact bytes"). The driver re-hashes the frozen task card
//      before it forms a single path and refuses on any mismatch. A campaign
//      run is a claim about a frozen object; a drifted card is a different
//      object.
//   2. ORDINAL WALL (card §1 as amended 2026-08-12-c: "Only sessions 125..917 are admissible. Any
//      path/session >=750 ... is refused before payload resolution"). The wall
//      is applied to the REQUEST, before any root is composed — not deep inside
//      a reader where a path has already been built.
//   3. PUBLISH DISCIPLINE (qr_emit's stage → RENAME_NOREPLACE). A worker that
//      dies mid-session leaves a stage directory and no published shard, and a
//      publish onto an existing shard is a typed refusal, never a replacement.
//      Resume therefore means SKIP, not overwrite.
//   4. ORDINAL-ORDERED MERGE (FINAL_PLAN §6: "ordinal-only merge"). Workers
//      finish in whatever order the machine gives them; the campaign receipt is
//      assembled by READING the per-session receipts in ordinal order, so the
//      published bytes are a function of the session set and never of the
//      worker count or the completion order.
#ifndef QR_CAMPAIGN_DRIVER_HPP
#define QR_CAMPAIGN_DRIVER_HPP

#include <array>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include "qr_core/refusal.hpp"
#include "qr_emit/shard_writer.hpp"
#include "qr_registry/day_scope.hpp"

namespace qr::campaign {

using qr::emit::Status;
using qr::emit::ok_status;

// ---------------------------------------------------------------------------
// The frozen bindings. Card §1 A8: the substrate "hard-codes only
// /workspace/data/tokens/{stock_trades,stock_quotes,options_prints}, IWM, and
// 125..917 (amended 2026-08-12-c) ... never opens `cutoff_context`, labels, option quotes, or a freely
// selected root". These are constants and not flags for exactly that reason.
// ---------------------------------------------------------------------------

inline constexpr std::int64_t kFirstScopedOrdinal = qr::kScopeFirstOrdinal;
inline constexpr std::int64_t kLastScopedOrdinal = qr::kScopeLastOrdinal;
inline constexpr std::int64_t kScopedSessionCount =
    kLastScopedOrdinal - kFirstScopedOrdinal + 1;
// FINAL_PLAN AMENDMENT 2026-08-12-c (D-038): 125..917 = the 793 in scope
// (was 125..749 = 625). The campaign wall is now DERIVED from the one wall in
// qr_registry/day_scope.hpp so the two can never drift apart again.
static_assert(kScopedSessionCount == 793, "AMENDMENT 2026-08-12-c: 125..917 = the 793 in scope");
static_assert(kLastScopedOrdinal == qr::kScopeLastOrdinal,
              "the campaign wall must be the qr_registry wall, not a copy of it");

/// The frozen task card, and the ORDERED lineage of its frozen shas. The driver
/// builds only against the lineage HEAD; a corpus published under an older row
/// stays valid exactly while every later amendment is declared outside the tape
/// read scope below. The lineage file states the grammar it is parsed under.
inline constexpr std::string_view kCardPath =
    "/workspace/evidence/claims/native_state/TASK_CARD_V4_DRAFT.md";
inline constexpr std::string_view kCardLineagePath =
    "/workspace/evidence/claims/native_state/CARD_LINEAGE.tsv";

/// The card sections the R2 tape constructors actually read: the walls and the
/// roster (S1), the watch and label kernels (S2, S3), the native inputs (S4)
/// and the leaf layout (APPENDIX C4). An amendment that declares any of these
/// retires every tape built before it; one that declares none cannot.
inline constexpr std::array<std::string_view, 5> kTapeReadScope{"S1", "S2", "S3", "S4", "C4"};

inline constexpr std::string_view kStockQuotesRoot = "/workspace/data/tokens/stock_quotes/IWM";
inline constexpr std::string_view kStockTradesRoot = "/workspace/data/tokens/stock_trades/IWM";
inline constexpr std::string_view kOptionPrintsRoot = "/workspace/data/tokens/options_prints/IWM";

/// FINAL_PLAN §9 R2 output root.
inline constexpr std::string_view kDefaultBaseRoot = "/workspace/artifacts/tensors/v4.0";

/// The R1 probe object (card §7: "The production probe is exactly {125,500,625},
/// two runs").
inline constexpr std::array<std::int64_t, 3> kProbeSessions{125, 500, 625};

// ---------------------------------------------------------------------------
// 1. the spec gate and 2. the ordinal wall
// ---------------------------------------------------------------------------

/// Re-hashes `card` and refuses unless it is exactly `expected_sha256`.
/// CONTENT_MISMATCH on drift, IO when the card cannot be read.
[[nodiscard]] Status verify_frozen_spec(const std::filesystem::path& card,
                                        std::string_view expected_sha256);

/// One row of CARD_LINEAGE.tsv.
struct CardLineageRow {
  std::string sha256;
  std::string date;
  std::string amendment;
  /// Normalized scope tokens: `ROOT` on the first row, else S1..S9 / C4.
  std::vector<std::string> scope;
  std::string consumers_invariant;

  /// True when this amendment's declared scope meets `kTapeReadScope`, i.e.
  /// when it retires every tape published before it.
  [[nodiscard]] bool touches_tape_read_scope() const;
};

/// The ordered card lineage: the honest replacement for a single pinned sha.
/// It answers the two different questions a pin conflates — "may I BUILD
/// against these card bytes?" (only against the head) and "is a corpus built
/// under an older card still valid?" (yes, exactly while every later amendment
/// is declared outside the tape read scope).
class CardLineage {
 public:
  /// Parses and validates the whole file: five fields per row, oldest first,
  /// 64-hex shas, no duplicates, `ROOT` on the first row and nowhere else, and
  /// no scope token outside the grammar. Anything malformed REFUSES — an
  /// unreadable lineage must never default a gate open.
  [[nodiscard]] static Expected<CardLineage, Refusal> load(const std::filesystem::path& path);

  [[nodiscard]] const std::vector<CardLineageRow>& rows() const noexcept { return rows_; }
  [[nodiscard]] const CardLineageRow& head() const noexcept { return rows_.back(); }

  /// The BUILD gate: `card` must hash to the lineage head.
  [[nodiscard]] Status verify_head_card(const std::filesystem::path& card) const;

  /// The CONSUMER gate: `sha` (a shard manifest's `census task_card_v4` value)
  /// must be a row of this lineage, and every row after it must be declared
  /// outside `kTapeReadScope`. A sha that is not in the lineage at all is a
  /// refusal — an unknown ancestor is not an ancestor.
  [[nodiscard]] Status verify_corpus_card_sha(std::string_view sha) const;

 private:
  std::vector<CardLineageRow> rows_;
};

/// Every distinct `census task_card_v4` sha under `<run_root>/tapes`, with the
/// number of shard manifests carrying it, sha-ordered. A manifest without that
/// census row is a refusal, not an empty answer.
[[nodiscard]] Expected<std::vector<std::pair<std::string, std::int64_t>>, Refusal>
corpus_card_shas(const std::filesystem::path& run_root);

/// The 125..749 wall, applied to a REQUESTED ordinal before any path exists.
[[nodiscard]] Status refuse_unless_in_scope(std::int64_t ordinal);

/// Parses `--sessions`: `all`, a comma list (`125,500,625`), inclusive ranges
/// (`125-200`), or any mixture. The result is sorted, deduplicated and fully
/// inside the wall; anything else refuses.
[[nodiscard]] Expected<std::vector<std::int64_t>, Refusal> parse_session_list(
    std::string_view spec);

// ---------------------------------------------------------------------------
// The run layout
// ---------------------------------------------------------------------------

/// Two runs of the same campaign publish into two disjoint sub-roots of the
/// same base, so the byte-identity comparison is a comparison of two trees and
/// never of a tree against itself.
struct RunLayout {
  std::filesystem::path base;
  int run_index = 1;  ///< 1 = R1, 2 = the --run2 identity re-run
  /// The lineage-head sha the spec gate bound this process to, stamped into
  /// every shard manifest and the campaign receipt. EMPTY until the gate has
  /// run: a publisher with an unbound layout REFUSES rather than name a card
  /// nobody verified.
  std::string card_sha256;

  [[nodiscard]] std::filesystem::path root() const;
  [[nodiscard]] std::filesystem::path tapes() const;
  [[nodiscard]] std::filesystem::path rosters() const;
  [[nodiscard]] std::filesystem::path roster_dir(std::int64_t ordinal) const;
  [[nodiscard]] std::filesystem::path roster_tsv(std::int64_t ordinal) const;
  [[nodiscard]] std::filesystem::path receipts() const;
  [[nodiscard]] std::filesystem::path session_receipt(std::int64_t ordinal) const;
  [[nodiscard]] std::filesystem::path session_timing(std::int64_t ordinal) const;
  [[nodiscard]] std::filesystem::path builder_census(std::int64_t ordinal) const;
  [[nodiscard]] std::filesystem::path truth_receipt(std::int64_t ordinal) const;
  /// The tagged constructor phase's own census (stream/carrier counters). The
  /// emit step merges it into the session receipt under `builder.*`.
  [[nodiscard]] std::filesystem::path builder_receipt(std::int64_t ordinal) const;
};

[[nodiscard]] Expected<RunLayout, Refusal> run_layout(const std::filesystem::path& base,
                                                      int run_index);

/// `s0125` — the C4 session directory component, four digits, never truncated.
[[nodiscard]] Expected<std::string, Refusal> session_dir_name(std::int64_t ordinal);

// ---------------------------------------------------------------------------
// 3. the task plan (publish discipline + resume)
// ---------------------------------------------------------------------------

enum class SideWork : std::uint8_t {
  BUILD,              ///< nothing published for this side yet
  ALREADY_PUBLISHED,  ///< manifest.tsv is on disk; resume SKIPS it
};

struct SessionTask {
  std::int64_t ordinal = 0;
  /// Index 0 = LONG, index 1 = SHORT (qr::emit::Side's own order).
  std::array<SideWork, 2> side{SideWork::BUILD, SideWork::BUILD};

  [[nodiscard]] bool any_work() const noexcept {
    return side[0] == SideWork::BUILD || side[1] == SideWork::BUILD;
  }
  [[nodiscard]] bool build(qr::emit::Side which) const noexcept {
    return side[static_cast<std::size_t>(which)] == SideWork::BUILD;
  }
};

/// True when `<tapes>/s<NNNN>/<L|S>/manifest.tsv` exists: a shard is published
/// exactly when its manifest is, because the manifest is written last and the
/// whole directory arrives in one rename.
[[nodiscard]] bool side_is_published(const RunLayout& layout, std::int64_t ordinal,
                                     qr::emit::Side side);

/// The ordinal-ordered work plan. With `resume=false` an already-published
/// shard is a REFUSAL (the no-replace law surfaced before a worker burns a
/// session on it); with `resume=true` it is skipped and never published twice.
[[nodiscard]] Expected<std::vector<SessionTask>, Refusal> plan_tasks(
    const RunLayout& layout, std::span<const std::int64_t> requested, bool resume);

// ---------------------------------------------------------------------------
// Deterministic receipts
// ---------------------------------------------------------------------------

/// A `section<TAB>metric<TAB>value` TSV in insertion order. NO TIMINGS EVER go
/// in one: the two-run byte-identity comparison covers these bytes.
class Receipt {
 public:
  void add(std::string_view section, std::string_view metric, std::int64_t value);
  void add_text(std::string_view section, std::string_view metric, std::string_view value);
  [[nodiscard]] std::string render() const;
  /// Writes through the repo's publish discipline: a sibling `.<name>.tmp-<pid>`
  /// staged, fsynced, then renamed over the destination.
  [[nodiscard]] Status write(const std::filesystem::path& path) const;
  [[nodiscard]] std::size_t rows() const noexcept { return rows_.size(); }

 private:
  std::vector<std::string> rows_;
};

/// One `section metric value` row, as `parse_receipt` hands it back.
struct ReceiptRow {
  std::string section;
  std::string metric;
  std::string value;
};

[[nodiscard]] Expected<std::vector<ReceiptRow>, Refusal> parse_receipt(
    const std::filesystem::path& path);

/// Value of one row, or a refusal when the receipt does not carry it.
[[nodiscard]] Expected<std::string, Refusal> receipt_value(std::span<const ReceiptRow> rows,
                                                           std::string_view section,
                                                           std::string_view metric);

// ---------------------------------------------------------------------------
// 4. the ordinal-ordered merge
// ---------------------------------------------------------------------------

/// The campaign-level receipt: it is assembled by READING the per-session
/// receipts of `ordinals` in ascending order, so neither the worker count nor
/// the completion order can reach the published bytes. The returned text ends
/// with the manifest root hash — sha256 over `s<NNNN>\t<L|S>\t<manifest sha>\n`
/// lines in that same order.
[[nodiscard]] Expected<std::string, Refusal> render_campaign_receipt(
    const RunLayout& layout, std::span<const std::int64_t> ordinals);

/// sha256 of an in-memory string, hex.
[[nodiscard]] std::string sha256_hex(std::string_view text);

// ---------------------------------------------------------------------------
// The shard emitter
// ---------------------------------------------------------------------------

/// The driver's one door to qr_emit. It exists so the campaign's publish
/// discipline is a single code path with a single fixture: stale stage
/// directories of EXACTLY this (ordinal, side) are removed first, the writer is
/// opened on the C4 path, and `publish()` is the only way bytes become visible.
class ShardEmitter {
 public:
  [[nodiscard]] static Expected<std::unique_ptr<ShardEmitter>, Refusal> open(
      const RunLayout& layout, std::int64_t ordinal, qr::emit::Side side,
      std::string build_id, std::vector<qr::emit::SourceRow> sources,
      std::vector<qr::emit::CensusRow> census);

  [[nodiscard]] qr::emit::ShardWriter& writer() noexcept { return *writer_; }
  [[nodiscard]] Expected<qr::emit::ShardReceipt, Refusal> publish();
  [[nodiscard]] const std::filesystem::path& stage_dir() const noexcept;

 private:
  explicit ShardEmitter(std::unique_ptr<qr::emit::ShardWriter> writer)
      : writer_(std::move(writer)) {}
  std::unique_ptr<qr::emit::ShardWriter> writer_;
};

/// Removes stage directories left by a dead worker for exactly this
/// (ordinal, side): `<tapes>/s<NNNN>/.<L|S>.stage-*`. A stage directory is by
/// construction not a published shard, so this can never delete published
/// bytes; it returns how many it removed.
[[nodiscard]] Expected<std::int64_t, Refusal> clear_stale_stages(const RunLayout& layout,
                                                                 std::int64_t ordinal,
                                                                 qr::emit::Side side);

}  // namespace qr::campaign

#endif  // QR_CAMPAIGN_DRIVER_HPP
