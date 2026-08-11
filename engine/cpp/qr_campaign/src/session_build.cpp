#include "qr_campaign/session_build.hpp"

#include <sys/wait.h>
#include <unistd.h>

#include <algorithm>
#include <array>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <optional>
#include <string>
#include <vector>

#include "qr_campaign/handoff.hpp"
#include "qr_campaign/roster_view.hpp"
#include "qr_candidates/prefix_reader.hpp"
#include "qr_candidates/roster.hpp"
#include "qr_candidates/rowgroup_table.hpp"
#include "qr_candidates/signal_root.hpp"
#include "qr_carriers/candidate_set.hpp"
#include "qr_carriers/direct_raw.hpp"
#include "qr_carriers/grid_1s.hpp"
#include "qr_carriers/location.hpp"
#include "qr_carriers/native_order.hpp"
#include "qr_carriers/streams.hpp"
#include "qr_emit/fd_census.hpp"
#include "qr_labels/execution_tape.hpp"
#include "qr_labels/label_kernel.hpp"
#include "qr_labels/watches.hpp"
#include "qr_registry/day_scope.hpp"
#include "qr_sources/option_prints.hpp"
#include "qr_sources/stock_quotes.hpp"
#include "qr_sources/stock_trades.hpp"

namespace qr::campaign {
namespace {

constexpr const char* kSite = "qr_campaign::session_build";

[[nodiscard]] Refusal content(const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, kSite, detail, context);
}
[[nodiscard]] Refusal io(const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::IO, kSite, detail, context);
}

// --- the bound publication authorities (card §1; identical pins to WP6) ------
constexpr const char* kEventSignalsPath =
    "/workspace/artifacts/runs/e1_rel037_verified_event/event_publication/event_signals.tsv";
constexpr const char* kT14Path =
    "/workspace/artifacts/runs/e1_rel037_verified_event/event_publication/t14_bounds.tsv";
constexpr const char* kProjectionPath =
    "/workspace/artifacts/runs/events.4_stage_run/pub/truth_relation_projection.parquet";
constexpr const char* kProjectionIndexPath =
    "/workspace/artifacts/runs/events.4_stage_run/pub/truth_relation_projection_session_index.tsv";
constexpr const char* kRegistryPath =
    "/workspace/artifacts/runs/e6_registry_fresh/candidate_action_registry.parquet";
constexpr const char* kRegistryIndexPath =
    "/workspace/artifacts/runs/e6_registry_fresh/candidate_action_registry_session_index.tsv";
constexpr const char* kProjectionSha =
    "c41b889b24305a87149eb48089afc0b06470faa09e72f979f3a090b1c35cc322";
constexpr const char* kProjectionIndexSha =
    "f54cc08bcf7af04f7175afe7b224b57609439e7048c45c87d490c035a0af3556";
constexpr const char* kRegistrySha =
    "f7a9a4d4b9b83fac467044251ec1947ef0019fae69113c2911291f74af2a9d71";
constexpr const char* kRegistryIndexSha =
    "827b72e0f91e10824050653f82e140bd98d1ea1fefd6bd657acf3280ef2587d8";
/// Card §1 A8's dialect-census pin: a census pointer in every manifest.
constexpr const char* kDialectCensusSha =
    "63557a434a981f5b5e2562b43c1a41086c1c7a0fd198d4560ace0f2f8b1c233b";
constexpr const char* kDialectCensusPath = "/workspace/artifacts/cache/cpp/dialect_census.tsv";

/// The C4 leaf names this driver owns (the native ones come from
/// qr_carriers::native_leaf_name, which stays the single naming authority).
constexpr const char* kLeafDirectRaw = "direct_raw";
constexpr const char* kLeafLocClock = "locclock";
constexpr const char* kLeafCandSet = "candset";
constexpr const char* kLeafCandSetOffsets = "candset_offsets";
constexpr const char* kLeafMasks = "masks";
constexpr const char* kLeafGrid = "grid_1s";
constexpr const char* kLeafKeys = "keys";

/// `masks [N,7] u1` — the availability plane APPENDIX C4 lists as "masks" and
/// card §7 buckets its destructions on ("(session,side,stage-mask,availability)").
/// Columns, frozen: the three watch-stage bits of the action row, the three
/// per-modality "the 120s window is nonempty" bits (copied from that modality's
/// own DIRECT full-window `nonempty` column, never recomputed), and
/// `legal_enter` (card §6: "determined only by the authenticated watch and
/// clock"), which is 1 for every published action row and is carried explicitly
/// because the replay reads it.
constexpr std::size_t kMaskColumns = 7;

using qr::carriers::kDirectColumnCount;
using qr::carriers::kLocationValueCount;
using qr::carriers::kModalityCount;
using qr::carriers::Modality;
using qr::carriers::NativeLeaf;

[[nodiscard]] qr::carriers::Side carrier_side(qr::labels::Side side) {
  return side == qr::labels::Side::LONG ? qr::carriers::Side::LONG : qr::carriers::Side::SHORT;
}
[[nodiscard]] qr::emit::Side emit_side(qr::labels::Side side) {
  return side == qr::labels::Side::LONG ? qr::emit::Side::LONG : qr::emit::Side::SHORT;
}

/// The same staged-then-rename discipline `Receipt::write` uses, for text this
/// module did not build as a receipt (a roster publication, the builder census
/// lifted out of the handoff). The staged name carries no pid for the reason
/// stated in driver.cpp: a pid would land inside a published fd census.
[[nodiscard]] Status write_text_atomic(const std::filesystem::path& path, std::string_view text) {
  std::error_code code;
  std::filesystem::create_directories(path.parent_path(), code);
  if (code) {
    return Status::refuse(io("cannot create a publication directory", code.value()));
  }
  const std::filesystem::path staged =
      path.parent_path() / ("." + path.filename().string() + ".staging");
  {
    std::ofstream out(staged, std::ios::binary | std::ios::trunc);
    if (!out) {
      return Status::refuse(io("cannot create a staged publication"));
    }
    out.write(text.data(), static_cast<std::streamsize>(text.size()));
    out.close();
    if (!out) {
      return Status::refuse(io("short write to a staged publication"));
    }
  }
  std::filesystem::rename(staged, path, code);
  if (code) {
    return Status::refuse(io("cannot rename a staged publication into place", code.value()));
  }
  return ok_status();
}

[[nodiscard]] Expected<std::string, Refusal> read_text(const std::filesystem::path& path) {
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return Expected<std::string, Refusal>::refuse(io("cannot read a published file"));
  }
  return Expected<std::string, Refusal>(
      std::string((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>()));
}

/// Publishes `text` at `path`, or byte-compares it against what is already
/// there. A resumed run standing on different bytes is a refusal, never a
/// silent replacement.
[[nodiscard]] Status publish_or_verify(const std::filesystem::path& path, std::string_view text) {
  std::error_code code;
  if (std::filesystem::is_regular_file(path, code)) {
    auto existing = read_text(path);
    if (!existing.has_value()) {
      return Status::refuse(existing.error());
    }
    if (existing.value() != text) {
      return Status::refuse(
          content("a published roster differs from the one this run rebuilt; two runs of the "
                  "same campaign must agree byte for byte"));
    }
    return ok_status();
  }
  return write_text_atomic(path, text);
}

}  // namespace

// ===========================================================================
// STAGE 1 — the roster stage
// ===========================================================================

