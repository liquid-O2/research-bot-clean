// qr_emit/shard_writer.cpp — the DecisionTape container (see shard_writer.hpp
// for the APPENDIX C4 text and the publish discipline this implements).
#include "qr_emit/shard_writer.hpp"

#include <fcntl.h>
#include <openssl/evp.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <utility>

#include "io_util.hpp"

#ifndef RENAME_NOREPLACE
#define RENAME_NOREPLACE (1 << 0)
#endif

namespace qr::emit {
namespace {

/// APPENDIX C4 shard path: `<base>/s<four digits>/<L|S>`.
constexpr std::size_t kShardOrdinalDigits = 4;

using internal::config_refusal;
using internal::decimal;
using internal::fsync_directory;
using internal::io_refusal;
using internal::sha256_hex_bytes;
using internal::write_whole_file;

/// A manifest field may not carry a TSV separator or a line break: a manifest
/// whose columns can be forged by its own content is not a manifest.
bool field_is_clean(std::string_view field) noexcept {
  for (const char character : field) {
    if (character == '\t' || character == '\n' || character == '\r') {
      return false;
    }
  }
  return true;
}

/// Leaf names are plain path components: no separator, no leading dot, and only
/// characters that survive a TSV, a shell and a Python identifier-ish lookup.
bool leaf_name_is_clean(std::string_view name) noexcept {
  if (name.empty() || name.size() > 128 || name.front() == '.') {
    return false;
  }
  for (const char character : name) {
    const bool allowed = (character >= 'a' && character <= 'z') ||
                         (character >= 'A' && character <= 'Z') ||
                         (character >= '0' && character <= '9') || character == '_' ||
                         character == '-';
    if (!allowed) {
      return false;
    }
  }
  return true;
}

}  // namespace

const char* side_name(Side side) noexcept {
  switch (side) {
    case Side::LONG:
      return "LONG";
    case Side::SHORT:
      return "SHORT";
  }
  detail::fail_fast("qr::emit::side_name: side outside {LONG, SHORT}");
}

char side_letter(Side side) noexcept {
  switch (side) {
    case Side::LONG:
      return 'L';
    case Side::SHORT:
      return 'S';
  }
  detail::fail_fast("qr::emit::side_letter: side outside {LONG, SHORT}");
}

Expected<std::filesystem::path, Refusal> c4_shard_dir(const std::filesystem::path& base,
                                                      std::int64_t session_ordinal, Side side) {
  using Result = Expected<std::filesystem::path, Refusal>;
  if (session_ordinal < 0 || session_ordinal > 9999) {
    return Result::refuse(config_refusal("qr_emit::c4_shard_dir",
                                         "session ordinal does not fit the four-digit C4 field",
                                         session_ordinal));
  }
  std::string session = decimal(session_ordinal);
  session.insert(session.begin(), kShardOrdinalDigits - session.size(), '0');
  return base / ("s" + session) / std::string(1, side_letter(side));
}

Status validate_c4_shard_dir(const std::filesystem::path& dir, std::int64_t session_ordinal,
                             Side side) {
  // `<base>/s0125/L` — the last two components and nothing looser. A trailing
  // slash strips the filename, so "s0125/L/" refuses here rather than silently
  // publishing one level up.
  if (dir.empty() || !dir.has_filename()) {
    return Status::refuse(config_refusal("qr_emit::validate_c4_shard_dir",
                                         "shard directory has no <L|S> component"));
  }
  const std::string side_component = dir.filename().string();
  if (side_component.size() != 1 || side_component[0] != side_letter(side)) {
    return Status::refuse(config_refusal(
        "qr_emit::validate_c4_shard_dir",
        "the last component is not this shard's side letter (L or S)"));
  }
  const std::filesystem::path parent = dir.parent_path();
  if (parent.empty() || !parent.has_filename()) {
    return Status::refuse(config_refusal("qr_emit::validate_c4_shard_dir",
                                         "shard directory has no s<ordinal> component"));
  }
  const std::string session_component = parent.filename().string();
  if (session_component.size() != kShardOrdinalDigits + 1 || session_component.front() != 's') {
    return Status::refuse(config_refusal(
        "qr_emit::validate_c4_shard_dir",
        "the session component is not s followed by exactly four digits"));
  }
  std::int64_t parsed = 0;
  for (std::size_t index = 1; index < session_component.size(); ++index) {
    const char digit = session_component[index];
    if (digit < '0' || digit > '9') {
      return Status::refuse(config_refusal(
          "qr_emit::validate_c4_shard_dir",
          "the session component is not s followed by exactly four digits"));
    }
    parsed = parsed * 10 + (digit - '0');
  }
  if (parsed != session_ordinal) {
    return Status::refuse(config_refusal("qr_emit::validate_c4_shard_dir",
                                         "the directory names a different session than the shard",
                                         parsed));
  }
  return ok_status();
}

const char* section_dir(Section section) noexcept {
  switch (section) {
    case Section::FEATURES:
      return "features";
    case Section::TRUTH:
      return "truth";
  }
  detail::fail_fast("qr::emit::section_dir: section outside {FEATURES, TRUTH}");
}

ShardWriter::ShardWriter(ShardSpec spec, std::filesystem::path stage_dir)
    : spec_(std::move(spec)), stage_dir_(std::move(stage_dir)) {}

ShardWriter::~ShardWriter() = default;

std::int64_t ShardWriter::leaf_count() const noexcept {
  return static_cast<std::int64_t>(leaves_.size());
}

Expected<std::unique_ptr<ShardWriter>, Refusal> ShardWriter::begin(ShardSpec spec) {
  using Result = Expected<std::unique_ptr<ShardWriter>, Refusal>;

  // The naming wall, run FIRST so a malformed destination costs nothing: a
  // whole session of tensors written under the wrong name is a defect that
  // cannot be repaired by a rename.
  Status named = validate_c4_shard_dir(spec.publish_dir, spec.session_ordinal, spec.side);
  if (!named) {
    return Result::refuse(named.error());
  }
  if (!field_is_clean(spec.build_id) || spec.build_id.empty()) {
    return Result::refuse(
        config_refusal("qr_emit::ShardWriter::begin", "build_id is empty or carries a separator"));
  }
  for (const SourceRow& row : spec.sources) {
    if (row.id.empty() || !field_is_clean(row.id) || !field_is_clean(row.sha256) ||
        !field_is_clean(row.path)) {
      return Result::refuse(
          config_refusal("qr_emit::ShardWriter::begin", "source row carries a separator"));
    }
  }
  for (const CensusRow& row : spec.census) {
    if (row.id.empty() || !field_is_clean(row.id) || !field_is_clean(row.sha256) ||
        !field_is_clean(row.path)) {
      return Result::refuse(
          config_refusal("qr_emit::ShardWriter::begin", "census row carries a separator"));
    }
  }

  std::error_code code;
  if (std::filesystem::exists(spec.publish_dir, code)) {
    return Result::refuse(io_refusal("qr_emit::ShardWriter::begin",
                                     "publish_dir already exists; publication never replaces"));
  }
  const std::filesystem::path parent = spec.publish_dir.parent_path();
  if (!parent.empty()) {
    std::filesystem::create_directories(parent, code);
    if (code) {
      return Result::refuse(io_refusal("qr_emit::ShardWriter::begin",
                                       "cannot create the publish parent directory",
                                       code.value()));
    }
  }

  // Sibling stage directory, hidden and pid-tagged: two concurrent builders of
  // the same shard both stage, and exactly one wins the no-replace rename.
  const std::filesystem::path stage =
      parent / ("." + spec.publish_dir.filename().string() + ".stage-" + decimal(::getpid()));
  std::filesystem::remove_all(stage, code);
  if (!std::filesystem::create_directory(stage, code)) {
    return Result::refuse(
        io_refusal("qr_emit::ShardWriter::begin", "cannot create the stage directory",
                   code.value()));
  }
  // Section directories are created LAZILY, on the first leaf of that section:
  // a feature-builder process must be able to run a whole build without the
  // string "truth" ever reaching a filesystem call (APPENDIX C4 separation).
  return std::unique_ptr<ShardWriter>(new ShardWriter(std::move(spec), stage));
}

Expected<NpyWriter*, Refusal> ShardWriter::open_leaf(Section section, std::string_view name,
                                                     NpyDtype dtype,
                                                     std::span<const std::int64_t> shape) {
  using Result = Expected<NpyWriter*, Refusal>;
  if (published_) {
    return Result::refuse(
        config_refusal("qr_emit::ShardWriter::open_leaf", "the shard is already published"));
  }
  if (open_writer_) {
    return Result::refuse(config_refusal("qr_emit::ShardWriter::open_leaf",
                                         "another leaf is still open; finish it first"));
  }
  if (!leaf_name_is_clean(name)) {
    return Result::refuse(
        config_refusal("qr_emit::ShardWriter::open_leaf", "leaf name is not a plain component"));
  }

  std::string rel_path = std::string(section_dir(section)) + "/" + std::string(name) + ".npy";
  for (const NpyLeafReceipt& leaf : leaves_) {
    if (leaf.rel_path == rel_path) {
      return Result::refuse(
          config_refusal("qr_emit::ShardWriter::open_leaf", "duplicate leaf name in this shard"));
    }
  }

  const std::filesystem::path section_path = stage_dir_ / section_dir(section);
  std::error_code code;
  if (!std::filesystem::exists(section_path, code) &&
      !std::filesystem::create_directory(section_path, code)) {
    return Result::refuse(io_refusal("qr_emit::ShardWriter::open_leaf",
                                     "cannot create the section directory", code.value()));
  }

  Expected<NpyWriter, Refusal> writer = NpyWriter::create(
      section_path / (std::string(name) + ".npy"), rel_path, dtype, shape);
  if (!writer) {
    return Result::refuse(writer.error());
  }
  open_writer_ = std::make_unique<NpyWriter>(std::move(writer).value());
  return open_writer_.get();
}

Status ShardWriter::finish_leaf() {
  if (!open_writer_) {
    return Status::refuse(
        config_refusal("qr_emit::ShardWriter::finish_leaf", "no leaf is open"));
  }
  Expected<NpyLeafReceipt, Refusal> receipt = open_writer_->finish();
  open_writer_.reset();
  if (!receipt) {
    return Status::refuse(receipt.error());
  }
  leaves_.push_back(std::move(receipt).value());
  return ok_status();
}

Expected<std::string, Refusal> ShardWriter::manifest_bytes() const {
  using Result = Expected<std::string, Refusal>;

  // SORTED FILE ORDER (frozen ruling). Published bytes are a function of the
  // leaf SET, never of the order the caller emitted them.
  std::vector<NpyLeafReceipt> leaves = leaves_;
  std::sort(leaves.begin(), leaves.end(),
            [](const NpyLeafReceipt& lhs, const NpyLeafReceipt& rhs) {
              return lhs.rel_path < rhs.rel_path;
            });
  std::vector<SourceRow> sources = spec_.sources;
  std::sort(sources.begin(), sources.end(), [](const SourceRow& lhs, const SourceRow& rhs) {
    return lhs.id != rhs.id ? lhs.id < rhs.id : lhs.path < rhs.path;
  });
  std::vector<CensusRow> census = spec_.census;
  std::sort(census.begin(), census.end(), [](const CensusRow& lhs, const CensusRow& rhs) {
    return lhs.id != rhs.id ? lhs.id < rhs.id : lhs.path < rhs.path;
  });

  std::int64_t total_bytes = 0;
  for (const NpyLeafReceipt& leaf : leaves) {
    total_bytes += leaf.file_bytes;
  }

  std::string out;
  out += "# ";
  out += kManifestSchema;
  out +=
      "\tfields\tmeta=key,value\tsource=id,sha256,path\tcensus=id,sha256,path"
      "\tleaf=path,dtype,shape,rows,sha256\n";

  // meta section, fixed order.
  out += "meta\tmanifest_schema\t";
  out += kManifestSchema;
  out += "\nmeta\tbuild_id\t";
  out += spec_.build_id;
  out += "\nmeta\tsession_ordinal\t";
  out += decimal(spec_.session_ordinal);
  out += "\nmeta\tside\t";
  out += side_name(spec_.side);
  out += "\nmeta\tleaf_count\t";
  out += decimal(static_cast<std::int64_t>(leaves.size()));
  out += "\nmeta\ttotal_leaf_bytes\t";
  out += decimal(total_bytes);
  out += "\n";

  for (const SourceRow& row : sources) {
    out += "source\t";
    out += row.id;
    out += "\t";
    out += row.sha256;
    out += "\t";
    out += row.path;
    out += "\n";
  }
  for (const CensusRow& row : census) {
    out += "census\t";
    out += row.id;
    out += "\t";
    out += row.sha256;
    out += "\t";
    out += row.path;
    out += "\n";
  }
  for (const NpyLeafReceipt& leaf : leaves) {
    out += "leaf\t";
    out += leaf.rel_path;
    out += "\t";
    out += npy_dtype_descr(leaf.dtype);
    out += "\t";
    for (std::size_t index = 0; index < leaf.shape.size(); ++index) {
      if (index > 0) {
        out += ",";
      }
      out += decimal(leaf.shape[index]);
    }
    out += "\t";
    out += decimal(leaf.rows);
    out += "\t";
    out += leaf.sha256;
    out += "\n";
  }
  return Result(std::move(out));
}

namespace {

/// True when the leaf's `rel_path` lives directly under `section`'s directory.
[[nodiscard]] bool leaf_is_in_section(const NpyLeafReceipt& leaf, Section section) noexcept {
  const std::string prefix = std::string(section_dir(section)) + "/";
  return leaf.rel_path.size() > prefix.size() &&
         leaf.rel_path.compare(0, prefix.size(), prefix) == 0;
}

/// The leaf name inside its section: `features/keys.npy` -> `keys.npy`.
[[nodiscard]] std::string_view leaf_name_of(const NpyLeafReceipt& leaf) noexcept {
  const std::size_t slash = leaf.rel_path.find_last_of('/');
  return slash == std::string::npos ? std::string_view(leaf.rel_path)
                                    : std::string_view(leaf.rel_path).substr(slash + 1);
}

}  // namespace

Expected<ShardReceipt, Refusal> ShardWriter::publish() {
  using Result = Expected<ShardReceipt, Refusal>;
  if (published_) {
    return Result::refuse(
        config_refusal("qr_emit::ShardWriter::publish", "the shard is already published"));
  }
  if (open_writer_) {
    return Result::refuse(config_refusal("qr_emit::ShardWriter::publish",
                                         "a leaf is still open; the shard is incomplete"));
  }
  if (leaves_.empty()) {
    return Result::refuse(
        config_refusal("qr_emit::ShardWriter::publish", "a shard with no leaves is not a tape"));
  }

  // THE FEATURE/TRUTH DIGEST-COLLISION REFUSAL (card section 7(p), verbatim:
  // "feature/truth digest-collision refusal — publishing refuses when any
  // features/ leaf sha256 equals any truth/ leaf sha256").
  //
  // This is the leg the fd census cannot supply. The census tests PATHS, and a
  // hard link, a symlink or an inherited descriptor gives a truth inode a second
  // name with no `truth` component in it (see fd_census.hpp, "WHAT IT DOES NOT
  // CATCH"). What cannot be laundered is the BYTES: a truth tensor republished
  // under a feature name has the same sha256, and the shard does not publish.
  //
  // Leaf counts are ~20 per shard, so the quadratic scan is a few hundred string
  // compares once per publish; there is no index to keep consistent and no
  // hidden cost to measure.
  for (const NpyLeafReceipt& feature : leaves_) {
    if (!leaf_is_in_section(feature, Section::FEATURES)) {
      continue;
    }
    for (const NpyLeafReceipt& truth : leaves_) {
      if (!leaf_is_in_section(truth, Section::TRUTH)) {
        continue;
      }
      if (feature.sha256 != truth.sha256) {
        continue;
      }
      // THE ONE DECLARED EXCEPTION, and it is C4's own. APPENDIX C4 lists
      // `keys` in BOTH sections — "`features/`: ... keys [N,4] i8 ...
      // `truth/`: ... label_state [N] u1; keys." — because it IS the join
      // between the two halves and is the same array on both sides by
      // construction. A rule that refused it would refuse every lawful shard.
      // The exception is by NAME and it is exactly one name: a truth tensor
      // republished under ANY other feature name, including the same name for
      // any other leaf, still refuses.
      if (leaf_name_of(feature) == leaf_name_of(truth) &&
          is_c4_shared_leaf(leaf_name_of(feature))) {
        continue;
      }
      {
        return Result::refuse(Refusal(
            RefusalCode::SOURCE_AUTHENTICATION_FAILED, "qr_emit::ShardWriter::publish",
            "a features/ leaf has the same sha256 as a truth/ leaf; a truth tensor cannot be "
            "published under a feature name",
            static_cast<std::int64_t>(feature.rows)));
      }
    }
  }

  Expected<std::string, Refusal> manifest = manifest_bytes();
  if (!manifest) {
    return Result::refuse(manifest.error());
  }
  Status written = write_whole_file(stage_dir_ / kManifestName, manifest.value());
  if (!written) {
    return Result::refuse(written.error());
  }

  // Durability order: leaves are fsynced as they finish, then the manifest,
  // then the directories that name them, and only then the rename.
  std::error_code code;
  for (const Section section : {Section::FEATURES, Section::TRUTH}) {
    const std::filesystem::path section_path = stage_dir_ / section_dir(section);
    if (std::filesystem::exists(section_path, code)) {
      Status synced = fsync_directory(section_path);
      if (!synced) {
        return Result::refuse(synced.error());
      }
    }
  }
  Status staged = fsync_directory(stage_dir_);
  if (!staged) {
    return Result::refuse(staged.error());
  }

  // The naming wall again, immediately before the rename: the publish itself is
  // gated, not merely the setup that led to it.
  Status named = validate_c4_shard_dir(spec_.publish_dir, spec_.session_ordinal, spec_.side);
  if (!named) {
    return Result::refuse(named.error());
  }

  // THE PUBLISH. RENAME_NOREPLACE is required, not attempted: a plain rename(2)
  // succeeds onto an existing empty directory, which is exactly the silent
  // replacement this discipline exists to prevent. Verified supported on the
  // MooseFS mount that holds /workspace (EEXIST when taken, 0 when free).
  const long moved = ::syscall(SYS_renameat2, AT_FDCWD, stage_dir_.c_str(), AT_FDCWD,
                               spec_.publish_dir.c_str(), RENAME_NOREPLACE);
  if (moved != 0) {
    return Result::refuse(io_refusal("qr_emit::ShardWriter::publish",
                                     "renameat2(RENAME_NOREPLACE) refused the publish", errno));
  }
  const std::filesystem::path parent = spec_.publish_dir.parent_path();
  if (!parent.empty()) {
    Status parent_synced = fsync_directory(parent);
    if (!parent_synced) {
      return Result::refuse(parent_synced.error());
    }
  }
  published_ = true;

  ShardReceipt receipt;
  receipt.publish_dir = spec_.publish_dir;
  receipt.manifest_sha256 = sha256_hex_bytes(manifest.value());
  receipt.leaves = leaves_;
  std::sort(receipt.leaves.begin(), receipt.leaves.end(),
            [](const NpyLeafReceipt& lhs, const NpyLeafReceipt& rhs) {
              return lhs.rel_path < rhs.rel_path;
            });
  receipt.leaf_count = static_cast<std::int64_t>(receipt.leaves.size());
  for (const NpyLeafReceipt& leaf : receipt.leaves) {
    receipt.total_leaf_bytes += leaf.file_bytes;
  }
  return receipt;
}

}  // namespace qr::emit
