// qr_emit/fd_census.hpp — the process-level file-descriptor census.
//
// SPEC: FINAL_PLAN.md APPENDIX C4, "Separation BY PROCESS (review F4)":
//   "the feature BUILDER's fd census proves it never opens truth/; the TRAINER
//    opens an explicit truth allowlist for loss computation only + static check
//    no truth array is concatenated into any feature tensor."
//
// WHAT A CENSUS HAS TO BE TO BE A PROOF. A census that only sees the opens made
// through this library's own API proves nothing about a builder that uses
// std::ifstream, fopen, or a bare ::open. So the census has three legs, and the
// first one is a real interposition, not a convention:
//
//   1. INTERPOSITION (src/fd_census_interpose.cpp). The census object file
//      defines open/open64/openat/openat64/creat/creat64/fopen/fopen64/freopen
//      in the executable image itself. Every call from our code, from
//      libstdc++'s filebuf, and from any shared library that resolves these
//      names through the global scope lands in the census first and reaches the
//      kernel second (via syscall(SYS_openat), so nothing depends on dlsym and
//      nothing can recurse into the loader). Measured to fire for std::ofstream,
//      std::ifstream and fopen under both the dev and the asan presets.
//   2. ENFORCEMENT. With ProcessRole::FEATURE_BUILDER set, a path with a
//      `truth` component is refused at the door with EACCES *and* recorded as a
//      violation; with ProcessRole::TRAINER it is refused unless the leaf is on
//      the explicit allowlist. Recording without refusing would let a defect
//      finish its run and be discovered later; the census refuses first.
//   3. /proc/self/fd SWEEP. verify_open_fds_are_censused() resolves every
//      descriptor the process currently holds and refuses on any regular-file
//      descriptor that the census never saw — the leg that catches an open made
//      by a path that never passed the door at all (a raw syscall).
//
// WHAT IT DOES NOT CATCH, stated plainly rather than implied away: a raw
// syscall(SYS_openat, ...) whose descriptor is closed again before the sweep
// runs. Nothing short of ptrace/seccomp closes that hole from inside the
// process, and the enforcement leg makes it a deliberate act rather than an
// accident.
//
// ROLES. The spec names exactly two constrained roles (feature builder,
// trainer). UNSET is the third state and constrains nothing: it is what a
// process that legitimately owns both halves of a tape (the emit job that
// writes features/ and truth/ in one pass) runs as. Adding a role is an
// orchestrator decision, not an implementation one.
#ifndef QR_EMIT_FD_CENSUS_HPP
#define QR_EMIT_FD_CENSUS_HPP

#include <cstdint>
#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

#include "qr_emit/npy_writer.hpp"

namespace qr::emit {

enum class ProcessRole : std::uint8_t {
  UNSET,           ///< no restriction; the census still records.
  FEATURE_BUILDER, ///< may not open any path with a `truth` component, at all.
  TRAINER,         ///< may open truth/ leaves on its explicit allowlist only.
};

[[nodiscard]] const char* process_role_name(ProcessRole role) noexcept;

/// True when the interposing translation unit is part of this binary. It is a
/// LINK-TIME fact: referencing this symbol is what drags the object that
/// defines open/openat/fopen out of the static archive and into the executable
/// image, so a census that reports `false` is a build defect, not a runtime
/// condition.
[[nodiscard]] bool fd_census_interposition_installed() noexcept;

/// True when any '/'-separated component of `path` is exactly "truth". Catches
/// "truth/x.npy", "/a/truth/x.npy", "a/../truth/x.npy" and the directory itself.
[[nodiscard]] bool path_has_truth_component(std::string_view path) noexcept;

/// The basename of a path, i.e. everything after the last '/'.
[[nodiscard]] std::string_view path_basename(std::string_view path) noexcept;

struct OpenRecord {
  std::uint64_t sequence = 0;  ///< strictly increasing, process-wide
  std::string path;            ///< exactly the path the caller passed
  bool truth = false;          ///< path_has_truth_component(path)
  bool refused = false;        ///< the census returned EACCES instead of an fd
};

/// Process-wide singleton. Thread-safe; the recorded order is the real call
/// order, so a single-threaded builder's census is deterministic.
class FdCensus {
 public:
  [[nodiscard]] static FdCensus& instance() noexcept;

  /// Starts recording and enforcing under `role`. Idempotent for the same role;
  /// changing an already-declared role is a fail-fast programmer error, because
  /// a process that re-tags itself mid-run can launder a truth open.
  void begin(ProcessRole role);

  /// TRAINER only: the explicit truth allowlist, by leaf basename (e.g.
  /// "menu_net_cent.npy"). Anything not listed stays refused.
  void set_truth_allowlist(std::vector<std::string> leaf_names);

  [[nodiscard]] bool recording() const noexcept;
  [[nodiscard]] ProcessRole role() const noexcept;
  [[nodiscard]] std::vector<std::string> truth_allowlist() const;

  /// The door. Returns true when the open may proceed. Called by the
  /// interposer for every open in the process; safe to call before begin().
  [[nodiscard]] bool admit(const char* path) noexcept;

  [[nodiscard]] std::vector<OpenRecord> records() const;
  [[nodiscard]] std::vector<OpenRecord> truth_records() const;
  [[nodiscard]] std::uint64_t opens_seen() const noexcept;

  /// Census leg: refuses when this process ever *touched* a truth path (any
  /// role), naming the first one. This is the assertion a feature-builder run
  /// publishes as its receipt.
  [[nodiscard]] Status verify_no_truth_opened() const;

  /// Census leg: refuses when a truth path outside the allowlist was touched.
  [[nodiscard]] Status verify_truth_allowlist_respected() const;

  /// /proc/self/fd leg: refuses on a currently-open regular-file descriptor
  /// whose path the census never saw, and on any open truth descriptor when the
  /// role forbids it. Directory, pipe, socket and anonymous descriptors are
  /// reported in the count and never refused — they carry no path.
  [[nodiscard]] Status verify_open_fds_are_censused() const;

  /// Deterministic census receipt: a sorted TSV of every recorded path with its
  /// first sequence number, open count, truth flag and refusal count. Written
  /// through the same no-replace discipline as a shard (O_CREAT|O_EXCL).
  [[nodiscard]] Status write_census_tsv(const std::filesystem::path& path) const;

  /// Test-only: drops all state. Never called by production code.
  void reset_for_test();

 private:
  FdCensus() = default;
};

/// RAII marker that suppresses recording for the census's own file access, so
/// reading /proc/self/fd or writing the census receipt does not census itself.
class CensusInternalScope {
 public:
  CensusInternalScope() noexcept;
  ~CensusInternalScope() noexcept;
  CensusInternalScope(const CensusInternalScope&) = delete;
  CensusInternalScope& operator=(const CensusInternalScope&) = delete;
};

}  // namespace qr::emit

#endif  // QR_EMIT_FD_CENSUS_HPP