Status build_rosters(const RunLayout& layout, std::span<const std::int64_t> ordinals,
                     const BuildOptions& options) {
  using qr::candidates::FileSource;
  using qr::candidates::PrefixSealOptions;
  using qr::candidates::RowGroupTable;
  using qr::candidates::SessionIndex;
  using qr::candidates::SessionSignals;

  std::vector<std::int64_t> wanted(ordinals.begin(), ordinals.end());
  std::sort(wanted.begin(), wanted.end());
  wanted.erase(std::unique(wanted.begin(), wanted.end()), wanted.end());
  if (wanted.empty()) {
    return Status::refuse(content("the roster stage was given no session"));
  }
  for (const std::int64_t ordinal : wanted) {
    const Status wall = refuse_unless_in_scope(ordinal);
    if (!wall.has_value()) {
      return wall;
    }
  }

  // --- the pinned digests of everything that will be DECODED ---------------
  const auto verify = [](const char* path, const char* expected) -> Status {
    auto digest = qr::candidates::sha256_file_hex(path);
    if (!digest.has_value()) {
      return Status::refuse(digest.error());
    }
    if (digest.value() != expected) {
      return Status::refuse(content("a bound publication is not its pinned sha256"));
    }
    return ok_status();
  };
  Status digested = verify(kProjectionIndexPath, kProjectionIndexSha);
  if (!digested.has_value()) {
    return digested;
  }
  digested = verify(kRegistryIndexPath, kRegistryIndexSha);
  if (!digested.has_value()) {
    return digested;
  }
  if (options.verify_publication_digests) {
    digested = verify(kProjectionPath, kProjectionSha);
    if (!digested.has_value()) {
      return digested;
    }
    digested = verify(kRegistryPath, kRegistrySha);
    if (!digested.has_value()) {
      return digested;
    }
  }

  // --- t14 bounds, then the two row-group tables ---------------------------
  const auto stop = static_cast<std::uint32_t>(wanted.back());
  qr::candidates::ReadStats t14_stats;
  std::vector<qr::candidates::T14Bound> bounds;
  {
    auto source = FileSource::open(kT14Path);
    if (!source.has_value()) {
      return Status::refuse(source.error());
    }
    auto loaded = qr::candidates::load_t14_bounds(*source.value(), stop, t14_stats);
    if (!loaded.has_value()) {
      return Status::refuse(loaded.error());
    }
    bounds = std::move(loaded).value();
  }

  auto projection_index = SessionIndex::load(kProjectionIndexPath, kProjectionIndexSha);
  if (!projection_index.has_value()) {
    return Status::refuse(projection_index.error());
  }
  auto registry_index = SessionIndex::load(kRegistryIndexPath, kRegistryIndexSha);
  if (!registry_index.has_value()) {
    return Status::refuse(registry_index.error());
  }
  const std::vector<std::string_view> projection_allow(
      qr::candidates::kProjectionAllowlist.begin(), qr::candidates::kProjectionAllowlist.end());
  const std::vector<std::string_view> projection_deny(
      qr::candidates::kProjectionForbidden.begin(), qr::candidates::kProjectionForbidden.end());
  const std::vector<std::string_view> registry_allow(qr::candidates::kRegistryAllowlist.begin(),
                                                     qr::candidates::kRegistryAllowlist.end());
  const std::vector<std::string_view> registry_deny(qr::candidates::kRegistryForbidden.begin(),
                                                    qr::candidates::kRegistryForbidden.end());
  std::string detail;
  // The digests were verified above; an empty expectation here avoids hashing
  // 6.2GB a second time. Both tables stay open for the whole pass — the seal
  // hands sessions over in ordinal order and each roster needs both row groups.
  auto projection = RowGroupTable::open(kProjectionPath, {}, std::move(projection_index).value(),
                                        projection_allow, projection_deny,
                                        qr::candidates::kPublicationRowGroups, &detail);
  if (!projection.has_value()) {
    return Status::refuse(projection.error());
  }
  auto registry = RowGroupTable::open(kRegistryPath, {}, std::move(registry_index).value(),
                                      registry_allow, registry_deny,
                                      qr::candidates::kPublicationRowGroups, &detail);
  if (!registry.has_value()) {
    return Status::refuse(registry.error());
  }

  // --- ONE bounded prefix pass, publishing one roster per requested session --
  Receipt receipt;
  receipt.add_text("roster_stage", "schema", "qr_campaign_roster_stage_v1");
  receipt.add("roster_stage", "stop_ordinal", stop);
  receipt.add("roster_stage", "requested_sessions", static_cast<std::int64_t>(wanted.size()));

  std::vector<std::int64_t> published;
  std::optional<Refusal> failure;
  PrefixSealOptions seal_options;
  seal_options.stop_ordinal = stop;
  seal_options.retain_from = static_cast<std::uint32_t>(wanted.front());
  seal_options.retain_to = stop;
  auto event = FileSource::open(kEventSignalsPath);
  if (!event.has_value()) {
    return Status::refuse(event.error());
  }
  auto sealed = qr::candidates::seal_prefix(
      *event.value(), bounds, seal_options,
      [&](SessionSignals& signals) -> Expected<bool, Refusal> {
        const auto ordinal = static_cast<std::int64_t>(signals.ordinal());
        if (!std::binary_search(wanted.begin(), wanted.end(), ordinal)) {
          return Expected<bool, Refusal>(true);  // retained by range, not wanted
        }
        auto projection_columns = projection.value().read_session(signals.ordinal());
        if (!projection_columns.has_value()) {
          return Expected<bool, Refusal>::refuse(projection_columns.error());
        }
        auto registry_columns = registry.value().read_session(signals.ordinal());
        if (!registry_columns.has_value()) {
          return Expected<bool, Refusal>::refuse(registry_columns.error());
        }
        auto roster = qr::candidates::build_session_roster(
            signals.ordinal(), registry_columns.value(), projection_columns.value(), signals);
        if (!roster.has_value()) {
          return Expected<bool, Refusal>::refuse(roster.error());
        }
        const std::string roster_text = qr::candidates::render_roster(roster.value());
        const std::string census_text = qr::candidates::render_census(roster.value().census);
        Status written = publish_or_verify(layout.roster_tsv(ordinal), roster_text);
        if (!written.has_value()) {
          return Expected<bool, Refusal>::refuse(written.error());
        }
        written = publish_or_verify(layout.roster_dir(ordinal) / "census.tsv", census_text);
        if (!written.has_value()) {
          return Expected<bool, Refusal>::refuse(written.error());
        }
        published.push_back(ordinal);
        return Expected<bool, Refusal>(true);
      });
  if (!sealed.has_value()) {
    return Status::refuse(sealed.error());
  }
  if (failure.has_value()) {
    return Status::refuse(failure.value());
  }
  if (published.size() != wanted.size()) {
    return Status::refuse(content("the prefix pass did not retain every requested session",
                                  static_cast<std::int64_t>(published.size())));
  }

  receipt.add("roster_stage", "published_sessions", static_cast<std::int64_t>(published.size()));
  receipt.add("roster_stage", "decoded_data_rows",
              static_cast<std::int64_t>(sealed.value().decoded_data_rows));
  receipt.add("roster_stage", "roots_verified",
              static_cast<std::int64_t>(sealed.value().roots_verified));
  receipt.add_text("roster_stage", "consumed_prefix_sha256", sealed.value().consumed_prefix_sha256);
  receipt.add_text("roster_stage", "truth_relation_projection_sha256", kProjectionSha);
  receipt.add_text("roster_stage", "candidate_action_registry_sha256", kRegistrySha);
  for (const std::int64_t ordinal : published) {
    auto text = read_text(layout.roster_tsv(ordinal));
    if (!text.has_value()) {
      return Status::refuse(text.error());
    }
    auto name = session_dir_name(ordinal);
    if (!name.has_value()) {
      return Status::refuse(name.error());
    }
    receipt.add_text("roster." + name.value(), "sha256", sha256_hex(text.value()));
  }
  return receipt.write(layout.receipts() / "roster_stage.tsv");
}

