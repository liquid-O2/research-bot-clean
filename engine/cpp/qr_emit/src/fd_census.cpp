// qr_emit/fd_census.cpp — the census state, the door, and the two verification
// legs (see fd_census.hpp for what each leg does and does not prove).
#include "qr_emit/fd_census.hpp"

#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

#include "io_util.hpp"

namespace qr::emit {
namespace {

using internal::config_refusal;
using internal::decimal;
using internal::io_refusal;
using internal::write_whole_file;

/// Non-truth records are capped so a long-running process cannot be made to
/// exhaust memory through its own file access; TRUTH records are NEVER capped,
/// because they are the proof this census exists to produce.
constexpr std::size_t kMaxNonTruthRecords = 1U << 20;

struct CensusState {
  std::mutex mutex;
  ProcessRole role = ProcessRole::UNSET;
  bool recording = false;
  std::uint64_t sequence = 0;
  std::uint64_t opens_seen = 0;
  std::uint64_t non_truth_dropped = 0;
  std::vector<OpenRecord> records;
  std::vector<std::string> truth_allowlist;              // sorted, by leaf basename
  std::vector<std::pair<int, std::string>> preexisting;  // sorted, fd -> target at begin()
};

/// Every descriptor this process currently holds, as (number, readlink target).
/// Taken at begin() so the /proc sweep can tell "opened before the census
/// existed" from "opened behind the census's back": a descriptor is excused
/// only when BOTH its number and its target are unchanged since begin().
std::vector<std::pair<int, std::string>> snapshot_open_fds() {
  const CensusInternalScope scope;
  std::vector<std::pair<int, std::string>> out;
  std::error_code code;
  std::filesystem::directory_iterator entries("/proc/self/fd", code);
  if (code) {
    return out;
  }
  for (const std::filesystem::directory_entry& entry : entries) {
    const std::string name = entry.path().filename().string();
    int value = 0;
    bool numeric = !name.empty();
    for (const char character : name) {
      if (character < '0' || character > '9') {
        numeric = false;
        break;
      }
      value = value * 10 + (character - '0');
    }
    if (!numeric) {
      continue;
    }
    char target[4096];
    const ssize_t length =
        ::readlink(entry.path().c_str(), target, sizeof(target) - 1);
    if (length <= 0) {
      continue;
    }
    out.emplace_back(value, std::string(target, static_cast<std::size_t>(length)));
  }
  std::sort(out.begin(), out.end());
  return out;
}

/// Function-local static: constructed on first use, which is the only shape
/// that is safe when the first caller may be the dynamic loader's very first
/// open in the process.
CensusState& state() noexcept {
  static CensusState singleton;
  return singleton;
}

thread_local int t_internal_depth = 0;

}  // namespace

const char* process_role_name(ProcessRole role) noexcept {
  switch (role) {
    case ProcessRole::UNSET:
      return "UNSET";
    case ProcessRole::FEATURE_BUILDER:
      return "FEATURE_BUILDER";
    case ProcessRole::TRAINER:
      return "TRAINER";
  }
  detail::fail_fast("qr::emit::process_role_name: role outside the three declared roles");
}

bool path_has_truth_component(std::string_view path) noexcept {
  std::size_t begin = 0;
  while (begin <= path.size()) {
    const std::size_t end = path.find('/', begin);
    const std::size_t stop = (end == std::string_view::npos) ? path.size() : end;
    if (stop - begin == 5 && path.compare(begin, 5, "truth") == 0) {
      return true;
    }
    if (end == std::string_view::npos) {
      break;
    }
    begin = end + 1;
  }
  return false;
}

std::string_view path_basename(std::string_view path) noexcept {
  const std::size_t slash = path.find_last_of('/');
  return slash == std::string_view::npos ? path : path.substr(slash + 1);
}

CensusInternalScope::CensusInternalScope() noexcept { ++t_internal_depth; }
CensusInternalScope::~CensusInternalScope() noexcept { --t_internal_depth; }

FdCensus& FdCensus::instance() noexcept {
  static FdCensus singleton;
  return singleton;
}

void FdCensus::begin(ProcessRole role) {
  // The reference that drags the interposing object out of the archive. A
  // census whose door is not linked in would record only this library's own
  // opens, which proves nothing about the process.
  if (!fd_census_interposition_installed()) {
    detail::fail_fast(
        "qr::emit::FdCensus::begin: the interposing object is not linked into this binary");
  }
  // Snapshot BEFORE the lock: the snapshot itself opens /proc/self/fd, which
  // goes through the door, which takes this same mutex.
  std::vector<std::pair<int, std::string>> preexisting = snapshot_open_fds();
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  if (census.recording && census.role != role) {
    detail::fail_fast(
        "qr::emit::FdCensus::begin: the process role was already declared; a process that "
        "re-tags itself mid-run can launder a truth open");
  }
  census.role = role;
  census.recording = true;
  census.preexisting = std::move(preexisting);
}

void FdCensus::set_truth_allowlist(std::vector<std::string> leaf_names) {
  std::sort(leaf_names.begin(), leaf_names.end());
  leaf_names.erase(std::unique(leaf_names.begin(), leaf_names.end()), leaf_names.end());
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  census.truth_allowlist = std::move(leaf_names);
}

bool FdCensus::recording() const noexcept {
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  return census.recording;
}

ProcessRole FdCensus::role() const noexcept {
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  return census.role;
}

std::vector<std::string> FdCensus::truth_allowlist() const {
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  return census.truth_allowlist;
}

bool FdCensus::admit(const char* path) noexcept {
  if (path == nullptr || t_internal_depth > 0) {
    return true;
  }
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  if (!census.recording) {
    return true;
  }
  census.opens_seen += 1;
  const std::string_view view(path);
  const bool truth = path_has_truth_component(view);
  bool refused = false;
  if (truth) {
    switch (census.role) {
      case ProcessRole::FEATURE_BUILDER:
        refused = true;
        break;
      case ProcessRole::TRAINER: {
        const std::string leaf(path_basename(view));
        refused = !std::binary_search(census.truth_allowlist.begin(),
                                      census.truth_allowlist.end(), leaf);
        break;
      }
      case ProcessRole::UNSET:
        refused = false;
        break;
    }
  }
  census.sequence += 1;
  if (truth || census.records.size() < kMaxNonTruthRecords) {
    OpenRecord record;
    record.sequence = census.sequence;
    record.path.assign(view);
    record.truth = truth;
    record.refused = refused;
    census.records.push_back(std::move(record));
  } else {
    census.non_truth_dropped += 1;
  }
  return !refused;
}

std::vector<OpenRecord> FdCensus::records() const {
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  return census.records;
}

std::vector<OpenRecord> FdCensus::truth_records() const {
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  std::vector<OpenRecord> out;
  for (const OpenRecord& record : census.records) {
    if (record.truth) {
      out.push_back(record);
    }
  }
  return out;
}

std::uint64_t FdCensus::opens_seen() const noexcept {
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  return census.opens_seen;
}

Status FdCensus::verify_no_truth_opened() const {
  const std::vector<OpenRecord> truth = truth_records();
  if (!truth.empty()) {
    return Status::refuse(Refusal(RefusalCode::SOURCE_AUTHENTICATION_FAILED,
                                  "qr_emit::FdCensus::verify_no_truth_opened",
                                  "this process touched a truth/ path",
                                  static_cast<std::int64_t>(truth.size())));
  }
  return ok_status();
}

Status FdCensus::verify_truth_allowlist_respected() const {
  const std::vector<std::string> allowed = truth_allowlist();
  for (const OpenRecord& record : truth_records()) {
    const std::string leaf(path_basename(record.path));
    if (!std::binary_search(allowed.begin(), allowed.end(), leaf)) {
      return Status::refuse(Refusal(RefusalCode::SOURCE_AUTHENTICATION_FAILED,
                                    "qr_emit::FdCensus::verify_truth_allowlist_respected",
                                    "a truth/ path outside the explicit allowlist was touched",
                                    static_cast<std::int64_t>(record.sequence)));
    }
  }
  return ok_status();
}

Status FdCensus::verify_open_fds_are_censused() const {
  const CensusInternalScope scope;

  // Every path the census saw, in both the form it was given and its canonical
  // form, because /proc always answers with the canonical one.
  std::vector<std::string> censused;
  for (const OpenRecord& record : records()) {
    censused.push_back(record.path);
    std::error_code code;
    const std::filesystem::path canonical =
        std::filesystem::weakly_canonical(std::filesystem::path(record.path), code);
    if (!code) {
      censused.push_back(canonical.string());
    }
  }
  std::sort(censused.begin(), censused.end());
  censused.erase(std::unique(censused.begin(), censused.end()), censused.end());

  std::vector<int> descriptors;
  std::error_code code;
  std::filesystem::directory_iterator entries("/proc/self/fd", code);
  if (code) {
    return Status::refuse(io_refusal("qr_emit::FdCensus::verify_open_fds_are_censused",
                                     "cannot read /proc/self/fd", code.value()));
  }
  for (const std::filesystem::directory_entry& entry : entries) {
    const std::string name = entry.path().filename().string();
    int value = 0;
    bool numeric = !name.empty();
    for (const char character : name) {
      if (character < '0' || character > '9') {
        numeric = false;
        break;
      }
      value = value * 10 + (character - '0');
    }
    if (numeric) {
      descriptors.push_back(value);
    }
  }
  std::sort(descriptors.begin(), descriptors.end());

  std::vector<std::pair<int, std::string>> preexisting;
  {
    CensusState& census = state();
    const std::lock_guard<std::mutex> lock(census.mutex);
    preexisting = census.preexisting;
  }
  const ProcessRole current_role = role();
  for (const int descriptor : descriptors) {
    struct stat status = {};
    if (::fstat(descriptor, &status) != 0) {
      continue;  // the directory_iterator's own descriptor, already gone
    }
    if (!S_ISREG(status.st_mode)) {
      continue;  // pipes, sockets, directories and anon inodes carry no path
    }
    const std::string link = "/proc/self/fd/" + decimal(descriptor);
    char target[4096];
    const ssize_t length = ::readlink(link.c_str(), target, sizeof(target) - 1);
    if (length <= 0) {
      continue;
    }
    target[length] = '\0';
    const std::string resolved(target, static_cast<std::size_t>(length));
    if (resolved.rfind("/proc/", 0) == 0) {
      continue;
    }
    if (std::binary_search(preexisting.begin(), preexisting.end(),
                           std::pair<int, std::string>(descriptor, resolved))) {
      continue;  // open before the census began, and unchanged since
    }
    if (path_has_truth_component(resolved) && current_role == ProcessRole::FEATURE_BUILDER) {
      return Status::refuse(Refusal(RefusalCode::SOURCE_AUTHENTICATION_FAILED,
                                    "qr_emit::FdCensus::verify_open_fds_are_censused",
                                    "a feature-builder process holds an open truth/ descriptor",
                                    descriptor));
    }
    if (!std::binary_search(censused.begin(), censused.end(), resolved)) {
      return Status::refuse(Refusal(RefusalCode::SOURCE_AUTHENTICATION_FAILED,
                                    "qr_emit::FdCensus::verify_open_fds_are_censused",
                                    "an open regular-file descriptor was never censused",
                                    descriptor));
    }
  }
  return ok_status();
}

Status FdCensus::write_census_tsv(const std::filesystem::path& path) const {
  std::vector<OpenRecord> all = records();
  const std::uint64_t seen = opens_seen();
  const CensusInternalScope scope;

  std::sort(all.begin(), all.end(), [](const OpenRecord& lhs, const OpenRecord& rhs) {
    return lhs.path != rhs.path ? lhs.path < rhs.path : lhs.sequence < rhs.sequence;
  });

  std::string out = "# qr_emit_fd_census_v1\trole\t";
  out += process_role_name(role());
  out += "\topens_seen\t";
  out += decimal(static_cast<std::int64_t>(seen));
  out += "\n";
  out += "path\tfirst_sequence\topen_count\ttruth\trefused_count\n";
  std::size_t index = 0;
  while (index < all.size()) {
    std::size_t end = index;
    std::int64_t refused = 0;
    while (end < all.size() && all[end].path == all[index].path) {
      refused += all[end].refused ? 1 : 0;
      ++end;
    }
    out += all[index].path;
    out += "\t";
    out += decimal(static_cast<std::int64_t>(all[index].sequence));
    out += "\t";
    out += decimal(static_cast<std::int64_t>(end - index));
    out += "\t";
    out += all[index].truth ? "1" : "0";
    out += "\t";
    out += decimal(refused);
    out += "\n";
    index = end;
  }
  return write_whole_file(path, out);
}

void FdCensus::reset_for_test() {
  CensusState& census = state();
  const std::lock_guard<std::mutex> lock(census.mutex);
  census.role = ProcessRole::UNSET;
  census.recording = false;
  census.sequence = 0;
  census.opens_seen = 0;
  census.non_truth_dropped = 0;
  census.records.clear();
  census.truth_allowlist.clear();
  census.preexisting.clear();
}

}  // namespace qr::emit
