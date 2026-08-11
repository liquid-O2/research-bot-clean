// qr_campaign/session_build.hpp — the payload-touching half of the driver: the
// roster stage and the per-session worker.
//
// NO SCIENCE LIVES HERE. Every number this file publishes is produced by a
// constructor that was specified, fixtured and reviewed in its own work
// package: qr_candidates builds the roster, qr_labels builds the watches and the
// label kernel, qr_carriers builds every feature value, qr_emit writes every
// byte. What this file owns is the ORDER those calls happen in, the process
// topology APPENDIX C4 requires, and the receipts.
//
// THE TWO STAGES, AND WHY THE FIRST ONE IS NOT PER-SESSION.
//
//   STAGE 1 — ROSTERS. `qr_candidates`'s prefix reader is a BOUNDED SEQUENTIAL
//   pass over one 14GB sealed publication: it walks ordinals 0..stop once and
//   hands each retained session to a sink. Running it once per session would
//   re-walk that prefix 625 times (measured 16.7s per full 0..749 pass — nearly
//   three hours of pure re-reading) for an answer the single pass already has.
//   So the roster stage is ONE pass that publishes one roster per requested
//   session, in ordinal order, and the per-session workers READ those rosters.
//   The two publication parquets are opened once each and their row groups are
//   addressed per session, exactly as `qr_candidates_seal` does for one.
//
//   STAGE 2 — SESSIONS. One worker per session; each worker publishes BOTH
//   shards of that session, because the two sides share one decode of the three
//   modality streams and one label pass. Inside a worker the APPENDIX C4
//   process separation is the WP10 topology, verbatim: a FEATURE_BUILDER-tagged
//   CHILD constructs every feature array and proves by its own fd census that it
//   never opened a truth path; the UNTAGGED parent runs the label kernel
//   MEANWHILE (the two phases overlap, which is why the label decode is free),
//   then writes features/ and truth/ into one staged shard per side and
//   publishes each with one no-replace rename.
#ifndef QR_CAMPAIGN_SESSION_BUILD_HPP
#define QR_CAMPAIGN_SESSION_BUILD_HPP

#include <cstdint>
#include <span>
#include <string>

#include "qr_campaign/driver.hpp"

namespace qr::campaign {

struct BuildOptions {
  /// Lands in every manifest. It carries NO run index and NO timestamp: two
  /// runs of the same campaign must be byte-identical, and a build id that
  /// moved with the run would make the identity test vacuous.
  std::string build_id = "qr_campaign_v1";
  /// Re-hash the two 3GB publication parquets in the roster stage. Production
  /// leaves this on; the probe gate turns it off only when it has already
  /// verified them in the same invocation.
  bool verify_publication_digests = true;
};

/// STAGE 1. Publishes `<run>/rosters/s<NNNN>/{roster.tsv,census.tsv}` for every
/// requested ordinal in one bounded prefix pass, plus
/// `<run>/receipts/roster_stage.tsv`. A roster that is already published is
/// BYTE-COMPARED against the one just built and any difference refuses — a
/// resumed run may not quietly stand on different bytes than the run it
/// resumes.
[[nodiscard]] Status build_rosters(const RunLayout& layout,
                                   std::span<const std::int64_t> ordinals,
                                   const BuildOptions& options);

/// STAGE 2. One session: rosters → watches → (tagged features ‖ labels) →
/// per-side publish → session receipt. Refuses on the first contradiction; a
/// refused session publishes nothing.
[[nodiscard]] Status build_session(const RunLayout& layout, const SessionTask& task,
                                   const BuildOptions& options);

}  // namespace qr::campaign

#endif  // QR_CAMPAIGN_SESSION_BUILD_HPP