// ===========================================================================
// STAGE 2 — one session
// ===========================================================================
namespace {

/// Everything the two phases of a worker share, computed BEFORE the fork so the
/// tagged child inherits it and cannot derive a different action order.
struct SessionPlan {
  qr::DayScope scope;
  qr::SessionClock clock;
  RosterView roster;
  qr::labels::WatchPlan watches;
  qr::labels::DecisionClock decision_clock;
  /// Indices into `watches.actions`, per side, ascending — the row order of the
  /// two shards.
  std::array<std::vector<std::size_t>, 2> rows;
  std::int64_t decision_roster_size = 0;
  std::int64_t decision_roster_off_second = 0;
  std::int64_t decision_roster_on_second = 0;
};

[[nodiscard]] Expected<SessionPlan, Refusal> plan_session(const RunLayout& layout,
                                                          std::int64_t ordinal) {
  using Result = Expected<SessionPlan, Refusal>;
  static const auto registry = qr::Registry::load_embedded();
  if (!registry.has_value()) {
    return Result::refuse(registry.error());
  }
  auto scope = qr::DayScope::admit(registry.value(), ordinal);
  if (!scope.has_value()) {
    return Result::refuse(scope.error());
  }
  auto clock = qr::SessionClock::from_session(scope.value().session());
  if (!clock.has_value()) {
    return Result::refuse(clock.error());
  }
  auto roster = RosterView::load(layout.roster_tsv(ordinal), ordinal);
  if (!roster.has_value()) {
    return Result::refuse(roster.error());
  }
  if (roster.value().day() != scope.value().day()) {
    return Result::refuse(content("the roster's day is not the registry's day for this ordinal",
                                  ordinal));
  }
  auto decision_clock = qr::labels::DecisionClock::from_clock(clock.value());
  if (!decision_clock.has_value()) {
    return Result::refuse(decision_clock.error());
  }
  auto decision_roster = qr::labels::DecisionRoster::build(
      decision_clock.value(), roster.value().admitted_visibilities());
  if (!decision_roster.has_value()) {
    return Result::refuse(decision_roster.error());
  }
  auto watches = qr::labels::build_watches(ordinal, decision_clock.value(),
                                           decision_roster.value(),
                                           roster.value().watch_candidates());
  if (!watches.has_value()) {
    return Result::refuse(watches.error());
  }
  SessionPlan plan{scope.value(), clock.value(), std::move(roster).value(),
                   std::move(watches).value(), decision_clock.value(), {}, 0, 0, 0};
  plan.decision_roster_size = decision_roster.value().size();
  plan.decision_roster_off_second = decision_roster.value().visibilities_off_second();
  plan.decision_roster_on_second = decision_roster.value().visibilities_on_second();
  for (std::size_t index = 0; index < plan.watches.actions.size(); ++index) {
    const qr::labels::ActionRow& action = plan.watches.actions[index];
    const std::size_t side = action.key.side == qr::labels::Side::LONG ? 0U : 1U;
    plan.rows[side].push_back(index);
  }
  return Result(std::move(plan));
}

// ---------------------------------------------------------------------------
// The FEATURE_BUILDER phase (child process)
// ---------------------------------------------------------------------------

/// Reads one modality into its stream. The three readers differ only in type,
/// so the loop is written once per reader by the caller.
template <class Reader, class Stream>
[[nodiscard]] Status pump(Reader& reader, Stream& stream) {
  typename Reader::Group group;
  for (;;) {
    auto more = reader.next_group(group);
    if (!more.has_value()) {
      return Status::refuse(more.error().refusal());
    }
    if (!more.value()) {
      return ok_status();
    }
    const auto pushed = stream.push_group(group.ts_ms_b, group.rows);
    if (!pushed.has_value()) {
      return Status::refuse(pushed.error());
    }
  }
}

[[nodiscard]] Status build_features(int handoff_fd, const RunLayout& layout,
                                    const SessionPlan& plan) {
  using namespace qr::carriers;  // NOLINT(build/namespaces) — the constructors

  qr::emit::FdCensus::instance().begin(qr::emit::ProcessRole::FEATURE_BUILDER);

  const std::int64_t ordinal = plan.scope.ordinal();
  const std::int64_t session_start_ns = plan.clock.session_start_a().ns();

  StreamOptions stream_options;
  stream_options.retain_group_vectors = true;
  stream_options.side_spot_stride = 0;

  NbboStream nbbo(plan.clock, stream_options);
  StockPrintStream prints(plan.clock, stream_options);
  OptionPrintStream options_stream(plan.clock, stream_options);
  std::int64_t quote_rth_rows = 0;
  std::int64_t quote_groups = 0;
  std::int64_t trade_rth_rows = 0;
  std::int64_t trade_groups = 0;
  std::int64_t option_rth_rows = 0;
  std::int64_t option_groups = 0;
  {
    auto opened = qr::sources::StockQuoteReader::open(plan.scope, kStockQuotesRoot,
                                                      plan.scope.profile());
    if (!opened.has_value()) {
      return Status::refuse(opened.error().refusal());
    }
    qr::sources::StockQuoteReader reader = std::move(opened).value();
    const Status pumped = pump(reader, nbbo);
    if (!pumped.has_value()) {
      return pumped;
    }
    quote_rth_rows = reader.rth_rows();
    quote_groups = reader.group_count();
  }
  {
    auto opened = qr::sources::StockTradeReader::open(plan.scope, kStockTradesRoot);
    if (!opened.has_value()) {
      return Status::refuse(opened.error().refusal());
    }
    qr::sources::StockTradeReader reader = std::move(opened).value();
    const Status pumped = pump(reader, prints);
    if (!pumped.has_value()) {
      return pumped;
    }
    trade_rth_rows = reader.rth_rows();
    trade_groups = reader.group_count();
  }
  {
    auto opened = qr::sources::OptionPrintReader::open(plan.scope, kOptionPrintsRoot);
    if (!opened.has_value()) {
      return Status::refuse(opened.error().refusal());
    }
    qr::sources::OptionPrintReader reader = std::move(opened).value();
    const Status pumped = pump(reader, options_stream);
    if (!pumped.has_value()) {
      return pumped;
    }
    option_rth_rows = reader.rth_rows();
    option_groups = reader.group_count();
  }

  // THE REGISTRY ORACLE, PER SESSION AND FOR FREE (FINAL_PLAN §6 oracle 2): the
  // stock-quote reader's own counts must reproduce the registry row exactly.
  if (quote_rth_rows != plan.scope.session().raw_rth_row_count ||
      quote_groups != plan.scope.session().complete_group_count) {
    return Status::refuse(content("the stock-quote reader did not reproduce the registry's "
                                  "raw_rth_row_count/complete_group_count for this session",
                                  ordinal));
  }

  auto grid = MidpointGrid::build(plan.clock, nbbo.eligible_midpoints());
  if (!grid.has_value()) {
    return Status::refuse(grid.error());
  }
  LocationInputs location_inputs;
  location_inputs.clock = &plan.clock;
  location_inputs.grid = &grid.value();
  location_inputs.eligible_mids = nbbo.eligible_midpoints();
  location_inputs.stock_print_groups = prints.groups();
  location_inputs.option_print_groups = options_stream.groups();
  location_inputs.vwap_notional_prefix = prints.vwap_notional_prefix();
  location_inputs.vwap_size_prefix = prints.vwap_size_prefix();
  const LocationBuilder location(location_inputs);

  const std::array<std::span<const GroupRecord>, kModalityCount> group_tables{
      prints.groups(), nbbo.groups(), options_stream.groups()};
  const std::array<const GroupVectorTable*, kModalityCount> vector_tables{
      &prints.group_vectors(), &nbbo.group_vectors(), &options_stream.group_vectors()};
  std::vector<DirectRawBuilder> direct;
  std::vector<NativeOrderBuilder> native;
  direct.reserve(kModalityCount);
  native.reserve(kModalityCount);
  for (std::size_t index = 0; index < kModalityCount; ++index) {
    const auto modality = static_cast<Modality>(index);
    direct.emplace_back(modality, group_tables[index]);
    native.emplace_back(modality, group_tables[index]);
  }

  HandoffWriter blob(handoff_fd);

  // --- grid_1s [S,4] f4 -----------------------------------------------------
  // DECLARED READING (reported as a STOP question): APPENDIX C4 gives the leaf
  // four columns and card §4 names exactly four quantities at an endpoint — the
  // carried midpoint plus the three grid-audit fields "source age in
  // microseconds", "fresh_in_bin" and "stale_gt_1s". Presence is not a fifth
  // column because a missing endpoint carries midpoint 0, which no valid
  // midpoint can be (the card requires it finite and POSITIVE). The u6 midpoint
  // is rounded to f4 exactly once here, as C4's dtype demands.
  {
    const std::vector<GridPoint>& points = grid.value().points();
    std::vector<float> values(points.size() * 4);
    for (std::size_t index = 0; index < points.size(); ++index) {
      const GridPoint& point = points[index];
      values[index * 4 + 0] = point.present ? static_cast<float>(point.mid_u6) : 0.0F;
      values[index * 4 + 1] = point.present ? static_cast<float>(point.age_micros) : 0.0F;
      values[index * 4 + 2] = point.fresh_in_bin ? 1.0F : 0.0F;
      values[index * 4 + 3] = point.stale_gt_1s ? 1.0F : 0.0F;
    }
    const std::array<std::int64_t, 2> shape{static_cast<std::int64_t>(points.size()), 4};
    const Status written = blob.append_values<float>(kLeafGrid, LeafScope::BOTH_SHARDS,
                                                     NpyDtype::F4, shape, values);
    if (!written.has_value()) {
      return written;
    }
  }

  // --- the per-side blocks --------------------------------------------------
  std::array<std::int64_t, kModalityCount> group_table_rows{};
  std::int64_t candset_total_rows = 0;
  std::int64_t candset_max_rows = 0;
  for (const qr::labels::Side side : {qr::labels::Side::LONG, qr::labels::Side::SHORT}) {
    const std::size_t side_index = side == qr::labels::Side::LONG ? 0U : 1U;
    const std::vector<std::size_t>& rows = plan.rows[side_index];
    const auto row_count = static_cast<std::int64_t>(rows.size());
    const LeafScope scope =
        side == qr::labels::Side::LONG ? LeafScope::LONG_SHARD : LeafScope::SHORT_SHARD;

    std::vector<float> direct_raw(rows.size() * kModalityCount * kDirectColumnCount, 0.0F);
    std::vector<float> locclock(rows.size() * 2 * kLocationValueCount, 0.0F);
    std::vector<std::uint8_t> masks(rows.size() * kMaskColumns, 0U);
    CandidateSetBlock candset;
    std::vector<NativeOrderShard> shards;
    shards.reserve(kModalityCount);
    for (std::size_t index = 0; index < kModalityCount; ++index) {
      shards.emplace_back(static_cast<Modality>(index), group_tables[index],
                          *vector_tables[index]);
    }

    for (std::size_t row = 0; row < rows.size(); ++row) {
      const qr::labels::ActionRow& action = plan.watches.actions[rows[row]];
      DecisionWindow window;
      window.cutoff_ns_a = action.key.decision_ts_ns;
      window.session_open_ns_a = session_start_ns;
      window.side = carrier_side(side);
      window.phase_reference_present =
          plan.roster.phase_reference(action.key.decision_ts_ns, side,
                                      window.phase_reference_ns_a);

      for (std::size_t modality = 0; modality < kModalityCount; ++modality) {
        auto built = direct[modality].build(window);
        if (!built.has_value()) {
          return Status::refuse(built.error());
        }
        const DirectRawRow& direct_row = built.value();
        const std::size_t base = (row * kModalityCount + modality) * kDirectColumnCount;
        for (std::size_t column = 0; column < kDirectColumnCount; ++column) {
          direct_raw[base + column] = static_cast<float>(direct_row.value[column]);
        }
        masks[row * kMaskColumns + 3 + modality] =
            direct_row.value[kDirectFullWindowOffset + kDirectNonempty] != 0.0 ? 1U : 0U;

        auto micro = native[modality].build_micro(window);
        if (!micro.has_value()) {
          return Status::refuse(micro.error());
        }
        auto bins = native[modality].build_bins(window);
        if (!bins.has_value()) {
          return Status::refuse(bins.error());
        }
        const PhaseSplit split = native[modality].split_for(window);
        const auto pushed = shards[modality].push_decision(micro.value(), bins.value(), split);
        if (!pushed.has_value()) {
          return Status::refuse(pushed.error());
        }
      }

      auto location_row = location.build(action.key.decision_ts_ns, carrier_side(side));
      if (!location_row.has_value()) {
        return Status::refuse(location_row.error());
      }
      for (std::size_t index = 0; index < kLocationValueCount; ++index) {
        locclock[row * 2 * kLocationValueCount + index] =
            static_cast<float>(location_row.value().value[index]);
        locclock[row * 2 * kLocationValueCount + kLocationValueCount + index] =
            location_row.value().presence(index) ? 1.0F : 0.0F;
      }

      auto context = plan.roster.candidate_set(action.key.decision_ts_ns, carrier_side(side));
      if (!context.has_value()) {
        return Status::refuse(context.error());
      }
      const auto appended = candset.push_decision(context.value());
      if (!appended.has_value()) {
        return Status::refuse(appended.error());
      }

      for (std::size_t stage = 0; stage < qr::labels::kWatchStageCount; ++stage) {
        masks[row * kMaskColumns + stage] =
            ((action.stage_mask >> stage) & 1U) != 0U ? 1U : 0U;
      }
      masks[row * kMaskColumns + 6] = 1U;  // legal_enter
    }

    // --- this side's leaves ------------------------------------------------
    {
      const std::array<std::int64_t, 3> shape{row_count, static_cast<std::int64_t>(kModalityCount),
                                              static_cast<std::int64_t>(kDirectColumnCount)};
      Status written = blob.append_values<float>(kLeafDirectRaw, scope, NpyDtype::F4, shape,
                                                 direct_raw);
      if (!written.has_value()) {
        return written;
      }
      const std::array<std::int64_t, 2> loc_shape{
          row_count, static_cast<std::int64_t>(2 * kLocationValueCount)};
      written = blob.append_values<float>(kLeafLocClock, scope, NpyDtype::F4, loc_shape, locclock);
      if (!written.has_value()) {
        return written;
      }
      const std::array<std::int64_t, 2> mask_shape{row_count,
                                                   static_cast<std::int64_t>(kMaskColumns)};
      written = blob.append_values<std::uint8_t>(kLeafMasks, scope, NpyDtype::U1, mask_shape,
                                                 masks);
      if (!written.has_value()) {
        return written;
      }
    }
    {
      // The RAGGED candidate set (orchestrator ruling, candidate_set.hpp): CSR
      // values `[R,24] f4` plus `[N+1] i4` offsets, never a 64-row cap.
      std::vector<float> values(candset.values().size());
      for (std::size_t index = 0; index < candset.values().size(); ++index) {
        values[index] = static_cast<float>(candset.values()[index]);
      }
      const auto total = static_cast<std::int64_t>(candset.total_rows());
      const std::array<std::int64_t, 2> shape{
          total, static_cast<std::int64_t>(qr::carriers::kCandidateSetFieldCount)};
      Status written = blob.append_values<float>(kLeafCandSet, scope, NpyDtype::F4, shape, values);
      if (!written.has_value()) {
        return written;
      }
      std::vector<std::int32_t> offsets(candset.offsets().size());
      for (std::size_t index = 0; index < candset.offsets().size(); ++index) {
        offsets[index] = static_cast<std::int32_t>(candset.offsets()[index]);
      }
      const std::array<std::int64_t, 1> offset_shape{static_cast<std::int64_t>(offsets.size())};
      written = blob.append_values<std::int32_t>(kLeafCandSetOffsets, scope, NpyDtype::I4,
                                                 offset_shape, offsets);
      if (!written.has_value()) {
        return written;
      }
      candset_total_rows += total;
      candset_max_rows = std::max(candset_max_rows, static_cast<std::int64_t>(candset.max_rows()));
    }
    for (std::size_t modality = 0; modality < kModalityCount; ++modality) {
      const NativeOrderShard& shard = shards[modality];
      group_table_rows[modality] = shard.groups();
      const auto per_side = {NativeLeaf::RECENT128, NativeLeaf::PHASE_SPLIT,
                             NativeLeaf::BINS_INDEX};
      for (const NativeLeaf leaf : per_side) {
        const std::vector<std::int64_t> shape = shard.leaf_shape(leaf);
        const std::span<const std::int32_t> values =
            leaf == NativeLeaf::RECENT128
                ? shard.recent128()
                : (leaf == NativeLeaf::PHASE_SPLIT ? shard.phase_split() : shard.bins_index());
        const Status written = blob.append_values<std::int32_t>(
            native_leaf_name(leaf, shard.modality()), scope, NpyDtype::I4, shape, values);
        if (!written.has_value()) {
          return written;
        }
      }
      if (side != qr::labels::Side::LONG) {
        continue;
      }
      // SIDE-NEUTRAL STORAGE (native_emit.hpp): the group table, its timestamps
      // and the orientation table are written ONCE, into the LONG shard.
      Status written = blob.append_values<float>(
          native_leaf_name(NativeLeaf::GROUPS, shard.modality()), LeafScope::SESSION_LONG_SHARD,
          NpyDtype::F4, shard.leaf_shape(NativeLeaf::GROUPS), shard.group_values());
      if (!written.has_value()) {
        return written;
      }
      written = blob.append_values<std::int64_t>(
          native_leaf_name(NativeLeaf::GROUP_TS, shard.modality()), LeafScope::SESSION_LONG_SHARD,
          NpyDtype::I8, shard.leaf_shape(NativeLeaf::GROUP_TS), shard.group_ts());
      if (!written.has_value()) {
        return written;
      }
      written = blob.append_values<std::int32_t>(
          native_leaf_name(NativeLeaf::ORIENTATION, shard.modality()),
          LeafScope::SESSION_LONG_SHARD, NpyDtype::I4,
          shard.leaf_shape(NativeLeaf::ORIENTATION), shard.orientation());
      if (!written.has_value()) {
        return written;
      }
    }
  }

  // --- the constructor phase's own census ----------------------------------
  Receipt census;
  census.add_text("builder", "schema", "qr_campaign_builder_v1");
  census.add("builder", "ordinal", ordinal);
  census.add("stock_nbbo", "reader_rth_rows", quote_rth_rows);
  census.add("stock_nbbo", "reader_group_count", quote_groups);
  census.add("stock_nbbo", "carrier_group_count", static_cast<std::int64_t>(nbbo.groups().size()));
  census.add("stock_nbbo", "eligible_midpoint_groups",
             static_cast<std::int64_t>(nbbo.eligible_midpoints().size()));
  census.add("stock_print", "reader_rth_rows", trade_rth_rows);
  census.add("stock_print", "reader_group_count", trade_groups);
  census.add("stock_print", "carrier_group_count",
             static_cast<std::int64_t>(prints.groups().size()));
  census.add("option_print", "reader_rth_rows", option_rth_rows);
  census.add("option_print", "reader_group_count", option_groups);
  census.add("option_print", "carrier_group_count",
             static_cast<std::int64_t>(options_stream.groups().size()));
  census.add("option_print", "directional_eligible_prints",
             options_stream.directional_eligible_prints());
  census.add("registry_oracle", "raw_rth_row_count", plan.scope.session().raw_rth_row_count);
  census.add("registry_oracle", "complete_group_count",
             plan.scope.session().complete_group_count);
  census.add("registry_oracle", "reproduced", 1);
  const MidpointGrid::Census grid_census = grid.value().census();
  census.add("grid_1s", "endpoints", grid_census.endpoints);
  census.add("grid_1s", "present", grid_census.present);
  census.add("grid_1s", "fresh_in_bin", grid_census.fresh_in_bin);
  census.add("grid_1s", "stale_gt_1s", grid_census.stale_gt_1s);
  census.add("grid_1s", "first_present_endpoint", grid_census.first_present_endpoint);
  for (std::size_t modality = 0; modality < kModalityCount; ++modality) {
    census.add(std::string("groups.") + modality_leaf_suffix(static_cast<Modality>(modality)),
               "rows", group_table_rows[modality]);
    census.add(std::string("groups.") + modality_leaf_suffix(static_cast<Modality>(modality)),
               "dim", static_cast<std::int64_t>(vector_tables[modality]->dim()));
  }
  census.add("candidate_set", "csr_total_rows", candset_total_rows);
  census.add("candidate_set", "max_rows_per_decision", candset_max_rows);
  // The builder's census travels through the HANDOFF, not through a file: a
  // file would put a fourth path — one that carries the run root — inside the
  // fd census the manifest pins, and two lawful runs would stop being byte
  // identical for a reason that has nothing to do with the science.
  {
    const std::string text = census.render();
    const std::array<std::int64_t, 1> shape{static_cast<std::int64_t>(text.size())};
    const Status handed = blob.append("builder_receipt", LeafScope::HANDOFF_ONLY, NpyDtype::U1,
                                      shape, text.data(),
                                      static_cast<std::uint64_t>(text.size()));
    if (!handed.has_value()) {
      return handed;
    }
  }
  const Status finished = blob.finish();
  if (!finished.has_value()) {
    return finished;
  }

  // --- the fd census: THE PROOF the constructor phase never opened truth ----
  Status clean = qr::emit::FdCensus::instance().verify_no_truth_opened();
  if (!clean.has_value()) {
    return clean;
  }
  clean = qr::emit::FdCensus::instance().verify_open_fds_are_censused();
  if (!clean.has_value()) {
    return clean;
  }
  std::error_code code;
  std::filesystem::create_directories(layout.builder_census(ordinal).parent_path(), code);
  std::filesystem::remove(layout.builder_census(ordinal), code);
  std::filesystem::remove(layout.truth_receipt(ordinal), code);
  clean = qr::emit::FdCensus::instance().write_census_tsv(layout.builder_census(ordinal));
  if (!clean.has_value()) {
    return clean;
  }
  return qr::emit::FdCensus::instance().write_truth_open_receipt_tsv(
      layout.truth_receipt(ordinal));
}

// ---------------------------------------------------------------------------
// The emit phase (parent process)
// ---------------------------------------------------------------------------

[[nodiscard]] bool leaf_belongs(LeafScope scope, qr::labels::Side side) {
  switch (scope) {
    case LeafScope::BOTH_SHARDS:
      return true;
    case LeafScope::SESSION_LONG_SHARD:
    case LeafScope::LONG_SHARD:
      return side == qr::labels::Side::LONG;
    case LeafScope::SHORT_SHARD:
      return side == qr::labels::Side::SHORT;
    case LeafScope::HANDOFF_ONLY:
      return false;
  }
  return false;
}

/// Lifts the constructor phase's census text out of the handoff and publishes
/// it under the run's receipts.
[[nodiscard]] Status publish_builder_receipt(const RunLayout& layout, std::int64_t ordinal,
                                             const HandoffReader& blob) {
  for (const HandoffLeaf& leaf : blob.leaves()) {
    if (leaf.name != "builder_receipt") {
      continue;
    }
    const std::string_view text(static_cast<const char*>(blob.payload(leaf)),
                                static_cast<std::size_t>(leaf.bytes));
    return write_text_atomic(layout.builder_receipt(ordinal), text);
  }
  return Status::refuse(content("the handoff carries no builder census", ordinal));
}

[[nodiscard]] Status write_handoff_leaf(qr::emit::ShardWriter& writer, const HandoffReader& blob,
                                        const HandoffLeaf& leaf) {
  auto elements = blob.elements(leaf);
  if (!elements.has_value()) {
    return Status::refuse(elements.error());
  }
  const auto count = static_cast<std::size_t>(elements.value());
  const void* payload = blob.payload(leaf);
  switch (leaf.dtype) {
    case NpyDtype::I8:
      return writer.write_leaf<std::int64_t>(
          qr::emit::Section::FEATURES, leaf.name, leaf.dtype, leaf.shape,
          std::span<const std::int64_t>(static_cast<const std::int64_t*>(payload), count));
    case NpyDtype::I4:
      return writer.write_leaf<std::int32_t>(
          qr::emit::Section::FEATURES, leaf.name, leaf.dtype, leaf.shape,
          std::span<const std::int32_t>(static_cast<const std::int32_t*>(payload), count));
    case NpyDtype::F4:
      return writer.write_leaf<float>(
          qr::emit::Section::FEATURES, leaf.name, leaf.dtype, leaf.shape,
          std::span<const float>(static_cast<const float*>(payload), count));
    case NpyDtype::U1:
      return writer.write_leaf<std::uint8_t>(
          qr::emit::Section::FEATURES, leaf.name, leaf.dtype, leaf.shape,
          std::span<const std::uint8_t>(static_cast<const std::uint8_t*>(payload), count));
  }
  return Status::refuse(content("a handoff leaf carries an unknown dtype"));
}

}  // namespace

