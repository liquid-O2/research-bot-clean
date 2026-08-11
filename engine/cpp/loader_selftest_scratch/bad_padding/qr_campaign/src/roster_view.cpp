#include "qr_campaign/roster_view.hpp"

#include <algorithm>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <utility>

#include "qr_campaign/driver.hpp"

namespace qr::campaign {
namespace {

constexpr const char* kSite = "qr_campaign::roster_view";
constexpr const char* kHeader =
    "session_ordinal\tday\tcandidate_id\tpolicy_name\treversal_bps\tvisible_ts_ns\t"
    "member_count\tcandidate_physical_key\tside\tcause\tenter_forbidden";

[[nodiscard]] Refusal content(const char* detail, std::int64_t context = 0) {
  return Refusal(RefusalCode::CONTENT_MISMATCH, kSite, detail, context);
}

}  // namespace

Expected<RosterView, Refusal> RosterView::load(const std::filesystem::path& path,
                                               std::int64_t ordinal) {
  using Result = Expected<RosterView, Refusal>;
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    return Result::refuse(Refusal(RefusalCode::IO, kSite, "cannot open the sealed roster"));
  }
  std::string text((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  input.close();

  RosterView view;
  view.sha256_ = sha256_hex(text);

  std::istringstream stream(text);
  std::string line;
  if (!std::getline(stream, line) || line != kHeader) {
    return Result::refuse(content("the roster header is not the WP6 authority's own header"));
  }
  while (std::getline(stream, line)) {
    if (line.empty()) {
      continue;
    }
    std::vector<std::string> field;
    field.reserve(11);
    std::string cell;
    std::istringstream row(line);
    while (std::getline(row, cell, '\t')) {
      field.push_back(std::move(cell));
      cell.clear();
    }
    if (field.size() != 11) {
      return Result::refuse(content("a roster row does not carry the authority's eleven fields",
                                    static_cast<std::int64_t>(field.size())));
    }
    if (std::strtoll(field[0].c_str(), nullptr, 10) != ordinal) {
      return Result::refuse(content("the roster carries a session other than the requested one",
                                    ordinal));
    }
    if (view.day_.empty()) {
      view.day_ = field[1];
    } else if (view.day_ != field[1]) {
      return Result::refuse(content("the roster carries two different days"));
    }
    RosterRow record;
    record.candidate_id = field[2];
    record.policy_name = field[3];
    record.reversal_bps = std::strtoull(field[4].c_str(), nullptr, 10);
    record.visible_ts_ns = std::strtoll(field[5].c_str(), nullptr, 10);
    record.member_count = std::strtoull(field[6].c_str(), nullptr, 10);
    record.candidate_physical_key = field[7];
    if (field[8] == "LONG") {
      record.side_available = true;
      record.side = qr::labels::Side::LONG;
      ++view.long_rows_;
    } else if (field[8] == "SHORT") {
      record.side_available = true;
      record.side = qr::labels::Side::SHORT;
      ++view.short_rows_;
    } else if (field[8] == "SIDE_UNAVAILABLE") {
      ++view.side_unavailable_;
    } else {
      return Result::refuse(content("a roster row carries an unknown side state"));
    }
    record.mixed_members = field[9] == "MIXED_MEMBER_SIDE";

    // EVERY admitted primitive's visibility joins the ordinal roster (CC-007),
    // side-resolved or not.
    view.admitted_visibilities_.push_back(record.visible_ts_ns);
    if (record.side_available) {
      qr::labels::WatchCandidate candidate;
      candidate.candidate_id = record.candidate_id;
      candidate.candidate_physical_key = record.candidate_physical_key;
      candidate.policy_name = record.policy_name;
      candidate.reversal_bps = record.reversal_bps;
      candidate.member_count = record.member_count;
      candidate.visible_ts_ns = record.visible_ts_ns;
      candidate.side = record.side;
      view.watch_candidates_.push_back(std::move(candidate));
    }
    view.rows_.push_back(std::move(record));
  }
  if (view.rows_.empty()) {
    return Result::refuse(content("the roster is empty", ordinal));
  }

  view.by_visibility_ = view.rows_;
  std::sort(view.by_visibility_.begin(), view.by_visibility_.end(),
            [](const RosterRow& left, const RosterRow& right) {
              if (left.visible_ts_ns != right.visible_ts_ns) {
                return left.visible_ts_ns < right.visible_ts_ns;
              }
              return left.candidate_id < right.candidate_id;
            });
  return Result(std::move(view));
}

Expected<std::vector<qr::carriers::CandidateSetRow>, Refusal> RosterView::candidate_set(
    std::int64_t cutoff_ns, qr::carriers::Side side) const {
  using Result = Expected<std::vector<qr::carriers::CandidateSetRow>, Refusal>;
  std::vector<qr::carriers::CandidateSetRow> out;
  for (const RosterRow& row : by_visibility_) {
    if (row.visible_ts_ns >= cutoff_ns) {
      break;  // by_visibility_ is ascending: nothing later can qualify
    }
    if (cutoff_ns - row.visible_ts_ns > kContextHorizonNs) {
      continue;
    }
    qr::carriers::VisibleCandidate candidate;
    candidate.policy_index = qr::carriers::policy_index_of(row.policy_name);
    candidate.reversal_bps = static_cast<std::int64_t>(row.reversal_bps);
    candidate.member_count = static_cast<std::int64_t>(row.member_count);
    candidate.visible_ts_ns_a = row.visible_ts_ns;
    if (!row.side_available) {
      candidate.relation = row.mixed_members ? qr::carriers::CandidateRelation::MIXED
                                             : qr::carriers::CandidateRelation::UNAVAILABLE;
    } else {
      const qr::carriers::Side row_side = row.side == qr::labels::Side::LONG
                                              ? qr::carriers::Side::LONG
                                              : qr::carriers::Side::SHORT;
      candidate.relation = row_side == side ? qr::carriers::CandidateRelation::OWN
                                            : qr::carriers::CandidateRelation::OPPOSITE;
    }
    auto encoded = qr::carriers::build_candidate_set_row(candidate, cutoff_ns);
    if (!encoded.has_value()) {
      return Result::refuse(encoded.error());
    }
    out.push_back(encoded.value());
  }
  return Result(std::move(out));
}

bool RosterView::phase_reference(std::int64_t cutoff_ns, qr::labels::Side side,
                                 std::int64_t& reference_ns) const {
  bool found = false;
  for (const RosterRow& row : by_visibility_) {
    if (row.visible_ts_ns >= cutoff_ns) {
      break;
    }
    if (!row.side_available || row.side != side) {
      continue;
    }
    if (cutoff_ns - row.visible_ts_ns > kContextHorizonNs) {
      continue;
    }
    reference_ns = row.visible_ts_ns;
    found = true;
  }
  return found;
}

}  // namespace qr::campaign