Status build_session(const RunLayout& layout, const SessionTask& task,
                     const BuildOptions& options) {
  const std::int64_t ordinal = task.ordinal;
  Status wall = refuse_unless_in_scope(ordinal);
  if (!wall.has_value()) {
    return wall;
  }
  if (!task.any_work()) {
    return ok_status();
  }

  auto planned = plan_session(layout, ordinal);
  if (!planned.has_value()) {
    return Status::refuse(planned.error());
  }
  const SessionPlan& plan = planned.value();

  // The receipt directories exist BEFORE the fork, so the tagged child creates
  // no directory the untagged parent has not already sanctioned.
  std::error_code code;
  for (const std::filesystem::path& directory :
       {layout.builder_receipt(ordinal).parent_path(),
        layout.builder_census(ordinal).parent_path(),
        layout.session_receipt(ordinal).parent_path(),
        layout.session_timing(ordinal).parent_path()}) {
    std::filesystem::create_directories(directory, code);
    if (code) {
      return Status::refuse(io("cannot create a receipt directory", code.value()));
    }
  }

  auto handoff = create_handoff_fd();
  if (!handoff.has_value()) {
    return Status::refuse(handoff.error());
  }
  const int handoff_fd = handoff.value();

  const ::pid_t child = ::fork();
  if (child < 0) {
    ::close(handoff_fd);
    return Status::refuse(io("cannot fork the feature-builder phase"));
  }
  if (child == 0) {
    // THE TAGGED CONSTRUCTOR PHASE, in its own process (APPENDIX C4).
    const Status built = build_features(handoff_fd, layout, plan);
    if (!built.has_value()) {
      std::fprintf(stderr, "REFUSED (feature builder, session %lld): %s\n",
                   static_cast<long long>(ordinal), built.error().message().c_str());
      ::_exit(11);
    }
    ::_exit(0);
  }

  // --- the label phase, running MEANWHILE ----------------------------------
  Status label_status = ok_status();
  std::vector<qr::labels::LabelRow> labels;
  qr::labels::LabelCensus label_census;
  std::int64_t tape_marks = 0;
  std::int64_t tape_groups_seen = 0;
  {
    auto opened = qr::sources::StockQuoteReader::open(plan.scope, kStockQuotesRoot,
                                                      plan.scope.profile());
    if (!opened.has_value()) {
      label_status = Status::refuse(opened.error().refusal());
    } else {
      qr::sources::StockQuoteReader reader = std::move(opened).value();
      auto tape = qr::labels::build_execution_tape(reader, plan.scope);
      if (!tape.has_value()) {
        label_status = Status::refuse(tape.error().refusal());
      } else {
        qr::labels::SessionLabelIndex index =
            qr::labels::SessionLabelIndex::build(std::move(tape).value());
        tape_marks = index.tape().size();
        tape_groups_seen = index.tape().census.groups_seen;
        auto labelled = qr::labels::label_session(index, plan.watches.actions);
        if (!labelled.has_value()) {
          label_status = Status::refuse(labelled.error());
        } else {
          labels = std::move(labelled).value();
          for (const qr::labels::LabelRow& row : labels) {
            label_census.observe(row);
          }
        }
      }
    }
  }

  int child_status = 0;
  while (::waitpid(child, &child_status, 0) < 0) {
    if (errno != EINTR) {
      ::close(handoff_fd);
      return Status::refuse(io("cannot wait for the feature-builder phase"));
    }
  }
  if (!label_status.has_value()) {
    ::close(handoff_fd);
    return label_status;
  }
  if (!WIFEXITED(child_status) || WEXITSTATUS(child_status) != 0) {
    ::close(handoff_fd);
    return Status::refuse(content("the feature-builder phase did not finish clean",
                                  WIFEXITED(child_status) ? WEXITSTATUS(child_status) : -1));
  }

  auto blob = HandoffReader::map(handoff_fd);
  ::close(handoff_fd);
  if (!blob.has_value()) {
    return Status::refuse(blob.error());
  }
  const Status builder_published = publish_builder_receipt(layout, ordinal, blob.value());
  if (!builder_published.has_value()) {
    return builder_published;
  }

  // --- the manifest's pinned sources and census pointers --------------------
  std::vector<qr::emit::SourceRow> sources;
  const std::array<std::pair<std::string_view, std::string_view>, 3> payload_roots{
      std::pair<std::string_view, std::string_view>{"stock_quotes", kStockQuotesRoot},
      std::pair<std::string_view, std::string_view>{"stock_trades", kStockTradesRoot},
      std::pair<std::string_view, std::string_view>{"option_prints", kOptionPrintsRoot}};
  for (const auto& source : payload_roots) {
    const std::filesystem::path path = plan.scope.source_path(source.second);
    auto digest = qr::candidates::sha256_file_hex(path.string());
    if (!digest.has_value()) {
      return Status::refuse(digest.error());
    }
    sources.push_back(
        qr::emit::SourceRow{std::string(source.first), digest.value(), path.string()});
  }
  // RUN-RELATIVE, deliberately: the two runs of a campaign publish into two
  // different roots, and an absolute path here would make the manifests of
  // byte-identical tapes differ for no scientific reason. Everything OUTSIDE
  // the run (the payload, the card, the dialect census) keeps its absolute
  // path, because that path is the same fact in both runs.
  const auto run_relative = [&layout](const std::filesystem::path& path) {
    return path.lexically_relative(layout.root()).generic_string();
  };
  sources.push_back(qr::emit::SourceRow{"candidate_roster", plan.roster.sha256(),
                                        run_relative(layout.roster_tsv(ordinal))});
  std::vector<qr::emit::CensusRow> census_rows{
      qr::emit::CensusRow{"task_card_v4", std::string(kCardSha256), std::string(kCardPath)},
      qr::emit::CensusRow{"dialect_census", kDialectCensusSha, kDialectCensusPath},
      qr::emit::CensusRow{"builder_fd_census", "",
                          run_relative(layout.builder_census(ordinal))}};
  {
    auto text = read_text(layout.builder_census(ordinal));
    if (!text.has_value()) {
      return Status::refuse(text.error());
    }
    census_rows.back().sha256 = sha256_hex(text.value());
  }

  Receipt receipt;
  receipt.add_text("session", "schema", "qr_campaign_session_v1");
  receipt.add("session", "ordinal", ordinal);
  receipt.add_text("session", "day", plan.scope.day());
  receipt.add_text("session", "build_id", options.build_id);
  receipt.add_text("roster", "sha256", plan.roster.sha256());
  receipt.add("roster", "rows", static_cast<std::int64_t>(plan.roster.rows().size()));
  receipt.add("roster", "long", plan.roster.long_rows());
  receipt.add("roster", "short", plan.roster.short_rows());
  receipt.add("roster", "side_unavailable", plan.roster.side_unavailable_rows());
  receipt.add("decision_roster", "size", plan.decision_roster_size);
  receipt.add("decision_roster", "registered_seconds", plan.decision_clock.second_count());
  receipt.add("decision_roster", "visibilities_off_second", plan.decision_roster_off_second);
  receipt.add("decision_roster", "visibilities_on_second", plan.decision_roster_on_second);
  receipt.add("watches", "built", plan.watches.census.watches_built);
  receipt.add("watches", "clock_unavailable", plan.watches.census.watches_clock_unavailable);
  for (std::size_t stage = 0; stage < qr::labels::kWatchStageCount; ++stage) {
    const char* name = qr::labels::watch_stage_name(static_cast<qr::labels::WatchStage>(stage));
    receipt.add("watches.built", name, plan.watches.census.per_stage_built[stage]);
    receipt.add("watches.clock_unavailable", name,
                plan.watches.census.per_stage_clock_unavailable[stage]);
  }
  receipt.add("watches", "converged", plan.watches.census.converged_watches);
  receipt.add("actions", "rows", plan.watches.census.actions);
  receipt.add("actions", "long", plan.watches.census.actions_long);
  receipt.add("actions", "short", plan.watches.census.actions_short);
  receipt.add("execution_tape", "lawful_marks", tape_marks);
  receipt.add("execution_tape", "groups_seen", tape_groups_seen);
  receipt.add("label_rows", "rows", label_census.rows);
  for (std::size_t state = 0; state < label_census.per_state.size(); ++state) {
    receipt.add("label_state",
                qr::replay::label_state_name(static_cast<qr::labels::LabelState>(state)),
                label_census.per_state[state]);
  }
  for (std::size_t horizon = 0; horizon < qr::labels::kHorizonCount; ++horizon) {
    const std::string name = qr::labels::kHorizonMinutes[horizon] >= 0
                                 ? std::to_string(qr::labels::kHorizonMinutes[horizon]) + "m"
                                 : std::string("close");
    receipt.add("stop_hit", name, label_census.stop_hit[horizon]);
  }
  for (std::size_t state = 0; state < qr::labels::kBarrierStateCount; ++state) {
    receipt.add("barrier_state",
                qr::labels::barrier_state_name(static_cast<qr::labels::BarrierState>(state)),
                label_census.barrier_state[state]);
  }
  receipt.add("labels", "gap_through_rows", label_census.gap_through_rows);
  receipt.add("labels", "certificate_positive_rows", label_census.certificate_positive_rows);
  {
    auto builder_rows = parse_receipt(layout.builder_receipt(ordinal));
    if (!builder_rows.has_value()) {
      return Status::refuse(builder_rows.error());
    }
    for (const ReceiptRow& row : builder_rows.value()) {
      receipt.add_text("builder." + row.section, row.metric, row.value);
    }
  }

  // --- one publish per side -------------------------------------------------
  for (const qr::labels::Side side : {qr::labels::Side::LONG, qr::labels::Side::SHORT}) {
    const std::size_t side_index = side == qr::labels::Side::LONG ? 0U : 1U;
    const std::vector<std::size_t>& rows = plan.rows[side_index];
    const auto row_count = static_cast<std::int64_t>(rows.size());
    const char letter = qr::emit::side_letter(emit_side(side));
    const std::string section = std::string("shard.") + letter;

    if (!task.build(emit_side(side))) {
      // Resume: the shard is already published, so its manifest sha is READ
      // rather than rewritten — the ledger still carries a complete row.
      const auto dir = qr::emit::c4_shard_dir(layout.tapes(), ordinal, emit_side(side));
      if (!dir.has_value()) {
        return Status::refuse(dir.error());
      }
      auto manifest = read_text(dir.value() / qr::emit::kManifestName);
      if (!manifest.has_value()) {
        return Status::refuse(manifest.error());
      }
      receipt.add_text(section, "manifest_sha256", sha256_hex(manifest.value()));
      receipt.add_text(section, "state", "ALREADY_PUBLISHED");
      receipt.add(section, "rows", row_count);
      // A skipped shard's leaf and byte counts are READ from the manifest it
      // published, so the campaign ledger's totals are the same numbers whether
      // a run built the shard or resumed onto it.
      const auto meta_number = [&manifest](std::string_view key) -> std::int64_t {
        const std::string needle = "meta\t" + std::string(key) + "\t";
        const std::size_t at = manifest.value().find(needle);
        if (at == std::string::npos) {
          return -1;
        }
        return std::strtoll(manifest.value().c_str() + at + needle.size(), nullptr, 10);
      };
      receipt.add(section, "leaves", meta_number("leaf_count"));
      receipt.add(section, "bytes", meta_number("total_leaf_bytes"));
      continue;
    }

    auto emitter = ShardEmitter::open(layout, ordinal, emit_side(side), options.build_id, sources,
                                      census_rows);
    if (!emitter.has_value()) {
      return Status::refuse(emitter.error());
    }
    qr::emit::ShardWriter& writer = emitter.value()->writer();

    for (const HandoffLeaf& leaf : blob.value().leaves()) {
      if (!leaf_belongs(leaf.scope, side)) {
        continue;
      }
      const Status written = write_handoff_leaf(writer, blob.value(), leaf);
      if (!written.has_value()) {
        return written;
      }
    }

    // THE JOIN KEY, written into BOTH sections from ONE array: APPENDIX C4
    // declares `keys` in features/ and truth/, and the publish-time digest
    // collision refusal exempts exactly that one leaf name.
    std::vector<std::int64_t> keys(rows.size() * 4);
    std::vector<std::int64_t> menu_net(rows.size() * qr::labels::kHorizonCount);
    std::vector<std::int64_t> menu_mae(rows.size() * qr::labels::kHorizonCount);
    std::vector<std::int64_t> menu_exit(rows.size() * qr::labels::kHorizonCount);
    std::vector<std::uint8_t> stop_hit(rows.size() * qr::labels::kHorizonCount);
    std::vector<std::int64_t> cert_net(rows.size());
    std::vector<std::int64_t> cert_mae(rows.size());
    std::vector<std::uint8_t> barrier(rows.size());
    std::vector<std::uint8_t> label_state(rows.size());
    std::vector<std::int64_t> entry_ts(rows.size());
    std::vector<std::int64_t> gap_through(rows.size());
    std::vector<std::int64_t> cost_charged(rows.size());
    for (std::size_t row = 0; row < rows.size(); ++row) {
      const qr::labels::LabelRow& label = labels[rows[row]];
      const std::array<std::int64_t, 4> key = label.menu.key.to_array();
      if (!(label.menu.key == plan.watches.actions[rows[row]].key)) {
        return Status::refuse(content("a label row's key is not its action row's key", ordinal));
      }
      for (std::size_t field = 0; field < 4; ++field) {
        keys[row * 4 + field] = key[field];
      }
      for (std::size_t horizon = 0; horizon < qr::labels::kHorizonCount; ++horizon) {
        const std::size_t at = row * qr::labels::kHorizonCount + horizon;
        menu_net[at] = label.menu.menu_net_cent[horizon];
        menu_mae[at] = label.menu.menu_mae_cent[horizon];
        menu_exit[at] = label.menu.menu_exit_ts[horizon];
        stop_hit[at] = label.menu.stop_hit[horizon];
      }
      cert_net[row] = label.certificate_net_cent;
      cert_mae[row] = label.certificate_mae_cent;
      barrier[row] = static_cast<std::uint8_t>(label.barrier.three_class);
      label_state[row] = static_cast<std::uint8_t>(label.menu.state);
      entry_ts[row] = label.menu.entry_ts_ns;
      gap_through[row] = label.menu.gap_through_cent;
      cost_charged[row] = label.menu.cost_charged_cent;
    }

    const std::array<std::int64_t, 2> key_shape{row_count, 4};
    const std::array<std::int64_t, 2> menu_shape{row_count,
                                                 static_cast<std::int64_t>(
                                                     qr::labels::kHorizonCount)};
    const std::array<std::int64_t, 1> scalar_shape{row_count};
    Status written = writer.write_leaf<std::int64_t>(qr::emit::Section::FEATURES, kLeafKeys,
                                                     NpyDtype::I8, key_shape, keys);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::int64_t>(qr::emit::Section::TRUTH, kLeafKeys, NpyDtype::I8,
                                              key_shape, keys);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::int64_t>(qr::emit::Section::TRUTH, "menu_net_cent",
                                              NpyDtype::I8, menu_shape, menu_net);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::int64_t>(qr::emit::Section::TRUTH, "menu_mae_cent",
                                              NpyDtype::I8, menu_shape, menu_mae);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::int64_t>(qr::emit::Section::TRUTH, "menu_exit_ts",
                                              NpyDtype::I8, menu_shape, menu_exit);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::uint8_t>(qr::emit::Section::TRUTH, "stop_hit", NpyDtype::U1,
                                              menu_shape, stop_hit);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::int64_t>(qr::emit::Section::TRUTH, "cert_net_cent",
                                              NpyDtype::I8, scalar_shape, cert_net);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::int64_t>(qr::emit::Section::TRUTH, "cert_mae_cent",
                                              NpyDtype::I8, scalar_shape, cert_mae);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::uint8_t>(qr::emit::Section::TRUTH, "barrier", NpyDtype::U1,
                                              scalar_shape, barrier);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::uint8_t>(qr::emit::Section::TRUTH, "label_state",
                                              NpyDtype::U1, scalar_shape, label_state);
    if (!written.has_value()) {
      return written;
    }
    // ADDITIVE, DECLARED (reported as a STOP question): the three columns the
    // FROZEN replay struct reads and C4's sketch does not list — `entry_ts_ns`
    // (card §3's fill instant), `gap_through_cent` (card §6's breach panel is
    // `stop_hit[h] AND gap_through_cent>0`, and the MAE test is the degenerate
    // statistic that paragraph forbids) and `cost_charged_cent` (the
    // cost-once invariant `replay()` refuses without). No C4 leaf is removed,
    // renamed or reshaped; without these three the published corpus cannot feed
    // the R5 replay and would have to be rebuilt.
    written = writer.write_leaf<std::int64_t>(qr::emit::Section::TRUTH, "entry_ts_ns",
                                              NpyDtype::I8, scalar_shape, entry_ts);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::int64_t>(qr::emit::Section::TRUTH, "gap_through_cent",
                                              NpyDtype::I8, scalar_shape, gap_through);
    if (!written.has_value()) {
      return written;
    }
    written = writer.write_leaf<std::int64_t>(qr::emit::Section::TRUTH, "cost_charged_cent",
                                              NpyDtype::I8, scalar_shape, cost_charged);
    if (!written.has_value()) {
      return written;
    }

    auto published = emitter.value()->publish();
    if (!published.has_value()) {
      return Status::refuse(published.error());
    }
    receipt.add_text(section, "manifest_sha256", published.value().manifest_sha256);
    receipt.add_text(section, "state", "PUBLISHED");
    receipt.add(section, "rows", row_count);
    receipt.add(section, "leaves", published.value().leaf_count);
    receipt.add(section, "bytes", published.value().total_leaf_bytes);
  }

  return receipt.write(layout.session_receipt(ordinal));
}

}  // namespace qr::campaign
